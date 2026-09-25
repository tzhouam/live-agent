"""End-to-end CPU tests: mock generator + scripted LLM + mock judge on a sped-up clock."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.mock import MockGenerator
from live_agent.ledger import StateLedger
from live_agent.llm import ScriptedLLM
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.prompt.h3_compiler import compile_prompt, extract_dialogue
from live_agent.qc.judge import MockJudge
from live_agent.sim import SimClient
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import EventType, Utterance, now

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "configs" / "persona_hanfu"
SPEED = 25.0


def responder(messages):
    text = messages[-1]["content"]
    if "喝" in text and "茶" in text:
        return json.dumps({"relation": "new", "target_chain": None, "kind": "action",
                           "steps": [{"intent": "drink_tea", "line": "好，我喝口茶。"}], "memory_note": None})
    if "挥" in text:
        return json.dumps({"relation": "new", "kind": "action", "steps": [{"intent": "wave", "line": ""}]})
    if "飞" in text:
        return json.dumps({"relation": "new", "kind": "action", "steps": [{"intent": "fly", "line": "好的"}]})
    return json.dumps({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "你好呀，今天想聊什么？"}]})


def build(p_default=1.0, p_by_phrase=None, boost=0.3, mode=DirectorMode.CLOSED_LOOP,
          correction=CorrectionMode.GRADIENT, max_requests=8):
    manifest = CapabilityManifest.load(CFG / "capabilities.json")
    manifest.min_status = Status.DOCUMENTED  # dev override: nothing is executed yet in CI
    ledger = StateLedger.from_config(CFG / "canon.json")
    canon = json.loads((CFG / "canon.json").read_text(encoding="utf-8"))
    director = Director(ScriptedLLM(responder), manifest, ledger, persona_name=canon["display_name"],
                        persona_bio=canon["persona_bio"], mode=mode)
    gen = MockGenerator(teacher_s=1.0, chunk_s=0.5, speed=SPEED)
    sched = LockScheduler(SchedulerConfig(request_s=5.0 / SPEED, sigma_s=0.5 / SPEED, delta_s=0.01,
                                          lambda_prior_s=3.0 / SPEED, time_scale=1.0 / SPEED))
    client = SimClient(speed=SPEED)
    orch = Orchestrator(gen, director, sched, client,
                        judge=MockJudge(p_default=p_default, p_by_phrase=p_by_phrase or {}, correction_boost=boost),
                        log=EventLog(), cfg=OrchestratorConfig(correction_mode=correction, max_requests=max_requests))
    client.orchestrator = orch
    return orch, client


async def run(orch, client, script):
    client.start()
    await orch.start()
    for delay, text in script:
        await asyncio.sleep(delay / SPEED)
        await orch.on_user_utterance(Utterance(uid=f"u{delay}", speaker="user", text=text, t_end=now()))
    try:
        await asyncio.wait_for(orch.wait_done(), timeout=20)
    finally:
        await orch.stop()
        client.close()


def events(orch, type_):
    return [e for e in orch.log.events if e.type == type_]


def test_compiler_matches_official_format():
    ledger = StateLedger.from_config(CFG / "canon.json")
    from live_agent.types import BlockScript
    s = BlockScript(request_index=3, plan_version=1, canon=ledger.canon,
                    action="she lifts the teacup and takes one sip", transcript="好，我喝口茶。")
    p = compile_prompt(s)
    assert p.startswith("integrated_multimodal_description: [Shot 1] ")
    assert "\n\noverall_soundscape: Clear dry Mandarin speech" in p
    assert p.endswith("non_diegetic_music: N/A")
    assert "<d>[Chinese] 好，我喝口茶。</d>" in p
    assert extract_dialogue(p) == "好，我喝口茶。"
    assert ledger.canon.subject in p  # canon copied verbatim


def test_action_verified_then_completion_claim():
    orch, client = build(p_default=1.0)
    asyncio.run(run(orch, client, [(2.0, "喝口茶吧")]))
    chains = orch.director.chains
    assert len(chains) == 1
    chain = next(iter(chains.values()))
    assert chain.status.value == "complied"
    claims = events(orch, EventType.COMPLETION_CLAIM)
    locks = {e.request_index: e for e in events(orch, EventType.LOCK)}
    # completion remark is only locked *after* the verifying verdict
    verdict_t = min(e.t for e in events(orch, EventType.VERDICT) if e.data.get("label") == "complied")
    assert claims and all(locks[c.request_index].t >= verdict_t for c in claims)


def test_failed_action_gets_forward_correction():
    orch, client = build(p_default=1.0, p_by_phrase={"teacup": 0.0}, boost=1.0, max_requests=10)
    asyncio.run(run(orch, client, [(2.0, "喝口茶")]))
    repairs = events(orch, EventType.REPAIR)
    assert repairs, "a failed check must trigger a repair"
    retry_locks = [e for e in events(orch, EventType.LOCK)
                   if any("clearly and visibly" in c for c in e.data.get("corrections", []))]
    assert retry_locks, "the retried request carries the forward correction"
    assert retry_locks[0].request_index >= repairs[0].data["next_unlocked"]
    assert next(iter(orch.director.chains.values())).status.value == "complied"


def test_unsupported_action_is_refused():
    orch, client = build()
    asyncio.run(run(orch, client, [(2.0, "你飞起来")]))
    chain = next(iter(orch.director.chains.values()))
    assert chain.status.value == "refused"
    assert events(orch, EventType.REFUSAL)


def test_jit_locks_follow_presentation():
    orch, client = build(max_requests=8)
    asyncio.run(run(orch, client, []))
    lock_ev = {e.request_index: e for e in events(orch, EventType.LOCK) if "lambda_est" in e.data}
    R = orch.sched.cfg.request_s
    checked = 0
    for k in range(1, 8):
        v_prev = orch.sched.presented_start.get(k - 1)
        if v_prev is None or k not in lock_ev:
            continue
        ev = lock_ev[k]
        # JIT: never lock before V_{k-1} + R - Lambda - sigma (Lambda = estimate in force at the lock)
        assert ev.t >= v_prev + R - ev.data["lambda_est"] - orch.sched.cfg.sigma_s - 0.01
        checked += 1
    assert checked >= 5
    assert not client.stalls or max(s.t_end - s.t_start for s in client.stalls) < R


def test_barge_in_drops_queued_and_marks_unshown():
    orch, client = build(max_requests=6)

    async def scenario():
        client.start()
        await orch.start()
        await asyncio.sleep(8 / SPEED)
        await orch.on_speech_start()
        await asyncio.sleep(1 / SPEED)
        await orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="挥挥手", t_end=now()))
        try:
            await asyncio.wait_for(orch.wait_done(), timeout=20)
        finally:
            await orch.stop()
            client.close()

    asyncio.run(scenario())
    assert events(orch, EventType.PLAYBACK_STOP)
    assert orch.director.plan_version >= 2


def test_open_loop_has_no_checks():
    orch, client = build(mode=DirectorMode.OPEN_LOOP)
    asyncio.run(run(orch, client, [(2.0, "喝口茶")]))
    assert all(not e.data.get("checks") for e in events(orch, EventType.LOCK))
    assert not events(orch, EventType.VERDICT)


def test_erasure_acks_all_targets_and_redacts_log(tmp_path):
    from live_agent.memory_bridge import MemoryBridge

    def resp(messages):
        text = messages[-1]["content"]
        if "忘" in text:
            return json.dumps({"relation": "chat", "kind": "memory", "steps": [{"intent": "", "line": "好的，忘掉了。"}],
                               "forget_term": "杭州"})
        return json.dumps({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "杭州很美。"}],
                           "memory_note": "用户的妹妹住在杭州"})

    orch, client = build(max_requests=8)
    orch.director.llm = ScriptedLLM(resp)
    orch.memory = MemoryBridge(str(tmp_path / "m.sqlite"), user_id="u", stream_id="s", session_id="sess", mode="private")
    orch.log = EventLog(tmp_path / "log.jsonl")
    asyncio.run(run(orch, client, [(1.0, "我妹妹住在杭州"), (6.0, "忘掉我妹妹住哪")]))
    stops = [e for e in events(orch, EventType.PLAYBACK_STOP) if e.data.get("erasure")]
    assert stops and stops[0].data["erasure_complete"], stops[0].data
    assert "杭州" not in (tmp_path / "log.jsonl").read_text(encoding="utf-8")
