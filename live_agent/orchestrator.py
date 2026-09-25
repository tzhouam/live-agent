"""Orchestrator: runs the live agent on the single timeline (proposal §10, §11).

Concurrent loops
- lock loop     : at each just-in-time lock time, ask the director for the next BlockScript,
                  audit it (§15), compile it to an H3 prompt and submit it (event LOCK).
- chunk loop    : forward generated chunks to the client transport (event CHUNK_READY).
- presentation  : client acks (start/end of each chunk) drive V_k and the evidence time E;
                  when all chunks of a request have been presented, run its QC checks once.
- input         : user utterances (after ASR) go to memory + director; speech onset = barge-in.

Everything that the evaluation needs is written to the EventLog as JSONL. A worker failure
stops the session (event ERROR) instead of hanging it.
"""

from __future__ import annotations

import asyncio
import enum
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from live_agent.director.director import CHARS_PER_REQUEST, Director, DirectorMode
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
    REPEAT = "repeat"  # contrast: repeat the instruction unchanged
    RANDOMIZED = "randomized"  # RQ2: arm drawn per eligible failure point (seeded, logged)
    NONE = "none"  # ablation / open loop


@dataclass
class OrchestratorConfig:
    session_id: str = "session-0"
    scope: str = "private"  # "private" (1:1) | "public" (test livestream)
    correction_mode: CorrectionMode = CorrectionMode.GRADIENT
    qc_enabled: bool = True
    max_requests: int | None = None  # stop after N requests (tests / batch runs)
    text_encode_s: float = 0.06  # part of the correction chain C [measured locally, M0 teacher text encode]
    restart_decision_wait_s: float = 1.5  # after an interruption, wait this long for an in-flight decision
    loop_lag_log_s: float = 0.2  # log event-loop stalls longer than this (diagnostic)
    seed: int = 0


_FORGET = re.compile(r"(忘掉|忘了|忘记|删掉|删除|别记|不要记)")


def audio_onset_s(chunk: Chunk, threshold: float = 0.02, window_s: float = 0.02) -> float | None:
    """Offset (s) of the first 20 ms window whose RMS exceeds ``threshold``; None if silent/absent."""
    a = chunk.audio
    if a is None or len(a) == 0:
        return None
    a = np.asarray(a, dtype=np.float32)
    a = a.mean(axis=1) if a.ndim == 2 else a
    w = max(1, int(window_s * chunk.sample_rate))
    n = len(a) // w
    if n == 0:
        return None
    rms = np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(axis=1))
    idx = np.nonzero(rms > threshold)[0]
    return float(idx[0] * w / chunk.sample_rate) if len(idx) else None


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
        self.chunk_start: dict[tuple[int, int], float] = {}
        self.next_lock = 0
        self._tasks: list[asyncio.Task] = []
        self._aux: set[asyncio.Task] = set()
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()  # cleared while an erasure quiesces locking
        self._ready.set()
        self._rng = random.Random(self.cfg.seed)
        self._chain_costs: list[float] = []
        self._checked: set[int] = set()
        self._onset_done: set[int] = set()
        self._claims: dict[int, list[tuple[str, int | None]]] = {}  # request -> [(chain, step)]
        self.dropped: set[int] = set()  # requests discarded by a barge-in / erasure (never fully shown)
        self.error: BaseException | None = None
        self.last_presented_end: float | None = None
        self._decisions = 0  # completed responder decisions
        self._decisions_at_interrupt = 0

    @property
    def n_chunks(self) -> int:
        return self.gen.info.chunks_per_request

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        await self.gen.start()
        self._tasks = [asyncio.create_task(self._guarded(self._lock_loop(), "lock_loop")),
                       asyncio.create_task(self._guarded(self._chunk_loop(), "chunk_loop")),
                       asyncio.create_task(self._guarded(self._lag_monitor(), "lag_monitor", fatal=False))]

    async def _lag_monitor(self) -> None:
        """Diagnostic: an event-loop stall delays acks, barge-in and locks; log the long ones.
        A watchdog thread records the loop thread's stack while it is stalled (where=stack)."""
        import sys
        import threading
        import traceback

        beat = [now()]
        loop_thread = threading.get_ident()
        stacks: list[str] = []

        def watchdog() -> None:
            import time as _t

            while not self._stop.is_set():
                _t.sleep(0.1)
                if now() - beat[0] > 0.5 and not stacks:
                    frame = sys._current_frames().get(loop_thread)
                    if frame is not None:
                        stacks.append("".join(traceback.format_stack(frame)[-8:]))

        threading.Thread(target=watchdog, daemon=True).start()
        while not self._stop.is_set():
            beat[0] = now()
            if stacks:
                self.log.emit(EventType.ERROR, now(), where="event_loop_stack", error=stacks.pop(), fatal=False)
            t = now()
            await asyncio.sleep(0.05)
            lag = now() - t - 0.05
            if lag > self.cfg.loop_lag_log_s:
                self.log.emit(EventType.ERROR, now(), where="event_loop", error=f"loop stalled {lag:.3f} s",
                              fatal=False, lag_s=lag)

    async def _guarded(self, coro, name: str, fatal: bool = True) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a failed loop must end the session visibly
            self.log.emit(EventType.ERROR, now(), where=name, error=f"{type(e).__name__}: {e}", fatal=fatal)
            if fatal:
                self.error = e
                self._stop.set()

    def _spawn(self, coro, name: str) -> None:
        """Auxiliary work (QC of one request): a failure is logged, the session continues."""
        t = asyncio.create_task(self._guarded(coro, name, fatal=False))
        self._aux.add(t)
        t.add_done_callback(self._aux.discard)

    async def stop(self) -> None:
        self._stop.set()
        tasks = [*self._tasks, *self._aux]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.log.emit(EventType.OBSERVATION_END, self.last_presented_end or now())
        try:
            await self.gen.close()
        finally:
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
            tl = None
            while not self._stop.is_set():
                tl = self.sched.lock_time(k)
                if tl is not None and tl <= now():
                    break
                await asyncio.sleep(0.01 if tl is None else min(0.05, tl - now()))
            # Never run more than two requests ahead of presentation (bounded backlog).
            while k >= 2 and not self._resolved(k - 2) and not self._stop.is_set():
                await asyncio.sleep(0.01)
            await self._ready.wait()  # erasure in progress
            if k == self.sched.restart and k > 0:
                # After an interruption nothing is playing: a short wait for the in-flight decision
                # avoids spending the first 5-s request on a filler (listen) segment.
                t_wait = now() + self.cfg.restart_decision_wait_s
                while self._decisions == self._decisions_at_interrupt and now() < t_wait \
                        and not self._stop.is_set():
                    await asyncio.sleep(0.01)
            if self._stop.is_set():
                return
            script = self.director.next_script(k)
            self._audit(script)
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
                          step=script.provenance.get("step"), revision=script.provenance.get("revision"),
                          checks=[{"qid": q.qid, "text": q.text, "kind": q.kind} for q in script.checks])
            if script.transcript and self.memory:
                # lineage: None = linked to every memory recalled this session (over-links, so
                # erasure/correction reach it); a None return is a refused (scope-violating) write
                rec = self.memory.on_persona_line(script.transcript, session_id=self.cfg.session_id,
                                                  scope=self.cfg.scope)
                if rec is None and getattr(self.memory, "scope_violations", None):
                    self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False,
                                  issues=["persona_line_not_recorded"],
                                  detail=str(self.memory.scope_violations[-1]))
            claims = [(c, s) for c, rid, s in self._drain(self.director.events.completion_claims) if rid == k]
            if claims:
                self._claims[k] = claims  # logged when the line is actually heard (speech onset)
            self._drain_director_events(t)

    def _audit(self, script: BlockScript) -> None:
        """Pre-generation script audit (§15): the model cannot be steered word by word, so the
        script is checked before it is generated. Shared by all conditions (safety substrate)."""
        issues = []
        for term in self.director.erased_terms:
            if term in script.transcript or term in script.action or any(term in c for c in script.corrections):
                script.transcript = script.transcript.replace(term, "")
                script.action = script.action.replace(term, "")
                script.corrections = [c for c in script.corrections if term not in c]
                issues.append("erased_term")
        if len(script.transcript) > 2 * CHARS_PER_REQUEST:
            script.transcript = script.transcript[: 2 * CHARS_PER_REQUEST]
            issues.append("too_long")
        self.log.emit(EventType.AUDIT, now(), request_index=script.request_index, ok=not issues, issues=issues)

    def _drain_director_events(self, t: float) -> None:
        ev = self.director.events
        for chain_id, reason in self._drain(ev.refusals):
            self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason)
        for chain_id, reason in self._drain(ev.degradations):
            self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason, degraded=True)
        for chain_id, revision in self._drain(ev.capacity_skips):
            self.log.emit(EventType.CAPACITY_SKIP, t, chain_id=chain_id, revision=revision)
        for original, cleaned in self._drain(ev.narration_guards):
            self.log.emit(EventType.NARRATION_GUARD, t, original=original, cleaned=cleaned)

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
            if ch.chunk_index == self.n_chunks - 1:
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
        if request_index in self.dropped:
            return  # late ack of interrupted content: not evidence
        if chunk_index == 0:
            self.sched.on_presented(request_index, t_start)
            self.director.ledger.mark_presented(request_index)
        self.presented[request_index].add(chunk_index)
        self.chunk_start[(request_index, chunk_index)] = t_start
        self.last_presented_end = max(self.last_presented_end or t_end, t_end)
        self.log.emit(EventType.CHUNK_PRESENTED, t_start, request_index=request_index,
                      chunk_index=chunk_index, t_end=t_end)
        self._maybe_onset(request_index, chunk_index, t_start)
        if len(self.presented[request_index]) == self.n_chunks and request_index not in self._checked:
            self._checked.add(request_index)
            if self.cfg.qc_enabled:
                self._spawn(self._run_checks(request_index, t_evidence=t_end), "qc")
        self._maybe_finish()

    def _maybe_onset(self, k: int, ci: int, t_start: float) -> None:
        """Speech onset / completion claim time = presentation time of the first audible audio
        of a request that carries a line (energy onset in the presented chunk)."""
        script = self.scripts.get(k)
        if k in self._onset_done or script is None or not script.transcript:
            return
        chunk = next((c for c in self.chunks.get(k, []) if c.chunk_index == ci), None)
        off = audio_onset_s(chunk) if chunk is not None else None
        if off is None:
            if ci < self.n_chunks - 1:
                return  # silent chunk: look at the next one
            if 0 not in self.presented[k]:
                return
            t, source = self.chunk_start.get((k, 0), t_start), "request_start"  # no audible audio found
        else:
            t, source = t_start + off, "audio_energy"
        self._onset_done.add(k)
        self.log.emit(EventType.SPEECH_ONSET, t, request_index=k, chain_ids=script.chain_ids,
                      onset_source=source)
        for chain_id, step in self._claims.pop(k, []):
            self.log.emit(EventType.COMPLETION_CLAIM, t, request_index=k, chain_id=chain_id, step=step,
                          text=script.transcript)

    def _maybe_finish(self) -> None:
        m = self.cfg.max_requests
        if m is None:
            return
        last = m - 1
        done = last in self.dropped or len(self.presented.get(last, ())) == self.n_chunks
        if done and all(self._resolved(k) for k in range(m)):
            self._stop.set()

    # ------------------------------------------------------------------ QC
    async def _run_checks(self, k: int, t_evidence: float) -> None:
        script = self.scripts.get(k)
        if script is None or not script.checks or self.director.mode == DirectorMode.OPEN_LOOP:
            return
        chunks = list(self.chunks[k])
        action_verdicts: list[Verdict] = []
        revision, step = script.provenance.get("revision"), script.provenance.get("step")
        for q in script.checks:
            if q.kind == "speech":
                if self.speech_check is None:
                    continue
                v = await asyncio.to_thread(self.speech_check.check, q, script.transcript, chunks, k, t_evidence)
            elif self.judge is not None:
                v = await self.judge.judge(q, chunks, k, t_evidence)
            else:
                continue
            if k in self.dropped:
                return
            if q.kind == "action":
                action_verdicts.append(v)
            self.log.emit(EventType.VERDICT, v.t_verdict, request_index=k, qid=v.qid, kind=q.kind,
                          label=v.label.value, confidence=v.confidence, rationale=v.rationale,
                          t_evidence=t_evidence, source="online_monitor", chain_ids=script.chain_ids,
                          revision=revision, step=step)
            self.director.ledger.record_verdict(k, v.qid, v.label.value)
        intent = script.provenance.get("intent", "")
        for chain_id in script.chain_ids:
            if action_verdicts and all(v.label == VerdictLabel.COMPLIED for v in action_verdicts):
                self.director.on_verified(chain_id, intent, k, t_evidence, revision=revision, step=step)
            elif any(v.label == VerdictLabel.NOT_COMPLIED for v in action_verdicts):
                await self._repair(chain_id, intent, script, action_verdicts, t_evidence)
        self._drain_director_events(now())

    async def _repair(self, chain_id: str, intent: str, script: BlockScript, failed: list[Verdict],
                      t_evidence: float) -> None:
        mode = self.cfg.correction_mode
        if mode == CorrectionMode.NONE:
            return
        if mode == CorrectionMode.RANDOMIZED:
            mode = self._rng.choice([CorrectionMode.GRADIENT, CorrectionMode.REPEAT])
        if mode == CorrectionMode.GRADIENT:
            qtext = {q.qid: q.text for q in script.checks}
            sentence = await self.corrector.correction(script.action, failed, qtext)
        else:
            sentence = ""
        # C = everything between the evidence time E and a lockable correction: VLM verdict,
        # correction synthesis, compile/audit (measured here) + text encoding (measured in M0).
        t0 = now()
        compile_prompt(BlockScript(request_index=script.request_index, plan_version=script.plan_version,
                                   canon=script.canon, action=script.action, transcript="",
                                   corrections=[sentence] if sentence else []))
        cost = (now() - t_evidence) + self.cfg.text_encode_s
        self._chain_costs.append(cost)
        j = self.sched.earliest_correctable(t_evidence, cost, self.next_lock)
        queued = self.director.queue_retry(chain_id, intent, correction=sentence,
                                           failed_request=script.request_index,
                                           revision=script.provenance.get("revision"),
                                           step=script.provenance.get("step"), min_request=j)
        self.log.emit(EventType.REPAIR, now(), request_index=script.request_index,
                      chain_id=chain_id, mode=mode.value, correction=sentence, queued=queued,
                      earliest_correctable=j, next_unlocked=self.next_lock, chain_cost_s=cost,
                      compile_s=now() - t0, step=script.provenance.get("step"),
                      revision=script.provenance.get("revision"))

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
        cut = []
        for k in range(self.next_lock):
            if len(self.presented.get(k, ())) < self.n_chunks and k not in self.dropped:
                if k in self.scripts:
                    cut.append(self.scripts[k])
                self.dropped.add(k)
                self._claims.pop(k, None)  # a claim that is never heard is not a claim
                self.director.ledger.mark_generated_not_presented(k)
        self.director.on_interrupted(cut)
        await self.transport.stop_playback()
        self.sched.interrupt(self.next_lock)
        self._decisions_at_interrupt = self._decisions

    async def on_user_utterance(self, utt: Utterance) -> dict[str, Any]:
        try:
            return await self._on_user_utterance(utt)
        finally:
            self._decisions += 1

    async def _on_user_utterance(self, utt: Utterance) -> dict[str, Any]:
        self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text)
        # A forget request must not recall the very fact it asks to erase into the responder.
        memories = None
        if self.memory and not _FORGET.search(utt.text):
            memories = self.memory.recall(utt.text, mode=self.cfg.scope)
        if self.memory:
            self.memory.on_user_utterance(utt)
        decision = await self.director.on_user_utterance(utt, memories)
        term = (decision or {}).get("forget_term")
        if term and self.memory is not None and hasattr(self.memory, "forget"):
            await self._erase(term)
        self._drain_director_events(now())
        if term:  # the decision itself names the erased term
            decision = json.loads(json.dumps(decision, ensure_ascii=False).replace(term, "[已删除]"))
        self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
                      chains={c.chain_id: c.status.value for c in self.director.chains.values()})
        return decision

    async def _erase(self, term: str) -> None:
        """Erasure (proposal §12): quiesce locking, memory cascade, purge controller state and
        stored prompts, drop unpresented content, restart the generator from canon. Fails closed:
        an incomplete memory erasure is logged as an ERROR."""
        self._ready.clear()
        ack = getattr(self.memory, "acknowledge_erasure", None)
        report = None

        def acknowledge(target: str, ok: bool, detail: str = "") -> None:
            if ack is not None and report is not None:
                ack(report, target, ok=ok, detail=detail)

        try:
            report = self.memory.forget(term)
            purged = self.director.purge(term)
            acknowledge("unsent_scripts", True, f"controller items purged: {purged}")
            # The responder is stateless per call; its context is rebuilt from purged state.
            acknowledge("llm_context", True, "stateless responder; memory notes and chains purged")
            for k, s in self.scripts.items():
                if term in s.transcript or term in s.action:
                    s.transcript = s.transcript.replace(term, "[已删除]")
                    s.action = s.action.replace(term, "[已删除]")
                if term in self.prompts.get(k, ""):
                    self.prompts[k] = self.prompts[k].replace(term, "[已删除]")
            self.log.redact(term)  # in memory and in the JSONL file
            await self._drop_unpresented()
            self.director.ledger.generated_not_presented.clear()  # erased content must not be bridged to
            try:
                await self.gen.reset()
                acknowledge("generator_state", True, "generator session reset to canon")
            except Exception as e:  # noqa: BLE001
                acknowledge("generator_state", False, f"reset failed: {e}")
            recorder = getattr(self.transport, "recorder", None)
            if recorder is None:
                acknowledge("recordings", True, "event log redacted; no media recording")
            else:  # presented audio/video cannot be redacted by text replacement
                acknowledge("recordings", False, f"media recording {getattr(recorder, 'path', '')} must be deleted")
        finally:
            self._ready.set()
        complete = getattr(report, "complete", True)
        pending = list(getattr(report, "pending_targets", []) or [])
        self.log.emit(EventType.PLAYBACK_STOP, now(), erasure=True,
                      deleted=len(getattr(report, "deleted_ids", []) or []),
                      kinds=getattr(report, "kinds", None), controller_purged=purged,
                      generator_reset=True, erasure_complete=complete, pending_targets=pending)
        if not complete:
            self.log.emit(EventType.ERROR, now(), where="erasure", error="memory erasure incomplete",
                          detail=str(getattr(report, "errors", "")))
        self._maybe_finish()

    def open_chains(self) -> list[str]:
        return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]
