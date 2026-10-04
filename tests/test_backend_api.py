"""The standalone backend owns data and media, without depending on browser assets."""

import json
import os

from fastapi.testclient import TestClient

from live_agent.backend.app import build_app
from live_agent.backend.config import parse_args


def backend(tmp_path, students="demo", asr_url=""):
    args = parse_args(["--generator", "mock", "--llm-url", "scripted", "--vlm-url", "mock", "--asr-url", asr_url,
                       "--memory-db", "", "--student-store", str(tmp_path / "students"),
                       "--log-dir", str(tmp_path / "logs"), "--students", students, "--dev-allow-uncalibrated"])
    return build_app(args)


def receive_ws_bounded(ws, timeout=5):
    """Await the test channel with a deadline, without leaving a blocked receiver thread behind."""
    import asyncio

    message = ws.portal.call(asyncio.wait_for, ws._send_rx.receive(), timeout)
    ws._raise_on_close(message)
    return message


def receive_utterance(ws, request_id):
    import time

    records, transcripts = [], []
    deadline = time.monotonic() + 5
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "utterance outcome did not arrive"
        packet = receive_ws_bounded(ws, remaining)
        if "text" not in packet:
            continue
        message = json.loads(packet["text"])
        if message.get("type") == "transcript":
            transcripts.append(message)
        if message.get("event") == "utterance_end" and message["data"].get("request_id") == request_id:
            records.append(message["data"])
            if "decision" in message["data"]:
                assert len(records) == 2
                return records, transcripts


def mock_voice_asr(monkeypatch, texts):
    from live_agent import asr
    from collections import deque
    import numpy as np

    pending, calls = deque(texts), []

    class FakeASR:
        def __init__(self, *args, **kwargs):
            pass  # no endpoint or credential access

        async def transcribe(self, audio, sample_rate):
            assert sample_rate == 16000 and len(audio) == 160
            calls.append(audio.copy())
            return pending.popleft()

        def transcribe_sync(self, *args):
            return ""  # speech QC is not exercised by these input checks

    monkeypatch.setattr(asr, "OpenAIASR", FakeASR)
    return asr.to_wav_bytes(np.zeros(160, dtype=np.float32), 16000), calls


def test_backend_runs_without_browser_views_and_documents_its_api(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "generator": "mock", "protocol_version": 1}
        for path in ("/", "/profile", "/traces", "/assets/live.js", "/static/index.html"):
            assert client.get(path).status_code == 404
        paths = client.get("/openapi.json").json()["paths"]
        assert {"/api/health", "/api/traces", "/api/students", "/api/curriculum"} <= paths.keys()
        assert "/profile" not in paths and "/traces" not in paths
        assert client.get("/api/students").headers["cache-control"] == "no-store"


def test_trace_index_returns_data_and_only_its_own_media(tmp_path):
    directory = tmp_path / "logs"
    directory.mkdir()
    first = directory / "sess-a.jsonl"
    first.write_text('{"type":"lock"}\n')
    second = directory / "sess-ab.jsonl"
    second.write_text('{"type":"stop"}\n')
    os.utime(first, (100, 100))
    os.utime(second, (200, 200))
    names = ["sess-a.mp4", "sess-a-part2.mp4", "sess-a.generated.mp4", "sess-a.generated-part2.mp4", "sess-ab.mp4"]
    for name in names:
        (directory / name).write_bytes(b"media")
    (directory / "sess-<bad>.jsonl").write_text("untrusted filename")
    (directory / "secret.txt").write_text("private")
    with TestClient(backend(tmp_path)) as client:
        response = client.get("/api/traces")
        assert response.headers["cache-control"] == "no-store"
        sessions = response.json()["sessions"]
        assert [s["id"] for s in sessions] == ["sess-ab", "sess-a"]
        session = sessions[1]
        assert session["size_bytes"] == first.stat().st_size
        assert session["updated_at"].endswith("+00:00")
        assert session["trace_url"] == "/traces/file/sess-a.jsonl"
        assert {v["name"] for v in session["videos"]} == set(names[:-1])
        assert {v["label"] for v in session["videos"]} == {"presented", "presented part2", "generated", "generated-part2"}
        assert client.get(session["trace_url"]).content == first.read_bytes()
        media = client.get("/traces/file/sess-a.mp4", headers={"Range": "bytes=1-3"})
        assert media.status_code == 206 and media.content == b"edi"
        assert media.headers["cache-control"] == "no-store"
        for path in ("/traces/file/secret.txt", "/traces/file/sess-missing.mp4", "/board/img/secret.txt"):
            assert client.get(path).status_code == 404


def test_websocket_keeps_hello_clock_and_binary_media_contract(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "user_id": "test", "video_codecs": []})
            ws.send_json({"type": "ping", "t": 123.0})
            status = pong = chunk = None
            binary_frames = 0
            for _ in range(150):
                msg = ws.receive()
                if "bytes" in msg:
                    binary_frames += 1
                else:
                    data = json.loads(msg["text"])
                    if data["type"] == "status":
                        status = data
                    elif data["type"] == "pong":
                        pong = data
                    elif data["type"] == "chunk":
                        chunk = data
                if status and pong and chunk and binary_frames >= chunk["n_frames"] + 1:
                    break
            assert status["generator"] == "mock" and status["responder"] == "rules"
            assert pong["t"] == 123.0 and isinstance(pong["ts"], float)
            assert chunk["codec"] == "jpeg" and chunk["sample_rate"] > 0 and chunk["duration"] > 0
            assert binary_frames >= chunk["n_frames"] + 1


def test_puppet_backend_streams_skeleton_chunks(tmp_path):
    """The CPU skeleton backend runs a real session end to end (synth voice, rule responder)."""
    args = parse_args(["--generator", "puppet", "--puppet-tts", "synth", "--llm-url", "scripted",
                       "--vlm-url", "mock", "--asr-url", "",
                       "--memory-db", "", "--student-store", str(tmp_path / "students"),
                       "--log-dir", str(tmp_path / "logs"), "--dev-allow-uncalibrated"])
    with TestClient(build_app(args)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "generator": "puppet", "protocol_version": 1}
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "user_id": "test", "video_codecs": []})
            ws.send_json({"type": "ping", "t": 5.0})
            status = chunk = None
            binary_frames = 0
            for _ in range(400):  # real-time rig: the first request takes a few seconds
                msg = ws.receive()
                if "bytes" in msg:
                    binary_frames += 1
                else:
                    data = json.loads(msg["text"])
                    if data["type"] == "status":
                        status = data
                    elif data["type"] == "chunk":
                        chunk = data
                if status and chunk and binary_frames >= chunk["n_frames"] + 1:
                    break
            assert status["generator"] == "puppet" and status["responder"] == "rules"
            assert chunk["codec"] == "jpeg" and chunk["sample_rate"] == 32000 and chunk["duration"] > 0
            assert binary_frames >= chunk["n_frames"] + 1  # JPEG frames + PCM16 audio per chunk


def test_old_server_module_is_a_compatibility_entrypoint():
    from live_agent.server.app import WSTransport, build_app as old_build_app
    from live_agent.backend.transport import WSTransport as transport

    assert old_build_app is build_app and WSTransport is transport


def test_presentation_timestamps_work_before_and_after_clock_sync():
    from live_agent.backend.transport import WSTransport
    from live_agent.types import now

    transport = WSTransport(None)
    start = now()
    assert start <= transport._to_server({}) <= now()
    assert start <= transport._to_server({"tp": 10.0}) <= now()
    transport.on_clock({"rtt": 20.0, "t_server": 100.0, "t_client": 1000.0})
    assert abs(transport._to_server({"tp": 1500.0}) - 100.49) < 1e-9


def test_curriculum_topics_come_from_real_school_entries(tmp_path):
    app = backend(tmp_path)
    curriculum = app.state.curriculum
    with TestClient(app) as client:
        response = client.get("/api/curriculum/topics")
        assert response.headers["cache-control"] == "no-store"
        topics = response.json()["topics"]
        assert topics
        assert client.get("/api/curriculum").json() == curriculum.summary()
        for item in topics:
            subject = next(s for s in curriculum.subjects if s["subject"] == item["subject"])
            entry = subject["grade_topics"][str(item["grade"])]
            assert item["topic"] in entry["topics"]
            assert subject["grades"][0] <= item["grade"] <= subject["grades"][1]
            assert item["basis"] == entry.get("basis", "")
        assert any(t["subject"] == "数学" and t["grade"] == 1 for t in topics)
        assert any(t["subject"] == "物理" and t["grade"] == 8 for t in topics)
        assert not any(t["subject"] == "科学" and t["grade"] > 6 for t in topics)


def test_curriculum_topics_empty_directory_and_invalid_entries(tmp_path, monkeypatch):
    import live_agent.backend.app as backend_module

    directory = tmp_path / "curriculum"
    directory.mkdir()
    monkeypatch.setattr(backend_module, "CURRICULUM", directory)
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/curriculum/topics").json() == {"topics": []}
    (directory / "subject.json").write_text(json.dumps({
        "subject": "数学", "grades": [1, 12], "grade_topics": {
            "1": {"topics": ["真实章节", "", {"topic": "not a title"}], "basis": "textbook", "source": "s1"},
            "13": {"topics": ["not a school grade"]},
            "adult": {"topics": ["not a school grade"]},
            "²": {"topics": ["not a grade integer"]},
        },
    }), encoding="utf-8")
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/curriculum/topics").json() == {"topics": [
            {"subject": "数学", "grade": 1, "topic": "真实章节", "basis": "textbook", "source": "s1"},
        ]}


def test_pending_exercise_snapshot_and_event_show_question_without_answer():
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.exercise import Exercise

    orch, _ = pipeline.build()
    exercise = Exercise(concept="加法", question="一加二等于几？", answer="B", kind="choice",
                        options=["A. 二", "B. 三"], explanation=["先数一，再数两次。"])
    orch.director.exercise = exercise
    orch._exercise_changed()
    expected = {"concept": "加法", "kind": "choice", "question": "一加二等于几？",
                "options": ["A", "B"], "option_texts": ["A. 二", "B. 三"]}
    assert orch.snapshot()["exercise"] == expected
    event = panel_event(orch.log.events[-1], 0)
    assert event["data"] == {"stage": "exercise_open", **expected}
    assert "answer" not in event["data"] and "explanation" not in event["data"]
    orch.director.exercise = None
    orch._exercise_changed()
    assert orch.snapshot()["exercise"] is None
    assert panel_event(orch.log.events[-1], 0)["data"] == {"stage": "exercise_closed"}


def saved_trace(directory, session_id, mode=None, student=None):
    from live_agent.timeline import EventLog
    from live_agent.types import EventType

    directory.mkdir(exist_ok=True)
    log = EventLog(directory / f"{session_id}.jsonl")
    if mode:
        log.emit(EventType.AUDIT, where="session_start", session_id=session_id, mode=mode, student_id=student)
    log.emit(EventType.UTTERANCE_END, speaker="user", uid="u1", text="给我讲加法。")
    log.emit(EventType.UTTERANCE_END, uid="u1", decision={"kind": "lesson"})
    log.emit(EventType.LOCK, request_index=0, transcript="一加一等于二。", prompt="internal generation prompt")
    log.emit(EventType.LOCK, request_index=1, transcript="没有播放的生成脚本。")
    for chunk in range(4):
        log.emit(EventType.CHUNK_PRESENTED, request_index=0, chunk_index=chunk, chunks_per_request=4,
                 request_complete=chunk == 3)
    log.close()
    for suffix in (".mp4", "-part2.mp4", ".generated.mp4"):
        (directory / f"{session_id}{suffix}").write_bytes(b"video")


def test_trace_filters_use_declared_learner_or_public_scope(tmp_path):
    directory = tmp_path / "logs"
    saved_trace(directory, "sess-alpha", "private", "alpha")
    saved_trace(directory, "sess-beta", "private", "beta")
    saved_trace(directory, "sess-public", "public")
    saved_trace(directory, "sess-legacy")
    saved_trace(directory, "sess-unknown", "private")
    with TestClient(backend(tmp_path, "alpha,beta")) as client:
        assert {s["id"] for s in client.get("/api/traces").json()["sessions"]} == {
            "sess-alpha", "sess-beta", "sess-public", "sess-legacy", "sess-unknown"}
        for query, expected in (("student=alpha", "sess-alpha"), ("student=beta", "sess-beta"), ("mode=public", "sess-public")):
            response = client.get("/api/traces?" + query)
            assert response.headers["cache-control"] == "no-store"
            sessions = response.json()["sessions"]
            assert len(sessions) == 1 and sessions[0]["id"] == expected
            session = sessions[0]
            assert session["transcript_url"] == f"/api/traces/{expected}/transcript?{query}"
            assert session["trace_url"].endswith("?" + query)
            assert all(video["url"].endswith("?" + query) for video in session["videos"])
            assert client.get(session["trace_url"]).status_code == 200
            assert all(client.get(video["url"]).status_code == 200 for video in session["videos"])
        assert client.get("/api/traces?student=outside").status_code == 404
        for query in ("student=alpha&mode=public", "mode=private", "mode=other"):
            assert client.get("/api/traces?" + query).status_code == 400
        assert client.get("/traces/file/sess-beta.mp4?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-legacy.jsonl?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-alpha.mp4?mode=public").status_code == 404


def test_transcript_is_readable_exact_script_and_input_with_scope_guard(tmp_path):
    directory = tmp_path / "logs"
    saved_trace(directory, "sess-alpha", "private", "alpha")
    saved_trace(directory, "sess-legacy")
    with (directory / "sess-alpha.jsonl").open("a") as trace:
        trace.write('{"unfinished":')
    with TestClient(backend(tmp_path, "alpha,beta")) as client:
        response = client.get("/api/traces/sess-alpha/transcript?student=alpha")
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"id": "sess-alpha", "mode": "private", "student_id": "alpha",
                                   "kind": "script_aid", "verified_audio": False, "omitted_partial_requests": [], "entries": [
                                       {"role": "user", "text": "给我讲加法。", "source": "utterance_end"},
                                       {"role": "teacher", "text": "一加一等于二。", "source": "lock", "request_index": 0,
                                        "presented": True, "kind": "planned_script", "may_include_unplayed_words": True,
                                        "presentation": {"status": "complete", "chunks_acknowledged": [0, 1, 2, 3], "chunks_expected": 4}},
                                   ]}
        assert client.get("/api/traces/sess-alpha/transcript?student=beta").status_code == 404
        assert client.get("/api/traces/sess-alpha/transcript?mode=public").status_code == 404
        assert client.get("/api/traces/sess-legacy/transcript?student=alpha").status_code == 404
        assert client.get("/api/traces/sess-missing/transcript").status_code == 404
        assert client.get("/api/traces/secret.txt/transcript").status_code == 404
        (directory / "sess-link.jsonl").symlink_to(directory / "sess-alpha.jsonl")
        assert client.get("/api/traces/sess-link/transcript").status_code == 404


def test_new_sessions_log_actual_profile_and_no_public_learner(tmp_path):
    app = backend(tmp_path, "alpha,beta")
    with TestClient(app) as client:
        ids = {}
        for mode, selected in (("private", "alpha"), ("private", "beta"), ("public", "alpha")):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "hello", "mode": mode, "student": selected, "user_id": "test"})
                while True:
                    message = ws.receive()
                    if "text" in message:
                        payload = json.loads(message["text"])
                        if payload.get("type") == "status":
                            ids[(mode, selected)] = payload["session"]
                            break
        for selected in ("alpha", "beta"):
            sessions = client.get("/api/traces?student=" + selected).json()["sessions"]
            assert [(s["id"], s["mode"], s["student_id"]) for s in sessions] == [
                (ids[("private", selected)], "private", selected)]
        app.state.profiles.allowed.clear()  # public browsing does not require private profiles
        sessions = client.get("/api/traces?mode=public").json()["sessions"]
        assert [(s["id"], s["mode"], s["student_id"]) for s in sessions] == [
            (ids[("public", "alpha")], "public", None)]


def test_websocket_catalogue_context_is_validated_and_carried_with_text(tmp_path, monkeypatch):
    from live_agent.orchestrator import Orchestrator

    received = []

    async def capture(self, utterance, **kwargs):
        received.append(utterance)
        await self.transport.send_json({"type": "received_for_test"})

    monkeypatch.setattr(Orchestrator, "on_user_utterance", capture)
    with TestClient(backend(tmp_path)) as client:
        item = client.get("/api/curriculum/topics").json()["topics"][0]
        selected = {key: item[key] for key in ("subject", "grade", "topic")}
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
            ws.send_json({"type": "text", "text": "请讲这一章。", "lesson_context": {**selected, "profile": "not trusted"}})
            while True:
                message = ws.receive()
                if "text" in message and json.loads(message["text"]).get("type") == "received_for_test":
                    break
            assert received[0].text == "请讲这一章。" and received[0].lesson_context == selected
            for invalid in ({**selected, "topic": "a fabricated course"}, {**selected, "grade": 13},
                            {**selected, "grade": True}, {**selected, "subject": "university"}):
                ws.send_json({"type": "text", "text": "不应该排队。", "lesson_context": invalid})
                while True:
                    message = ws.receive()
                    if "text" in message:
                        payload = json.loads(message["text"])
                        if payload.get("type") == "error":
                            assert payload["error"] == "invalid catalogue topic selection"
                            break
            assert len(received) == 1


def test_declared_media_base_owns_ambiguous_part_names_in_index_and_files(tmp_path):
    directory = tmp_path / "logs"
    saved_trace(directory, "sess-a", "private", "alpha")
    saved_trace(directory, "sess-a-part2", "private", "beta")
    (directory / "sess-a-part3.mp4").write_bytes(b"alpha part 3")
    (directory / "sess-a-part2.mp4").write_bytes(b"beta base")
    with TestClient(backend(tmp_path, "alpha,beta")) as client:
        a = client.get("/api/traces?student=alpha").json()["sessions"][0]
        b = client.get("/api/traces?student=beta").json()["sessions"][0]
        assert {v["name"] for v in a["videos"]} == {"sess-a.mp4", "sess-a.generated.mp4", "sess-a-part3.mp4"}
        assert {v["name"] for v in b["videos"]} == {"sess-a-part2.mp4", "sess-a-part2.generated.mp4", "sess-a-part2-part2.mp4"}
        operator = client.get("/api/traces").json()["sessions"]
        names = [video["name"] for session in operator for video in session["videos"]]
        assert len(names) == len(set(names))
        assert client.get("/traces/file/sess-a-part2.mp4?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-a-part2.mp4?student=beta").content == b"beta base"
        assert client.get("/traces/file/sess-a-part3.mp4?student=alpha").content == b"alpha part 3"
        assert client.get("/traces/file/sess-a-part2-part2.mp4?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-a-part2.generated.mp4?student=beta").status_code == 200


def test_script_aid_omits_known_partial_requests_and_labels_legacy_uncertainty(tmp_path):
    from live_agent.timeline import EventLog
    from live_agent.types import EventType

    directory = tmp_path / "logs"
    saved_trace(directory, "sess-alpha", "private", "alpha")
    log = EventLog(directory / "sess-alpha.jsonl")
    log.emit(EventType.LOCK, request_index=2, transcript="前半句可能播放了，后半句没有。")
    log.emit(EventType.CHUNK_PRESENTED, request_index=2, chunk_index=0, chunks_per_request=4, request_complete=False)
    log.emit(EventType.LOCK, request_index=3, transcript="旧日志没有完整播放信息。")
    log.emit(EventType.CHUNK_PRESENTED, request_index=3, chunk_index=0)
    log.close()
    with TestClient(backend(tmp_path, "alpha")) as client:
        result = client.get("/api/traces/sess-alpha/transcript?student=alpha").json()
        assert result["kind"] == "script_aid" and result["verified_audio"] is False
        assert result["omitted_partial_requests"] == [2]
        teacher = [entry for entry in result["entries"] if entry["role"] == "teacher"]
        assert [entry["request_index"] for entry in teacher] == [0, 3]
        assert all(entry["kind"] == "planned_script" and entry["may_include_unplayed_words"] for entry in teacher)
        assert teacher[0]["presentation"]["status"] == "complete"
        assert teacher[1]["presentation"] == {"status": "unknown", "chunks_acknowledged": [0], "chunks_expected": None}


def test_presentation_events_record_expected_chunks_and_full_request_end():
    import test_pipeline as pipeline
    from live_agent.types import EventType

    orch, _ = pipeline.build()
    orch.cfg.qc_enabled = False
    for chunk in range(orch.n_chunks):
        orch.on_presented(0, chunk, float(chunk), float(chunk + 1))
    events = [event for event in orch.log.events if event.type == EventType.CHUNK_PRESENTED]
    assert len(events) == orch.n_chunks
    assert all(event.data["chunks_per_request"] == orch.n_chunks for event in events)
    assert [event.data["request_complete"] for event in events] == [False] * (orch.n_chunks - 1) + [True]


def test_text_request_ids_round_trip_in_initial_and_decision_panel_events(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
            outcomes = []
            for request_id, text in (("chat-A", "你好"), ("practice-B", "再聊一句"), (None, "普通消息")):
                packet = {"type": "text", "text": text}
                if request_id is not None:
                    packet["request_id"] = request_id
                ws.send_json(packet)
                records = []
                while True:
                    message = ws.receive()
                    if "text" not in message:
                        continue
                    event = json.loads(message["text"])
                    if event.get("event") == "utterance_end":
                        records.append(event["data"])
                        if "decision" in event["data"]:
                            break
                assert len(records) == 2 and records[0]["text"] == text
                assert records[0]["uid"] == records[1]["uid"]
                if request_id is None:
                    assert all("request_id" not in record and "applied" not in record for record in records)
                else:
                    assert all(record["request_id"] == request_id for record in records)
                    assert "applied" not in records[0] and records[1]["applied"] is True
                outcomes.append(records[1])
            assert outcomes[0]["request_id"] != outcomes[1]["request_id"]


def test_invalid_request_ids_are_not_queued_and_maximum_id_is_preserved(tmp_path, monkeypatch):
    from live_agent.orchestrator import Orchestrator

    received = []

    async def capture(self, utterance, **kwargs):
        received.append(utterance)
        await self.transport.send_json({"type": "received_for_test"})

    monkeypatch.setattr(Orchestrator, "on_user_utterance", capture)
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private"})
            for invalid in (None, True, 3, "", "   ", "r" * 65):
                ws.send_json({"type": "text", "text": "不要排队", "request_id": invalid})
                while True:
                    message = ws.receive()
                    if "text" in message:
                        payload = json.loads(message["text"])
                        if payload.get("type") == "error":
                            assert payload["error"] == "invalid request_id"
                            break
            valid = "r" * 64
            ws.send_json({"type": "text", "text": "有效消息", "request_id": valid})
            while True:
                message = ws.receive()
                if "text" in message and json.loads(message["text"]).get("type") == "received_for_test":
                    break
            assert len(received) == 1 and received[0].request_id == valid


def test_grading_result_keeps_the_answer_request_id_in_panel_events():
    import asyncio
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.exercise import Exercise
    from live_agent.types import EventType, Utterance, now

    orch, _ = pipeline.build()
    orch.director.exercise = Exercise("加法", "一加一等于几？", "二")
    result = asyncio.run(orch.on_user_utterance(Utterance("server-uid", "user", "二", now(), request_id="answer-ticket")))
    assert result["exercise_result"]["correct"]
    events = [panel_event(event, 0)["data"] for event in orch.log.events if event.type == EventType.UTTERANCE_END]
    assert len(events) == 2 and all(event["request_id"] == "answer-ticket" for event in events)
    assert all(event["uid"] == "server-uid" for event in events)
    assert events[1]["decision"]["exercise_result"]["correct"]
    assert "applied" not in events[0] and events[1]["applied"] is True


def test_correlated_decision_reports_not_applied_after_a_newer_input():
    import asyncio
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.types import EventType, Utterance, now

    async def scenario():
        orch, _ = pipeline.build()
        entered, release = asyncio.Event(), asyncio.Event()

        class HeldDecision:
            async def chat(self, messages, **kwargs):
                assert messages[0]["role"] == "system"  # skipped request must never begin exercise generation
                if "考考我" in messages[-1]["content"]:
                    entered.set()
                    await release.wait()
                    return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
                return json.dumps({"kind": "chat", "steps": []})

        orch.director.llm = HeldDecision()
        await orch.on_speech_start()
        old = asyncio.create_task(orch.on_user_utterance(Utterance("B", "user", "考考我", now(), request_id="B-ticket")))
        await asyncio.wait_for(entered.wait(), timeout=2)
        await orch.on_speech_start()
        await orch.on_user_utterance(Utterance("C", "user", "换个话题", now(), request_id="C-ticket"))
        release.set()
        returned = await old
        assert returned["kind"] == "exercise"  # existing server return semantics stay compatible
        assert not orch._aux and orch.director.exercise is None
        outcomes = {event.data["request_id"]: panel_event(event, 0)["data"] for event in orch.log.events
                    if event.type == EventType.UTTERANCE_END and "decision" in event.data}
        assert outcomes["B-ticket"]["applied"] is False and outcomes["B-ticket"]["decision"]["kind"] == "exercise"
        assert outcomes["C-ticket"]["applied"] is True
        assert any(event.type == EventType.CAPACITY_SKIP and event.data.get("uid") == "B" for event in orch.log.events)

    asyncio.run(scenario())


def test_correlated_grading_supersession_reports_not_applied():
    import asyncio
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.exercise import Exercise
    from live_agent.types import EventType, Utterance, now

    async def scenario():
        orch, _ = pipeline.build()
        entered, release = asyncio.Event(), asyncio.Event()
        orch.director.exercise = Exercise("加法", "一加一等于几？", "二")

        class HeldGrade:
            async def chat(self, messages, **kwargs):
                entered.set()
                await release.wait()
                return json.dumps({"is_answer": True, "correct": True, "feedback": ["答对了。"]}, ensure_ascii=False)

        orch.director.llm = HeldGrade()
        old = asyncio.create_task(orch.on_user_utterance(Utterance("answer", "user", "可能是二", now(), request_id="answer-ticket")))
        await asyncio.wait_for(entered.wait(), timeout=2)
        await orch.on_speech_start()
        release.set()
        returned = await old
        assert returned["superseded"] is True
        outcome = next(panel_event(event, 0)["data"] for event in orch.log.events
                       if event.type == EventType.UTTERANCE_END and "decision" in event.data)
        assert outcome["request_id"] == "answer-ticket" and outcome["applied"] is False
        assert not any(event.type == EventType.LESSON and event.data.get("stage") == "exercise_graded" for event in orch.log.events)

    asyncio.run(scenario())


def test_newer_websocket_text_supersedes_a_held_decision_without_speech_start(tmp_path, monkeypatch):
    import asyncio
    import threading
    import time
    from live_agent.llm import RuleResponder

    entered, release = threading.Event(), threading.Event()
    calls = []

    async def held_chat(self, messages, **kwargs):
        # This is the actual responder path. Exercise generation must never begin for B.
        assert messages[0]["role"] == "system"
        text = messages[-1]["content"]
        calls.append(text)
        if text == "考考我":
            entered.set()
            assert await asyncio.to_thread(release.wait, 5), "test did not release held decision"
            return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
        return json.dumps({"kind": "chat", "steps": []})

    monkeypatch.setattr(RuleResponder, "chat", held_chat)
    messages = []
    outcomes = {}

    def collect(packet):
        if "text" not in packet:
            return {}
        message = json.loads(packet["text"])
        messages.append(message)
        if message.get("event") == "utterance_end" and "decision" in message["data"]:
            outcomes[message["data"]["request_id"]] = message["data"]
        return message

    def receive_until(ws, condition):
        deadline = time.monotonic() + 5
        while not condition():
            remaining = deadline - time.monotonic()
            assert remaining > 0, "expected WebSocket outcome did not arrive"
            message = collect(receive_ws_bounded(ws, remaining))
            if message.get("type") == "pong" and message.get("t") == "C-received":
                return

    try:
        with TestClient(backend(tmp_path)) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
                ws.send_json({"type": "text", "text": "考考我", "request_id": "B-ticket"})
                assert entered.wait(3), "B did not reach the held responder"
                ws.send_json({"type": "text", "text": "换个话题", "request_id": "C-ticket"})
                ws.send_json({"type": "ping", "t": "C-received"})
                receive_until(ws, lambda: False)  # pong proves C was queued with its newer epoch
                release.set()
                receive_until(ws, lambda: len(outcomes) == 2)
                assert outcomes["B-ticket"]["decision"]["kind"] == "exercise"
                assert outcomes["B-ticket"]["applied"] is False
                assert outcomes["C-ticket"]["applied"] is True
    finally:
        release.set()
    assert calls == ["考考我", "换个话题"]
    assert not any(message.get("event") == "lesson" and message["data"].get("request_id") == "B-ticket"
                   for message in messages)
    logged = [json.loads(line) for path in (tmp_path / "logs").glob("*.jsonl") for line in path.read_text().splitlines()]
    assert not any(event["type"] == "lesson" and event["data"].get("request_id") == "B-ticket" for event in logged)


def test_manual_and_voice_requests_keep_distinct_ids_and_legacy_audio_stays_unowned(tmp_path, monkeypatch):
    from live_agent.llm import RuleResponder
    from live_agent.orchestrator import Orchestrator

    audio, asr_calls = mock_voice_asr(monkeypatch, ["请讲加法", "普通语音", "旧版语音", "没有开始包的旧版语音"])
    started = []

    async def classify(self, messages, **kwargs):
        return json.dumps({"kind": "lesson", "topic": "加法", "steps": []}) if messages[-1]["content"] == "请讲加法" else \
            json.dumps({"kind": "chat", "steps": []})

    def capture_lesson(self, topic, context=None, request_id=None):
        started.append((topic, request_id))

    monkeypatch.setattr(RuleResponder, "chat", classify)
    monkeypatch.setattr(Orchestrator, "_start_lesson", capture_lesson)
    with TestClient(backend(tmp_path, asr_url="http://unused.test/v1")) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private"})
            ws.send_json({"type": "text", "text": "请讲加法", "request_id": "manual-A"})
            records, _ = receive_utterance(ws, "manual-A")
            assert records[1]["applied"] is True
            for owner in ("voice-B", "voice-C", None):
                start = {"type": "speech_start"}
                if owner is not None:
                    start["request_id"] = owner
                ws.send_json(start)
                ws.send_json({"type": "audio_end"})
                ws.send_bytes(audio)
                records, transcripts = receive_utterance(ws, owner)
                assert records[1]["decision"]["kind"] == ("lesson" if owner == "voice-B" else "chat")
                assert len(transcripts) == 1 and transcripts[0].get("request_id") == owner
                if owner is None:
                    assert all("request_id" not in event and "applied" not in event for event in records)
                    assert "request_id" not in transcripts[0]
                else:
                    assert all(event["request_id"] == owner for event in records) and records[1]["applied"] is True
            ws.send_json({"type": "audio_end"})
            ws.send_bytes(audio)  # older clients can still send complete audio without a start packet
            records, transcripts = receive_utterance(ws, None)
            assert all("request_id" not in event for event in records) and "request_id" not in transcripts[0]
    assert started == [("加法", "manual-A"), ("加法", "voice-B")]
    assert len(asr_calls) == 4


def test_invalid_speech_ids_do_not_interrupt_or_transcribe_and_boundary_id_is_preserved(tmp_path, monkeypatch):
    from live_agent.orchestrator import Orchestrator

    audio, asr_calls = mock_voice_asr(monkeypatch, ["有效语音"])
    interrupts = []
    original = Orchestrator.on_speech_start

    async def capture_start(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        interrupts.append(self.input_epoch)

    monkeypatch.setattr(Orchestrator, "on_speech_start", capture_start)
    with TestClient(backend(tmp_path, asr_url="http://unused.test/v1")) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private"})
            for invalid in (None, True, 3, "", "   ", "r" * 65):
                ws.send_json({"type": "speech_start", "request_id": invalid})
                while True:
                    packet = receive_ws_bounded(ws)
                    if "text" in packet:
                        message = json.loads(packet["text"])
                        if message.get("type") == "error":
                            assert message["error"] == "invalid request_id"
                            break
                ws.send_json({"type": "audio_end"})
                ws.send_bytes(audio)  # a rejected recording is not treated as legacy unowned audio
            valid = "r" * 64
            ws.send_json({"type": "speech_start", "request_id": valid})
            ws.send_json({"type": "audio_end"})
            ws.send_bytes(audio)
            records, transcripts = receive_utterance(ws, valid)
            assert all(event["request_id"] == valid for event in records) and records[1]["applied"] is True
            assert transcripts[0]["request_id"] == valid
    assert len(interrupts) == 1 and len(asr_calls) == 1


def test_voice_recording_started_before_newer_text_keeps_its_older_epoch(tmp_path, monkeypatch):
    from live_agent.llm import RuleResponder

    audio, asr_calls = mock_voice_asr(monkeypatch, ["考考我"])
    calls = []

    async def classify(self, messages, **kwargs):
        assert messages[0]["role"] == "system"  # superseded voice must never generate an exercise
        calls.append(messages[-1]["content"])
        return json.dumps({"kind": "exercise", "topic": "加法", "steps": []}) if messages[-1]["content"] == "考考我" else \
            json.dumps({"kind": "chat", "steps": []})

    monkeypatch.setattr(RuleResponder, "chat", classify)
    with TestClient(backend(tmp_path, asr_url="http://unused.test/v1")) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private"})
            ws.send_json({"type": "speech_start", "request_id": "voice-A"})
            ws.send_json({"type": "text", "text": "换个话题", "request_id": "manual-B"})
            newer, _ = receive_utterance(ws, "manual-B")
            assert newer[1]["applied"] is True
            ws.send_json({"type": "audio_end"})
            ws.send_bytes(audio)
            older, _ = receive_utterance(ws, "voice-A")
            assert older[1]["decision"]["kind"] == "exercise" and older[1]["applied"] is False
    assert len(asr_calls) == 1 and calls == ["换个话题", "考考我"]
    logged = [json.loads(line) for path in (tmp_path / "logs").glob("*.jsonl") for line in path.read_text().splitlines()]
    assert not any(event["type"] == "lesson" and event["data"].get("request_id") == "voice-A" for event in logged)
