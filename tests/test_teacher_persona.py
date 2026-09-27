"""The classroom teacher persona (configs/persona_teacher): question answering on the generic director."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director
from live_agent.ledger import StateLedger
from live_agent.llm import ScriptedLLM
from live_agent.prompt.h3_compiler import compile_prompt
from live_agent.types import Utterance, now

CFG = Path(__file__).resolve().parents[1] / "configs" / "persona_teacher"
ANSWER = {"relation": "chat", "target_chain": None, "kind": "content", "memory_note": None, "forget_term": None,
          "steps": [{"intent": "", "line": "因为阳光被空气散射了。"}, {"intent": "", "line": "蓝光波长短，最容易被散射。"},
                    {"intent": "", "line": "想想傍晚为什么是红色的？"}]}


def _director(reply):
    canon = json.loads((CFG / "canon.json").read_text(encoding="utf-8"))
    manifest = CapabilityManifest.load(CFG / "capabilities.json")
    manifest.min_status = Status.DOCUMENTED
    llm = ScriptedLLM(lambda messages: json.dumps(reply, ensure_ascii=False))
    intents = canon["intents"]
    d = Director(llm, manifest, StateLedger.from_config(CFG / "canon.json"), persona_name=canon["display_name"],
                 persona_bio=canon["persona_bio"], idle_intent=intents["idle"], listen_intent=intents["listen"],
                 speak_intent=intents["speak"], responder_style=canon["responder_style"],
                 responder_examples=canon["responder_examples"])
    return d, llm, manifest


def _ask(d, text):
    utt = Utterance(uid="u1", speaker="user", text=text, t_end=now())
    d.apply(utt, asyncio.run(d.decide(utt, None)))


def test_responder_gets_teaching_rules_and_the_teachers_own_examples():
    d, llm, _ = _director(ANSWER)
    _ask(d, "老师，为什么天空是蓝色的？")
    system = llm.calls[0][0]["content"]
    assert "教学规则" in system and "为什么天空是蓝色" in system
    assert "drink_tea" not in system  # no examples in another persona's intents
    assert "point_board" in system and "idle_teach" in system


def test_an_answer_is_spoken_over_requests_with_the_explaining_gesture():
    d, _, manifest = _director(ANSWER)
    _ask(d, "老师，为什么天空是蓝色的？")
    explain = manifest.by_intent("explain").phrase
    scripts = [d.next_script(k) for k in range(3)]
    assert [s.transcript for s in scripts] == [st["line"] for st in ANSWER["steps"]]
    assert all(s.action == explain for s in scripts)
    assert all(q.kind == "speech" for s in scripts for q in s.checks)  # a gesture is not a checked action
    for k, s in enumerate(scripts):
        p = compile_prompt(s, first_request=(k == 0))
        assert "gesturing naturally" in p and "chalkboard" in p and "the textbook open and lying on the lectern" in p


def test_requested_teaching_actions_are_checked_and_idle_is_the_lectern():
    d, _, _ = _director({"relation": "new", "target_chain": None, "kind": "action", "memory_note": None,
                         "forget_term": None, "steps": [{"intent": "point_board", "line": "好，我们看黑板这里。"}]})
    idle = d.next_script(0)
    assert "stands behind the lectern" in idle.action and "the textbook open and lying on the lectern" in idle.action
    _ask(d, "老师，指一下黑板")
    s = d.next_script(1)
    assert "points at the chalk drawing" in s.action and any(q.kind == "action" for q in s.checks)


def test_follow_up_questions_see_the_previous_exchange_and_erasure_removes_it():
    d, llm, _ = _director(ANSWER)
    _ask(d, "老师，为什么天空是蓝色的？")
    _ask(d, "我没听懂，能再讲一遍吗？")
    second = llm.calls[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[1]["content"] == "老师，为什么天空是蓝色的？" and "散射" in second[2]["content"]
    d.purge("天空")
    assert all("天空" not in t for _, t in d.dialogue)
