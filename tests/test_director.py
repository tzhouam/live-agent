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
