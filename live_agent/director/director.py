"""Online director (proposal §8.2 layers 1-2, §9, §10).

Responsibilities
- Interpret each user utterance with the responder LLM: new intent chain, revision of
  an open chain, or withdrawal; the plan is a queue of *segments* (one per 5-s request:
  an action intent and at most ~5 s of speech).
- On a new plan version, drop *unsent* segments of older versions (cancellation rule).
- At each lock, build the BlockScript for the next request: canon from the ledger
  (verbatim), action via the capability manifest (emit / degrade / refuse), pending
  forward corrections, and compile-time check questions.
- Narration policy: the LLM never claims completion; the director appends a completion
  remark only after QC verified the action on presented frames (FCR control).

Modes: ``closed_loop`` (A2) and ``open_loop`` (A1 baseline: the LLM writes the action
phrase freely, no manifest, no QC-driven corrections, no narration guard).
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
    intent: str = ""  # capability intent (closed loop) or free phrase (open loop)
    line: str = ""
    step: int | None = None
    is_completion_remark: bool = False
    correction: str = ""  # forward correction attached to a retried action
    retry_of: int | None = None  # request index whose check failed


@dataclass
class DirectorEvents:
    """Things the orchestrator must log (consumed by the eval schema)."""

    refusals: list[tuple[str, str]] = field(default_factory=list)  # (chain_id, reason)
    degradations: list[tuple[str, str]] = field(default_factory=list)
    completion_claims: list[tuple[str, int]] = field(default_factory=list)  # (chain_id, request)
    capacity_skips: list[str] = field(default_factory=list)


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
        self.chains: dict[str, IntentChain] = {}
        self.pending_corrections: dict[int, list[str]] = {}  # request index -> correction sentences
        self.events = DirectorEvents()
        self.listening = False
        self.memory_notes: list[tuple[str, str]] = []  # (utterance id, note)

    # ------------------------------------------------------------ utterances
    def _open_chains(self) -> list[IntentChain]:
        return [c for c in self.chains.values() if c.status == ChainStatus.OPEN]

    async def on_user_utterance(self, utt: Utterance, memories: list[str] | None = None) -> dict:
        """Interpret an utterance and replace the unsent plan. Returns the parsed decision."""
        intents = ", ".join(sorted({c.intent for c in self.manifest.caps.values()
                                    if self.mode == DirectorMode.OPEN_LOOP
                                    or c.usable(self.manifest.min_status, self.manifest.min_p)})) or "（暂无）"
        open_chains = [{"chain_id": c.chain_id, "intent": c.final_intent} for c in self._open_chains()]
        sys = RESPONDER_SYSTEM.format(
            name=self.persona_name, bio=self.persona_bio, intents=intents, chars=CHARS_PER_REQUEST,
            open_chains=open_chains or "无", state=self.ledger.continuity_sentence(),
            memories=memories or "无")
        raw = await self.llm.chat([{"role": "system", "content": sys},
                                   {"role": "user", "content": utt.text}], json_mode=True)
        try:
            d = parse_json(raw)
        except ValueError:
            d = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "抱歉，我没听清，可以再说一次吗？"}]}
        self._apply_decision(utt, d)
        return d

    def _apply_decision(self, utt: Utterance, d: dict) -> None:
        relation = d.get("relation", "new")
        kind = TaskKind(d.get("kind", "chat")) if d.get("kind") in TaskKind._value2member_map_ else TaskKind.CHAT
        steps = [s for s in d.get("steps", []) if isinstance(s, dict)]
        # Enforce the contract in code, not only in the prompt: actions only for action/multistep
        # chains and only from the manifest; lines must not be empty punctuation.
        allowed = {c.intent for c in self.manifest.caps.values()}
        for st in steps:
            if kind not in (TaskKind.ACTION, TaskKind.MULTISTEP) or st.get("intent") not in allowed:
                if kind in (TaskKind.ACTION, TaskKind.MULTISTEP) and st.get("intent"):
                    st["unsupported_intent"] = st["intent"]  # keep: the compiler will refuse it
                    continue
                st["intent"] = ""
        target = self.chains.get(d.get("target_chain") or "")
        if d.get("memory_note"):
            self.memory_notes.append((utt.uid, d["memory_note"]))

        # New plan version: drop unsent segments of older versions (sent ones can only be superseded).
        self.plan_version += 1
        self.queue.clear()

        if relation == "withdrawal" and target:
            target.status = ChainStatus.WITHDRAWN
            chain_id = None
        elif relation == "revision" and target:
            target.revisions.append(utt.uid)
            target.final_intent = utt.text
            target.clock_origin = utt.t_end
            target.steps = [s.get("intent", "") for s in steps]
            target.step_index = 0
            chain_id = target.chain_id
        elif relation == "chat" and kind == TaskKind.CHAT:
            chain_id = None
        else:
            chain = IntentChain(chain_id=new_id("chain"), kind=kind, opened_by=utt.uid,
                                final_intent=utt.text, clock_origin=utt.t_end,
                                steps=[s.get("intent", "") for s in steps])
            self.chains[chain.chain_id] = chain
            chain_id = chain.chain_id

        for i, s in enumerate(steps):
            for j, line in enumerate(_split_line(s.get("line", "")) or [""]):
                self.queue.append(Segment(chain_id=chain_id, plan_version=self.plan_version,
                                          intent=(s.get("intent") or "") if j == 0 else "",
                                          line=line, step=i if len(steps) > 1 else None))
        self.listening = False

    def on_barge_in(self) -> None:
        """User started speaking: stop planning ahead; next requests show the persona listening."""
        self.plan_version += 1
        self.queue.clear()
        self.listening = True

    # ------------------------------------------------------------ verdict feedback
    def on_verified(self, chain_id: str, intent: str, request_index: int, t: float) -> None:
        chain = self.chains.get(chain_id)
        if not chain or chain.status != ChainStatus.OPEN:
            return
        self.ledger.apply_verified_action(intent)
        chain.step_index += 1
        if chain.first_compliant_t is None:
            chain.first_compliant_t = t
        if chain.step_index >= max(1, len([s for s in chain.steps if s])):
            chain.status = ChainStatus.COMPLIED
            if self.mode == DirectorMode.CLOSED_LOOP:
                # Narration policy: completion is voiced only after verification.
                self.queue.appendleft(Segment(chain_id=chain_id, plan_version=self.plan_version,
                                              intent="", line="好了。", is_completion_remark=True))

    def schedule_correction(self, request_index: int, sentence: str) -> None:
        self.pending_corrections.setdefault(request_index, []).append(sentence)

    def queue_retry(self, chain_id: str, intent: str, *, correction: str, failed_request: int,
                    plan_version: int) -> bool:
        """Forward repair: retry the action in the next request to be locked.

        Dropped if the chain is no longer open or a newer plan superseded the one that
        produced the failed request (the user changed their mind meanwhile).
        """
        chain = self.chains.get(chain_id)
        if chain is None or chain.status != ChainStatus.OPEN or plan_version != self.plan_version:
            return False
        self.queue.appendleft(Segment(chain_id=chain_id, plan_version=self.plan_version, intent=intent,
                                      line="", correction=correction, retry_of=failed_request))
        return True

    # ------------------------------------------------------------ script building
    def next_script(self, request_index: int) -> BlockScript:
        seg = self.queue.popleft() if self.queue else None
        if seg is None:
            intent = self.listen_intent if self.listening else self.idle_intent
            seg = Segment(chain_id=None, plan_version=self.plan_version, intent=intent, line="")

        action_phrase, cap_ids, checks = "", [], []
        line = seg.line
        if seg.intent:
            if self.mode == DirectorMode.OPEN_LOOP:
                cap = self.manifest.by_intent(seg.intent)
                action_phrase = cap.phrase if cap else seg.intent
            else:
                res = self.manifest.decide(seg.intent)
                if res.decision == Decision.EMIT and res.capability:
                    action_phrase = res.capability.phrase
                    cap_ids.append(res.capability.cap_id)
                    if seg.chain_id and res.capability.check_question:
                        checks.append(CheckQuestion(qid=new_id("q"), text=res.capability.check_question,
                                                    kind="action"))
                elif res.decision == Decision.DEGRADE and res.capability:
                    self.events.degradations.append((seg.chain_id or "", res.reason))
                    line = line or res.capability.degrade_to
                    self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
                else:
                    self.events.refusals.append((seg.chain_id or "", res.reason))
                    line = line or "这个我现在做不到，不过我们可以聊聊别的。"
                    self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
        if line and self.mode == DirectorMode.CLOSED_LOOP:
            checks.append(CheckQuestion(qid=new_id("q"), text="台词是否被完整、准确地说出？", kind="speech"))
        if seg.is_completion_remark and seg.chain_id:
            self.events.completion_claims.append((seg.chain_id, request_index))
        elif self.mode == DirectorMode.OPEN_LOOP and seg.chain_id and _claims_completion(line):
            self.events.completion_claims.append((seg.chain_id, request_index))

        corrections = list(self.pending_corrections.pop(request_index, []))
        if seg.correction:
            corrections.append(seg.correction)
        if self.mode == DirectorMode.CLOSED_LOOP:
            bridge = self.ledger.bridging_note()
            if bridge:
                corrections.append(bridge)
                self.ledger.generated_not_presented.clear()  # bridge once, then continue normally
        script = BlockScript(request_index=request_index, plan_version=seg.plan_version,
                             canon=self.ledger.canon, action=action_phrase, transcript=line,
                             corrections=corrections, checks=checks,
                             chain_ids=[seg.chain_id] if seg.chain_id else [],
                             capability_ids=cap_ids,
                             provenance={"intent": seg.intent, "step": seg.step, "retry_of": seg.retry_of})
        if seg.chain_id and seg.chain_id in self.chains:
            self.chains[seg.chain_id].requests.append(request_index)
        self.ledger.record_request(request_index, action_phrase, line)
        return script

    def _fail_chain(self, chain_id: str | None, status: ChainStatus) -> None:
        if chain_id and chain_id in self.chains and self.chains[chain_id].status == ChainStatus.OPEN:
            self.chains[chain_id].status = status


def _split_line(line: str, n: int = CHARS_PER_REQUEST) -> list[str]:
    """Split a spoken line into <= n-character pieces at punctuation where possible."""
    line = line.strip()
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
    return [x for x in out if re.search(r"[\w\u4e00-\u9fff]", x)]


_COMPLETION = re.compile(r"(完了|好了|做完|喝完|已经|done|finished)")


def _claims_completion(line: str) -> bool:
    return bool(_COMPLETION.search(line or ""))
