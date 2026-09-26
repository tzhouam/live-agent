"""Live-agent server: FastAPI + WebSocket, one session per connection.

Wire protocol (WS /ws), JSON text frames unless noted:
  client -> server
    {"type":"hello","mode":"private"|"public","user_id":"u1"}
    {"type":"speech_start"}                        barge-in (push-to-talk pressed)
    binary frame                                   recorded speech (webm/opus or wav) -> ASR
    {"type":"text","text":"..."}                   typed utterance (fallback / tests)
    {"type":"chunk_start","request":k,"chunk":c}   presentation start (server stamps arrival)
    {"type":"chunk_end","request":k,"chunk":c}     presentation end
    {"type":"ping","t":...}
  server -> client
    {"type":"chunk","request":k,"chunk":c,"n_frames":n,"fps":24,"sample_rate":sr,
     "width":w,"height":h,"transcript":"..."}      followed by n binary JPEG frames and one binary PCM16 frame
    {"type":"stop"}                                 drop everything queued (barge-in)
    {"type":"transcript","text":"..."}             ASR result of the user's speech
    {"type":"status", ...}

Presentation times are stamped with the *server* monotonic clock on arrival of the
client's chunk_start / chunk_end messages (network delay is logged via ping RTT).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import SessionView
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import BlockScript, Chunk, Utterance, new_id, now

log = logging.getLogger("live_agent.server")
STATIC = Path(__file__).parent / "static"


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def to_pcm16(audio: np.ndarray | None, n_samples: int) -> bytes:
    if audio is None or len(audio) == 0:
        return np.zeros(n_samples, dtype=np.int16).tobytes()
    a = audio.mean(axis=1) if audio.ndim == 2 else audio
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


PANEL_EVENTS = {"lock", "verdict", "repair", "completion_claim", "refusal", "capacity_skip", "narration_guard",
                "playback_stop", "speech_onset", "utterance_end", "audit", "error", "request_done"}
PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
                "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
                "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
                "decision", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
                "audibility", "revision", "speaker", "uid")


def panel_event(ev, t0: float) -> dict | None:
    """Compact, display-only form of a timeline event (the full log stays on disk)."""
    if ev.type.value not in PANEL_EVENTS:
        return None
    if ev.type.value == "error" and ev.data.get("where") in ("event_loop_stack",):
        return None
    data = {k: ev.data[k] for k in PANEL_FIELDS if k in ev.data}
    if isinstance(data.get("rationale"), str):
        data["rationale"] = data["rationale"][:160]
    return {"type": "event", "event": ev.type.value, "t": round(ev.t - t0, 2), "request": ev.request_index,
            "data": data}


class WSTransport:
    """Orchestrator transport over one WebSocket connection.

    Presentation times: the client reports, for each chunk, when its audio starts / ends at the
    audio *output* (AudioContext.getOutputTimestamp -> performance clock, ``tp`` in ms). The
    server maps that clock to its own with the lowest-RTT ping sample (NTP-style,
    offset = t_server - (t_client_send + rtt/2)). Until a mapping exists, arrival time is used
    (and the event says so)."""

    def __init__(self, ws: WebSocket, record_path: Path | None = None):
        self.ws = ws
        self.orchestrator: Orchestrator | None = None
        # trace recording: exactly the chunks the client reports as played (chunk_end acks), in order
        self.record_path = record_path
        self.recorder = None
        self._part = 1
        self._sent: dict[tuple[int, int], Chunk] = {}
        if record_path is not None:
            self._new_recorder()
        self._send_lock = asyncio.Lock()
        self._starts: dict[tuple[int, int], float] = {}
        self._epoch = 0  # incremented on stop; stale sends are skipped
        self.clock_offset_s: float | None = None
        self.clock_rtt_s: float | None = None

    def _new_recorder(self) -> None:
        from live_agent.sim import Recorder

        path = self.record_path if self._part == 1 else self.record_path.with_name(
            f"{self.record_path.stem}-part{self._part}{self.record_path.suffix}")
        self.recorder = Recorder(path)

    def restart_recording(self) -> None:
        """After an erasure deleted the recording, continue in a new part file."""
        if self.record_path is not None:
            self._part += 1
            self._new_recorder()

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        if self.recorder is not None:
            self._sent[(chunk.request_index, chunk.chunk_index)] = chunk
        epoch = self._epoch
        frames = chunk.video if chunk.video is not None else np.zeros((chunk.n_frames, 8, 8, 3), np.uint8)
        # Encode off the event loop.
        loop = asyncio.get_running_loop()
        jpegs = await loop.run_in_executor(None, lambda: [encode_jpeg(f) for f in frames])
        pcm = to_pcm16(chunk.audio, int(chunk.duration_s * chunk.sample_rate))
        async with self._send_lock:
            if epoch != self._epoch:
                return
            h, w = frames.shape[1:3]
            await self.ws.send_text(json.dumps({
                "type": "chunk", "request": chunk.request_index, "chunk": chunk.chunk_index,
                "n_frames": len(jpegs), "fps": chunk.fps, "sample_rate": chunk.sample_rate,
                "duration": chunk.duration_s,  # media duration (may differ from len(jpegs) / fps)
                "width": int(w), "height": int(h), "transcript": script.transcript}))
            for j in jpegs:
                if epoch != self._epoch:
                    return  # interrupted mid-chunk: the client discards the partial chunk
                await self.ws.send_bytes(j)
            if epoch == self._epoch:
                await self.ws.send_bytes(pcm)

    async def send_json(self, obj: dict) -> None:
        """Small control/panel messages, sent between (never inside) a chunk's binary frames."""
        async with self._send_lock:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))

    async def stop_playback(self) -> None:
        """Immediate: does not wait for an in-flight chunk send (which aborts at its next frame)."""
        self._epoch += 1
        self._sent.clear()  # interrupted chunks were never (fully) shown: not recorded
        await self.ws.send_text(json.dumps({"type": "stop"}))

    def in_flight(self):
        """(request, chunk, start time) of a chunk that started playing but has not ended."""
        if not self._starts:
            return None
        (k, ci), t = max(self._starts.items(), key=lambda kv: kv[1])
        return (k, ci, t)

    def on_clock(self, msg: dict) -> None:
        rtt = float(msg["rtt"]) / 1000.0
        if self.clock_rtt_s is None or rtt <= self.clock_rtt_s:
            self.clock_rtt_s = rtt
            self.clock_offset_s = float(msg["t_server"]) - (float(msg["t_client"]) / 1000.0 + rtt / 2)

    def _to_server(self, msg: dict) -> float:
        if msg.get("tp") is not None and self.clock_offset_s is not None:
            return float(msg["tp"]) / 1000.0 + self.clock_offset_s
        return now()

    def on_client_message(self, msg: dict) -> None:
        t = self._to_server(msg)
        key = (int(msg.get("request", -1)), int(msg.get("chunk", -1)))
        if msg["type"] == "chunk_start":
            self._starts[key] = t
        elif msg["type"] == "chunk_end" and self.orchestrator is not None:
            ch = self._sent.pop(key, None)
            if ch is not None and self.recorder is not None:
                self.recorder.write(ch)  # background-thread encoding
            painted = msg.get("painted")
            t_paint = (self._to_server({"tp": msg["tp_last_paint"]}) if msg.get("tp_last_paint") is not None
                       and self.clock_offset_s is not None else None)
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t,
                                           painted=[int(i) for i in painted] if painted is not None else None,
                                           t_last_paint=t_paint)


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI()
    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()

    @app.on_event("startup")
    async def _startup() -> None:
        if args.record:  # recordings left unfinished by a killed session
            from live_agent.sim import salvage_recordings

            fixed = await asyncio.to_thread(salvage_recordings, args.log_dir)
            if fixed:
                log.info("finalised %d interrupted recording(s): %s", len(fixed), ", ".join(fixed))
        from live_agent.llm import OpenAICompatLLM

        if args.llm_url != "scripted":
            await OpenAICompatLLM(args.llm_url, args.llm_model).warmup()  # SDK lazy imports, off the session path
        # Heavy generators are started once and shared (reset per session); the mock is per session.
        if args.generator != "mock":
            gen = make_generator(args)
            try:
                await gen.start()
            except BaseException:
                await gen.close()  # workers / listener of a partial start must not linger
                raise
            app.state.shared_gen = gen

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.shared_gen is not None:
            await app.state.shared_gen.close()

    import re as _re

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    trace_name = _re.compile(r"^sess-[A-Za-z0-9_-]+(\.generated(-part\d+)?)?\.(jsonl|mp4)$")

    @app.get("/traces")
    async def traces() -> HTMLResponse:
        """Recorded sessions: event trace (JSONL) and the presented audio/video (MP4)."""
        d = Path(args.log_dir)
        rows = []
        for f in sorted(d.glob("sess-*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)[:200]:
            vids = sorted(d.glob(f"{f.stem}*.mp4"))  # presented (+ parts) and generated (+ parts)
            when = __import__("time").strftime("%m-%d %H:%M:%S", __import__("time").localtime(f.stat().st_mtime))
            def label(v):
                rest = v.name[len(f.stem):-4].lstrip(".-")
                return ("generated" + rest[len("generated"):]) if rest.startswith("generated") else ("presented" + (" " + rest if rest else ""))
            links = " · ".join(f'<a href="/traces/file/{v.name}">{label(v)}</a>' for v in vids) \
                or "<span style='color:#888'>no video</span>"
            rows.append(f"<tr><td>{when}</td><td>{f.stem}</td><td><a href='/traces/file/{f.name}'>trace.jsonl</a> "
                        f"({f.stat().st_size // 1024} KB)</td><td>{links}</td></tr>")
        html = ("<!doctype html><meta charset='utf-8'><title>Live Agent traces</title>"
                "<style>body{font:14px system-ui;margin:24px}td,th{padding:4px 10px;border-bottom:1px solid #ddd}</style>"
                "<h2>Recorded sessions</h2><p><a href='/'>← demo</a></p><table><tr><th>last update</th><th>session</th>"
                "<th>event trace</th><th>video (presented = what the viewer saw; generated = everything produced)</th></tr>" + "".join(rows) + "</table>")
        return HTMLResponse(html)

    @app.get("/traces/file/{name}")
    async def trace_file(name: str):
        if not trace_name.match(name):
            raise HTTPException(404)
        f = Path(args.log_dir) / name
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, media_type="video/mp4" if name.endswith(".mp4") else "application/x-ndjson",
                            filename=name)

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = "public" if hello.get("mode") == "public" else "private"
        session_id = new_id("sess")
        record_path = Path(args.log_dir) / f"{session_id}.mp4" if args.record else None
        if record_path is not None:
            record_path.parent.mkdir(parents=True, exist_ok=True)
        transport = WSTransport(ws, record_path)
        shared = app.state.shared_gen is not None
        if shared:
            if app.state.session_lock.locked():
                await ws.send_text(json.dumps({"type": "error", "error": "generator busy (one live session at a time)"}))
                await ws.close()
                return
            await app.state.session_lock.acquire()
        orch = None
        inputs: asyncio.Queue = asyncio.Queue()
        worker = None
        try:
            from live_agent.llm import OpenAICompatLLM

            manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
            if args.llm_url == "scripted":  # CPU-only demo: rule-based responder, no model server
                from live_agent.llm import RuleResponder

                llm = RuleResponder(manifest)
            else:
                llm = OpenAICompatLLM(args.llm_url, args.llm_model)
            if args.dev_allow_uncalibrated:
                manifest.min_status = Status.DOCUMENTED
            ledger = StateLedger.from_config(cfg_dir / "canon.json")
            director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                                persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode))
            generator = SessionView(app.state.shared_gen) if shared else make_generator(args)
            sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
                                                  lambda_prior_s=args.lambda_prior))
            judge = speech = None
            if args.vlm_url == "mock":  # demo only: simulated verdicts (p=0.8), never a measurement
                from live_agent.qc.judge import MockJudge

                # the placeholder video always "performs" the locked action, so by default the simulated
                # judge agrees (p=1); a lower --mock-judge-p demonstrates the repair loop
                judge = MockJudge(p_default=args.mock_judge_p)
            elif args.vlm_url:
                from live_agent.qc.judge import VLMJudge

                judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model), k=8, contrast=True)
            asr = None
            if args.asr_url:
                from live_agent.asr import OpenAIASR
                from live_agent.qc.judge import SpeechCheck

                asr = OpenAIASR(args.asr_url, args.asr_model)
                speech = SpeechCheck(asr.transcribe_sync)
            from live_agent.qc.judge import ForwardCorrector

            log_dir = Path(args.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=ForwardCorrector(None if args.llm_url == "scripted" else llm),
                                speech_check=speech, memory=make_memory(args, hello, session_id, mode),
                                log=EventLog(log_dir / f"{session_id}.jsonl"),
                                cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                       correction_mode=CorrectionMode(args.correction_mode)))
            transport.orchestrator = orch
            if args.record:  # everything the generator produced, incl. chunks dropped by barge-ins
                from live_agent.sim import Recorder

                parts = iter(range(1, 10**6))

                def gen_rec():
                    n = next(parts)
                    return Recorder(Path(args.log_dir) / (f"{session_id}.generated.mp4" if n == 1
                                                          else f"{session_id}.generated-part{n}.mp4"))

                orch.gen_recorder, orch.gen_recorder_factory = gen_rec(), gen_rec
            # live panel: timeline events + a 2 Hz state snapshot to the page (display only)
            panel_q: asyncio.Queue = asyncio.Queue(maxsize=500)
            t_session = now()

            def on_event(ev) -> None:
                msg = panel_event(ev, t_session)
                if msg is not None and not panel_q.full():
                    panel_q.put_nowait(msg)

            orch.log.listeners.append(on_event)

            async def panel_sender() -> None:
                while True:
                    try:
                        msg = await asyncio.wait_for(panel_q.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        msg = {"type": "state", **orch.snapshot()}
                    await transport.send_json(msg)

            panel_task = asyncio.create_task(panel_sender())
            await orch.start()
            await ws.send_text(json.dumps({"type": "status", "session": session_id, "mode": mode,
                                           "generator": generator.info.name, "director": args.director_mode,
                                           "judge": "mock" if args.vlm_url == "mock" else ("vlm" if args.vlm_url else "none"),
                                           "responder": "rules" if args.llm_url == "scripted" else args.llm_model,
                                           "asr": bool(args.asr_url), "persona": canon.get("display_name", "")},
                                          ensure_ascii=False))

            async def handle_inputs() -> None:
                """Utterances are processed in order, off the receive loop, so presentation acks
                and barge-in keep being read (and timestamped) while ASR / the LLM run."""
                while True:
                    kind, payload, t_end, epoch = await inputs.get()  # epoch stamped at receipt
                    try:
                        if kind == "audio":
                            from live_agent.asr import decode_audio_bytes

                            audio = decode_audio_bytes(payload, 16000)
                            text = await asr.transcribe(audio, 16000)
                            await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                        else:
                            text = payload
                        if text:
                            # t_end = when the user stopped speaking / sent (client clock, mapped), so
                            # ASR and queueing delay count toward the deadlines (proposal §7)
                            await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, t_end,
                                                                   session_id=session_id, scope=mode),
                                                         epoch=epoch)
                    except Exception:  # noqa: BLE001
                        log.exception("input handling failed")

            worker = asyncio.create_task(handle_inputs())
            audio_end = now()
            done = asyncio.create_task(orch.wait_done())
            while True:
                recv = asyncio.create_task(ws.receive())
                await asyncio.wait({recv, done}, return_when=asyncio.FIRST_COMPLETED)
                if not recv.done():  # the orchestrator stopped (fatal error or bounded run)
                    recv.cancel()
                    err = f"{type(orch.error).__name__}: {orch.error}" if orch.error else "session ended"
                    try:
                        await ws.send_text(json.dumps({"type": "error", "error": err}))
                        await ws.close()
                    except Exception:  # noqa: BLE001
                        pass
                    break
                msg = recv.result()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    if asr is not None:
                        inputs.put_nowait(("audio", msg["bytes"], audio_end, orch.input_epoch))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    await orch.on_speech_start()
                elif t == "text" and data.get("text", "").strip():
                    # a typed instruction interrupts like speech does (before its LLM work is queued)
                    await orch.on_speech_start()
                    inputs.put_nowait(("text", data["text"].strip(), transport._to_server(data), orch.input_epoch))
                elif t == "audio_end":  # precedes the recorded audio bytes
                    audio_end = transport._to_server(data)
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
                elif t == "clock":
                    transport.on_clock(data)
        except WebSocketDisconnect:
            pass
        finally:
            try:
                if "panel_task" in locals():
                    panel_task.cancel()
                if worker is not None:
                    worker.cancel()
                if orch is not None:
                    await orch.stop()
                if transport.recorder is not None:
                    await asyncio.to_thread(transport.recorder.close)  # mux video + audio
            except Exception:  # noqa: BLE001
                log.exception("session cleanup failed")
            finally:
                if shared:
                    app.state.session_lock.release()

    return app


def make_generator(args: argparse.Namespace):
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator

        return MockGenerator(size=(864, 480), render_text=True)  # portrait, like TaoMate-H3 480x864
    if args.generator == "taomate_h3":
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        return TaoMateH3Generator.from_args(args)
    raise ValueError(args.generator)


def make_memory(args: argparse.Namespace, hello: dict, session_id: str, scope: str = "private"):
    if not args.memory_db:
        return None
    from live_agent.memory_bridge import MemoryBridge

    return MemoryBridge(args.memory_db, user_id=hello.get("user_id", "anon"),
                        stream_id=hello.get("stream_id", "stream-0"), session_id=session_id, mode=scope)


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--asr-url", default="http://127.0.0.1:8103/v1")
    p.add_argument("--asr-model", default="qwen3-asr")
    p.add_argument("--memory-db", default=".cache/memory.sqlite")
    p.add_argument("--log-dir", default=".cache/sessions")
    p.add_argument("--record", action="store_true", help="record each session's presented audio/video to <log-dir>/<session>.mp4")
    p.add_argument("--director-mode", default="closed_loop", choices=["closed_loop", "open_loop"])
    p.add_argument("--correction-mode", default="gradient", choices=["gradient", "repeat", "none"])
    p.add_argument("--lambda-prior", type=float, default=3.0)
    p.add_argument("--mock-judge-p", type=float, default=1.0, help="with --vlm-url mock: P(action judged done)")
    p.add_argument("--dev-allow-uncalibrated", action="store_true",
                   help="allow capabilities that were never executed (development only)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8200)
    # TaoMate-H3 generator options are parsed by the adapter (see taomate_h3.py).
    args, rest = p.parse_known_args()
    args.extra = rest
    # JPEG/PCM frames do not compress: per-message deflate only burned event-loop time (stall watchdog)
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info", ws_per_message_deflate=False)


if __name__ == "__main__":
    main()
