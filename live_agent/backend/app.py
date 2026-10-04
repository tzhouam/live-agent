"""API-only FastAPI backend: scoped resources and one session per WebSocket.

The standalone frontend owns HTML, CSS, JavaScript and its same-origin proxy.
HTTP routes and the existing /ws media protocol are documented in
``docs/frontend_backend.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import SessionView
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import EventType, Utterance, new_id, now
from live_agent.backend.config import BOARD_IMAGES, CURRICULUM, STUDENT_SEEDS, parse_args
from live_agent.backend.resources import register_resources
from live_agent.backend.runtime import llm_api_key, make_generator, make_memory
from live_agent.backend.transport import WSTransport, encode_h264, encode_jpeg, panel_event, to_pcm16

log = logging.getLogger("live_agent.backend")


def _valid_request_id(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 64


def _validated_lesson_context(curriculum, value) -> dict | None:
    if not isinstance(value, dict) or type(value.get("grade")) is not int:
        return None
    subject, grade, topic = value.get("subject"), value["grade"], value.get("topic")
    if not isinstance(subject, str) or not isinstance(topic, str) or not 1 <= grade <= 12:
        return None
    for entry in curriculum.subjects:
        grades = entry.get("grade_topics")
        if entry.get("subject") != subject or not isinstance(grades, dict):
            continue
        chapter = grades.get(str(grade))
        if isinstance(chapter, dict) and isinstance(chapter.get("topics"), list) and any(
                isinstance(title, str) and title.strip() == topic for title in chapter["topics"]):
            return {"subject": subject, "grade": grade, "topic": topic}
    return None


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI(title="Live Agent Backend", version="1.0")

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/", "/traces/file/", "/board/img/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()
    from live_agent.student import ProfileStore

    # one shared copy per student for sessions and the profile page; only ids on the allow-list are reachable
    profiles = ProfileStore(Path(args.student_store), STUDENT_SEEDS,
                            [x for x in (args.students or args.student).split(",")
                             if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", x)])
    app.state.profiles = profiles
    from live_agent.curriculum import Curriculum

    curriculum = Curriculum.load(CURRICULUM)  # course knowledge base (empty if not present)
    app.state.curriculum = curriculum

    @app.get("/api/curriculum")
    async def curriculum_summary() -> dict:
        return curriculum.summary()

    @app.get("/api/curriculum/topics")
    async def curriculum_topics() -> dict:
        topics = []
        for subject in curriculum.subjects:
            name = subject.get("subject")
            entries = subject.get("grade_topics")
            if not isinstance(name, str) or not isinstance(entries, dict):
                continue
            for grade_text, entry in entries.items():
                if not re.fullmatch(r"[0-9]{1,2}", str(grade_text)) or not 1 <= int(grade_text) <= 12 or not isinstance(entry, dict):
                    continue
                values = entry.get("topics")
                if not isinstance(values, list):
                    continue
                for topic in values:
                    if not isinstance(topic, str) or not topic.strip():
                        continue
                    basis = entry.get("basis")
                    item = {"subject": name, "grade": int(grade_text), "topic": topic.strip(),
                            "basis": basis if isinstance(basis, str) else ""}
                    if isinstance(entry.get("source"), str):
                        item["source"] = entry["source"]
                    topics.append(item)
        return {"topics": topics}

    @app.on_event("startup")
    async def _startup() -> None:
        if args.record:  # recordings left unfinished by a killed session
            from live_agent.sim import salvage_recordings

            fixed = await asyncio.to_thread(salvage_recordings, args.log_dir)
            if fixed:
                log.info("finalised %d interrupted recording(s): %s", len(fixed), ", ".join(fixed))
        from live_agent.llm import OpenAICompatLLM, make_chat_llm

        if args.llm_url != "scripted":
            await make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args)).warmup()  # SDK lazy imports
        # Heavy generators are started once and shared (reset per session); the mock and the CPU
        # puppet are per session (trivial start-up, no worker processes).
        if args.generator not in ("mock", "puppet"):
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

    register_resources(app, args, profiles)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = "public" if hello.get("mode") == "public" else "private"
        session_id = new_id("sess")
        record_path = Path(args.log_dir) / f"{session_id}.mp4" if args.record else None
        if record_path is not None:
            record_path.parent.mkdir(parents=True, exist_ok=True)
        codec = "h264" if args.video_codec == "auto" and "h264" in (hello.get("video_codecs") or []) else "jpeg"
        transport = WSTransport(ws, record_path, video_codec=codec)
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
            from live_agent.llm import OpenAICompatLLM, make_chat_llm

            manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
            if args.llm_url == "scripted":  # CPU-only demo: rule-based responder, no model server
                from live_agent.llm import RuleResponder

                llm = RuleResponder(manifest)
            else:
                llm = make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args))
            if args.dev_allow_uncalibrated:
                manifest.min_status = Status.DOCUMENTED
            ledger = StateLedger.from_config(cfg_dir / "canon.json")
            intents = canon.get("intents", {})  # persona filler gestures (idle / listen / while speaking)
            director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                                persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode),
                                idle_intent=intents.get("idle", "idle_read"),
                                listen_intent=intents.get("listen", "listen"),
                                speak_intent=intents.get("speak"),
                                responder_style=canon.get("responder_style", ""),
                                responder_examples=canon.get("responder_examples"))
            director.present_intent = intents.get("present")  # gesture toward the page's board
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

                hosted = not args.vlm_url.startswith(("http://127.", "http://localhost"))
                judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model,
                                                 api_key=llm_api_key(args) if hosted else "EMPTY", timeout_s=60.0),
                                 k=8, contrast=True)
            asr = None
            if args.asr_url.startswith("wss://"):  # hosted realtime audio model: user speech only (no per-request
                from live_agent.asr import HostedRealtimeASR  # speech QC: an API call per 5 s line, ~6 s each)

                asr = HostedRealtimeASR(args.asr_url, args.asr_model, llm_api_key(args))
            elif args.asr_url:
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
                                                       correction_mode=CorrectionMode(args.correction_mode),
                                                       # the demo's vLLM-Omni configs hold for every prompt
                                                       generator_holds=args.generator == "vllm_omni_h3",
                                                       lesson_self_check=args.lesson_self_check))
            transport.orchestrator = orch
            if args.image_url:
                from live_agent.board_images import ImageMaker

                orch.image_maker = ImageMaker(args.image_url, BOARD_IMAGES)
            orch.figure_dir = BOARD_IMAGES  # exact plots need no model
            orch.answer_boards = bool(canon.get("board"))
            orch.curriculum = curriculum  # a persona with a board writes one for every knowledge answer
            # the page may pick a profile only from the server's allow-list: the demo has one shared access token and no
            # per-student accounts, so the operator decides which profiles this deployment exposes
            allowed = profiles.allowed
            student_id = str(hello.get("student") or args.student)
            if student_id not in allowed:
                student_id = args.student
            if mode == "private" and student_id in allowed:
                # personal data: only a private session reads or updates the saved profile (the shared copy)
                orch.student = profiles.get(student_id)
                orch.profile_store = profiles
                if orch.student is not None:
                    profiles.subscribe(student_id, orch.on_profile_edited)
            orch.log.emit(EventType.AUDIT, now(), where="session_start", session_id=session_id,
                          mode=mode, student_id=orch.student.student_id if orch.student is not None else None)
            if getattr(judge, "vlm", None) is not None:  # the camera focus check uses the judge's VLM (opt-in)
                from live_agent.attention import AttentionMonitor

                orch.attention = AttentionMonitor(judge.vlm)
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
                                           "asr": bool(args.asr_url), "persona": canon.get("display_name", ""),
                                           "examples": canon.get("examples", []),
                                           "attention": orch.attention is not None,
                                           "board": bool(canon.get("board")),
                                           "student": orch.student.view() if orch.student is not None else None},
                                          ensure_ascii=False))

            async def handle_inputs() -> None:
                """Utterances are processed in order, off the receive loop, so presentation acks
                and barge-in keep being read (and timestamped) while ASR / the LLM run."""
                while True:
                    kind, payload, t_end, epoch, lesson_context, request_id = await inputs.get()  # epoch stamped at receipt
                    try:
                        if kind == "audio":
                            from live_agent.asr import decode_audio_bytes

                            audio = decode_audio_bytes(payload, 16000)
                            text = await asr.transcribe(audio, 16000)
                            correlation = {"request_id": request_id} if request_id is not None else {}
                            await ws.send_text(json.dumps({"type": "transcript", "text": text, **correlation}))
                        else:
                            text = payload
                        if text:
                            # t_end = when the user stopped speaking / sent (client clock, mapped), so
                            # ASR and queueing delay count toward the deadlines (proposal §7)
                            await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, t_end,
                                                                   session_id=session_id, scope=mode,
                                                                   lesson_context=lesson_context, request_id=request_id),
                                                         epoch=epoch)
                    except Exception:  # noqa: BLE001
                        log.exception("input handling failed")

            worker = asyncio.create_task(handle_inputs())
            audio_end = now()
            audio_request_id, audio_epoch, audio_rejected = None, None, False
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
                    if audio_rejected:
                        audio_rejected = False  # discard the recording whose start packet was rejected
                        continue
                    request_id, epoch = audio_request_id, audio_epoch
                    audio_request_id, audio_epoch = None, None  # one complete recording per binary message
                    if asr is not None:
                        inputs.put_nowait(("audio", msg["bytes"], audio_end,
                                          orch.input_epoch if epoch is None else epoch, None, request_id))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end", "chunk_received"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    request_id = data.get("request_id")
                    if "request_id" in data and not _valid_request_id(request_id):
                        audio_request_id, audio_epoch, audio_rejected = None, None, True
                        await ws.send_json({"type": "error", "error": "invalid request_id"})
                        continue
                    await orch.on_speech_start()
                    audio_request_id, audio_epoch, audio_rejected = request_id, orch.input_epoch, False
                elif t == "text" and data.get("text", "").strip():
                    request_id = data.get("request_id")
                    if "request_id" in data and not _valid_request_id(request_id):
                        await ws.send_json({"type": "error", "error": "invalid request_id"})
                        continue
                    lesson_context = None
                    if "lesson_context" in data:
                        lesson_context = _validated_lesson_context(curriculum, data["lesson_context"])
                        if lesson_context is None:
                            await ws.send_json({"type": "error", "error": "invalid catalogue topic selection"})
                            continue
                    # a typed instruction interrupts like speech does (before its LLM work is queued)
                    await orch.on_speech_start()
                    inputs.put_nowait(("text", data["text"].strip(), transport._to_server(data), orch.input_epoch, lesson_context, request_id))
                elif t == "audio_end":  # precedes the recorded audio bytes
                    audio_end = transport._to_server(data)
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
                elif t == "clock":
                    transport.on_clock(data)
                elif t == "camera" and isinstance(data.get("jpeg"), str) and len(data["jpeg"]) <= 400_000:
                    try:  # opt-in attention check: analysed in memory, never stored or recorded
                        orch.on_camera(base64.b64decode(data["jpeg"]))
                    except (ValueError, TypeError):
                        pass
                elif t == "camera_off":
                    orch.camera_off()
                elif t == "profile" and orch.student is not None and isinstance(data.get("profile"), dict):
                    orch.student.update_basics(data["profile"])  # name, grade, exams (mastery comes from exercises)
                    orch._save_profile()
                    orch._emit_profile()
                elif t == "video_codec" and data.get("codec") == "jpeg":
                    transport.video_codec = "jpeg"  # the page failed to decode H.264
        except WebSocketDisconnect:
            pass
        finally:
            try:
                if "panel_task" in locals():
                    panel_task.cancel()
                if worker is not None:
                    worker.cancel()
                if orch is not None:
                    if orch.student is not None:
                        profiles.unsubscribe(orch.student.student_id, orch.on_profile_edited)
                    await orch.stop()
                if transport.recorder is not None:
                    await asyncio.to_thread(transport.recorder.close)  # mux video + audio
            except Exception:  # noqa: BLE001
                log.exception("session cleanup failed")
            finally:
                if shared:
                    app.state.session_lock.release()

    return app


def main() -> None:
    import uvicorn

    args = parse_args()
    # Media binary frames need no deflate; it stalls the event loop.
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info", ws_per_message_deflate=False)


if __name__ == "__main__":
    main()
