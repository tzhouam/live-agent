"""A live persona (a canon without a board, e.g. the hanfu reading host) is a plain live agent (D-068):
the backend serves no teaching endpoints, attaches no learner profile, ignores catalogue selections,
and responder decisions never enter classroom workflows (lessons, exercises, profile updates)."""

from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

import test_pipeline as tp
from live_agent.backend.app import build_app
from live_agent.backend.config import parse_args
from live_agent.types import EventType


def live_backend(tmp_path):
    args = parse_args(["--generator", "mock", "--llm-url", "scripted", "--vlm-url", "mock", "--asr-url", "",
                       "--memory-db", "", "--student-store", str(tmp_path / "students"),
                       "--log-dir", str(tmp_path / "logs"), "--dev-allow-uncalibrated"])
    # no --config: the default is configs/persona_hanfu, the persona without a board
    return build_app(args)


def test_live_persona_serves_no_teaching_endpoints(tmp_path):
    with TestClient(live_backend(tmp_path)) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/curriculum" not in paths and "/api/curriculum/topics" not in paths
        assert client.get("/api/curriculum").status_code == 404
        assert client.get("/api/students").json() == {"students": []}  # clients keep working, the picker stays empty
        assert client.get("/api/students/demo").status_code == 404
        assert client.put("/api/students/demo", json={"version": 1}).status_code == 404
        assert client.post("/api/students/demo/reset", json={"version": 1}).status_code == 404


def test_live_persona_session_has_no_learner_and_ignores_catalogue_selection(tmp_path, monkeypatch):
    from live_agent.orchestrator import Orchestrator

    received = []

    async def capture(self, utterance, **kwargs):
        received.append(utterance)
        await self.transport.send_json({"type": "received_for_test"})

    monkeypatch.setattr(Orchestrator, "on_user_utterance", capture)
    with TestClient(live_backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "student": "demo", "user_id": "live-user"})
            status = None
            while True:
                message = ws.receive()
                if "text" in message:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "status":
                        status = payload
                        break
            assert status["board"] is False and status["student"] is None and status["attention"] is False
            # a stray catalogue selection from a non-live client is ignored, not an error
            ws.send_json({"type": "text", "text": "聊点什么",
                          "lesson_context": {"subject": "数学", "grade": 1, "topic": "不存在的章节"}})
            while True:
                message = ws.receive()
                if "text" in message and json.loads(message["text"]).get("type") == "received_for_test":
                    break
            assert received[0].text == "聊点什么" and received[0].lesson_context is None


def test_a_live_persona_ignores_lesson_decisions():
    def llm(messages):
        if messages[0]["role"] != "system":  # the planner must never be called
            return json.dumps({"title": "不应出现的大纲", "sections": []}, ensure_ascii=False)
        return json.dumps({"relation": "new", "kind": "lesson", "topic": "光合作用",
                           "steps": [{"intent": "", "line": "好，我们来上一节课。"}]}, ensure_ascii=False)

    orch, client = tp.build(max_requests=6)
    orch.teaching = False
    orch.director.llm.fn = llm
    asyncio.run(tp.run(orch, client, [(1.0, "给我上一节光合作用的课")]))
    assert not tp.events(orch, EventType.LESSON) and orch.director.lesson_title == ""
    said = [e.data["transcript"] for e in tp.events(orch, EventType.LOCK) if e.data["transcript"]]
    assert "好，我们来上一节课。" in said  # the reply's own opening line still plays as speech


def test_a_live_persona_ignores_exercise_decisions():
    def llm(messages):
        return json.dumps({"relation": "new", "kind": "exercise", "topic": "加法",
                           "steps": [{"intent": "", "line": "我们来练一道。"}]}, ensure_ascii=False)

    orch, client = tp.build(max_requests=6)
    orch.teaching = False
    orch.director.llm.fn = llm
    asyncio.run(tp.run(orch, client, [(1.0, "给我出道练习题")]))
    assert orch.director.exercise is None and not tp.events(orch, EventType.LESSON)
