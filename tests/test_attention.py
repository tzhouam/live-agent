"""Opt-in camera focus check: smoothing of VLM verdicts and the teacher's nudge during a lesson."""

from __future__ import annotations

import asyncio
import json
import base64

import pytest

import test_pipeline as tp
from live_agent.attention import NUDGES, AttentionMonitor, check_frame
from live_agent.llm import ScriptedLLM
from live_agent.types import EventType, BlockScript
from live_agent.lesson import Board
from live_agent.director.director import Segment


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
    assert m.stable == "distracted" and m.run == 2
    m.update({"state": "distracted", "confidence": 0.3})  # not confident: ignored
    assert m.stable is None and m.run == 0  # uncertainty cannot reinforce an old verdict


def test_default_detector_confirms_a_change_on_the_second_observation_and_recovers():
    m = AttentionMonitor(vlm([]))
    def observe(state):return m.update({'state':state,'confidence':.9})
    assert observe('focused')=='focused'
    assert observe('distracted')=='focused' and m.run==0
    assert observe('focused')=='focused'  # a brief glance never becomes a confirmed episode
    assert observe('absent')=='focused' and m.run==0
    assert observe('absent')=='absent' and m.run==2
    assert observe('focused')=='absent' and m.run==0
    assert observe('focused')=='focused' and m.run==2


@pytest.mark.parametrize('confidence',[.1,float('nan'),float('inf'),2,'bad'])
def test_uncertain_or_invalid_observations_clear_stale_focus_without_counting_as_evidence(confidence):
    m=AttentionMonitor(vlm([]))
    m.update({'state':'focused','confidence':.9})
    assert m.update({'state':'distracted','confidence':confidence}) is None
    assert m.run==0
    assert m.update({'state':'distracted','confidence':.9}) is None
    assert m.update({'state':'distracted','confidence':.9})=='distracted'


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


def test_nudge_follows_the_second_confirmed_sample_during_an_ordinary_board_answer():
    orch=_orch(['distracted']*2)
    orch.director.queue.append(Segment(None,1,line='植物需要阳光。',board=Board('a','光合作用',['阳光'])))
    _run_checks(orch,1)
    assert len(orch.director.queue)==1
    _run_checks(orch,1)
    assert orch.director.queue[0].line==NUDGES['distracted'][0]
    assert orch.director.queue[1].line=='植物需要阳光。'


def test_no_nudge_interrupts_a_pending_action_or_listening_even_with_an_active_board():
    for action,listening in [(True,False),(False,True)]:
        orch=_orch(['distracted']*3)
        orch.scripts[0]=BlockScript(0,1,orch.director.ledger.canon,'','讲解。',board=Board('a','课程',['要点']).view(None))
        orch.director.listening=listening
        if action:orch.director.queue.append(Segment(None,1,intent='wave'))
        _run_checks(orch,3)
        assert not any(e.data.get('nudge') for e in tp.events(orch,EventType.ATTENTION))


def test_busy_detector_processes_the_latest_frame_without_a_backlog_or_parallel_calls():
    async def go():
        orch=_orch([])
        frames=[];started=asyncio.Event();release=asyncio.Event()
        class VLM:
            async def chat(self,messages,**kwargs):
                frame=base64.b64decode(messages[0]['content'][1]['image_url']['url'].split(',')[1])
                frames.append(frame)
                if len(frames)==1:started.set();await release.wait()
                return json.dumps({'state':'focused','confidence':.9})
        orch.attention=AttentionMonitor(VLM())
        orch.on_camera(b'first');await started.wait()
        orch.on_camera(b'obsolete');orch.on_camera(b'newest')
        assert frames==[b'first'] and orch._camera_pending==b'newest'
        release.set()
        while orch._aux:
            await asyncio.gather(*list(orch._aux))
            await asyncio.sleep(0)  # allow auxiliary cleanup callbacks to run
        assert frames==[b'first',b'newest'] and orch._camera_pending is None
        assert all('first' not in json.dumps(e.data) and 'newest' not in json.dumps(e.data)
                   for e in tp.events(orch,EventType.ATTENTION))
    asyncio.run(go())


def test_camera_off_cancels_work_and_reenable_does_not_publish_an_old_verdict():
    async def go():
        orch=_orch([]);started=asyncio.Event();cancelled=asyncio.Event()
        class VLM:
            async def chat(self,messages,**kwargs):
                if not cancelled.is_set():
                    started.set()
                    try:await asyncio.Event().wait()
                    finally:cancelled.set()
                return json.dumps({'state':'focused','confidence':.9})
        orch.attention=AttentionMonitor(VLM())
        orch.on_camera(b'old');await started.wait();orch.on_camera(b'queued')
        orch.camera_off();orch.on_camera(b'new')  # rapid re-enable before cancellation finishes
        while orch._aux:
            await asyncio.gather(*list(orch._aux),return_exceptions=True)
            await asyncio.sleep(0)
        assert cancelled.is_set() and orch._camera_pending is None
        events=tp.events(orch,EventType.ATTENTION)
        assert [e.data['state'] for e in events]==['off','focused']
    asyncio.run(go())


def test_reset_invalidates_an_in_flight_result_even_when_the_provider_finishes_normally():
    async def go():
        started,release=asyncio.Event(),asyncio.Event()
        class VLM:
            async def chat(self,*args,**kwargs):
                started.set();await release.wait()
                return json.dumps({'state':'distracted','confidence':.95})
        monitor=AttentionMonitor(VLM())
        task=asyncio.create_task(check_frame(monitor,b'jpeg'))
        await started.wait();monitor.reset();release.set()
        assert await task is None and monitor.stable is None and monitor.run==0 and not monitor.busy
    asyncio.run(go())


def test_the_hypotenuse_label_moves_to_the_longest_side():
    import numpy as np

    from live_agent.board_plot import fix_hypotenuse
    xy = np.array([[0, 0], [4, 0], [0, 3]], float)  # legs 4 and 3, hypotenuse from (4,0) to (0,3) = side 1
    assert fix_hypotenuse(xy, ["直角边a", "直角边b", "斜边c"]) == ["直角边a", "斜边c", "直角边b"]
    assert fix_hypotenuse(xy, ["a", "斜边c", "b"]) == ["a", "斜边c", "b"]
    assert fix_hypotenuse(np.array([[0, 0], [4, 0], [1, 3]], float), ["a", "b", "斜边"]) == ["a", "b", "斜边"]
