"""Runner -> SCHEMA.md log -> scoring, on the mock stack with a scripted responder."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from live_agent.eval.runner import mock_factory, run_task
from live_agent.eval.schema import load_session
from live_agent.eval.scoring import score_session
from live_agent.eval.tasks import load_suite
from live_agent.llm import ScriptedLLM

ROOT = Path(__file__).resolve().parents[1]


def responder(messages):
    text = messages[-1]["content"]
    table = {"茶": "drink_tea", "翻": "turn_page", "挥": "wave", "点头": "nod"}
    for k, intent in table.items():
        if k in text:
            return json.dumps({"relation": "new", "kind": "action",
                               "steps": [{"intent": intent, "line": "好的。"}]})
    return json.dumps({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "嗯。"}]})


def test_runner_produces_scorable_logs(tmp_path):
    tasks = {t.task_id: t for t in load_suite(ROOT / "eval/tasks/e2_committed.jsonl")}
    task = tasks["E2-A01"]  # 喝茶
    factory = mock_factory(ROOT / "configs/persona_hanfu", speed=20.0, llm=ScriptedLLM(responder), p_default=1.0)
    path = asyncio.run(run_task(task, "A2", 0, factory=factory, speed=20.0, out_dir=tmp_path))
    session = load_session(path)
    score = score_session(session)
    outcomes = [c.outcome.value for c in score.chains]
    assert outcomes == ["success"], outcomes
    types = {e["type"] for e in session.events}
    assert {"utterance", "chain_annotation", "lock", "chunk_presented", "verdict"} <= types


def test_open_loop_has_no_judge_verdicts(tmp_path):
    tasks = {t.task_id: t for t in load_suite(ROOT / "eval/tasks/e2_committed.jsonl")}
    factory = mock_factory(ROOT / "configs/persona_hanfu", speed=20.0, llm=ScriptedLLM(responder), p_default=1.0)
    path = asyncio.run(run_task(tasks["E2-A01"], "A1", 0, factory=factory, speed=20.0, out_dir=tmp_path))
    session = load_session(path)
    assert not session.of_type("verdict")  # A1 is scored only by independent (human) adjudication
