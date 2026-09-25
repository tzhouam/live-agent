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


class WSTransport:
    """Orchestrator transport over one WebSocket connection.

    Presentation times: the client reports, for each chunk, when its audio starts / ends at the
    audio *output* (AudioContext.getOutputTimestamp -> performance clock, ``tp`` in ms). The
    server maps that clock to its own with the lowest-RTT ping sample (NTP-style,
    offset = t_server - (t_client_send + rtt/2)). Until a mapping exists, arrival time is used
    (and the event says so)."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.orchestrator: Orchestrator | None = None
        self._send_lock = asyncio.Lock()
        self._starts: dict[tuple[int, int], float] = {}
        self._epoch = 0  # incremented on stop; stale sends are skipped
        self.clock_offset_s: float | None = None
        self.clock_rtt_s: float | None = None

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
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
                "width": int(w), "height": int(h), "transcript": script.transcript}))
            for j in jpegs:
                if epoch != self._epoch:
                    return  # interrupted mid-chunk: the client discards the partial chunk
                await self.ws.send_bytes(j)
            if epoch == self._epoch:
                await self.ws.send_bytes(pcm)

    async def stop_playback(self) -> None:
        """Immediate: does not wait for an in-flight chunk send (which aborts at its next frame)."""
        self._epoch += 1
        await self.ws.send_text(json.dumps({"type": "stop"}))

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
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t)


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI()
    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()

    @app.on_event("startup")
    async def _startup() -> None:
        # Heavy generators are started once and shared (reset per session); the mock is per session.
        if args.generator != "mock":
            gen = make_generator(args)
            await gen.start()
            app.state.shared_gen = gen

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.shared_gen is not None:
            await app.state.shared_gen.close()

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = "public" if hello.get("mode") == "public" else "private"
        session_id = new_id("sess")
        transport = WSTransport(ws)
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

            llm = OpenAICompatLLM(args.llm_url, args.llm_model)
            manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
            if args.dev_allow_uncalibrated:
                manifest.min_status = Status.DOCUMENTED
            ledger = StateLedger.from_config(cfg_dir / "canon.json")
            director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                                persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode))
            generator = SessionView(app.state.shared_gen) if shared else make_generator(args)
            sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
                                                  lambda_prior_s=args.lambda_prior))
            judge = speech = None
            if args.vlm_url:
                from live_agent.qc.judge import VLMJudge

                judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model))
            asr = None
            if args.asr_url:
                from live_agent.asr import OpenAIASR
                from live_agent.qc.judge import SpeechCheck

                asr = OpenAIASR(args.asr_url, args.asr_model)
                speech = SpeechCheck(asr.transcribe_sync)
            from live_agent.qc.judge import ForwardCorrector

            log_dir = Path(args.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=ForwardCorrector(llm),
                                speech_check=speech, memory=make_memory(args, hello, session_id, mode),
                                log=EventLog(log_dir / f"{session_id}.jsonl"),
                                cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                       correction_mode=CorrectionMode(args.correction_mode)))
            transport.orchestrator = orch
            await orch.start()
            await ws.send_text(json.dumps({"type": "status", "session": session_id, "mode": mode,
                                           "generator": generator.info.name}))

            async def handle_inputs() -> None:
                """Utterances are processed in order, off the receive loop, so presentation acks
                and barge-in keep being read (and timestamped) while ASR / the LLM run."""
                while True:
                    kind, payload = await inputs.get()
                    try:
                        if kind == "audio":
                            from live_agent.asr import decode_audio_bytes

                            audio = decode_audio_bytes(payload, 16000)
                            text = await asr.transcribe(audio, 16000)
                            await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                        else:
                            text = payload
                        if text:
                            await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, now(),
                                                                   session_id=session_id, scope=mode))
                    except Exception:  # noqa: BLE001
                        log.exception("input handling failed")

            worker = asyncio.create_task(handle_inputs())
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    if asr is not None:
                        inputs.put_nowait(("audio", msg["bytes"]))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    await orch.on_speech_start()
                elif t == "text" and data.get("text", "").strip():
                    inputs.put_nowait(("text", data["text"].strip()))
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
                elif t == "clock":
                    transport.on_clock(data)
        except WebSocketDisconnect:
            pass
        finally:
            if worker is not None:
                worker.cancel()
            if orch is not None:
                await orch.stop()
            if shared:
                app.state.session_lock.release()

    return app


def make_generator(args: argparse.Namespace):
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator

        return MockGenerator(size=(480, 864))
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
    p.add_argument("--director-mode", default="closed_loop", choices=["closed_loop", "open_loop"])
    p.add_argument("--correction-mode", default="gradient", choices=["gradient", "repeat", "none"])
    p.add_argument("--lambda-prior", type=float, default=3.0)
    p.add_argument("--dev-allow-uncalibrated", action="store_true",
                   help="allow capabilities that were never executed (development only)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8200)
    # TaoMate-H3 generator options are parsed by the adapter (see taomate_h3.py).
    args, rest = p.parse_known_args()
    args.extra = rest
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
