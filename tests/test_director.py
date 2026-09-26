"""Director / scheduler / orchestrator rules added after Codex impl1 (docs/reviews/impl1_review.md)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import RequestTiming
from live_agent.ledger import StateLedger
from live_agent.llm import ScriptedLLM
from live_agent.timeline import LockScheduler, SchedulerConfig
from live_agent.types import ChainStatus, Utterance

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "configs" / "persona_hanfu"


def make(reply: dict | None = None, mode=DirectorMode.CLOSED_LOOP, replies: list[dict] | None = None):
    queue = list(replies or [])

    def fn(messages):
        return json.dumps(queue.pop(0) if queue else reply)

    manifest = CapabilityManifest.load(CFG / "capabilities.json")
    manifest.min_status = Status.DOCUMENTED
    canon = json.loads((CFG / "canon.json").read_text(encoding="utf-8"))
    return Director(ScriptedLLM(fn), manifest, StateLedger.from_config(CFG / "canon.json"),
                    persona_name=canon["display_name"], persona_bio=canon["persona_bio"], mode=mode)


def say(d: Director, text: str, uid: str = "u1", t: float = 0.0):
    return asyncio.run(d.on_user_utterance(Utterance(uid, "user", text, t)))


TEA = {"relation": "new", "kind": "action", "steps": [{"intent": "drink_tea", "line": "好，我喝口茶。"}]}
MULTI = {"relation": "new", "kind": "multistep", "steps": [
    {"intent": "drink_tea", "line": "先喝茶。"}, {"intent": "turn_page", "line": "再翻页。"},
    {"intent": "", "line": "这一页讲的是春天。"}]}


def test_multistep_releases_next_step_only_after_verification():
    d = make(MULTI)
    say(d, "先喝茶再翻页然后讲讲")
    chain = next(iter(d.chains.values()))
    s0 = d.next_script(0)
    assert s0.provenance["step"] == 0 and "teacup" in s0.action
    idle = d.next_script(1)  # step 1 is held until step 0 is verified
    assert not idle.chain_ids
    assert not d.on_verified(chain.chain_id, "turn_page", 0, 1.0, revision=0, step=1)  # wrong step
    assert d.on_verified(chain.chain_id, "drink_tea", 0, 1.0, revision=0, step=0)
    s1 = d.next_script(2)
    assert s1.provenance["step"] == 1
    assert d.on_verified(chain.chain_id, "turn_page", 2, 2.0, revision=0, step=1)
    s2 = d.next_script(3)
    assert s2.provenance["step"] == 2 and "春天" in s2.transcript  # trailing content released
    remark = d.next_script(4)
    assert remark.provenance["completion_remark"] and chain.status == ChainStatus.COMPLIED


def test_stale_verdict_from_superseded_revision_is_ignored():
    rev = {"relation": "revision", "target_chain": None, "kind": "action", "steps": [{"intent": "wave", "line": "好，挥挥手。"}]}
    d = make(replies=[TEA])
    say(d, "喝口茶", "u1")
    chain = next(iter(d.chains.values()))
    d.next_script(0)  # tea locked under revision 0
    rev["target_chain"] = chain.chain_id
    d.llm = ScriptedLLM(lambda m: json.dumps(rev))
    say(d, "不对，挥挥手", "u2", 1.0)
    assert len(chain.revisions) == 1
    assert not d.on_verified(chain.chain_id, "drink_tea", 0, 2.0, revision=0)  # late tea verdict
    assert chain.status == ChainStatus.OPEN
    assert not d.queue_retry(chain.chain_id, "drink_tea", correction="x", failed_request=0, revision=0)


def test_newer_instruction_capacity_skips_unexecuted_one():
    wave = {"relation": "new", "kind": "action", "steps": [{"intent": "wave", "line": "好。"}]}
    d = make(replies=[TEA, wave])
    say(d, "喝口茶", "u1")
    say(d, "挥挥手", "u2", 0.5)  # tea never locked -> skipped by admission control
    tea, wav = list(d.chains.values())
    assert tea.status == ChainStatus.CAPACITY_SKIPPED and wav.status == ChainStatus.OPEN
    assert d.events.capacity_skips == [(tea.chain_id, 0)]


def test_chat_does_not_displace_instruction():
    chat = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "今天天气不错。"}]}
    d = make(replies=[TEA, chat])
    say(d, "喝口茶", "u1")
    say(d, "天气真好", "u2", 0.5)
    tea = next(iter(d.chains.values()))
    assert tea.status == ChainStatus.OPEN
    assert not d.next_script(0).chain_ids  # chat reply first
    assert d.next_script(1).chain_ids == [tea.chain_id]


def test_unsupported_action_with_empty_intent_is_logged_refusal():
    d = make({"relation": "new", "kind": "action", "steps": [{"intent": "", "line": "我飞不起来呀。"}]})
    say(d, "你飞起来")
    chain = next(iter(d.chains.values()))
    assert chain.status == ChainStatus.REFUSED and d.events.refusals


def test_narration_guard_removes_unverified_completion_claim():
    d = make({"relation": "new", "kind": "action", "steps": [{"intent": "drink_tea", "line": "好的，我喝完了。"}]})
    say(d, "喝口茶")
    s = d.next_script(0)
    assert "喝完" not in s.transcript and d.events.narration_guards
    assert not d.events.completion_claims


def test_retry_waits_for_reserved_request():
    d = make(TEA)
    say(d, "喝口茶")
    chain = next(iter(d.chains.values()))
    d.next_script(0)
    assert d.queue_retry(chain.chain_id, "drink_tea", correction="clearly", failed_request=0,
                         revision=0, min_request=3)
    assert not d.next_script(2).chain_ids
    assert d.next_script(3).chain_ids == [chain.chain_id]


def test_purge_removes_term_from_controller_state():
    d = make({"relation": "new", "kind": "content", "steps": [{"intent": "", "line": "你妹妹住在杭州。"}]})
    say(d, "说说我妹妹住在杭州的事")
    d.ledger.record_request(0, "", "你妹妹住在杭州")
    d.purge("杭州")
    assert all("杭州" not in s.line for s in d.queue)
    assert all("杭州" not in c.final_intent for c in d.chains.values())
    assert all("杭州" not in r.transcript for r in d.ledger.history)


def test_open_loop_uses_llm_action_phrase_without_manifest():
    d = make({"relation": "new", "kind": "action", "steps": [{"action": "she flies up to the ceiling", "line": "好呀"}]},
             mode=DirectorMode.OPEN_LOOP)
    say(d, "你飞起来")
    s = d.next_script(0)
    assert s.action == "she flies up to the ceiling" and not s.checks and not s.capability_ids


def test_lambda_excludes_kv_wait():
    sch = LockScheduler(SchedulerConfig(min_observations=1, delta_s=0.0, lambda_quantile=1.0))
    # request 1 was locked at 0 but could only start after request 0 finished at 3.0
    sch.observe_timing(RequestTiming(0, t_lock=-5.0, t_first_chunk=-3.5, t_done=3.0))
    sch.observe_timing(RequestTiming(1, t_lock=0.0, t_first_chunk=4.5, t_done=8.0))
    assert abs(max(sch.effective_leads()) - 1.5) < 1e-9  # not 4.5


def test_timeline_restarts_after_interruption():
    from live_agent.types import now

    sch = LockScheduler(SchedulerConfig())
    sch.on_presented(0, now() - 1.0)
    sch.on_presented(1, now())  # requests 2, 3 locked, then dropped by a barge-in
    sch.interrupt(4)
    assert sch.lock_time(4) <= now()  # the replacement locks immediately
    assert sch.lock_time(5) is None  # then waits for V_4, not for the dropped requests


def test_cut_step_is_capacity_skipped_by_newer_instruction_or_resumed_after_chat():
    wave = {"relation": "new", "kind": "action", "steps": [{"intent": "wave", "line": "好。"}]}
    chat = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "嗯？"}]}
    # newer instruction -> skip
    d = make(replies=[TEA, wave])
    say(d, "喝口茶", "u1")
    s = d.next_script(0)
    d.on_interrupted([s])
    say(d, "挥挥手", "u2", 1.0)
    tea = next(iter(d.chains.values()))
    assert tea.status == ChainStatus.CAPACITY_SKIPPED
    # chat -> the cut step is re-queued
    d = make(replies=[TEA, chat])
    say(d, "喝口茶", "u1")
    s = d.next_script(0)
    d.on_interrupted([s])
    say(d, "嗯", "u2", 1.0)
    d.next_script(1)  # chat line first
    again = d.next_script(2)
    assert again.chain_ids == s.chain_ids and "teacup" in again.action


def test_open_loop_chains_close_when_presented():
    d = make({"relation": "new", "kind": "action", "steps": [{"action": "she waves", "line": "好"}]},
             mode=DirectorMode.OPEN_LOOP)
    say(d, "挥挥手")
    s = d.next_script(0)
    d.on_request_presented(s, done=set())  # locked but not fully presented: stays open
    assert next(iter(d.chains.values())).status == ChainStatus.OPEN
    d.on_request_presented(s, done={0})
    assert next(iter(d.chains.values())).status == ChainStatus.PRESENTED
    assert not d._open_chains()


def test_completion_guard_catches_ordinary_claims():
    from live_agent.director.director import _claims_completion

    for line in ["我把茶喝了。", "刚才那首歌你喜欢吗", "我已经翻好了", "挥完了"]:
        assert _claims_completion(line), line
    for line in ["好，我喝口茶。", "我来翻一页。", "你想喝了吗"]:
        assert not _claims_completion(line), line


def test_repeat_arm_retry_carries_original_line():
    d = make(TEA)
    say(d, "喝口茶")
    chain = next(iter(d.chains.values()))
    s0 = d.next_script(0)
    assert d.queue_retry(chain.chain_id, "drink_tea", correction="", failed_request=0, revision=0,
                         line=s0.transcript)
    again = d.next_script(1)
    assert again.transcript == s0.transcript and again.action == s0.action


def test_old_plan_segments_wait_for_the_new_decision_after_barge_in():
    wave = {"relation": "new", "kind": "action", "steps": [{"intent": "wave", "line": "好。"}]}
    d = make(replies=[TEA, wave])
    say(d, "喝口茶", "u1")
    d.on_barge_in()
    filler = d.next_script(0)  # decision not yet applied: no old-plan segment, only listening
    assert not filler.chain_ids and "listening" in filler.action
    say(d, "挥挥手", "u2", 1.0)
    assert "waves" in d.next_script(1).action


def test_barge_in_cannot_release_the_erasure_gate():
    import asyncio as aio

    from live_agent.generator.mock import MockGenerator
    from live_agent.orchestrator import Orchestrator
    from live_agent.sim import SimClient

    async def main():
        orch = Orchestrator(MockGenerator(speed=50.0), make(TEA), LockScheduler(), SimClient(speed=50.0))
        orch._ready.clear()  # an erasure holds its gate
        await orch.on_speech_start()
        return orch._ready.is_set(), orch._barge_gate.is_set()

    erasure_gate, barge_gate = aio.run(main())
    assert not erasure_gate and barge_gate


def test_degraded_or_refused_action_speaks_the_decision_not_the_acceptance():
    d = make(TEA)
    say(d, "喝口茶")
    d.manifest.min_status = Status.CALIBRATED  # drink_tea is only documented -> refused at compile
    s = d.next_script(0)
    assert s.transcript != "好，我喝口茶。" and not s.action


def test_action_lines_use_intent_wording_only():
    d = make({"relation": "new", "kind": "action", "steps": [{"intent": "drink_tea", "line": "茶我喝光啦"}]})
    say(d, "喝口茶")
    assert d.next_script(0).transcript == "好的。"


def test_completion_remark_deferred_while_barge_in_decision_pending():
    wave = {"relation": "new", "kind": "action", "steps": [{"intent": "wave", "line": "好。"}]}
    d = make(replies=[TEA, wave])
    say(d, "喝口茶", "u1")
    tea = next(iter(d.chains.values()))
    d.next_script(0)
    d.on_barge_in()
    assert d.on_verified(tea.chain_id, "drink_tea", 0, 1.0, revision=0)
    assert not any(x.is_completion_remark for x in d.queue)  # held while the decision is pending
    say(d, "挥挥手", "u2", 2.0)
    assert tea.status == ChainStatus.COMPLIED  # verification applied...
    assert not any(x.is_completion_remark for x in d.queue)  # ...but a new instruction drops the old "好了。"
    chat = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "嗯？"}]}
    d2 = make(replies=[TEA, chat])
    say(d2, "喝口茶", "u1")
    tea2 = next(iter(d2.chains.values()))
    d2.next_script(0)
    d2.on_barge_in()
    d2.on_verified(tea2.chain_id, "drink_tea", 0, 1.0, revision=0)
    say(d2, "嗯", "u2", 2.0)
    assert any(x.is_completion_remark for x in d2.queue)  # after chat the remark is released


def test_validate_refusal_never_speaks_acceptance():
    d = make({"relation": "new", "kind": "action", "steps": [{"intent": "fly", "line": "好，我飞起来！"}]})
    say(d, "你飞起来")
    s = d.next_script(0)
    assert "飞起来" not in s.transcript and "做不到" in s.transcript


def test_completion_guard_covers_chat_lines():
    d = make({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "茶被我喝净了，你呢？"}]})
    say(d, "你喝茶了吗")
    s = d.next_script(0)
    assert "喝净" not in s.transcript and d.events.narration_guards


def test_verification_during_pending_decision_keeps_chain_revisable():
    rev = {"relation": "revision", "target_chain": None, "kind": "action", "steps": [{"intent": "wave", "line": "好。"}]}
    d = make(replies=[TEA])
    say(d, "喝口茶", "u1")
    tea = next(iter(d.chains.values()))
    d.next_script(0)
    d.on_barge_in()
    d.on_verified(tea.chain_id, "drink_tea", 0, 1.0, revision=0)
    assert tea.status == ChainStatus.OPEN and tea in d._open_chains()  # still revisable
    rev["target_chain"] = tea.chain_id
    d.llm = ScriptedLLM(lambda m: json.dumps(rev))
    say(d, "不对，挥挥手", "u2", 2.0)
    assert tea.status == ChainStatus.OPEN and len(tea.revisions) == 1  # stale verification dropped
    assert not any(x.is_completion_remark for x in d.queue)


def test_partially_shown_request_is_not_claimed_unsaid():
    d = make(TEA)
    d.ledger.record_request(3, "she lifts the teacup", "好，我喝口茶。")
    d.ledger.mark_generated_not_presented(3, partially_shown=True)
    note = d.ledger.bridging_note()
    assert "did not say" not in note and "mid-way" in note


def test_expired_step_fails_without_late_transitions():
    d = make(MULTI)
    say(d, "先喝茶再翻页然后讲讲")
    chain = next(iter(d.chains.values()))
    d.next_script(0)
    d.expire(chain.chain_id, 0)
    assert chain.status == ChainStatus.FAILED
    assert not d.on_verified(chain.chain_id, "drink_tea", 0, 99.0, revision=0, step=0)  # no late release
    assert not d.held.get(chain.chain_id)
