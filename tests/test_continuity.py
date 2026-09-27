"""Scene continuity: prop inventory rendered from ledger state, action side effects (pending -> verified or
reverted), and the prop-count check on presented frames that queues corrections."""

from __future__ import annotations

import asyncio
import json

import test_pipeline as tp
from live_agent.capability import CapabilityManifest
from live_agent.ledger import StateLedger
from live_agent.types import EventType

HELD = "held open in both of her hands"
HOME = "open and lying flat on the desk in front of her"


def _ledger():
    return StateLedger.from_config(tp.CFG / "canon.json")


def test_inventory_is_rendered_from_state_and_effects_are_pending_until_verified():
    ledger = _ledger()
    pick = CapabilityManifest.load(tp.CFG / "capabilities.json").by_intent("pick_up_book")
    assert f"the book {HOME}" in ledger.inventory_sentence(1)
    ledger.expect(3, pick.side_effects)  # pick-up locked into request 3
    assert f"the book {HOME}" in ledger.inventory_sentence(3)  # request 3 itself starts from the old state
    assert f"the book {HELD}" in ledger.inventory_sentence(4)  # later requests start from its end state
    assert ledger.fill("she reads the book {book}", 4) == f"she reads the book {HELD}"
    assert ledger.props["book"].location == HOME  # nothing committed before verification
    ledger.revert(3)
    assert f"the book {HOME}" in ledger.inventory_sentence(4)
    ledger.expect(5, pick.side_effects)
    ledger.commit(5)
    assert ledger.props["book"].location == HELD and ledger.props["book"].carrier == "S1"


def test_guard_and_fixes_come_from_the_inventory():
    ledger = _ledger()
    assert "no second book" in ledger.duplicate_guard() and "no second teapot" in ledger.duplicate_guard()
    assert ledger.expected_counts()["书"] == 1
    fix = ledger.continuity_fix("书", 2, 7)
    assert "only one book" in fix and len(fix) <= 200
    assert "clearly visible" in ledger.continuity_fix("茶杯", 0, 7)
    assert ledger.continuity_fix("unknown", 2, 7) is None


def _responder(messages):
    text = messages[-1]["content"]
    if "拿起" in text:
        return json.dumps({"relation": "new", "kind": "action",
                           "steps": [{"intent": "pick_up_book", "line": "好，我把书拿起来。"}]})
    return tp.responder(messages)


def _run(p_by_phrase=None, counts=None, script=((2.0, "把书拿起来吧"),), max_requests=9):
    orch, client = tp.build(p_default=1.0, p_by_phrase=p_by_phrase, max_requests=max_requests)
    orch.director.llm.fn = _responder
    if counts is not None:
        async def count_props(chunks, labels):
            return counts
        orch.judge.count_props = count_props
    asyncio.run(tp.run(orch, client, list(script)))
    return orch


def _prompts(orch):
    return {e.request_index: e.data["prompt"] for e in tp.events(orch, EventType.LOCK)}


def test_a_verified_pick_up_changes_every_later_prompt():
    orch = _run()
    assert orch.director.ledger.props["book"].location == HELD
    prompts = _prompts(orch)
    last = prompts[max(prompts)]
    assert f"the book {HELD}" in last and f"the book {HOME}" not in last
    assert all("Exactly these objects are in the scene" in p for p in prompts.values())


def test_a_failed_pick_up_is_reverted():
    pick = CapabilityManifest.load(tp.CFG / "capabilities.json").by_intent("pick_up_book").phrase
    orch = _run(p_by_phrase={pick: 0.0})
    assert orch.director.ledger.props["book"].location == HOME
    assert not orch.director.ledger.pending or all(k >= max(_prompts(orch)) for k in orch.director.ledger.pending)


def test_a_duplicated_prop_on_every_frame_gets_a_correction_in_a_later_request():
    orch = _run(counts={"书": [2, 2, 2], "茶杯": [1, 1, 1]}, script=(), max_requests=16)
    ev = [e for e in tp.events(orch, EventType.CONTINUITY) if e.data.get("corrections")]
    assert ev and "书" in ev[0].data["wrong"] and "茶杯" not in ev[0].data["wrong"]
    target = ev[0].data["target"]
    prompts = _prompts(orch)
    assert target in prompts and "the extra book is gone" in prompts[target]
    fixes = [e.data["target"] for e in ev]
    assert all(b - a >= orch.cfg.continuity_cooldown for a, b in zip(fixes, fixes[1:]))  # rate-limited
    assert len(fixes) <= orch.cfg.continuity_max_fixes  # a drift the model never fixes is not repeated forever


def test_one_disagreeing_frame_is_not_evidence():
    orch = _run(counts={"书": [1, 2, 2]}, script=())
    assert not any(e.data.get("corrections") for e in tp.events(orch, EventType.CONTINUITY))


def test_the_anchor_shot_defines_the_scene_and_a_verified_action_brings_a_prop_back():
    ledger = _ledger()
    removed = ledger.anchor({"书": [1, 1, 1], "茶杯": [0, 0, 0], "团扇": [0, 1, 0]})
    assert removed == ["茶杯"]  # never drawn in any frame (the fan was seen once: kept)
    assert "teacup" not in ledger.inventory_sentence(2) and "no second teacup" not in ledger.duplicate_guard()
    assert "茶杯" not in ledger.expected_counts()
    ledger.record_request(5, "she lifts the teacup to her lips and clearly takes a sip", "")
    ledger.commit(5)  # verified tea: the cup is in the scene from now on
    assert "the teacup" in ledger.inventory_sentence(6) and ledger.expected_counts()["茶杯"] == 1


def test_anchor_removal_happens_once_and_missing_props_are_not_corrected():
    orch = _run(counts={"书": [1, 1, 1], "茶杯": [0, 0, 0]}, script=(), max_requests=12)
    ev = tp.events(orch, EventType.CONTINUITY)
    assert ev[0].data["anchor_removed"] == ["茶杯"] and not ev[0].data["corrections"]
    assert not any(e.data.get("corrections") for e in ev)
    assert all(e.data["anchor_removed"] == [] for e in ev[1:])
