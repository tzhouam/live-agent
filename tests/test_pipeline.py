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
          correction=CorrectionMode.GRADIENT, max_requests=8, soft_switch=True):
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
                        log=EventLog(), cfg=OrchestratorConfig(correction_mode=correction, max_requests=max_requests,
                                                               soft_switch=soft_switch))
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
    # the retry is verified only after the 15 s action deadline (repair offset 2 with 5 s requests),
    # so by the preregistered rule the step has failed: no late "complied", no late "好了。"
    chain = next(iter(orch.director.chains.values()))
    assert chain.status.value == "failed"
    assert not events(orch, EventType.COMPLETION_CLAIM)


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
    orch, client = build(max_requests=6, soft_switch=False)  # hard cut (the erasure path, or opt-out)

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
                               "forget_term": "妹妹"})  # keyword names the fact, not its value
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


def test_public_session_persona_lines_carry_complete_lineage(tmp_path):
    from live_agent.memory_bridge import MemoryBridge

    def resp(messages):
        return json.dumps({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "欢迎来到直播间。"}]})

    orch, client = build(max_requests=6)
    orch.cfg.scope = "public"
    orch.director.llm = ScriptedLLM(resp)
    orch.memory = MemoryBridge(str(tmp_path / "m.sqlite"), user_id="u", stream_id="s", session_id="sess", mode="public")
    asyncio.run(run(orch, client, [(1.0, "大家好")]))
    refused = [e for e in events(orch, EventType.AUDIT) if "persona_line_not_recorded" in e.data.get("issues", [])]
    assert not refused, orch.memory.scope_violations


def test_erasure_confirmation_spoken_only_after_verified_erasure(tmp_path):
    from live_agent.memory_bridge import MemoryBridge

    def resp(messages):
        if "忘" in messages[-1]["content"]:
            return json.dumps({"relation": "chat", "kind": "memory", "forget_term": "妹妹",
                               "steps": [{"intent": "", "line": "好的，关于你妹妹的事我已经忘掉了。"}]})
        return json.dumps({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "嗯嗯。"}]})

    orch, client = build(max_requests=8)
    orch.director.llm = ScriptedLLM(resp)
    orch.memory = MemoryBridge(str(tmp_path / "m.sqlite"), user_id="u", stream_id="s", session_id="sess", mode="private")
    asyncio.run(run(orch, client, [(1.0, "我妹妹住在杭州"), (6.0, "忘掉我妹妹住哪")]))
    lines = [e.data.get("transcript", "") for e in events(orch, EventType.LOCK)]
    assert "好的，这件事我已经忘掉了。" in lines
    assert not any("妹妹" in x for x in lines)


def test_abstaining_qc_still_reaches_a_terminal_state_by_the_deadline():
    from live_agent.types import ChainStatus

    class Abstain:
        async def judge(self, q, chunks, k, t_evidence):
            from live_agent.types import Verdict, VerdictLabel
            return Verdict(q.qid, k, VerdictLabel.UNKNOWN, 0.0, "cannot tell", t_evidence, now())

    orch, client = build(max_requests=10)
    orch.judge = Abstain()
    asyncio.run(run(orch, client, [(1.0, "喝口茶")]))
    chain = next(iter(orch.director.chains.values()))
    assert chain.status == ChainStatus.FAILED  # expired by the step deadline, not left open


def test_silent_requests_are_muted_for_the_viewer():
    orch, client = build(max_requests=6)
    sent = []
    orig = client.send_chunk

    async def spy(ch, script):
        sent.append((bool(script.transcript), float(abs(ch.audio).max()) if ch.audio is not None else 0.0))
        await orig(ch, script)

    client.send_chunk = spy
    asyncio.run(run(orch, client, [(2.0, "喝口茶")]))
    assert any(not has_line for has_line, _ in sent)
    assert all(peak < 1e-6 for has_line, peak in sent if not has_line)  # silent requests reach the viewer muted
    assert any(peak > 0 for has_line, peak in sent if has_line)  # lines are untouched


def test_measured_delivery_replaces_the_transport_guess_in_lambda():
    from live_agent.generator.base import RequestTiming
    from live_agent.timeline import LockScheduler, SchedulerConfig

    s = LockScheduler(SchedulerConfig(delta_s=0.15, min_observations=3))
    for k in range(4):
        s.observe_timing(RequestTiming(k, t_lock=10.0 * k, t_first_chunk=10.0 * k + 2.4))
    assert abs(s.lambda_estimate() - (2.4 + 0.15)) < 1e-9  # nothing measured yet: the configured guess
    for d in (0.9, 1.0, 1.1, 1.6):  # a remote bridge
        s.observe_delivery(d)
    assert abs(s.lambda_estimate() - (2.4 + 1.6)) < 1e-9  # high quantile of the measured delivery
    s.observe_delivery(-1.0)  # clock glitches are ignored
    assert len(s._delivery) == 4


def test_a_comment_keeps_the_video_playing_until_the_reply_is_ready():
    orch, client = build(max_requests=8)  # soft switch (default)

    async def scenario():
        client.start()
        await orch.start()
        await asyncio.sleep(8 / SPEED)
        await orch.on_speech_start()
        t_comment = now()
        await asyncio.sleep(0.5 / SPEED)
        await orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="挥挥手", t_end=now()))
        try:
            await asyncio.wait_for(orch.wait_done(), timeout=20)
        finally:
            await orch.stop()
            client.close()
        return t_comment

    t_comment = asyncio.run(scenario())
    stops = events(orch, EventType.PLAYBACK_STOP)
    assert len(stops) == 1 and stops[0].data["soft"]  # one cut, at the switch, not at the comment
    target = stops[0].data["switch_to"]
    ready = min(e.t for e in events(orch, EventType.CHUNK_READY) if e.request_index == target and e.chunk_index == 0)
    assert stops[0].t >= ready - 1e-6 and stops[0].t > t_comment  # cut exactly when the reply became ready
    shown_between = [e for e in events(orch, EventType.CHUNK_PRESENTED) if t_comment < e.t < stops[0].t]
    assert shown_between  # the old video kept playing meanwhile (no freeze)
    lock = next(e for e in events(orch, EventType.LOCK) if e.request_index == target)
    assert "wave" in lock.data["action"]  # the switch target is the reply
    assert any(e.request_index == target for e in events(orch, EventType.CHUNK_PRESENTED))


def test_hosted_qwen_gets_the_top_level_thinking_switch_and_local_vllm_the_template_one():
    from types import SimpleNamespace

    from live_agent.llm import OpenAICompatLLM

    def fake(llm):
        seen = {}

        async def create(**kw):
            seen.update(kw)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])
        llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return seen

    hosted = OpenAICompatLLM("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-flash", api_key="k")
    seen = fake(hosted)
    asyncio.run(hosted.chat([{"role": "user", "content": "hi"}], json_mode=True))
    assert seen["extra_body"] == {"enable_thinking": False} and seen["response_format"] == {"type": "json_object"}
    local = OpenAICompatLLM("http://127.0.0.1:8101/v1", "qwen3-8b")
    seen = fake(local)
    asyncio.run(local.chat([{"role": "user", "content": "hi"}]))
    assert seen["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_anthropic_endpoint_gets_the_messages_api_with_system_on_top():
    import httpx

    from live_agent.llm import AnthropicCompatLLM, OpenAICompatLLM, make_chat_llm

    seen = {}

    def handler(request):
        seen["url"], seen["key"] = str(request.url), request.headers.get("x-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": '{"ok": true}'}]})

    llm = make_chat_llm("https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic", "m", api_key="k")
    assert isinstance(llm, AnthropicCompatLLM)
    llm._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = asyncio.run(llm.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], json_mode=True))
    assert out == '{"ok": true}' and seen["url"].endswith("/apps/anthropic/v1/messages") and seen["key"] == "k"
    assert seen["body"]["system"].startswith("S") and "JSON" in seen["body"]["system"]
    assert seen["body"]["messages"] == [{"role": "user", "content": "U"}]
    assert isinstance(make_chat_llm("http://127.0.0.1:8101/v1", "qwen3-8b"), OpenAICompatLLM)


def _slow_reply_run(holds: bool):
    orch, client = build(max_requests=10)
    orch.cfg.generator_holds = holds
    orch.cfg.restart_decision_wait_s = 1.5 / SPEED  # both waits at the simulation's time scale
    orch.cfg.switch_decision_wait_s = 10.0 / SPEED
    slow = orch.director.llm

    class SlowLLM:
        calls = slow.calls

        async def chat(self, messages, **kw):
            await asyncio.sleep(6.0 / SPEED)  # longer than a request
            return await slow.chat(messages, **kw)
    orch.director.llm = SlowLLM()

    async def scenario():
        client.start()
        await orch.start()
        await asyncio.sleep(8 / SPEED)
        await orch.on_speech_start()
        t_comment = now()
        await orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="挥挥手", t_end=now()))
        try:
            await asyncio.wait_for(orch.wait_done(), timeout=30)
        finally:
            await orch.stop()
            client.close()
        return t_comment

    t_comment = asyncio.run(scenario())
    decided = min(e.t for e in events(orch, EventType.UTTERANCE_END) if e.data.get("decision"))
    locks = [e for e in events(orch, EventType.LOCK) if e.t > t_comment]
    return [e for e in locks if e.t < decided], [e for e in locks if e.t >= decided]


def test_a_holding_generator_is_not_left_waiting_for_a_slow_reply():
    # seen live: vLLM-Omni holding for every prompt froze 8 s while the hosted LLM decided (the soft switch waited up
    # to 10 s for the decision, assuming the old video keeps playing, which it does not under a hold)
    before, after = _slow_reply_run(holds=True)
    assert before, "a request is locked while the reply is still being decided (no freeze)"
    assert all("wave" not in (e.data.get("action") or "") for e in before)  # listening, not the reply
    assert any("wave" in (e.data.get("action") or "") for e in after)  # the reply comes next
    before_free, _ = _slow_reply_run(holds=False)  # a generator that keeps playing: waiting for the reply is free
    assert not before_free


def _ready_switch_lock(blocked=None):
    orch, _ = build(max_requests=3)
    orch.next_lock = 1
    orch.sched.lock_time = lambda k: now() + 60  # a filler has a distant playback deadline
    orch.director.apply(Utterance('ready', 'user', '你好', now()),
                        {'relation': 'chat', 'kind': 'chat', 'steps': [{'intent': '', 'line': '你好呀。'}]})
    orch._switch_pending, orch._switch_target = True, None
    orch._switch_plan = orch.director.plan_version
    orch._decisions, orch._decisions_at_interrupt = 1, 0
    if blocked == 'holding': orch.cfg.generator_holds = True
    if blocked == 'undecided': orch._decisions = 0
    if blocked == 'target': orch._switch_target = 0
    if blocked == 'erasure': orch._ready.clear()
    if blocked == 'barge': orch._barge_gate.clear()
    submitted = []
    submitted_event = asyncio.Event()
    async def submit(k, prompt):
        submitted.append((k, prompt))
        submitted_event.set()
    orch.gen.submit = submit
    async def main():
        task = asyncio.create_task(orch._lock_loop())
        try:
            if blocked:
                await asyncio.sleep(.08)
                assert not submitted and not events(orch, EventType.LOCK)
            else:
                await asyncio.wait_for(submitted_event.wait(), timeout=1)
                await asyncio.sleep(.08)
                assert not task.done() and len(submitted) == 1  # subsequent locks return to JIT pacing
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(main())
    return orch, submitted


def test_ready_soft_switch_bypasses_filler_deadline_once():
    orch, submitted = _ready_switch_lock()
    assert len(submitted) == 1 and submitted[0][0] == 1
    assert extract_dialogue(submitted[0][1]) == '你好呀。'
    assert orch._switch_target == 1
    assert events(orch, EventType.LOCK)[0].data['lock_reason'] == 'ready_soft_switch'


@pytest.mark.parametrize('blocked', ['holding', 'undecided', 'target', 'erasure', 'barge'])
def test_ready_soft_switch_preserves_generation_and_input_gates(blocked):
    _ready_switch_lock(blocked)
