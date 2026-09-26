"""Online director (proposal §8.2 layers 1-2, §9, §10).

Responsibilities
- Interpret each user utterance with the responder LLM: new intent chain, revision of
  an open chain, withdrawal, or chat. The plan is a queue of *segments* (one per 5-s request:
  an action intent and at most ~5 s of speech).
- Admission control (§4): at most one unexecuted instruction. A newer instruction supersedes
  an older unexecuted one, which is logged as a *capacity skip* (distinct from the user's own
  revision / withdrawal, which only touch the chain they target).
- Multistep chains are released step by step: step i+1 is queued only after step i was verified.
- Verdicts and retries are bound to (chain, revision, step): a late verdict about a superseded
  intent or another step is ignored.
- At each lock, build the BlockScript for the next request: canon from the ledger (verbatim),
  action via the capability manifest (emit / degrade / refuse), pending forward corrections,
  compile-time check questions. Repairs are reserved for their earliest correctable request.
- Narration policy: completion is voiced only after QC verified the action on presented
  frames; completion wording in LLM lines is removed in code (not only by the prompt).

Modes: ``closed_loop`` (A2) and ``open_loop`` (A1 comparator, proposal §7.2: the LLM writes the
next request's prompt directly — a free visible-action phrase and the line; no manifest, no
ledger context, no QC, no corrections, no narration guard, no step gating). Both modes share
the generator, canon compiler, LLM, memory and presentation path.
"""

from __future__ import annotations

import enum
import re
from collections import deque
from dataclasses import dataclass, field

from live_agent.capability import CapabilityManifest, Decision
from live_agent.ledger import StateLedger
from live_agent.llm import ChatLLM, parse_json
from live_agent.types import (BlockScript, ChainStatus, CheckQuestion, IntentChain, TaskKind,
                              Utterance, new_id)

CHARS_PER_REQUEST = 22  # ~4.5 Chinese characters/s x 5 s [estimate; calibrate in E1]


class DirectorMode(str, enum.Enum):
    CLOSED_LOOP = "closed_loop"  # A2
    OPEN_LOOP = "open_loop"  # A1


@dataclass
class Segment:
    chain_id: str | None
    plan_version: int
    intent: str = ""  # capability intent (closed loop)
    line: str = ""
    step: int | None = None
    is_completion_remark: bool = False
    correction: str = ""  # forward correction attached to a retried action
    retry_of: int | None = None  # request index whose check failed
    revision: int | None = None  # chain revision count this segment was planned under
    action_text: str = ""  # open loop: the LLM's own visible-action phrase
    min_request: int = 0  # reserved slot: do not lock before this request index
    memory_ids: list[str] | None = None  # memories the responder saw when writing this line (None = unknown)
    recall_id: str | None = None  # memory recall token for that decision (lineage computed by the bridge)


@dataclass
class DirectorEvents:
    """Things the orchestrator must log (consumed by the eval schema)."""

    refusals: list[tuple[str, str]] = field(default_factory=list)  # (chain_id, reason)
    degradations: list[tuple[str, str]] = field(default_factory=list)
    completion_claims: list[tuple[str, int, int | None]] = field(default_factory=list)  # (chain, request, step)
    capacity_skips: list[tuple[str, int]] = field(default_factory=list)  # (chain_id, revision)
    narration_guards: list[tuple[str, str]] = field(default_factory=list)  # (original, cleaned)


RESPONDER_SYSTEM = """你是直播数字人「{name}」的应答大脑。人设：{bio}
人设能做的动作只有这些 intent：{intents}。
输出一个 JSON 对象（不要输出任何其他文字），字段：
- "relation": "new"（用户提出新的要求）| "revision"（用户改口、纠正尚未完成的要求）| "withdrawal"（用户取消尚未完成的要求）| "chat"（闲聊、提问、陈述）
- "target_chain": relation 为 revision/withdrawal 时，被修改的链 id（从下面的未完成链中选）；否则 null
- "kind": "action"（要求做一个动作）| "multistep"（按顺序做多个动作）| "content"（讲解、唱歌、回答知识问题）| "memory"（要求记住或忘记某事）| "chat"
- "steps": [{{"intent": ..., "line": ...}}]，按顺序执行
- "memory_note": 用户陈述了关于**他自己**的事实时，用第三人称写成一句（如「用户的妹妹住在杭州」）；否则 null
- "forget_term": 用户要求忘记某事时，写出关键词；否则 null
规则：
1. 只有当用户**明确要求人设做动作**时（kind 为 action 或 multistep），steps 里才写动作 intent；其他情况 intent 一律写 ""。
2. 用户要求的动作不在上面的列表里时，intent 写 ""，并在 line 里礼貌说明做不到。
3. 每个 line 不超过 {chars} 个汉字；长回答拆成多个 step。
4. 只说意图（「好，我喝口茶」），不说已经完成（不说「我喝完了」）。
5. 称呼用户用「你」。绝不把用户说的关于他自己的事说成是人设自己的事。
示例：
用户：喝口茶吧 → {{"relation":"new","target_chain":null,"kind":"action","steps":[{{"intent":"drink_tea","line":"好，我喝口茶。"}}],"memory_note":null,"forget_term":null}}
用户：你能飞起来吗 → {{"relation":"chat","target_chain":null,"kind":"chat","steps":[{{"intent":"","line":"我可飞不起来，不过可以给你讲讲飞行的原理。"}}],"memory_note":null,"forget_term":null}}
用户：我妹妹住在杭州 → {{"relation":"chat","target_chain":null,"kind":"chat","steps":[{{"intent":"","line":"原来你妹妹住在杭州，那里很美。"}}],"memory_note":"用户的妹妹住在杭州","forget_term":null}}
用户：忘掉我妹妹的事 → {{"relation":"chat","target_chain":null,"kind":"memory","steps":[{{"intent":"","line":"好的，关于你妹妹的事我已经忘掉了。"}}],"memory_note":null,"forget_term":"妹妹"}}
用户（有未完成链 chain-1：翻书）：不对，先挥挥手 → {{"relation":"revision","target_chain":"chain-1","kind":"action","steps":[{{"intent":"wave","line":"好，先挥挥手。"}}],"memory_note":null,"forget_term":null}}
当前未完成的指令链：{open_chains}
人设当前状态：{state}
相关记忆（带来源标签，只作参考）：{memories}"""

# A1 comparator: the LLM writes the request prompt content directly (free action phrase + line).
OPEN_LOOP_SYSTEM = """你是直播数字人「{name}」的导演，直接为下一段 5 秒的视频写提示。人设：{bio}
画面里的人设是一位女性，视频模型读英文动作描述、中文台词。
输出一个 JSON 对象（不要输出任何其他文字），字段：
- "relation": "new" | "revision" | "withdrawal" | "chat"（含义：新要求 / 改口 / 取消 / 闲聊）
- "target_chain": relation 为 revision/withdrawal 时，被修改的链 id；否则 null
- "kind": "action" | "multistep" | "content" | "memory" | "chat"
- "steps": [{{"action": 英文短语，描述她在画面里可见地做什么（如 "she lifts the teacup and takes a sip"），没有动作就写 "", "line": 她说的中文台词}}]，每个 step 是一段 5 秒视频
- "memory_note": 用户陈述了关于他自己的事实时写成一句；否则 null
- "forget_term": 用户要求忘记某事时写关键词；否则 null
每个 line 不超过 {chars} 个汉字。
当前未完成的指令链：{open_chains}
相关记忆（只作参考）：{memories}"""


class Director:
    def __init__(self, llm: ChatLLM, manifest: CapabilityManifest, ledger: StateLedger, *,
                 persona_name: str, persona_bio: str, mode: DirectorMode = DirectorMode.CLOSED_LOOP,
                 idle_intent: str = "idle_read", listen_intent: str = "listen"):
        self.llm = llm
        self.manifest = manifest
        self.ledger = ledger
        self.mode = mode
        self.persona_name = persona_name
        self.persona_bio = persona_bio
        self.idle_intent = idle_intent
        self.listen_intent = listen_intent
        self.plan_version = 0
        self.queue: deque[Segment] = deque()
        self.held: dict[str, dict[int, list[Segment]]] = {}  # multistep: steps not yet released
        self.chains: dict[str, IntentChain] = {}
        self.latest_chain: str | None = None  # the newest instruction (admission control)
        self.pending_corrections: dict[int, list[str]] = {}  # request index -> correction sentences
        self.events = DirectorEvents()
        self.listening = False
        self.memory_notes: list[tuple[str, str]] = []  # (utterance id, note)
        self.erased_terms: set[str] = set()
        self.interrupted: dict[str, Segment] = {}  # open chain -> its cut (dropped, unverified) segment
        self.awaiting_decision = False
        self.deferred: list[Segment] = []
        self.deferred_verifications: list[tuple] = []
        self.plan_steps: dict[str, list[list[Segment]]] = {}  # multistep plan (for replay after a repair)
        self.replay_pending: set[str] = set()  # chains whose later steps were pulled back by a failure
        self._last_action = ""  # the previous request's (non-filler) action, for smooth follow-through
        self.step_base_t: dict[str, float] = {}  # chain -> time the current step's clock started
        self._suppress_remarks: set[str] = set()

    @property
    def closed(self) -> bool:
        return self.mode == DirectorMode.CLOSED_LOOP

    # ------------------------------------------------------------ utterances
    def _open_chains(self) -> list[IntentChain]:
        return [c for c in self.chains.values() if c.status == ChainStatus.OPEN]

    async def on_user_utterance(self, utt: Utterance, memories: list[str] | None = None) -> dict:
        """Interpret an utterance and update the plan. Returns the parsed decision."""
        d = await self.decide(utt, memories)
        self.apply(utt, d)
        return d

    def apply(self, utt: Utterance, d: dict, memory_ids: list[str] | None = None,
              recall_id: str | None = None) -> None:
        """Apply a decision to the plan (the caller may first discard a superseded decision).
        ``memory_ids``: exactly the memories given to the responder for this decision (lineage)."""
        before = {id(x) for x in self.queue}
        self.awaiting_decision = False
        deferred, self.deferred = self.deferred, []
        self._apply_decision(utt, d)
        touched = {(d.get("target_chain") or "")} if d.get("relation") in ("revision", "withdrawal") else set()
        instruction = self.latest_chain is not None and d.get("relation") in ("new", "revision", "withdrawal") \
            and d.get("kind") not in ("chat", "memory")
        for seg in reversed(deferred):
            if seg.chain_id in touched or (instruction and seg.is_completion_remark):
                continue  # a new instruction resolves the barge-in: the old "好了。" is not spoken
            self.queue.appendleft(seg)
        pending, self.deferred_verifications = self.deferred_verifications, []
        for chain_id, intent, k, t, revision, step in pending:
            # a revised chain has a new revision count, so a stale verification no longer matches
            if instruction:
                self._suppress_remarks.add(chain_id)
            self.on_verified(chain_id, intent, k, t, revision=revision, step=step)
            self._suppress_remarks.discard(chain_id)
        for seg in self.queue:
            if id(seg) not in before:
                seg.memory_ids = list(memory_ids) if memory_ids is not None else None
                seg.recall_id = recall_id
        for steps in self.held.values():
            for segs in steps.values():
                for seg in segs:
                    if seg.memory_ids is None and id(seg) not in before:
                        seg.memory_ids = list(memory_ids) if memory_ids is not None else None
                        seg.recall_id = recall_id

    async def decide(self, utt: Utterance, memories: list[str] | None = None) -> dict:
        """Responder LLM call only; no state is changed."""
        open_chains = [{"chain_id": c.chain_id, "intent": c.final_intent} for c in self._open_chains()]
        if self.closed:
            intents = ", ".join(sorted({c.intent for c in self.manifest.caps.values()
                                        if c.usable(self.manifest.min_status, self.manifest.min_p)})) or "（暂无）"
            sys = RESPONDER_SYSTEM.format(
                name=self.persona_name, bio=self.persona_bio, intents=intents, chars=CHARS_PER_REQUEST,
                open_chains=open_chains or "无", state=self.ledger.continuity_sentence(),
                memories=memories or "无")
        else:
            sys = OPEN_LOOP_SYSTEM.format(name=self.persona_name, bio=self.persona_bio, chars=CHARS_PER_REQUEST,
                                          open_chains=open_chains or "无", memories=memories or "无")
        raw = await self.llm.chat([{"role": "system", "content": sys},
                                   {"role": "user", "content": utt.text}], json_mode=True)
        try:
            d = parse_json(raw)
        except ValueError:
            d = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "抱歉，我没听清，可以再说一次吗？"}]}
        return d

    def _declined_request(self, utt_text: str, kind: TaskKind, steps: list[dict]) -> bool:
        """Independent of the LLM's ``kind``: an imperative / ability request for the persona that
        the reply declines is an unsupported action request (a refusal chain), not chat."""
        asks = bool(_REQUEST.search(utt_text))
        declines = any(_DECLINE.search(st.get("line") or "") for st in steps)
        return self.closed and asks and declines and kind not in (TaskKind.ACTION, TaskKind.MULTISTEP)

    def _validate(self, kind: TaskKind, steps: list[dict]) -> str | None:
        """Closed loop: enforce the contract in code. Returns a refusal reason or None."""
        allowed = {c.intent for c in self.manifest.caps.values()}
        is_action = kind in (TaskKind.ACTION, TaskKind.MULTISTEP)
        unsupported = []
        for st in steps:
            it = st.get("intent") or ""
            if not is_action:
                st["intent"] = ""
            elif it and it not in allowed:
                unsupported.append(it)
                st["intent"] = ""
        if is_action and unsupported:
            return f"unsupported intent(s): {', '.join(unsupported)}"
        if is_action and not any(st.get("intent") for st in steps):
            return "action requested but no supported capability"  # LLM declined with a line only
        return None

    def _guard(self, line: str) -> str:
        """Closed loop: remove clauses that claim completion from an (unverified) LLM line —
        every spoken line, not only action-bearing ones."""
        if not self.closed or not _claims_completion(line):
            return line
        kept = [c for c in re.split(r"(?<=[。！？!?；;，,])", line) if c and not _claims_completion(c)]
        clean = "".join(kept)
        self.events.narration_guards.append((line, clean))
        return clean

    def _apply_decision(self, utt: Utterance, d: dict) -> None:
        relation = d.get("relation", "new")
        kind = TaskKind(d.get("kind", "chat")) if d.get("kind") in TaskKind._value2member_map_ else TaskKind.CHAT
        steps = [dict(s) for s in d.get("steps", []) if isinstance(s, dict)]
        refusal = self._validate(kind, steps) if self.closed else None
        if self._declined_request(utt.text, kind, steps):
            kind, relation, refusal = TaskKind.ACTION, "new", "declined by responder (unsupported request)"
        for st in steps:
            original = st.get("line") or ""
            st["line"] = self._guard(original)
            if self.closed and st.get("intent") and original and (not st["line"] or _PERFECTIVE.search(st["line"])):
                # an action-bearing line is spoken *before* the action is verified: only intent
                # wording is allowed (no perfective 了/啦/过/光/完 markers)
                self.events.narration_guards.append((st["line"], "好的。"))
                st["line"] = "好的。"
        target = self.chains.get(d.get("target_chain") or "")
        if d.get("memory_note"):
            self.memory_notes.append((utt.uid, d["memory_note"]))
        self.plan_version += 1
        self.listening = False

        if relation == "withdrawal" and target and target.status == ChainStatus.OPEN:
            target.status = ChainStatus.WITHDRAWN
            self._drop_chain_segments(target.chain_id)
            self._enqueue_chat(steps)
            return
        if relation == "revision" and target and target.status == ChainStatus.OPEN:
            self._drop_chain_segments(target.chain_id)
            target.revisions.append(utt.uid)
            target.final_intent = utt.text
            target.clock_origin = utt.t_end
            self.step_base_t.pop(target.chain_id, None)  # the revised intent's clock starts at its utterance
            target.kind = kind if kind != TaskKind.CHAT else target.kind
            target.steps = [s.get("intent", "") for s in steps]
            target.step_index = 0
            chain = target
        elif kind in (TaskKind.CHAT, TaskKind.MEMORY) and relation in ("chat", "new", "withdrawal", "revision"):
            self._enqueue_chat(steps)
            return
        else:
            chain = IntentChain(chain_id=new_id("chain"), kind=kind, opened_by=utt.uid,
                                final_intent=utt.text, clock_origin=utt.t_end,
                                steps=[s.get("intent", "") for s in steps])
            self.chains[chain.chain_id] = chain
        self._admit(chain.chain_id)
        self.interrupted.pop(chain.chain_id, None)  # its own (revised) plan follows
        if refusal:
            chain.status = ChainStatus.REFUSED
            self.events.refusals.append((chain.chain_id, refusal))
            # keep the LLM's words only if they actually decline; never speak an acceptance
            declines = [st for st in steps if _DECLINE.search(st.get("line") or "")]
            self._enqueue_chat(declines or [{"line": "这个我现在做不到，不过我们可以聊聊别的。"}])
            return
        self._enqueue_chain(chain, steps)

    # ------------------------------------------------------------ queue management
    def _admit(self, chain_id: str) -> None:
        """At most one unexecuted instruction: older unexecuted chains are capacity-skipped."""
        for c in self._open_chains():
            if c.chain_id != chain_id and self._unexecuted(c.chain_id):
                self._drop_chain_segments(c.chain_id)
                c.status = ChainStatus.CAPACITY_SKIPPED
                self.events.capacity_skips.append((c.chain_id, len(c.revisions)))
        self.latest_chain = chain_id

    def _unexecuted(self, chain_id: str) -> bool:
        return any(s.chain_id == chain_id and not s.is_completion_remark for s in self.queue) or \
            bool(self.held.get(chain_id)) or chain_id in self.interrupted

    def on_interrupted(self, scripts: list[BlockScript]) -> None:
        """Requests carrying an open chain's step were dropped before being fully presented:
        that step was never shown, so the chain counts as unexecuted again."""
        for sc in scripts:
            for cid in sc.chain_ids:
                c = self.chains.get(cid)
                if c is None or c.status != ChainStatus.OPEN or sc.provenance.get("completion_remark"):
                    continue
                if sc.provenance.get("revision") != len(c.revisions):
                    continue
                self.interrupted.setdefault(cid, Segment(
                    chain_id=cid, plan_version=self.plan_version, intent=sc.provenance.get("intent") or "",
                    action_text="" if self.closed else sc.action,  # A1: its own phrase
                    line="" if self.closed else sc.transcript,
                    step=sc.provenance.get("step"), revision=len(c.revisions)))
                if sc.request_index in c.requests:  # a cut request no longer counts toward closure
                    c.requests.remove(sc.request_index)

    def _resume_interrupted(self) -> None:
        """No newer instruction displaced them: re-queue the cut step (no correction: it was not
        judged, only not shown)."""
        for cid, seg in list(self.interrupted.items()):
            c = self.chains.get(cid)
            if c is not None and c.status == ChainStatus.OPEN and (seg.intent or seg.action_text or seg.line) and \
                    not any(s.chain_id == cid for s in self.queue):
                seg.plan_version = self.plan_version
                self.queue.append(seg)
        self.interrupted.clear()

    def _drop_chain_segments(self, chain_id: str) -> None:
        self.queue = deque(s for s in self.queue if s.chain_id != chain_id)
        self.held.pop(chain_id, None)
        self.interrupted.pop(chain_id, None)

    def say_verified(self, line: str) -> None:
        """Queue a line whose claim the controller has verified (e.g. an erasure confirmation)."""
        for seg in reversed([Segment(chain_id=None, plan_version=self.plan_version, line=x, memory_ids=[])
                             for x in _split_line(line)]):
            self.queue.appendleft(seg)

    def _enqueue_chat(self, steps: list[dict]) -> None:
        """Chat / explanation lines go first; they do not displace instructions."""
        segs = [Segment(chain_id=None, plan_version=self.plan_version, line=line)
                for s in steps for line in _split_line(s.get("line", ""))]
        for seg in reversed(segs):
            self.queue.appendleft(seg)
        self._resume_interrupted()

    def _segments_for_step(self, chain: IntentChain, i: int, s: dict, n_steps: int) -> list[Segment]:
        out = []
        for j, line in enumerate(_split_line(s.get("line", "")) or [""]):
            out.append(Segment(chain_id=chain.chain_id, plan_version=self.plan_version,
                               intent=(s.get("intent") or "") if j == 0 else "",
                               action_text=(s.get("action") or "") if j == 0 else "",
                               line=line, step=i if n_steps > 1 else None, revision=len(chain.revisions)))
        return [x for x in out if x.intent or x.action_text or x.line]

    @staticmethod
    def _one_line(steps: list[dict]) -> list[dict]:
        """A multi-action command is presented as ONE response: the action steps' announcements are
        merged into a single line on the first action step and the later action steps run silently
        back to back (the step split stays internal). Content steps (no intent) keep their own lines."""
        acts = [i for i, st in enumerate(steps) if st.get("intent") or st.get("action")]
        lines = [(steps[i].get("line") or "").strip() for i in acts]
        if len(acts) < 2 or sum(1 for x in lines if x) < 2:
            return steps
        parts = []
        for x in (x for x in lines if x):
            x = x.rstrip("。！!.")
            if parts:
                x = re.sub(r"^(好的?|嗯|行)[，,]?\s*", "", x)
                x = re.sub(r"^(我|再|然后|接着)+", "", x)
            parts.append(x)
        combined = "，再".join(parts) + "。"
        if len(combined) > CHARS_PER_REQUEST * 2:
            combined = lines[0]
        out = [dict(st) for st in steps]
        for n, i in enumerate(acts):
            out[i]["line"] = combined if n == 0 else ""
        return out

    def _enqueue_chain(self, chain: IntentChain, steps: list[dict]) -> None:
        """All steps are released back to back (fluent on screen: no filler between steps). Each
        action step is still verified in order; if one fails, later steps are pulled back and
        replayed after its repair is verified (`queue_retry` / `on_verified`)."""
        if chain.kind == TaskKind.MULTISTEP and len(steps) > 1:
            steps = self._one_line(steps)
        per_step = [self._segments_for_step(chain, i, s, len(steps)) for i, s in enumerate(steps)]
        if self.closed and chain.kind == TaskKind.MULTISTEP and len(steps) > 1:
            self.plan_steps[chain.chain_id] = per_step
        self.queue.extend(seg for segs in per_step for seg in segs)

    def _replay_after(self, chain: IntentChain, step: int) -> list[Segment]:
        """Fresh copies of the planned segments of every step after ``step`` (replay in order)."""
        from dataclasses import replace

        plan = self.plan_steps.get(chain.chain_id, [])
        return [replace(seg, plan_version=self.plan_version, revision=len(chain.revisions), memory_ids=seg.memory_ids)
                for i in range(step + 1, len(plan)) for seg in plan[i]]

    def _release_upto(self, chain: IntentChain, after: int) -> int:
        """Index of the last step released together after step ``after``: all following
        content steps up to and including the next action step."""
        i = after + 1
        while i < len(chain.steps) - 1 and not chain.steps[i]:
            i += 1
        return min(i, len(chain.steps) - 1)

    def _action_steps(self, chain: IntentChain) -> list[int]:
        idx = [i for i, s in enumerate(chain.steps) if s]
        return idx or [0]

    def _expected_step(self, chain: IntentChain) -> int | None:
        acts = self._action_steps(chain)
        return acts[chain.step_index] if chain.step_index < len(acts) else None

    def _matches(self, chain: IntentChain, revision: int | None, step: int | None) -> bool:
        if revision is not None and revision != len(chain.revisions):
            return False  # verdict about a superseded intent
        exp = self._expected_step(chain)
        return exp is not None and (step if step is not None else self._action_steps(chain)[0]) == exp

    def on_barge_in(self) -> None:
        """User started speaking: stop planning ahead; next requests show the persona listening.
        Unsent segments of open chains are kept (the utterance decides what happens to them)."""
        self.plan_version += 1
        self.queue = deque(s for s in self.queue if s.chain_id is not None and not s.is_completion_remark)
        self.listening = True
        self.awaiting_decision = True  # old-plan segments stay ineligible until the next decision

    # ------------------------------------------------------------ verdict feedback
    def on_verified(self, chain_id: str, intent: str, request_index: int, t: float, *,
                    revision: int | None = None, step: int | None = None) -> bool:
        if self.awaiting_decision:
            # a barge-in decision is pending: the chain must stay open (revision-eligible) and
            # no "好了。" may be queued until the decision resolves; re-applied after `apply`
            self.deferred_verifications.append((chain_id, intent, request_index, t, revision, step))
            return True
        chain = self.chains.get(chain_id)
        if not chain or chain.status != ChainStatus.OPEN or not self._matches(chain, revision, step):
            return False
        self.ledger.apply_verified_action(intent)
        done_step = self._expected_step(chain)
        self.step_base_t[chain_id] = t  # the next step's deadline counts from this verification
        chain.step_index += 1
        if chain.first_compliant_t is None:
            chain.first_compliant_t = t
        released: list[Segment] = []
        if chain_id in self.replay_pending and done_step is not None:
            # a failed earlier step pulled the later steps back: replay them now, in order
            self.replay_pending.discard(chain_id)
            released += self._replay_after(chain, done_step)
        remark: Segment | None = None
        if chain.step_index >= len(self._action_steps(chain)):
            chain.status = ChainStatus.COMPLIED
            self.held.pop(chain_id, None)
            self.plan_steps.pop(chain_id, None)
            if self.closed and chain_id not in self._suppress_remarks and self.latest_chain == chain_id:
                # (a verdict arriving after a newer instruction does not speak an old "好了。")
                # Narration policy: completion is voiced only after verification, and after the
                # chain's remaining spoken content, if any.
                remark = Segment(chain_id=chain_id, plan_version=self.plan_version, line="好了。",
                                 is_completion_remark=True, revision=len(chain.revisions), memory_ids=[])
        if self.awaiting_decision:
            # a barge-in is waiting for its decision: hold the release (incl. any "好了。") until
            # the decision is applied; if it revises/withdraws this chain the remark is dropped
            self.deferred.extend(released + ([remark] if remark else []))
            return True
        for seg in reversed(released):
            self.queue.appendleft(seg)
        if remark is not None:
            # after this chain's still-queued segments (e.g. a trailing explanation step)
            idx = max((i for i, q in enumerate(self.queue) if q.chain_id == chain_id), default=-1)
            self.queue.insert(idx + 1, remark)
        return True

    def expire(self, chain_id: str, revision: int | None) -> None:
        """The current step's deadline passed before its check: the chain has failed (no late
        verification, step release or repair)."""
        c = self.chains.get(chain_id)
        if c is not None and c.status == ChainStatus.OPEN and (revision is None or revision == len(c.revisions)):
            c.status = ChainStatus.FAILED
            self._drop_chain_segments(chain_id)

    def schedule_correction(self, request_index: int, sentence: str) -> None:
        self.pending_corrections.setdefault(request_index, []).append(sentence)

    def on_request_presented(self, script: BlockScript, done: set[int] | None = None) -> None:
        """Open loop (A1): no QC closes a chain, so a chain is closed as PRESENTED (unverified)
        once no segment is pending and every request it was locked into has been fully presented
        (or dropped). Lifecycle only, not compliance."""
        if self.closed:
            return
        done = done or set()
        for cid in script.chain_ids:
            c = self.chains.get(cid)
            if c is not None and c.status == ChainStatus.OPEN and not self._unexecuted(cid) \
                    and all(r in done for r in c.requests):
                c.status = ChainStatus.PRESENTED

    def queue_retry(self, chain_id: str, intent: str, *, correction: str, failed_request: int,
                    revision: int | None = None, step: int | None = None, min_request: int = 0,
                    line: str = "") -> bool:
        """Forward repair: retry the action no earlier than ``min_request`` (the earliest
        correctable request). Dropped if the chain is no longer open, the verdict was about a
        superseded intent or another step, or a newer instruction exists (admission control:
        the chain is then capacity-skipped)."""
        chain = self.chains.get(chain_id)
        if chain is None or chain.status != ChainStatus.OPEN or not self._matches(chain, revision, step):
            return False
        if self.latest_chain != chain_id:
            # executed (presented) and failed its check, and a newer instruction exists: the step
            # failed; this is not a capacity skip (that is for never-executed instructions)
            chain.status = ChainStatus.FAILED
            self._drop_chain_segments(chain_id)
            return False
        if chain_id in self.plan_steps and step is not None:
            # later steps must not run before this one is repaired: pull them back, replay them
            # after the repair is verified (strict order; fluent in the success path)
            self.queue = deque(q for q in self.queue if not (q.chain_id == chain_id and (q.step or 0) > step))
            self.replay_pending.add(chain_id)
        self.queue.appendleft(Segment(chain_id=chain_id, plan_version=self.plan_version, intent=intent,
                                      line=line, correction=correction, retry_of=failed_request, step=step,
                                      revision=len(chain.revisions), min_request=min_request))
        return True

    # ------------------------------------------------------------ erasure
    def purge(self, term: str) -> int:
        """Erasure (§12): remove the term from all controller state that can reach a prompt."""
        self.erased_terms.add(term)
        n = 0
        before = len(self.queue)
        self.queue = deque(s for s in self.queue if term not in s.line and term not in s.action_text)
        for sq in self.queue:
            sq.correction = sq.correction.replace(term, "[已删除]")
        self.deferred = [x for x in self.deferred if term not in x.line and term not in x.action_text]
        for cid, seg in list(self.interrupted.items()):
            if term in seg.line or term in seg.action_text or term in seg.correction:
                del self.interrupted[cid]
        n += before - len(self.queue)
        for cid, steps in list(self.held.items()):
            for i, segs in list(steps.items()):
                steps[i] = [s for s in segs if term not in s.line and term not in s.action_text]
        for c in self.chains.values():
            if term in c.final_intent:
                c.final_intent = c.final_intent.replace(term, "[已删除]")
                n += 1
        self.memory_notes = [(u, x) for u, x in self.memory_notes if term not in x]
        self.pending_corrections = {k: [x for x in v if term not in x] for k, v in self.pending_corrections.items()}
        n += self.ledger.redact(term)
        return n

    # ------------------------------------------------------------ script building
    def _pop_segment(self, request_index: int) -> Segment | None:
        if self.awaiting_decision:
            return None  # after a barge-in only a listening filler until the new decision lands
        # A repair reserved for exactly this request takes the slot before anything else.
        for i, seg in enumerate(self.queue):
            if seg.retry_of is not None and seg.min_request == request_index:
                del self.queue[i]
                return seg
        for i, seg in enumerate(self.queue):
            if seg.min_request <= request_index:
                del self.queue[i]
                return seg
        return None

    def next_script(self, request_index: int) -> BlockScript:
        seg = self._pop_segment(request_index)
        follow_through = ""
        if seg is None:
            intent = self.listen_intent if self.listening else self.idle_intent
            seg = Segment(chain_id=None, plan_version=self.plan_version, intent=intent, line="")
            if self._last_action and not self.listening:
                # the previous request carried an action: let it finish naturally instead of cutting
                # straight to the idle pose (fluency on screen; not a new action)
                follow_through = self._last_action
        chain = self.chains.get(seg.chain_id or "")
        if chain is not None and chain.status not in (ChainStatus.OPEN, ChainStatus.COMPLIED):
            seg = Segment(chain_id=None, plan_version=self.plan_version, intent=self.idle_intent,
                          line=seg.line)  # chain closed meanwhile: keep the words, drop the binding

        action_phrase, cap_ids, checks = "", [], []
        line = seg.line
        if not self.closed:
            if seg.action_text:
                action_phrase = seg.action_text
            elif seg.intent:  # idle / listen filler: same phrase as A2
                cap = self.manifest.by_intent(seg.intent)
                action_phrase = cap.phrase if cap else ""
        elif seg.intent:
            res = self.manifest.decide(seg.intent)
            if res.decision == Decision.EMIT and res.capability:
                action_phrase = res.capability.phrase
                cap_ids.append(res.capability.cap_id)
                if seg.chain_id and res.capability.check_question:
                    checks.append(CheckQuestion(qid=new_id("q"), text=res.capability.check_question,
                                                kind="action"))
            elif seg.chain_id is None:
                action_phrase = ""  # filler intent not usable: no action
            elif res.decision == Decision.DEGRADE and res.capability:
                # the spoken line states the capability decision (never the LLM's acceptance)
                self.events.degradations.append((seg.chain_id, res.reason))
                line = res.capability.degrade_to or "这个动作我现在做不好，我换个方式回应你。"
                self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
            else:
                self.events.refusals.append((seg.chain_id, res.reason))
                line = "这个我现在做不到，不过我们可以聊聊别的。"
                self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
        if follow_through and action_phrase:
            action_phrase = (f"she smoothly finishes the previous movement ({follow_through.rstrip('.')}) and puts "
                             f"everything back in place, then {action_phrase.removeprefix('she ')}")[:290]
        self._last_action = action_phrase if (seg.intent and seg.chain_id) or seg.action_text else ""
        if line and self.closed:
            checks.append(CheckQuestion(qid=new_id("q"), text="台词是否被完整、准确地说出？", kind="speech"))
        if seg.is_completion_remark and seg.chain_id:
            self.events.completion_claims.append((seg.chain_id, request_index, seg.step))
        elif not self.closed and seg.chain_id and _claims_completion(line):
            self.events.completion_claims.append((seg.chain_id, request_index, seg.step))

        corrections = list(self.pending_corrections.pop(request_index, []))
        if seg.correction:
            corrections.append(seg.correction)
        if self.closed:
            bridge = self.ledger.bridging_note()
            if bridge:
                corrections.append(bridge)
                self.ledger.bridge_request = request_index  # divergence kept until this is presented
        script = BlockScript(request_index=request_index, plan_version=seg.plan_version,
                             canon=self.ledger.canon, action=action_phrase, transcript=line,
                             corrections=corrections, checks=checks,
                             chain_ids=[seg.chain_id] if seg.chain_id else [],
                             capability_ids=cap_ids,
                             provenance={"intent": seg.intent, "step": seg.step, "retry_of": seg.retry_of,
                                         "revision": seg.revision, "memory_ids": seg.memory_ids,
                                         "recall_id": seg.recall_id,
                                         "completion_remark": seg.is_completion_remark})
        if seg.chain_id and seg.chain_id in self.chains:
            self.chains[seg.chain_id].requests.append(request_index)
        self.ledger.record_request(request_index, action_phrase, line)
        return script

    def _fail_chain(self, chain_id: str | None, status: ChainStatus) -> None:
        if chain_id and chain_id in self.chains and self.chains[chain_id].status == ChainStatus.OPEN:
            self.chains[chain_id].status = status
            self._drop_chain_segments(chain_id)


def _split_line(line: str, n: int = CHARS_PER_REQUEST) -> list[str]:
    """Split a spoken line into <= n-character pieces at punctuation where possible."""
    line = (line or "").strip()
    if not line:
        return []
    out, cur = [], ""
    for piece in re.split(r"(?<=[。！？!?；;，,])", line):
        if len(cur) + len(piece) <= n:
            cur += piece
        else:
            if cur:
                out.append(cur)
            while len(piece) > n:
                out.append(piece[:n])
                piece = piece[n:]
            cur = piece
    if cur:
        out.append(cur)
    return [x for x in out if re.search(r"[\w一-鿿]", x)]


# Completion meaning (claims an act already happened), incl. the proposal's example
# 「刚才那首歌你喜欢吗」: past-reference markers (刚才/刚刚/已经 ... 了), completive verb
# complements (…完/…好了/…过了) and explicit completion words. Deliberately broad: a guarded line
# loses a clause, a missed claim is a false completion.
_PERFECTIVE = re.compile(r"[了啦过光完]")

_COMPLETION = re.compile(
    r"(刚才|刚刚|方才|已经|完成|搞定|好了|[做喝吃写翻唱讲说画看读挥放拿站坐跳弹]完|"
    r"[做写画]好|[唱讲说看读]过了|把.{1,8}[喝吃写翻挥放拿收摆倒]了|"
    r"[喝吃写翻挥放拿站坐鞠点摇]了(?![吗呢])|[喝吃]光|[了完好过光]啦|done|finished)")


_ACTION_VERB = "喝饮品吃尝写翻挥放拿站坐鞠点摇倒扇笑看读唱讲画收摆捧端举"
_VERB_PERFECTIVE = re.compile(rf"[{_ACTION_VERB}][^，。！？,.!?；;]{{0,4}}[了啦过完光净尽好掉]")


def _claims_completion(line: str) -> bool:
    """Completion meaning: explicit markers, or an action verb followed (same clause) by a
    perfective / resultative marker (e.g. 茶被我喝净了, 书放好了)."""
    line = line or ""
    if _COMPLETION.search(line):
        return True
    for clause in re.split(r"(?<=[，。！？,.!?；;])", line):
        if re.search(r"[吗呢？?]\s*[，。！？,.!?；;]?$", clause.strip()):
            continue  # a question does not claim anything
        if _VERB_PERFECTIVE.search(clause):
            return True
    return False


_REQUEST = re.compile(r"(请|吧|给我|帮我|能不能|能否|可以.{0,6}吗|你能.{0,8}吗|来.{0,4}一下|一下)")
_DECLINE = re.compile(r"(做不到|不能|没法|无法|不会|飞不|办不到|做不了)")
