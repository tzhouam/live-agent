"""Opt-in camera focus check: smoothing of VLM verdicts and the teacher's nudge during a lesson."""

from __future__ import annotations

import asyncio
import json

import test_pipeline as tp
from live_agent.attention import NUDGES, AttentionMonitor
from live_agent.llm import ScriptedLLM
from live_agent.types import EventType


def vlm(states):
    it = iter(states)

    def reply(messages):
        s = next(it)
        return json.dumps({"state": s, "confidence": 0.9, "reason": "视线离开屏幕"}, ensure_ascii=False)
    return ScriptedLLM(reply)


def test_one_odd_frame_does_not_change_the_state():
    m = AttentionMonitor(vlm([]), window=3)
    for s in ["focused", "focused", "distracted"]:
        m.update({"state": s, "confidence": 0.9})
    assert m.stable == "focused"
    m.update({"state": "distracted", "confidence": 0.9})
    assert m.stable == "distracted" and m.run == 1
    m.update({"state": "distracted", "confidence": 0.3})  # not confident: ignored
    assert m.run == 2  # still distracted (majority unchanged), one more consecutive check


def _orch(states):
    orch, client = tp.build(max_requests=4)
    orch.attention = AttentionMonitor(vlm(states))
    return orch


def _run_checks(orch, n):
    async def go():
        for _ in range(n):
            await orch._attention_check(b"jpeg")
    asyncio.run(go())


def test_a_distracted_student_gets_a_nudge_during_a_lesson_then_a_cooldown():
    orch = _orch(["distracted"] * 6)
    orch.director.lesson_title = "光合作用"
    _run_checks(orch, 4)
    nudges = [e.data["nudge"] for e in tp.events(orch, EventType.ATTENTION) if e.data.get("nudge")]
    assert nudges == [NUDGES["distracted"][0]]  # after 2 consecutive checks, then the 45 s cooldown holds
    seg = orch.director.queue[0]
    assert seg.line == NUDGES["distracted"][0] and seg.gesture and seg.chain_id is None
    assert all("jpeg" not in json.dumps(e.data) for e in tp.events(orch, EventType.ATTENTION))  # no frame logged


def test_no_nudge_outside_a_lesson_or_when_focused():
    orch = _orch(["distracted"] * 3)
    _run_checks(orch, 3)  # no lesson running: just the state
    assert not any(e.data.get("nudge") for e in tp.events(orch, EventType.ATTENTION))
    orch2 = _orch(["focused"] * 3)
    orch2.director.lesson_title = "光合作用"
    _run_checks(orch2, 3)
    assert not any(e.data.get("nudge") for e in tp.events(orch2, EventType.ATTENTION))
    assert [e.data["stable"] for e in tp.events(orch2, EventType.ATTENTION)] == ["focused"] * 3
