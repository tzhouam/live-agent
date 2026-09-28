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


def test_nudges_are_capped_per_episode_and_reset_when_the_student_returns():
    orch = _orch(["absent"] * 4 + ["focused"] * 3 + ["absent"] * 3)
    orch.director.lesson_title = "光合作用"
    orch.cfg.attention_cooldown_s = 0.0  # isolate the per-episode cap from the cooldown
    _run_checks(orch, 7)
    orch.director.queue.clear()  # the first nudge was spoken (nothing locks requests in this test)
    _run_checks(orch, 3)
    nudges = [e.data["nudge"] for e in tp.events(orch, EventType.ATTENTION) if e.data.get("nudge")]
    assert nudges == [NUDGES["absent"][0]] * 2  # once per absence, again after the student came back and left


def test_the_hypotenuse_label_moves_to_the_longest_side():
    import numpy as np

    from live_agent.board_plot import fix_hypotenuse
    xy = np.array([[0, 0], [4, 0], [0, 3]], float)  # legs 4 and 3, hypotenuse from (4,0) to (0,3) = side 1
    assert fix_hypotenuse(xy, ["直角边a", "直角边b", "斜边c"]) == ["直角边a", "斜边c", "直角边b"]
    assert fix_hypotenuse(xy, ["a", "斜边c", "b"]) == ["a", "斜边c", "b"]
    assert fix_hypotenuse(np.array([[0, 0], [4, 0], [1, 3]], float), ["a", "b", "斜边"]) == ["a", "b", "斜边"]
