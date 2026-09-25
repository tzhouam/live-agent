"""Orchestrator: runs the live agent on the single timeline (proposal §10, §11).

Concurrent loops
- lock loop     : at each just-in-time lock time, ask the director for the next BlockScript,
                  compile it to an H3 prompt and submit it to the generator (event LOCK).
- chunk loop    : forward generated chunks to the client transport (event CHUNK_READY).
- presentation  : client acks (start/end of each chunk) drive V_k and the evidence time E;
                  when a request's last chunk has been presented, run its QC checks.
- input         : user utterances (after ASR) go to memory + director; speech onset = barge-in.

Everything that the evaluation needs is written to the EventLog as JSONL.
"""

from __future__ import annotations

import asyncio
import enum
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import Generator
from live_agent.prompt.h3_compiler import compile_prompt
from live_agent.qc.judge import ForwardCorrector
from live_agent.timeline import EventLog, LockScheduler
from live_agent.types import (BlockScript, ChainStatus, Chunk, EventType, Utterance, Verdict,
                              VerdictLabel, now)


class Transport(Protocol):
    """Client side: plays chunks and reports presentation times via Orchestrator.on_presented."""

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None: ...

    async def stop_playback(self) -> None: ...


class MemoryPort(Protocol):
    """Minimal memory interface used by the orchestrator (adapter over live_agent.memory)."""

    def recall(self, text: str, *, mode: str) -> list[str]: ...

    def on_user_utterance(self, utt: Utterance) -> None: ...

    def on_persona_line(self, text: str, *, session_id: str, scope: str) -> None: ...


class Judge(Protocol):
    async def judge(self, q, chunks, request_index: int, t_evidence: float) -> Verdict: ...


class CorrectionMode(str, enum.Enum):
    GRADIENT = "gradient"  # forward semantic gradient (A2)
    REPEAT = "repeat"  # RQ2 contrast: repeat the instruction unchanged
    NONE = "none"  # ablation / open loop


@dataclass
class OrchestratorConfig:
    session_id: str = "session-0"
    scope: str = "private"  # "private" (1:1) | "public" (test livestream)
    correction_mode: CorrectionMode = CorrectionMode.GRADIENT
    qc_enabled: bool = True
    max_requests: int | None = None  # stop after N requests (tests / batch runs)
    correction_chain_prior_s: float = 1.0  # C estimate until measured
    seed: int = 0


class Orchestrator:
    def __init__(self, generator: Generator, director: Director, scheduler: LockScheduler,
                 transport: Transport, *, judge: Judge | None = None,
                 corrector: ForwardCorrector | None = None, speech_check=None,
                 memory: MemoryPort | None = None, log: EventLog | None = None,
                 cfg: OrchestratorConfig | None = None):
        self.gen = generator
        self.director = director
        self.sched = scheduler
        self.transport = transport
        self.judge = judge
        self.corrector = corrector or ForwardCorrector()
        self.speech_check = speech_check
        self.memory = memory
        self.log = log or EventLog()
        self.cfg = cfg or OrchestratorConfig()
        self.scripts: dict[int, BlockScript] = {}
        self.prompts: dict[int, str] = {}
        self.chunks: dict[int, list[Chunk]] = defaultdict(list)
        self.presented: dict[int, set[int]] = defaultdict(set)
        self.next_lock = 0
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._rng = random.Random(self.cfg.seed)
        self._chain_costs: list[float] = []
        self.dropped: set[int] = set()  # requests discarded by a barge-in (never presented in full)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        await self.gen.start()
        self._tasks = [asyncio.create_task(self._lock_loop()), asyncio.create_task(self._chunk_loop())]

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await self.gen.close()
        self.log.close()

    async def wait_done(self) -> None:
        await self._stop.wait()

    # ------------------------------------------------------------------ lock loop
    async def _lock_loop(self) -> None:
        while not self._stop.is_set():
            k = self.next_lock
            if self.cfg.max_requests is not None and k >= self.cfg.max_requests:
                return
            # Re-evaluate while waiting: V_{k-1} becomes known (or better extrapolated) meanwhile.
            while not self._stop.is_set():
                tl = self.sched.lock_time(k)
                if tl is not None and tl <= now():
                    break
                await asyncio.sleep(0.01 if tl is None else min(0.05, tl - now()))
            # Never run more than two requests ahead of presentation (bounded backlog).
            while k >= 2 and not self._resolved(k - 2) and not self._stop.is_set():
                await asyncio.sleep(0.01)
            script = self.director.next_script(k)
            prompt = compile_prompt(script, first_request=(k == 0))
            self.scripts[k], self.prompts[k] = script, prompt
            t = now()
            await self.gen.submit(k, prompt)
            self.sched.on_lock(k, t)
            self.next_lock = k + 1
            self.log.emit(EventType.LOCK, t, request_index=k, plan_version=script.plan_version,
                          lambda_est=self.sched.lambda_estimate(), planned_lock=tl,
                          action=script.action, transcript=script.transcript,
                          chain_ids=script.chain_ids, corrections=script.corrections,
                          capability_ids=script.capability_ids, prompt=prompt,
                          checks=[{"qid": q.qid, "text": q.text, "kind": q.kind} for q in script.checks])
            if script.transcript and self.memory:
                self.memory.on_persona_line(script.transcript, session_id=self.cfg.session_id,
                                            scope=self.cfg.scope)
            for chain_id, rid in self.director.events.completion_claims:
                if rid == k:
                    self.log.emit(EventType.COMPLETION_CLAIM, t, request_index=k, chain_id=chain_id)
            for chain_id, reason in self._drain(self.director.events.refusals):
                self.log.emit(EventType.REFUSAL, t, request_index=k, chain_id=chain_id, reason=reason)
            for chain_id, reason in self._drain(self.director.events.degradations):
                self.log.emit(EventType.REFUSAL, t, request_index=k, chain_id=chain_id, reason=reason,
                              degraded=True)

    def _resolved(self, k: int) -> bool:
        return k in self.sched.presented_start or k in self.dropped

    @staticmethod
    def _drain(items: list) -> list:
        out = list(items)
        items.clear()
        return out

    # ------------------------------------------------------------------ chunk loop
    async def _chunk_loop(self) -> None:
        async for ch in self.gen.chunks():
            self.chunks[ch.request_index].append(ch)
            self.log.emit(EventType.CHUNK_READY, ch.t_ready, request_index=ch.request_index,
                          chunk_index=ch.chunk_index, n_frames=ch.n_frames)
            if ch.chunk_index == 3:
                self.sched.on_duration(ch.request_index,
                                       sum(c.duration_s for c in self.chunks[ch.request_index]))
                for tm in self.gen.timings:
                    if tm.request_index == ch.request_index:
                        self.sched.observe_timing(tm)
                        self.log.emit(EventType.REQUEST_DONE, now(), request_index=ch.request_index,
                                      lead_s=tm.lead_s, teacher_s=tm.teacher_s,
                                      total_s=(tm.t_done - tm.t_lock) if tm.t_done else None)
            if ch.request_index in self.dropped:
                continue  # generated before a barge-in: never shown
            script = self.scripts.get(ch.request_index)
            if script is not None:
                await self.transport.send_chunk(ch, script)

    # ------------------------------------------------------------------ presentation acks
    def on_presented(self, request_index: int, chunk_index: int, t_start: float, t_end: float) -> None:
        """Called by the transport when a chunk *finished* presenting (with its start/end times)."""
        if chunk_index == 0:
            self.sched.on_presented(request_index, t_start)
            self.director.ledger.mark_presented(request_index)
        self.presented[request_index].add(chunk_index)
        self.log.emit(EventType.CHUNK_PRESENTED, t_start, request_index=request_index,
                      chunk_index=chunk_index, t_end=t_end)
        n = len(self.chunks.get(request_index, [])) or 4
        if len(self.presented[request_index]) == n and self.cfg.qc_enabled:
            asyncio.ensure_future(self._run_checks(request_index, t_evidence=t_end))
        self._maybe_finish()

    def _maybe_finish(self) -> None:
        m = self.cfg.max_requests
        if m is None:
            return
        last = m - 1
        done = last in self.dropped or len(self.presented.get(last, ())) == (len(self.chunks.get(last, [])) or 4)
        if done and all(self._resolved(k) for k in range(m)):
            self._stop.set()

    # ------------------------------------------------------------------ QC
    async def _run_checks(self, k: int, t_evidence: float) -> None:
        script = self.scripts.get(k)
        if script is None or not script.checks or self.director.mode == DirectorMode.OPEN_LOOP:
            return
        chunks = self.chunks[k]
        action_verdicts: list[Verdict] = []
        for q in script.checks:
            if q.kind == "speech":
                if self.speech_check is None:
                    continue
                v = self.speech_check.check(q, script.transcript, chunks, k, t_evidence)
            elif self.judge is not None:
                v = await self.judge.judge(q, chunks, k, t_evidence)
            else:
                continue
            if q.kind == "action":
                action_verdicts.append(v)
            self.log.emit(EventType.VERDICT, v.t_verdict, request_index=k, qid=v.qid, kind=q.kind,
                          label=v.label.value, confidence=v.confidence, rationale=v.rationale,
                          t_evidence=t_evidence, source="online_monitor")
            self.director.ledger.record_verdict(k, v.qid, v.label.value)
        intent = script.provenance.get("intent", "")
        for chain_id in script.chain_ids:
            if action_verdicts and all(v.label == VerdictLabel.COMPLIED for v in action_verdicts):
                self.director.on_verified(chain_id, intent, k, t_evidence)
            elif any(v.label == VerdictLabel.NOT_COMPLIED for v in action_verdicts):
                await self._repair(chain_id, intent, script, action_verdicts, t_evidence)

    async def _repair(self, chain_id: str, intent: str, script: BlockScript, failed: list[Verdict],
                      t_evidence: float) -> None:
        mode = self.cfg.correction_mode
        if mode == CorrectionMode.NONE:
            return
        t0 = now()
        if mode == CorrectionMode.GRADIENT:
            qtext = {q.qid: q.text for q in script.checks}
            sentence = await self.corrector.correction(script.action, failed, qtext)
        else:
            sentence = ""
        cost = now() - t0
        self._chain_costs.append(cost)
        j_planned = self.sched.earliest_correctable(t_evidence, cost, self.next_lock)
        queued = self.director.queue_retry(chain_id, intent, correction=sentence,
                                           failed_request=script.request_index,
                                           plan_version=script.plan_version)
        self.log.emit(EventType.REPAIR, now(), request_index=script.request_index,
                      chain_id=chain_id, mode=mode.value, correction=sentence, queued=queued,
                      earliest_correctable=j_planned, next_unlocked=self.next_lock, chain_cost_s=cost)

    # ------------------------------------------------------------------ user input
    async def on_speech_start(self, t: float | None = None) -> None:
        """Barge-in: stop playback now; stop planning ahead; mark unshown generated content."""
        t = now() if t is None else t
        await self._drop_unpresented()
        self.log.emit(EventType.PLAYBACK_STOP, now(), t_speech_onset=t, dropped=sorted(self.dropped))
        self.director.on_barge_in()
        self._maybe_finish()

    async def _drop_unpresented(self) -> None:
        """Stop playback and discard everything locked but not (fully) presented."""
        await self.transport.stop_playback()
        for k in range(self.next_lock):
            n = len(self.chunks.get(k, [])) or 4
            if len(self.presented.get(k, ())) < n:
                self.dropped.add(k)
                self.director.ledger.mark_generated_not_presented(k)

    async def on_user_utterance(self, utt: Utterance) -> dict[str, Any]:
        self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text)
        memories = self.memory.recall(utt.text, mode=self.cfg.scope) if self.memory else None
        if self.memory:
            self.memory.on_user_utterance(utt)
        decision = await self.director.on_user_utterance(utt, memories)
        term = (decision or {}).get("forget_term")
        if term and self.memory is not None and hasattr(self.memory, "forget"):
            await self._erase(term)
        self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
                      chains={c.chain_id: c.status.value for c in self.director.chains.values()})
        return decision

    async def _erase(self, term: str) -> None:
        """Erasure (proposal §12): memory cascade + drop unsent scripts + restart generator state."""
        report = self.memory.forget(term)
        # Unsent plan segments that mention the term are dropped.
        self.director.queue = type(self.director.queue)(
            s for s in self.director.queue if term not in (s.line or ""))
        # The generator's KV / teacher tail may hold the erased content: restart from canon.
        await self._drop_unpresented()
        self.director.ledger.generated_not_presented.clear()  # erased content must not be bridged to
        await self.gen.reset()
        self._maybe_finish()
        self.log.emit(EventType.PLAYBACK_STOP, now(), erasure=True, deleted=len(report.deleted_ids),
                      kinds=report.kinds, generator_reset=True)

    def open_chains(self) -> list[str]:
        return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]
