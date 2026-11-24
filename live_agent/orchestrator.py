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
import html
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Protocol

import numpy as np

from live_agent.director.director import CHARS_PER_REQUEST, Director, DirectorMode, board_mentions
from live_agent.generator.base import Generator
from live_agent.prompt.h3_compiler import PromptError, compile_prompt
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


ANSWER_BOARD_PROMPT = """学生问：「{question}」
老师口头回答：「{answer}」
请为这个回答写黑板板书，只输出 JSON：{{"title": 标题（不超过 12 字）, "items": [2-4 条板书要点，每条不超过 30 字，公式写在 $...$ 里（LaTeX）]}}
板书只写回答里讲到的内容，简洁准确，像老师真正写在黑板上的。"""


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
    loop_stack_s: float = 0.15  # the watchdog captures the loop thread's stack after this long
    qc_timeout_s: float = 8.0  # a check that takes longer abstains (verdict unknown) [proposed target]
    # Presentation policy: a request with no scripted line is silent. H3 still emits soft hums on such
    # requests ("嗯…" measured on idle audio, 2026-09-27) despite the prompt, so its audio is muted
    # (short fade) before it reaches the viewer. The raw audio is kept in the generated-stream record.
    mute_silent_requests: bool = True
    mute_fade_s: float = 0.03
    # Scene continuity (ledger props): count the props on presented frames every N-th request and queue a
    # correction for the next unlocked request when every sampled frame shows the wrong number
    continuity_every: int = 2
    # A comment (typed or spoken) does not cut the video: already generated content keeps playing and the
    # player switches to the reply at the moment the reply's first chunk is ready (erasure still cuts at once)
    soft_switch: bool = True
    lesson_lookahead: int = 6  # generate the next lesson section once fewer lines than this are waiting (~30 s)
    # self-check of every generated section against the lesson-quality checklist (configs/curriculum/teaching_craft
    # .json): "off"; "log" (background editorial scores); "revise" (every section is reviewed before
    # presentation, rewritten once if weak, and reviewed again; known failed material is withheld).
    lesson_self_check: str = "log"
    lesson_revise_deadline_s: float = 60.0  # configuration target: bounded review/rewrite/review
    # student attention (opt-in camera): nudge during a lesson after this many consecutive distracted/absent checks
    attention_nudge_after: int = 2
    attention_cooldown_s: float = 20.0
    switch_decision_wait_s: float = 10.0  # while old video plays, wait this long for the reply decision
    # the generator waits for every request's prompt (vLLM-Omni taomate_h3_hold_for_prompt): old video does NOT keep
    # playing while we wait, so a pending switch waits no longer than after an interruption (seen live: an 8 s
    # freeze while the hosted LLM decided); an undecided reply then gets a listening request first
    generator_holds: bool = False
    continuity_cooldown: int = 3  # requests between two corrections of the same prop
    continuity_max_fixes: int = 2  # corrections per prop without effect before giving up on it (logged)
    blocklist: tuple[str, ...] = ()  # operator term blocklist for the script audit (no moderation model)
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
        # Lock gates with single owners: an erasure's gate can only be released by that erasure
        # (fail closed); a barge-in's gate only by that barge-in.
        self._ready = asyncio.Event()  # erasure gate
        self._ready.set()
        self._barge_gate = asyncio.Event()
        self._barge_gate.set()
        self._erase_lock = asyncio.Lock()
        self.chunk_end: dict[tuple[int, int], float] = {}
        self.last_paint: dict[tuple[int, int], float] = {}
        self._fully_presented: set[int] = set()
        self._continuity_fixed: dict[str, int] = {}  # prop label -> request that carried its last correction
        self._home_pose = director.ledger.pose  # the pose the desk props are framed in
        self._continuity_tries: dict[str, int] = {}  # prop label -> corrections issued since it was last right
        self._anchored = False  # the first continuity check of a generator session sets the anchor
        self._switch_pending = False  # a comment arrived; old video plays until the reply is ready
        self._switch_target: int | None = None  # first request locked with the reply (line or action)
        self._switch_plan = 0
        self._lesson_task: asyncio.Task | None = None
        self.attention = None  # attention.AttentionMonitor, set by the app when a VLM is available
        self._camera_pending: bytes | None = None  # latest frame only, never an unbounded queue
        self._camera_task: asyncio.Task | None = None
        self._camera_epoch = 0
        self._last_nudge = -1e9
        self._nudge_i = 0
        self._episode: tuple[str | None, int] = (None, 0)  # (stable state, nudges given in this episode)
        self.image_maker = None  # board_images.ImageMaker (illustrations), set by the app when configured
        self.figure_dir = None  # where exact plots are drawn (board_plot); set by the app
        self._answer_figure_boards: set[str] = set()  # one visual-planning call per answer
        self.student = None  # student.StudentProfile (private sessions): adapts lessons, records exercise results
        self.profile_store = None  # student.ProfileStore shared with the profile page (set by the app)
        self.curriculum = None  # curriculum.Curriculum: course knowledge base (grade profiles, standards; set by the app)
        self._lesson_mistakes: list[str] = []  # this lesson's wrong answers, addressed by the next section
        self._exercises = 0
        self._shown_exercise = None  # the exercise the page was last told about
        self.answer_boards = False  # persona with a board: every knowledge answer gets one (set by the app)
        self.teaching = True  # persona runs classroom features (lessons/exercises/profiles); the app clears it
        # for a live persona (D-068); direct constructions keep the classroom default
        self._profile_epoch = 0  # bumped by erasure and profile resets: work started before it must not write to the profile
        self._profile_resets = 0  # the store's reset count last seen
        self._rng = random.Random(self.cfg.seed)
        self._chain_costs: list[float] = []
        self._checked: set[int] = set()
        self._onset_done: set[int] = set()
        self._claims: dict[int, list[tuple[str, int | None]]] = {}  # request -> [(chain, step)]
        self._claim_rev: dict[int, int | None] = {}
        self.dropped: set[int] = set()  # requests discarded by a barge-in / erasure (never fully shown)
        self.error: BaseException | None = None
        self.last_presented_end: float | None = None
        # optional recording of *everything generated* (incl. chunks later dropped by a barge-in)
        self.gen_recorder = None
        self.gen_recorder_factory = None  # () -> new recorder (next part after an erasure)
        self._decisions = 0  # completed responder decisions
        self._input_epoch = 0  # bumped by every barge-in; decisions from older epochs are discarded
        self.painted: dict[tuple[int, int], list[int] | None] = {}  # client-reported painted frame indices
        self._decisions_at_interrupt = 0
        self._locking: int | None = None
        self._qc_epoch = 0  # bumped by erasure: pending QC results are discarded
        self._onset_uncertain: set[int] = set()
        self._barge_t = 0.0

    @property
    def n_chunks(self) -> int:
        return self.gen.info.chunks_per_request

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        store = getattr(self.memory, "store", None)
        if store is not None and hasattr(store, "recover_interrupted"):
            store.recover_interrupted()  # finish the DB side of any erasure interrupted by a crash
        pending = getattr(self.memory, "pending_erasures", lambda: [])() if self.memory else []
        if pending:
            # An earlier erasure is not complete (e.g. a purge target failed): fail closed — no
            # content is generated until an operator resumes it (MemoryBridge.resume_erasure).
            self._ready.clear()
            self.log.emit(EventType.ERROR, now(), where="erasure",
                          error="pending erasure receipt(s): session paused (fail closed)",
                          receipts=[getattr(r, "receipt_id", None) or (r.get("receipt_id") if isinstance(r, dict) else str(r))
                                    for r in pending])
        await self.gen.start()
        self._tasks = [asyncio.create_task(self._guarded(self._lock_loop(), "lock_loop")),
                       asyncio.create_task(self._guarded(self._chunk_loop(), "chunk_loop")),
                       asyncio.create_task(self._guarded(self._lag_monitor(), "lag_monitor", fatal=False)),
                       asyncio.create_task(self._guarded(self._deadline_sweeper(), "deadline_sweeper"))]

    async def _deadline_sweeper(self) -> None:
        """Independent step-deadline expiry (closed loop): every open action/multistep chain reaches
        a terminal state by its current step's deadline, whatever happened to QC (abstention,
        'unknown', no repair mode, frames not presented)."""
        if self.director.mode != DirectorMode.CLOSED_LOOP:
            return
        from live_agent.types import TaskKind

        while not self._stop.is_set():
            t = now()
            for c in list(self.director.chains.values()):
                if c.status != ChainStatus.OPEN or c.kind not in (TaskKind.ACTION, TaskKind.MULTISTEP):
                    continue
                if self.director.awaiting_decision and t - self._barge_t < 10.0 * self.sched.cfg.time_scale:
                    continue  # a barge-in decision may revise this chain; it decides first (bounded wait)
                base = self.director.step_base_t.get(c.chain_id, c.clock_origin)
                if t > base + 15.0 * self.sched.cfg.time_scale:  # action step D [proposed target, §7]
                    self.director.expire(c.chain_id, len(c.revisions))
                    self.log.emit(EventType.AUDIT, t, ok=False, issues=["step_deadline_expired"],
                                  chain_id=c.chain_id, revision=len(c.revisions))
            self._drain_director_events(t)
            await asyncio.sleep(0.1)

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

            captured_for = None
            while not self._stop.is_set():
                _t.sleep(0.02)
                stalled_since = beat[0]
                if now() - stalled_since > self.cfg.loop_stack_s and captured_for != stalled_since:
                    captured_for = stalled_since  # one stack per stall
                    frames = sys._current_frames()
                    frame = frames.get(loop_thread)
                    if frame is not None:
                        # other threads too: a C extension holding the GIL elsewhere also stalls the loop
                        others = [f"[thread {tid}]\n" + "".join(traceback.format_stack(f)[-3:])
                                  for tid, f in frames.items() if tid not in (loop_thread, threading.get_ident())]
                        stacks.append("".join(traceback.format_stack(frame)[-8:]) + "\n--- other threads ---\n"
                                      + "\n".join(others)[-3000:])

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

    def _spawn(self, coro, name: str) -> asyncio.Task:
        """Auxiliary work (QC of one request): a failure is logged, the session continues."""
        t = asyncio.create_task(self._guarded(coro, name, fatal=False))
        self._aux.add(t)

        def done(task: asyncio.Task) -> None:
            self._aux.discard(task)
            self._maybe_finish()

        t.add_done_callback(done)
        return t

    async def stop(self, drain_s: float = 30.0) -> None:
        """Cancellation-safe: tasks are cancelled, the generator closed and the log closed even if
        this call is cancelled (the cancellation is re-raised afterwards)."""
        self._stop.set()
        self.camera_off()
        cancelled = None
        try:
            if self._aux:  # let running QC of already-presented requests finish (bounded)
                await asyncio.wait(list(self._aux), timeout=drain_s)
        except asyncio.CancelledError as e:
            cancelled = e
        tasks = [*self._tasks, *self._aux]
        for t in tasks:
            t.cancel()
        try:
            await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
        except asyncio.CancelledError as e:
            cancelled = cancelled or e
        self.log.emit(EventType.OBSERVATION_END, self.last_presented_end or now())
        if self.gen_recorder is not None:
            await asyncio.to_thread(self.gen_recorder.close)
        close = asyncio.ensure_future(self.gen.close())
        while not close.done():  # finish worker shutdown even if this call is cancelled meanwhile
            try:
                await asyncio.shield(close)
            except asyncio.CancelledError as e:
                cancelled = cancelled or e
            except Exception:  # noqa: BLE001 - close errors are logged by the adapter
                break
        self.log.close()
        if cancelled is not None:
            raise cancelled

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
            lock_reason = "scheduled"
            while not self._stop.is_set():
                tl = self.sched.lock_time(k)
                # A reviewed reply can arrive after the restart wait expired
                # and a silent filler was locked. Do not wait for that filler's
                # playback deadline: the soft switch already drops old media
                # once the reply is ready. Holding generators retain JIT pacing.
                if self._switch_pending and self._switch_target is None \
                        and self._decisions != self._decisions_at_interrupt and not self.cfg.generator_holds:
                    lock_reason = "ready_soft_switch"
                    break
                if tl is not None and tl <= now():
                    break
                await asyncio.sleep(0.01 if tl is None else min(0.05, tl - now()))
            # Never run more than two requests ahead of presentation (bounded backlog); a pending soft
            # switch may lock the reply anyway (the old requests are dropped when it is ready)
            while k >= 2 and not self._resolved(k - 2) and not self._stop.is_set() \
                    and not (self._switch_pending and self._switch_target is None):
                await asyncio.sleep(0.01)
            await self._ready.wait()  # erasure in progress (only the erasure releases it)
            await self._barge_gate.wait()
            if k == self.sched.restart and k > 0:
                # After an interruption nothing is playing: a short wait for the in-flight decision
                # avoids spending the first 5-s request on a filler (listen) segment.
                free = self._switch_pending and not self.cfg.generator_holds  # old video still plays: waiting is free
                t_wait = now() + (self.cfg.switch_decision_wait_s if free else self.cfg.restart_decision_wait_s)
                while self._decisions == self._decisions_at_interrupt and now() < t_wait \
                        and not self._stop.is_set():
                    await asyncio.sleep(0.01)
            if self._stop.is_set():
                return
            if not self._ready.is_set():
                continue  # an erasure started while waiting: re-check the gates
            for tm in self.gen.timings:  # refresh: t_done etc. arrive after the last chunk
                self.sched.observe_timing(tm)
            self._locking = k  # from popping the segment until the lock is recorded
            script = self.director.next_script(k)
            self._exercise_changed()
            self._audit(script)
            try:
                prompt = compile_prompt(script, first_request=(k == 0))
            except PromptError as e:
                # a bad correction/line must not end the session: drop the optional parts, log it
                self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False, issues=["prompt_rejected"],
                              detail=str(e))
                script.corrections, script.transcript = [], ""
                prompt = compile_prompt(script, first_request=(k == 0))
            self.scripts[k], self.prompts[k] = script, prompt
            t = now()
            await self.gen.submit(k, prompt)
            self.sched.on_lock(k, t)
            self.next_lock = k + 1
            self._locking = None
            if self._switch_pending and self._switch_target is None and script.plan_version >= self._switch_plan:
                if script.chain_ids or script.transcript:
                    self._switch_target = k  # the reply: playback switches to it when its first chunk is ready
                elif self._decisions != self._decisions_at_interrupt:
                    self._switch_pending = False  # decided, but nothing to say or do: no switch, nothing cut
            self.log.emit(EventType.LOCK, t, request_index=k, plan_version=script.plan_version,
                          lambda_est=self.sched.lambda_estimate(), planned_lock=tl,
                          lock_reason=lock_reason,
                          action=script.action, transcript=script.transcript,
                          chain_ids=script.chain_ids, corrections=script.corrections,
                          capability_ids=script.capability_ids, prompt=prompt,
                          step=script.provenance.get("step"), revision=script.provenance.get("revision"),
                          board=({"key": script.board["key"], "reveal": script.board.get("reveal"),
                                  "progress": script.board.get("progress")} if script.board else None),
                          retry_of=script.provenance.get("retry_of"),
                          checks=[{"qid": q.qid, "text": q.text, "kind": q.kind} for q in script.checks])
            if script.transcript and self.memory:
                # lineage: None = linked to every memory recalled this session (over-links, so
                # erasure/correction reach it); a None return is a refused (scope-violating) write
                # The bridge computes lineage from the recall token it issued for this line's
                # decision; template / verified lines (no memory input) get an empty token.
                token = script.provenance.get("recall_id")
                if token is None and script.provenance.get("memory_ids") == [] and hasattr(self.memory, "no_recall"):
                    token = self._no_recall()  # template / verified line: no memory input
                try:
                    rec = self.memory.on_persona_line(script.transcript, session_id=self.cfg.session_id,
                                                      scope=self.cfg.scope, recall_id=token, request_index=k)
                except TypeError:  # simple memory ports without lineage support
                    rec = self.memory.on_persona_line(script.transcript, session_id=self.cfg.session_id,
                                                      scope=self.cfg.scope)
                if rec is None and getattr(self.memory, "scope_violations", None):
                    self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False,
                                  issues=["persona_line_not_recorded"],
                                  detail=str(self.memory.scope_violations[-1]))
            claims = [(c, s) for c, rid, s in self._drain(self.director.events.completion_claims) if rid == k]
            self._claim_rev[k] = script.provenance.get("revision")
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
        for term in self.cfg.blocklist:
            if term and (term in script.transcript or term in script.action):
                # withhold the whole segment; its chain is refused and nothing can verify it later
                script.transcript, script.action, script.checks = "", "", []
                for cid in script.chain_ids:
                    self.director._fail_chain(cid, ChainStatus.REFUSED)
                    self.director.events.refusals.append((cid, "audit: blocklisted content withheld"))
                script.chain_ids = []
                issues.append("blocklisted")
                break
        for term in self.cfg.blocklist:  # corrections are prompt text too
            if term and any(term in c for c in script.corrections):
                script.corrections = [c for c in script.corrections if term not in c]
                issues.append("blocklisted_correction")
        too_long = [c for c in script.corrections if len(c) > 200]  # compiler limit per correction
        if too_long:
            script.corrections = [c for c in script.corrections if len(c) <= 200]
            issues.append("correction_too_long")
        if len(script.transcript) > 2 * CHARS_PER_REQUEST:
            script.transcript = script.transcript[: 2 * CHARS_PER_REQUEST]
            issues.append("too_long")
        self.log.emit(EventType.AUDIT, now(), request_index=script.request_index, ok=not issues, issues=issues)

    def _drain_director_events(self, t: float) -> None:
        ev = self.director.events
        rev = lambda cid: len(self.director.chains[cid].revisions) if cid in self.director.chains else None  # noqa: E731
        timeout_requests = self._drain(ev.exercise_timeout_requests)
        for i, concept in enumerate(self._drain(ev.exercise_timeouts)):
            request_id = timeout_requests[i] if i < len(timeout_requests) else None
            correlation = {"request_id": request_id} if request_id is not None else {}
            self.log.emit(EventType.LESSON, t, stage="exercise_timeout", concept=concept, **correlation)
        for chain_id, reason in self._drain(ev.refusals):
            self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason, revision=rev(chain_id))
        for chain_id, reason in self._drain(ev.degradations):
            self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason, degraded=True,
                          revision=rev(chain_id))
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
            # A speech-timed generator knows the full utterance length before
            # rendering chunk 0. Use it before playback can start, even when
            # later chunks take longer to render or deliver.
            duration = ch.meta.get("request_duration_s") if ch.chunk_index == 0 else None
            if type(duration) in (int, float) and np.isfinite(duration) and duration > 0:
                self.sched.on_duration(ch.request_index, duration)
            if self.gen_recorder is not None:
                self.gen_recorder.write(ch)  # background-thread encoding
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
            if self._switch_pending and ch.request_index == self._switch_target and ch.chunk_index == 0:
                await self._switch_to(ch.request_index)
            if ch.request_index in self.dropped:
                if ch.chunk_index == self.n_chunks - 1:
                    self._evict(ch.request_index)
                continue  # generated before a barge-in: never shown
            script = self.scripts.get(ch.request_index)
            if script is not None:
                if self.cfg.mute_silent_requests and not script.transcript and ch.audio is not None:
                    ch = self._muted(ch)
                self._last_sent_silent = not script.transcript
                await self.transport.send_chunk(ch, script)

    def _muted(self, ch: Chunk) -> Chunk:
        """Silence a chunk of a no-line request; fade out if the previous chunk was audible."""
        from dataclasses import replace

        a = np.asarray(ch.audio, dtype=np.float32)
        out = np.zeros_like(a)
        if not getattr(self, "_last_sent_silent", True):
            n = min(len(a), int(self.cfg.mute_fade_s * ch.sample_rate))
            ramp = np.linspace(1.0, 0.0, n, dtype=np.float32)
            out[:n] = a[:n] * (ramp[:, None] if a.ndim == 2 else ramp)
        return replace(ch, audio=out)

    # ------------------------------------------------------------------ presentation acks
    def on_received(self, request_index: int, chunk_index: int, t: float) -> None:
        """The client has the chunk decoded and ready to play: ready -> received is the delivery time
        (encode + transport + decode), which the lock lead must cover (a remote bridge adds ~1 s)."""
        ch = next((c for c in self.chunks.get(request_index, []) if c.chunk_index == chunk_index), None)
        if ch is not None and ch.t_ready:
            self.sched.observe_delivery(t - ch.t_ready)

    def on_presented(self, request_index: int, chunk_index: int, t_start: float, t_end: float,
                     painted: list[int] | None = None, t_last_paint: float | None = None) -> None:
        """Called by the transport when a chunk *finished* presenting (with its start/end times).
        ``painted``: indices of the chunk's frames the client actually displayed (None = all)."""
        if request_index in self.dropped:
            return  # late ack of interrupted content: not evidence
        self.painted[(request_index, chunk_index)] = painted
        if t_last_paint is not None:
            self.last_paint[(request_index, chunk_index)] = t_last_paint  # measured (client clock, mapped)
        if chunk_index == 0:
            self.sched.on_presented(request_index, t_start)
            self.director.ledger.mark_presented(request_index)
        self.presented[request_index].add(chunk_index)
        self.chunk_start[(request_index, chunk_index)] = t_start
        self.chunk_end[(request_index, chunk_index)] = t_end
        self.last_presented_end = max(self.last_presented_end or t_end, t_end)
        ch = next((c for c in self.chunks.get(request_index, []) if c.chunk_index == chunk_index), None)
        self.log.emit(EventType.CHUNK_PRESENTED, t_start, request_index=request_index,
                      chunk_index=chunk_index, t_end=t_end, n_frames=ch.n_frames if ch is not None else None,
                      chunks_per_request=self.n_chunks, request_complete=len(self.presented[request_index]) == self.n_chunks)
        self._maybe_onset(request_index, chunk_index, t_start)
        if len(self.presented[request_index]) == self.n_chunks and request_index not in self._checked:
            self._checked.add(request_index)
            self._fully_presented.add(request_index)
            self.director.ledger.mark_fully_presented(request_index)
            if request_index in self.scripts:
                self.director.on_request_presented(self.scripts[request_index],
                                                   done=set(self._fully_presented))  # dropped != shown
            if self.cfg.qc_enabled:
                self._spawn(self._run_checks(request_index, t_evidence=self._evidence_time(request_index, t_end)),
                            "qc")
            else:
                self._evict(request_index)
        self._maybe_finish()

    def _no_recall(self):
        try:
            return self.memory.no_recall(isolated_context=True)
        except TypeError:
            return self.memory.no_recall()

    def _chain_deadline(self, script: BlockScript) -> float | None:
        """Wall-clock deadline of the step this request serves: D (the check's ``deadline_s``,
        15 s for actions) from the chain origin, or from the previous step's verification."""
        c = self.director.chains.get(script.chain_ids[0]) if script.chain_ids else None
        d = next((q.deadline_s for q in script.checks if q.kind == "action"), None)
        if c is None or d is None:
            return None  # no action check: content/speech replies are not cut by an action deadline
        return self.director.step_base_t.get(c.chain_id, c.clock_origin) + d * self.sched.cfg.time_scale

    def _qc_budget(self, script: BlockScript) -> float:
        """A check may use at most qc_timeout_s and never runs past the step's deadline."""
        d = self._chain_deadline(script)
        remaining = self.cfg.qc_timeout_s if d is None else d - now()
        return min(self.cfg.qc_timeout_s, remaining)

    def _evidence_time(self, k: int, t_end: float) -> float:
        """E = presentation time of the last *painted* frame of the request, searched backwards
        over all chunks (a chunk without painted-frame reports counts as shown to its end)."""
        if getattr(self.transport, "avatar_mesh", False):
            capture_time = self.transport.avatar_evidence_time(k)
            if capture_time is not None:
                return capture_time
        for ci in range(self.n_chunks - 1, -1, -1):
            idx = self.painted.get((k, ci))
            start, end = self.chunk_start.get((k, ci)), self.chunk_end.get((k, ci))
            ch = next((c for c in self.chunks.get(k, []) if c.chunk_index == ci), None)
            if (k, ci) in self.last_paint:
                return self.last_paint[(k, ci)]  # measured paint time of the last displayed frame
            if idx is None:
                return end if end is not None else t_end
            if idx and ch is not None and start is not None and ch.n_frames:  # estimate from index
                return start + (max(idx) + 1) * ch.duration_s / ch.n_frames
        return t_end

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
            # the scripted line was never audible: no onset, and a claim that is not heard is no claim
            self._onset_done.add(k)
            dropped_claims = self._claims.pop(k, [])
            self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False, issues=["no_audible_speech"],
                          claims_not_heard=[c for c, _ in dropped_claims])
            return
        t = t_start + off
        self._onset_done.add(k)
        uncertain = k in self._onset_uncertain
        self.log.emit(EventType.SPEECH_ONSET, t, request_index=k, chain_ids=script.chain_ids,
                      onset_source="audio_energy_cut" if uncertain else "audio_energy",
                      revision=script.provenance.get("revision"), audibility="uncertain" if uncertain else "heard")
        for chain_id, step in self._claims.pop(k, []):
            self.log.emit(EventType.COMPLETION_CLAIM, t, request_index=k, chain_id=chain_id, step=step,
                          text=script.transcript, revision=self._claim_rev.get(k),
                          audibility="uncertain" if uncertain else "heard")

    def _audible_before_cut(self, k: int, ci: int, t_start: float) -> None:
        """A request cut while chunk ``ci`` was playing: speech onset (and a completion claim)
        that became audible before the cut was heard and is logged, not discarded."""
        if k in self._onset_done or k not in self.scripts or not self.scripts[k].transcript:
            return
        chunk = next((c for c in self.chunks.get(k, []) if c.chunk_index == ci), None)
        off = audio_onset_s(chunk) if chunk is not None else None
        if off is not None and t_start + off <= now():
            # energy onset within the played interval: *possibly* the line (a clink is also energy)
            self._onset_uncertain.add(k)
            self._maybe_onset(k, ci, t_start)

    def _maybe_finish(self) -> None:
        m = self.cfg.max_requests
        if m is None:
            return
        last = m - 1
        done = last in self.dropped or len(self.presented.get(last, ())) == self.n_chunks
        if done and all(self._resolved(k) for k in range(m)) and not self._aux:  # QC drained
            self._stop.set()

    # ------------------------------------------------------------------ QC
    def _presented_media(self, k: int) -> tuple[list[Chunk], int, int]:
        """The request's chunks restricted to frames the client reported as painted."""
        from dataclasses import replace

        if getattr(self.transport, "avatar_mesh", False):
            chunks, issue = self.transport.visual_evidence(k, self.chunks.get(k, []), self.painted)
            out, shown, total = [], 0, 0
            for ch in chunks:
                n = 0 if ch.video is None else len(ch.video)
                shown += n
                original = next((original for original in self.chunks.get(k, [])
                                 if original.chunk_index == ch.chunk_index), ch)
                total += original.n_frames if ch.meta.get("visual_source") == "server_video" else n
                out.append(replace(ch, meta={**ch.meta, "visual_evidence_issue": issue}))
            return out, shown, total
        out, shown, total = [], 0, 0
        for ch in self.chunks.get(k, []):
            n = 0 if ch.video is None else len(ch.video)
            idx = self.painted.get((k, ch.chunk_index))
            total += n
            if idx is None or ch.video is None:
                out.append(ch)
                shown += n
                continue
            keep = sorted(i for i in set(idx) if 0 <= i < n)
            shown += len(keep)
            if len(keep) == n:
                out.append(ch)  # everything shown: no copy (a copy is ~40 MB per chunk)
            else:
                out.append(replace(ch, video=ch.video[keep] if keep else ch.video[:0]))
        return out, shown, total

    def _evict(self, k: int) -> None:
        """Media is kept only until presentation and QC are done (a 30-min session would otherwise
        hold ~50 GiB of RGB frames [derived])."""
        self.chunks.pop(k, None)
        if getattr(self.transport, "avatar_mesh", False):
            self.transport.evict_request(k)
        for ci in range(self.n_chunks):
            self.painted.pop((k, ci), None)

    async def _run_checks(self, k: int, t_evidence: float) -> None:
        try:
            await self._run_checks_inner(k, t_evidence)
            if k % max(1, self.cfg.continuity_every) == 0:
                await self._continuity_check(k)
        finally:
            self._evict(k)

    async def _continuity_check(self, k: int) -> None:
        """Do the presented frames show every prop exactly as often as the ledger says? A prop counted
        wrong in *every* sampled frame (not a miscount or a brief occlusion) gets a correction sentence in
        the next unlocked request; duplicates always, missing props only in the home pose (standing up can
        take the desk out of frame)."""
        ledger = self.director.ledger
        expected = ledger.expected_counts()
        count = getattr(self.judge, "count_props", None)
        if not expected or count is None or k in self.dropped or self.director.mode == DirectorMode.OPEN_LOOP:
            return
        chunks, shown, total = await asyncio.to_thread(self._presented_media, k)  # large frame copies
        if not chunks or any(ch.meta.get("visual_evidence_issue") for ch in chunks) or (total and shown / total < 0.5):
            return
        try:
            counts = await asyncio.wait_for(count(chunks, list(expected)), timeout=self.cfg.qc_timeout_s)
        except Exception as e:  # noqa: BLE001 - abstain: a failed count is not evidence
            self.log.emit(EventType.CONTINUITY, now(), request_index=k, error=str(e)[:120])
            return
        if k in self.dropped:
            return
        target = self.next_lock + (1 if self._locking == self.next_lock else 0)
        anchored = []
        if not self._anchored:
            # the first checked shot of this generator session is the anchor: props it never drew leave the
            # inventory instead of being nagged about (the text follows the picture); duplicates still count
            self._anchored = True
            anchored = ledger.anchor(counts or {})
            expected = ledger.expected_counts()
        home_pose = ledger.pose == self._home_pose
        wrong, fixes = {}, []
        gave_up = []
        for label, want in expected.items():
            seen = [n for n in (counts or {}).get(label, []) if isinstance(n, int)]
            if not seen or any(n == want for n in seen):
                self._continuity_tries.pop(label, None)  # right again: a later drift gets fresh corrections
                continue  # at least one frame agrees: no consistent evidence of drift
            found = min(seen) if min(seen) > want else max(seen)
            if found < want and not home_pose:
                continue
            wrong[label] = seen
            last = self._continuity_fixed.get(label, -10**9)
            if target - last < self.cfg.continuity_cooldown:
                continue
            if self._continuity_tries.get(label, 0) >= self.cfg.continuity_max_fixes:
                gave_up.append(label)  # the model does not render it this way: stop repeating the sentence
                continue
            fix = ledger.continuity_fix(label, found, target)
            if fix:
                self.director.schedule_correction(target, fix)
                self._continuity_fixed[label] = target
                self._continuity_tries[label] = self._continuity_tries.get(label, 0) + 1
                fixes.append(fix)
        self.log.emit(EventType.CONTINUITY, now(), request_index=k, counts=counts, expected=expected,
                      wrong=wrong, corrections=fixes, target=target if fixes else None, gave_up=gave_up,
                      anchor_removed=anchored)

    async def _run_checks_inner(self, k: int, t_evidence: float) -> None:
        script = self.scripts.get(k)
        if script is None or not script.checks or self.director.mode == DirectorMode.OPEN_LOOP:
            return
        chunks, shown, total = await asyncio.to_thread(self._presented_media, k)  # large frame copies
        evidence_issue = next((ch.meta.get("visual_evidence_issue") for ch in chunks
                               if ch.meta.get("visual_evidence_issue")), None)
        if getattr(self.transport, "avatar_mesh", False) and not chunks:
            evidence_issue = "avatar_frames_missing"
        if not evidence_issue and total and shown / total < 0.5:
            # presentation of the visual evidence cannot be established: abstain (no verdict)
            self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False, issues=["frames_not_presented"],
                          painted_fraction=shown / total)
            return
        revision, step = script.provenance.get("revision"), script.provenance.get("step")
        qc_epoch = self._qc_epoch
        deadline = self._chain_deadline(script)  # action steps only (content has its own D, not enforced here)
        if deadline is not None and deadline <= now() and script.chain_ids:
            # past the step's deadline: no check, no late control transition (verification,
            # step release, repair); the step has failed by the preregistered rule
            for cid in script.chain_ids:
                self.director.expire(cid, revision)
            self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False, issues=["check_after_deadline"])
            self._drain_director_events(now())
            return
        actions = [q for q in script.checks if q.kind == "action"] if self.judge is not None else []
        # (no judge configured: no online action control; only the step deadline applies)
        speech = [q for q in script.checks if q.kind == "speech"]
        # 1) Action checks first: they alone drive control (verification, next step, repair).
        action_verdicts: list[Verdict] = []
        for q in actions:
            if self.judge is None:
                break
            if evidence_issue:
                v = Verdict(q.qid, k, VerdictLabel.UNKNOWN, 0.0, str(evidence_issue), t_evidence, now())
            else:
                v = await self._one_check(q, self.judge.judge(q, chunks, k, t_evidence), k, t_evidence, deadline)
            if k in self.dropped or qc_epoch != self._qc_epoch:
                return  # interrupted, or invalidated by an erasure
            if v is None:
                break  # the deadline passed before this check could run
            action_verdicts.append(v)
            self._log_verdict(script, q, v, t_evidence, deadline)
        if qc_epoch != self._qc_epoch:
            return
        # timely = every action check ran and returned by the step's deadline (a timeout at the
        # deadline returns just after it, so it is not timely)
        timely = deadline is None or (len(action_verdicts) == len(actions)
                                      and all(v.t_verdict <= deadline for v in action_verdicts))
        if deadline is not None and actions and not timely:
            # action QC missed the step's deadline (late, timed out or never ran): the step failed
            for cid in script.chain_ids:
                self.director.expire(cid, revision)
            self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False, issues=["check_missed_deadline"])
            self._drain_director_events(now())
            timely = False
        if action_verdicts and timely:
            intent = script.provenance.get("intent", "")
            for chain_id in script.chain_ids:
                if all(v.label == VerdictLabel.COMPLIED for v in action_verdicts):
                    self.director.on_verified(chain_id, intent, k, t_evidence, revision=revision, step=step)
                elif any(v.label == VerdictLabel.NOT_COMPLIED for v in action_verdicts):
                    self.director.ledger.revert(k)  # the action did not happen: its state change neither
                    await self._repair(chain_id, intent, script, action_verdicts, t_evidence)
            self._drain_director_events(now())
        # 2) Speech checks: logged evidence only; they never gate or expire the chain.
        for q in speech:
            if self.speech_check is None:
                break
            call = asyncio.to_thread(self.speech_check.check, q, script.transcript, chunks, k, t_evidence)
            v = await self._one_check(q, call, k, t_evidence, None)
            if v is None or k in self.dropped or qc_epoch != self._qc_epoch:
                return
            self._log_verdict(script, q, v, t_evidence, None)

    async def _one_check(self, q, call, k: int, t_evidence: float, deadline: float | None) -> Verdict | None:
        budget = self.cfg.qc_timeout_s if deadline is None else min(self.cfg.qc_timeout_s, deadline - now())
        if budget <= 0:
            call.close() if hasattr(call, "close") else None
            return None
        try:
            return await asyncio.wait_for(call, timeout=budget)
        except asyncio.TimeoutError:
            # a stalled judge/ASR must not hold verification, repair or the session: abstain
            return Verdict(q.qid, k, VerdictLabel.UNKNOWN, 0.0, f"timeout after {budget:.2f} s", t_evidence, now())

    def _log_verdict(self, script: BlockScript, q, v: Verdict, t_evidence: float, deadline: float | None) -> None:
        self.log.emit(EventType.VERDICT, v.t_verdict, request_index=script.request_index, qid=v.qid, kind=q.kind,
                      label=v.label.value, confidence=v.confidence, rationale=v.rationale,
                      t_evidence=t_evidence, source="online_monitor", chain_ids=script.chain_ids,
                      revision=script.provenance.get("revision"), step=script.provenance.get("step"),
                      after_deadline=deadline is not None and v.t_verdict > deadline)
        self.director.ledger.record_verdict(script.request_index, v.qid, v.label.value)

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
        # The correction is ready *now*, so every request not yet locked is eligible: the earliest
        # correctable request is the next lock opportunity (the one being locked right now, if a
        # lock is in progress, is already fixed). The planned-time formula is logged for reference.
        j_planned = self.sched.earliest_correctable(t_evidence, cost, self.next_lock)
        j = self.next_lock + (1 if self._locking == self.next_lock else 0)
        # REPEAT arm = the original instruction unchanged (same action and line); GRADIENT arm =
        # the same action and line plus the forward correction (only the correction text differs). The LOCK of the carrying
        # request logs its exact prompt and retry_of.
        queued = self.director.queue_retry(chain_id, intent, correction=sentence,
                                           failed_request=script.request_index,
                                           revision=script.provenance.get("revision"),
                                           step=script.provenance.get("step"), min_request=j,
                                           line=script.transcript)  # both arms keep the line: only the correction differs
        self.log.emit(EventType.REPAIR, now(), request_index=script.request_index,
                      chain_id=chain_id, mode=mode.value, correction=sentence, queued=queued,
                      earliest_correctable=j, earliest_correctable_planned=j_planned,
                      next_unlocked=self.next_lock, chain_cost_s=cost,
                      compile_s=now() - t0, step=script.provenance.get("step"),
                      revision=script.provenance.get("revision"), t_evidence=t_evidence,
                      arm_drawn=self.cfg.correction_mode == CorrectionMode.RANDOMIZED)

    # ------------------------------------------------------------------ user input
    def on_input_failed(self, epoch: int) -> bool:
        """Release a failed input's listening state without changing a newer input or an erasure.

        An empty chat decision resumes the interrupted lesson/instruction and its deferred
        verification bookkeeping. It supplies no user text, dialogue turn or memory fact.
        Retained segments keep their original recall lineage when they are re-queued.
        """
        if epoch != self._input_epoch or not self._ready.is_set():
            return False
        d = self.director
        retained = [*d.queue, *d.deferred, *d.interrupted.values(),
                    *(segment for steps in d.held.values() for segments in steps.values() for segment in segments)]
        lineage = [(segment, segment.memory_ids, segment.recall_id) for segment in retained]
        recall_id = self._no_recall() if self.memory is not None and hasattr(self.memory, "no_recall") else None
        d.apply(Utterance("", "user", "", now(), session_id=self.cfg.session_id, scope=self.cfg.scope),
                {"relation": "chat", "kind": "chat", "steps": []}, memory_ids=[], recall_id=recall_id)
        for segment, memory_ids, original_recall in lineage:
            segment.memory_ids, segment.recall_id = memory_ids, original_recall
        self._decisions += 1  # release the same post-interruption wait as a successful input
        self._drain_director_events(now())
        return True

    async def on_speech_start(self, t: float | None = None) -> None:
        """Barge-in: stop playback now; stop planning ahead; mark unshown generated content.
        The plan changes and locking pauses *before* the first await, so no old-plan request
        can be locked in between; decisions still in flight become stale (input epoch)."""
        t = now() if t is None else t
        self._input_epoch += 1
        self._barge_t = now()
        self._barge_gate.clear()
        try:
            self.director.on_barge_in()
            if self.cfg.soft_switch:
                # keep playing what exists; lock the reply as soon as it is decided; cut over when it is ready
                self.sched.interrupt(self.next_lock)
                self._decisions_at_interrupt = self._decisions
                self._switch_pending, self._switch_target = True, None
                self._switch_plan = self.director.plan_version
            else:
                await self._drop_unpresented()
        finally:
            self._barge_gate.set()  # never touches the erasure gate
        if self.cfg.soft_switch:
            self.log.emit(EventType.INTERRUPT, now(), t_speech_onset=t, soft=True)
        else:
            self.log.emit(EventType.PLAYBACK_STOP, now(), t_speech_onset=t, dropped=sorted(self.dropped))
        self._maybe_finish()

    # ------------------------------------------------------------------ attention (opt-in camera)
    def on_camera(self, jpeg: bytes) -> None:
        """Keep the freshest camera frame while one inference is in flight."""
        if self.attention is None or self._stop.is_set() or not self._ready.is_set():
            return
        self._camera_pending = jpeg
        if self._camera_task is None or self._camera_task.done():
            self._start_camera_worker()

    def _start_camera_worker(self) -> None:
        task = self._spawn(self._drain_camera(self._camera_epoch), "attention")
        self._camera_task = task
        def done(completed: asyncio.Task) -> None:
            if self._camera_task is completed:
                self._camera_task = None
                if self._camera_pending is not None and not self._stop.is_set() and self._ready.is_set():
                    self._start_camera_worker()
        task.add_done_callback(done)

    async def _drain_camera(self, epoch: int) -> None:
        while self._camera_pending is not None and epoch == self._camera_epoch:
            jpeg, self._camera_pending = self._camera_pending, None
            await self._attention_check(jpeg, epoch=epoch)

    def camera_off(self) -> None:
        self._camera_epoch += 1
        self._camera_pending = None
        if self._camera_task is not None:
            self._camera_task.cancel()
        self._episode = (None, 0)
        if self.attention is not None:
            self.attention.reset()
            self.log.emit(EventType.ATTENTION, now(), state="off")

    async def _attention_check(self, jpeg: bytes, *, epoch: int | None = None) -> None:
        from live_agent.attention import NUDGES, check_frame

        epoch = self._camera_epoch if epoch is None else epoch
        monitor = self.attention
        if monitor is None or epoch != self._camera_epoch:
            return
        try:
            r = await check_frame(monitor, jpeg)
        except Exception as e:  # noqa: BLE001 - no verdict this time
            if epoch != self._camera_epoch or monitor is not self.attention:
                return
            monitor.update({"state": "unknown"})
            self.log.emit(EventType.ATTENTION, now(), state="unknown", reason=f"check failed: {str(e)[:80]}")
            return
        if r is None or epoch != self._camera_epoch or monitor is not self.attention:
            return
        nudge = None
        d = self.director
        if r["stable"] is not None and self._episode[0] != r["stable"]:
            self._episode = (r["stable"], 0)  # a new episode: the student came back, or drifted off again
        cap = {"absent": 1, "distracted": 3}.get(r["stable"], 0)  # asking an empty room again helps nobody
        queued_teaching = any(s.board is not None for s in d.queue)
        playing_teaching = any(sc.board and k not in self.dropped and len(self.presented.get(k, ())) < self.n_chunks
                               for k, sc in self.scripts.items())
        teaching = d.lesson_title or queued_teaching or playing_teaching
        can_insert = all(s.board is not None or s.lesson for s in d.queue)
        if (r["stable"] in NUDGES and r["run"] >= self.cfg.attention_nudge_after and teaching
                and self._episode[1] < cap
                and now() - self._last_nudge >= self.cfg.attention_cooldown_s
                and can_insert and not d.awaiting_decision and not d.listening):
            lines = NUDGES[r["stable"]]
            nudge = lines[self._nudge_i % len(lines)]
            self._nudge_i += 1
            self._last_nudge = now()
            self._episode = (r["stable"], self._episode[1] + 1)
            d.nudge(nudge)  # spoken next, with a gesture toward the board; the lesson continues after it
        self.log.emit(EventType.ATTENTION, now(), state=r["state"], stable=r["stable"],
                      confidence=round(r["confidence"], 2), reason=r["reason"], nudge=nudge)

    # ------------------------------------------------------------------ lessons
    def _start_lesson(self, topic: str, lesson_context: dict | None = None, request_id: str | None = None) -> None:
        self._stop_lesson()
        self._lesson_mistakes = []
        self.director.lesson_title = topic
        self._lesson_task = asyncio.create_task(self._guarded(self._lesson_loop(topic, lesson_context, request_id), "lesson", fatal=False))
        self._aux.add(self._lesson_task)
        self._lesson_task.add_done_callback(lambda t: (self._aux.discard(t), self._maybe_finish()))

    def _make_figures(self) -> None:
        """Render requested figures in the background and publish their ready state."""
        d = self.director
        figs, d.pending_figures = d.pending_figures, []
        for fig in figs:
            if fig.queued or fig.url:
                continue
            fig.queued = True
            if fig.plot is not None and self.figure_dir is not None:
                self._spawn(self._make_plot(fig), "figure")
            elif fig.prompt and self.image_maker is not None:
                self._spawn(self._make_figure(fig), "figure")

    async def _make_plot(self, fig) -> None:
        from live_agent.board_plot import render_plot

        try:
            name = await asyncio.to_thread(render_plot, fig.plot, self.figure_dir)
            fig.url = f"/board/img/{name}"
            self.log.emit(EventType.LESSON, now(), stage="figure", board=fig.board_key, point=fig.point, kind="plot",
                          figure={"url": fig.url, "caption": html.escape(fig.caption)})
        except Exception as e:  # noqa: BLE001 - a bad spec leaves the board without its graph
            self.log.emit(EventType.LESSON, now(), stage="figure_failed", board=fig.board_key, point=fig.point,
                          error=str(e)[:160])

    async def _make_figure(self, fig, attempts: int = 3) -> None:
        """Generate the figure; when the prompt names labels and a VLM judge is available, read the labels back
        and regenerate with another seed on a missing or misspelt one (Qwen-Image wrote 二氧化硼 for 二氧化碳).
        No figure is better than a wrong one: after ``attempts`` failures the board keeps its points only."""
        from live_agent.board_images import expected_labels, missing_labels, read_labels

        t0 = now()
        want = expected_labels(fig.prompt)
        vlm = getattr(self.judge, "vlm", None)
        miss: list[str] = []
        for attempt in range(attempts):
            try:
                url = await self.image_maker.make(fig.prompt, seed=42 + attempt)
                if want and vlm is not None and not getattr(self.image_maker, "exact_labels", False):
                    try:
                        seen = await read_labels(vlm, self.image_maker.out_dir / url.rsplit("/", 1)[1])
                    except Exception:  # noqa: BLE001 - the reader failed (e.g. a looping reply), not the image
                        seen = None
                    miss = missing_labels(want, seen, fig.prompt) if seen is not None else []
                    if miss:
                        continue
                fig.url = url
                self.log.emit(EventType.LESSON, now(), stage="figure", board=fig.board_key, point=fig.point,
                              seconds=round(now() - t0, 2), attempt=attempt, labels=want,
                              kind="diagram" if getattr(self.image_maker, "exact_labels", False) else "illustration",
                              figure={"url": fig.url, "caption": html.escape(fig.caption)})
                return
            except Exception as e:  # noqa: BLE001 - the board works without its picture
                self.log.emit(EventType.LESSON, now(), stage="figure_failed", board=fig.board_key, point=fig.point,
                              error=str(e)[:160])
                return
        self.log.emit(EventType.LESSON, now(), stage="figure_failed", board=fig.board_key, point=fig.point,
                      error=f"labels wrong after {attempts} tries: missing {miss}")

    async def _judge_figures(self, planner, lines, request_id: str | None = None) -> None:
        """Which points of a new section need an explanatory figure (a separate judgement, logged per point);
        runs while the section's first lines already play, so it never delays the lesson."""
        correlation = {"request_id": request_id} if request_id is not None else {}
        try:
            verdicts = await planner.judge_figures(lines)
        except Exception as e:  # noqa: BLE001 - the section works without figures
            self.log.emit(EventType.LESSON, now(), stage="figure_judgement_failed", error=str(e)[:160], **correlation)
            return
        board = lines[0].board
        self.log.emit(EventType.LESSON, now(), stage="figure_judgement", board=board.key, title=board.title,
                      judgements=verdicts, **correlation)
        self.director.pending_figures += [f for f in board.figures if not f.url]
        self._make_figures()

    async def _judge_answer_figures(self, board, spoken: list[str], request_id: str | None = None) -> None:
        """Illustrate ordinary knowledge answers without waiting for a request to draw.

        Answer sentences explain the board as a whole; their indexes are not board
        point indexes. Keep this shared context separate in the figure planner.
        """
        if self.image_maker is None or board.key in self._answer_figure_boards:
            return
        self._answer_figure_boards.add(board.key)
        from live_agent.lesson import LessonLine, LessonPlanner

        planner = LessonPlanner(self.director.llm, name=self.director.persona_name, bio=self.director.persona_bio)
        lines = [LessonLine(text, board, None) for text in spoken if text] or [LessonLine("", board, None)]
        existing = list(board.figures)
        correlation = {"request_id": request_id} if request_id is not None else {}
        try:
            verdicts = await asyncio.wait_for(planner.judge_figures(lines, max_figs=4), timeout=20)
        except Exception as error:  # auxiliary visuals never prevent the spoken answer
            self.log.emit(EventType.LESSON, now(), stage="figure_judgement_failed", board=board.key,
                          error=str(error)[:160] or type(error).__name__, **correlation)
            return

        def signature(figure):
            return (figure.prompt, json.dumps(figure.plot, sort_keys=True, ensure_ascii=False))

        seen = {signature(figure) for figure in existing}
        added = []
        for figure in list(board.figures):
            if any(figure is original for original in existing):
                continue
            identity = signature(figure)
            if identity in seen:
                board.figures.remove(figure)
                continue
            seen.add(identity)
            added.append(figure)
        # Quick answers have no reveal index. An overview gives them an automatic
        # image, while the remaining point figures can be browsed in the gallery.
        if added and not any(figure.point is None for figure in existing):
            added[0].point = None
        self.log.emit(EventType.LESSON, now(), stage="figure_judgement", board=board.key,
                      title=board.title, judgements=verdicts, **correlation)
        self.director.pending_figures += [figure for figure in added if not figure.url]
        self._make_figures()

    # ------------------------------------------------------------------ exercises
    async def _grade_answer(self, utt: Utterance, epoch: int) -> dict | None:
        """While an exercise waits: is this utterance its answer? If so grade it, speak the feedback, update the
        student profile and return the decision for the log; None: not an answer (the responder handles it)."""
        from live_agent.exercise import grade

        d = self.director
        ex = d.exercise
        correlation = {"request_id": ex.request_id} if ex.request_id is not None else {}
        profile_epoch = self._profile_epoch
        try:
            r = await grade(d.llm, ex, utt.text)
        except Exception as e:  # noqa: BLE001 - grading failed: the responder answers as usual
            self.log.emit(EventType.LESSON, now(), stage="grading_failed", error=str(e)[:160], **correlation)
            return None
        if not r.get("is_answer"):
            return None
        decision = {"relation": "chat", "target_chain": None, "kind": "chat", "memory_note": None,
                    "forget_term": None, "steps": [{"intent": "", "line": x} for x in r.get("feedback") or []],
                    "exercise_result": {"correct": r["correct"], "concept": ex.concept}}
        if epoch != self._input_epoch or d.exercise is not ex or profile_epoch != self._profile_epoch:
            # a newer utterance (or an erasure) came first: nothing is applied or recorded
            self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
            return {"relation": "chat", "kind": "superseded", "steps": [], "superseded": True}
        before = {id(x) for x in d.queue}
        d.apply(utt, decision)
        d.close_exercise(before)
        self._decisions += 1
        change = None
        if self.student is not None:
            change = self.student.record_exercise(ex.concept, r["correct"], question=ex.question, answer=utt.text,
                                                  misconception=r.get("misconception") or "", subject=ex.subject)
            self._save_profile()
        if not r["correct"] and (ex.source == "lesson" or d.lesson_title):
            self._lesson_mistakes.append(ex.concept + (f"（{r['misconception']}）" if r.get("misconception") else ""))
        self.log.emit(EventType.LESSON, now(), stage="exercise_graded", concept=ex.concept, correct=r["correct"],
                      skipped=bool(r.get("skipped")), misconception=r.get("misconception"), mastery=change, **correlation)
        self._emit_profile()
        self._exercise_changed()
        return decision

    def _catalogue_teaching_context(self, selected: dict | None):
        if selected is None:
            return self.student, self.curriculum
        from live_agent.curriculum import Curriculum
        from live_agent.student import StudentProfile

        grade = f"{selected['grade']}年级"
        profile = replace(self.student, grade=grade) if self.student is not None else \
            StudentProfile(student_id="catalogue", grade=grade)
        curriculum = Curriculum([s for s in self.curriculum.subjects if s.get("subject") == selected["subject"]],
                                self.curriculum.pedagogy, self.curriculum.craft)
        return profile, curriculum

    async def _give_exercise(self, topic: str, lesson_context: dict | None = None, *,
                             input_epoch: int | None = None, profile_epoch: int | None = None,
                             plan_version: int | None = None, request_id: str | None = None) -> None:
        """The student asked for an exercise: one on ``topic`` at the level the profile suggests."""
        from live_agent.exercise import make_exercise

        d = self.director
        correlation = {"request_id": request_id} if request_id is not None else {}
        self._exercises += 1
        input_epoch = self._input_epoch if input_epoch is None else input_epoch
        profile_epoch = self._profile_epoch if profile_epoch is None else profile_epoch
        plan = d.plan_version if plan_version is None else plan_version

        def superseded() -> bool:
            return input_epoch != self._input_epoch or profile_epoch != self._profile_epoch or plan != d.plan_version

        def drop_superseded() -> None:
            self.log.emit(EventType.AUDIT, now(), where="exercise_generation", topic=topic, reason="superseded", **correlation)

        if superseded():
            drop_superseded()
            return
        from live_agent.curriculum import parse_grade

        exercise_profile, curriculum = self._catalogue_teaching_context(lesson_context)
        g = parse_grade(exercise_profile.grade) if exercise_profile is not None else None
        profile = exercise_profile.summary() if lesson_context else self._student_context()
        profile = profile or "无（新学生，没有档案）"
        if curriculum and exercise_profile is not None:
            if lesson_context:
                profile += "\n" + curriculum.teaching_context(g, CHARS_PER_REQUEST, brief=True)
            profile += "\n" + curriculum.topic_context(topic, g)
            if curriculum.exercise_style(g):
                profile += f"\n这个年级的练习形式：{curriculum.exercise_style(g)}"
        try:
            craft = curriculum.practice_craft(g, curriculum.subject_of(topic, g)) \
                if curriculum and exercise_profile is not None else ""
            ex = await make_exercise(d.llm, name=d.persona_name, topic=topic, profile=profile,
                                     key=f"q{self._exercises}", craft=craft)
        except Exception as e:  # noqa: BLE001
            if superseded():
                drop_superseded()
                return
            self.log.emit(EventType.LESSON, now(), stage="exercise_failed", topic=topic, error=str(e)[:160], **correlation)
            d.say_verified("抱歉，这道题我没出好，你可以换个问法。")
            return
        if superseded():
            drop_superseded()
            return
        if d.exercise is not None or any(
                t in ex.question or t in ex.concept for t in d.erased_terms):
            self.log.emit(EventType.LESSON, now(), stage="exercise_dropped", concept=ex.concept,
                          reason="another exercise is open" if d.exercise is not None else "erasure", **correlation)
            return
        ex.request_id = request_id
        lines = ex.lines(22)
        d.pose_exercise(lines[1:])  # the responder already said it will give one
        self.log.emit(EventType.LESSON, now(), stage="exercise", concept=ex.concept, exercise=ex.question,
                      options=ex.options, kind=ex.kind, **correlation)

    def _exercise_changed(self) -> None:
        """Tell the page when an exercise opens or closes (its answer buttons); the 2 Hz state snapshot is only
        sent in gaps between events, which a lesson rarely leaves."""
        ex = self.director.exercise
        if ex is self._shown_exercise:
            return
        previous = self._shown_exercise
        self._shown_exercise = ex
        if ex is None:
            correlation = {"request_id": previous.request_id} if previous is not None and previous.request_id is not None else {}
            self.log.emit(EventType.LESSON, now(), stage="exercise_closed", **correlation)
        else:
            correlation = {"request_id": ex.request_id} if ex.request_id is not None else {}
            self.log.emit(EventType.LESSON, now(), stage="exercise_open", concept=ex.concept,
                          kind=ex.kind, question=ex.question, option_texts=list(ex.options),
                          options=[o[:1] for o in ex.options], **ex.presentation(), **correlation)

    def _remind_existing_exercise(self, request_id: str | None) -> None:
        """Tell the current input owner which authoritative question must be answered first."""
        self.director.remind_exercise()
        ex = self.director.exercise
        correlation = {"request_id": request_id} if request_id is not None else {}
        self.log.emit(EventType.LESSON, now(), stage="exercise_existing", concept=ex.concept,
                      kind=ex.kind, question=ex.question, options=[o[:1] for o in ex.options],
                      option_texts=list(ex.options), exercise_request_id=ex.request_id, **ex.presentation(), **correlation)

    def _erase_learning(self, terms: list[str]) -> int:
        """Erasure of teaching state: the student profile, a pending exercise that mentions a term (with its queued
        lines and answer board), this lesson's mistakes; in-flight grading / exercise generation is invalidated."""
        n = 0
        self._profile_epoch += 1  # grading / exercise generation in flight must not write back erased data
        ex = self.director.exercise
        if ex is not None and any(x in json.dumps(ex.__dict__, ensure_ascii=False, default=str) for x in terms):
            self.director.close_exercise(set(id(s) for s in self.director.queue))  # its lines go too
            self.director.queue = type(self.director.queue)(s for s in self.director.queue
                                                           if s.board is None or s.board.key not in (ex.key, ex.key + "a"))
        if self.student is not None:
            n += sum(self.student.purge(x) for x in terms)
            self._save_profile()
            self._emit_profile()  # the page drops what it showed
        self._lesson_mistakes = [m for m in self._lesson_mistakes if not any(x in m for x in terms)]
        return n

    async def _answer_board(self, question: str, segs: list, request_id: str | None = None) -> None:
        from live_agent.llm import parse_json

        d = self.director
        t0 = now()
        raw = await d.llm.chat([{"role": "user", "content": ANSWER_BOARD_PROMPT.format(
            question=question[:200], answer="".join(x.line for x in segs)[:600])}],
            max_tokens=400, temperature=0.2, json_mode=True)
        b = d.answer_board(parse_json(raw))
        if b is None:
            return
        waiting = [x for x in segs if any(x is q for q in d.queue)]  # lines not yet locked
        for x in waiting:
            x.board = b
        self._make_figures()
        if waiting:
            self._spawn(self._judge_answer_figures(b, [x.line for x in segs], request_id), "answer_figures")
        self.log.emit(EventType.LESSON, now(), stage="answer_board", title=b.title, board=b.key,
                      seconds=round(now() - t0, 2), lines=len(waiting))

    def _student_context(self) -> str:
        """What the responder knows about the student: the profile, and how to talk to a student of this grade."""
        if self.student is None:
            return ""
        ctx = self.student.summary()
        if self.curriculum:
            from live_agent.curriculum import parse_grade

            from live_agent.director.director import CHARS_PER_REQUEST

            # the responder sees this on every utterance: tone, wording and feedback only
            teach = self.curriculum.teaching_context(parse_grade(self.student.grade), CHARS_PER_REQUEST, brief=True)
            if teach:
                ctx += "\n" + teach
        return ctx

    def _save_profile(self) -> None:
        """Save through the shared store (other sessions and the profile page see the change), else directly."""
        if self.profile_store is not None:
            self.profile_store.changed(self.student.student_id, source=self.on_profile_edited)
        else:
            self.student.save()

    def on_profile_edited(self) -> None:
        """Someone else (the profile page, another session) changed this student's profile: refresh the page. After
        a reset, grading and exercise generation in flight must not write into the fresh profile."""
        store, sid = self.profile_store, getattr(self.student, "student_id", None)
        resets = store.resets.get(sid, 0) if store is not None else 0
        if resets != self._profile_resets:
            self._profile_resets = resets
            self._profile_epoch += 1
        self._emit_profile()

    def _emit_profile(self) -> None:
        """The page gets the profile view directly; the durable log records only that it changed."""
        if self.student is None:
            return
        self.log.emit(EventType.LESSON, now(), stage="profile_changed")
        send = getattr(self.transport, "send_json", None)
        if send is not None:
            self._spawn(send({"type": "profile", "profile": self.student.view()}), "profile")

    def _stop_lesson(self) -> None:
        self._lesson_mistakes = []
        if self._lesson_task is not None and not self._lesson_task.done():
            self._lesson_task.cancel()
        self._lesson_task = None
        self.director.stop_lesson()

    async def _lesson_loop(self, topic: str, lesson_context: dict | None = None, request_id: str | None = None) -> None:
        """Outline first (its intro plays with the outline on the board), then one section at a time, each
        generated while the previous one plays (a section is ~1 min of speech, ~10-20 s to generate)."""
        from live_agent.lesson import LessonLine, LessonPlanner

        d = self.director
        correlation = {"request_id": request_id} if request_id is not None else {}
        lesson_profile, lesson_curriculum = self._catalogue_teaching_context(lesson_context)
        planner = LessonPlanner(d.llm, name=d.persona_name, bio=d.persona_bio, curriculum=lesson_curriculum)
        context = "；".join(t for r, t in d.dialogue if r == "user")[-300:]
        try:
            outline = await planner.outline(topic, context, profile=lesson_profile)
        except Exception as e:  # noqa: BLE001
            self.log.emit(EventType.LESSON, now(), stage="outline_failed", topic=topic, error=str(e)[:160], **correlation)
            d.add_lesson_lines([LessonLine("抱歉，这节课我还没准备好，你可以先问我问题。", None, None)])
            return
        if self.cfg.lesson_self_check == "revise":
            outline = await self._review_outline(planner, outline, topic, context, profile=lesson_profile,
                                                  request_id=request_id)
            if outline is None:
                d.add_lesson_lines([LessonLine("这节课的安排还需要核对，你可以先问一个具体问题。", None, None)])
                return
        d.lesson_title = outline.title
        d.add_lesson_lines(planner.intro_lines(outline))
        self.log.emit(EventType.LESSON, now(), stage="outline", topic=topic, title=outline.title,
                      sections=[s["title"] for s in outline.sections],
                      plan=[{"title": s["title"], "concepts": s.get("concepts", []), "depth": s.get("depth"),
                             "exercise": s.get("exercise", False)} for s in outline.sections],
                      note=outline.note, adaptive=self.student is not None, subject=outline.subject,
                      subject_source=getattr(planner, "last_subject", None), objectives=outline.objectives,
                      key_point=outline.key_point, difficulty=outline.difficulty, hook=outline.hook_type, **correlation)
        covered: list[str] = []
        waiting_for = None  # the previous section's exercise: its result shapes the next section
        for i in range(len(outline.sections)):
            # a judged-and-rewritten section takes about twice as long to produce: start it earlier
            lookahead = self.cfg.lesson_lookahead * (2 if self.cfg.lesson_self_check == "revise" else 1)
            while not self._stop.is_set() and (
                    len(d.lesson_backlog) >= lookahead
                    or (waiting_for is not None and (d.exercise is waiting_for
                                                     or any(x.exercise is waiting_for for x in d.lesson_backlog)))
                    or (self.student is not None and d.exercise is not None)):
                await asyncio.sleep(0.5)
            waiting_for = None
            lines = None
            for attempt in range(2):
                try:
                    lines = await planner.section(outline, i, covered, profile=lesson_profile,
                                                  mistakes=list(self._lesson_mistakes))
                    break
                except Exception as e:  # noqa: BLE001 - retry once, then skip the section
                    self.log.emit(EventType.LESSON, now(), stage="section_failed", section=i, attempt=attempt,
                                  error=str(e)[:160], **correlation)
            if lines and self.cfg.lesson_self_check == "revise":
                lines = await self._revise_section(planner, outline, i, covered, lines, profile=lesson_profile, request_id=request_id)
                if not lines:
                    self.log.emit(EventType.LESSON, now(), stage="quality_hold", section=i, **correlation)
                    d.add_lesson_lines([LessonLine("这一节的讲解还需要核对，我们先停在这里。", None, None)])
                    return
            if lines:
                for line in lines:
                    if getattr(line, "exercise", None) is not None:
                        line.exercise.request_id = request_id
                if self.cfg.lesson_self_check == "log":
                    self._spawn(self._check_section(planner, outline, i, lines, profile=lesson_profile, request_id=request_id), "lesson_check")
                self._lesson_mistakes.clear()  # addressed by this section
                d.add_lesson_lines(lines)
                if self.student is not None and outline.sections[i].get("concepts"):
                    self.student.mark_taught(outline.sections[i]["concepts"])
                    self._save_profile()
                self._make_figures()
                self._spawn(self._judge_figures(planner, lines, request_id), "figure_judgement")
                ex = next((ln.exercise for ln in lines if getattr(ln, "exercise", None) is not None), None)
                waiting_for = ex if self.student is not None else None  # adapt the next section to the answer
                self.log.emit(EventType.LESSON, now(), stage="section", section=i,
                              title=outline.sections[i]["title"], lines=len(lines),
                              points=len(lines[0].board.items), depth=outline.sections[i].get("depth"),
                              exercise=(ex.question if ex is not None else None), **correlation)
                covered.append(outline.sections[i]["title"])
        self.log.emit(EventType.LESSON, now(), stage="planned", title=outline.title, **correlation)

    async def _review_outline(self, planner, outline, topic: str, context: str, *, profile=None,
                              request_id: str | None = None):
        from live_agent.teaching_quality import revision_feedback
        correlation = {"request_id": request_id} if request_id is not None else {}
        async def workflow():
            candidate = outline
            for attempt in range(2):
                verdict = await planner.review_outline(candidate, topic, profile=profile)
                self.log.emit(EventType.LESSON, now(), stage="outline_check", passed=verdict["pass"],
                              scores=verdict["scores"], evidence=verdict.get("evidence"),
                              problems=verdict["problems"], revised=bool(attempt), **correlation)
                if verdict["pass"]:
                    return candidate
                if attempt == 0:
                    candidate = await planner.outline(topic, context, profile=profile,
                                                      feedback=revision_feedback(verdict))
            return None
        try:
            candidate = await asyncio.wait_for(workflow(), timeout=self.cfg.lesson_revise_deadline_s)
        except Exception as exc:
            self.log.emit(EventType.LESSON, now(), stage="outline_check_failed", error=str(exc)[:160], **correlation)
            candidate = None
        if candidate is None:
            self.log.emit(EventType.LESSON, now(), stage="plan_hold", **correlation)
        return candidate

    async def _check_section(self, planner, outline, i: int, lines, *, revised: bool = False, profile=None,
                             request_id: str | None = None) -> dict:
        """Judge a section against the lesson-quality checklist and log the verdict (never raises)."""
        correlation = {"request_id": request_id} if request_id is not None else {}
        try:
            check = planner.review_section if self.cfg.lesson_self_check == "revise" else planner.check_section
            v = await check(outline, i, lines, profile=profile if profile is not None else self.student)
        except Exception as e:  # noqa: BLE001 - the check is advisory
            self.log.emit(EventType.LESSON, now(), stage="check_failed", section=i, error=str(e)[:160], **correlation)
            return {}
        if v:
            self.log.emit(EventType.LESSON, now(), stage="check", section=i, title=outline.sections[i]["title"],
                          passed=v["pass"], scores=v["scores"], problems=v["problems"], fix=v["fix"], revised=revised,
                          evidence=v.get("evidence"), critical_errors=v.get("critical_errors"), **correlation)
        return v

    async def _revise_section(self, planner, outline, i: int, covered: list[str], lines, *, profile=None,
                              request_id: str | None = None):
        """Review before presentation; one rewrite must preserve exercise/correction and pass re-review.
        Failure or timeout holds the section rather than presenting known weak material."""
        from live_agent.lesson import rewrite_keeps
        from live_agent.teaching_quality import revision_feedback
        correlation = {"request_id": request_id} if request_id is not None else {}

        async def judge_and_rewrite():
            v = await self._check_section(planner, outline, i, lines, profile=profile, request_id=request_id)
            if not v:
                return []
            if v["pass"]:
                return lines
            feedback = revision_feedback(v)
            try:
                new = await planner.section(outline, i, covered, profile=profile if profile is not None else self.student,
                                            mistakes=list(self._lesson_mistakes), feedback=feedback)
            except Exception as e:  # noqa: BLE001 - keep the first version
                self.log.emit(EventType.LESSON, now(), stage="revise_failed", section=i, error=str(e)[:160], **correlation)
                return []
            lost = rewrite_keeps(lines, new, list(self._lesson_mistakes))
            if lost:
                self.log.emit(EventType.LESSON, now(), stage="revise_rejected", section=i, reason=lost, **correlation)
                return []
            second = await self._check_section(planner, outline, i, new, revised=True, profile=profile, request_id=request_id)
            if not second or not second["pass"]:
                self.log.emit(EventType.LESSON, now(), stage="revise_rejected", section=i,
                              reason="rewrite did not pass review", **correlation)
                return []
            self.log.emit(EventType.LESSON, now(), stage="revised", section=i, feedback=feedback[:200], lines=len(new), **correlation)
            return new

        try:
            return await asyncio.wait_for(judge_and_rewrite(), timeout=self.cfg.lesson_revise_deadline_s)
        except asyncio.TimeoutError:
            self.log.emit(EventType.LESSON, now(), stage="revise_timeout", section=i,
                          deadline_s=self.cfg.lesson_revise_deadline_s, **correlation)
            return []

    async def _switch_to(self, target: int) -> None:
        """The reply's first chunk is ready: drop what was generated before it and not yet fully shown, stop
        the player (it cuts at the current frame) and let the reply play next."""
        self._switch_pending, self._switch_target = False, None
        cut = self._mark_dropped(range(target))
        self.director.on_interrupted(cut)
        await self.transport.stop_playback()
        self.log.emit(EventType.PLAYBACK_STOP, now(), soft=True, switch_to=target, dropped=sorted(self.dropped))

    async def _drop_unpresented(self) -> None:
        """Stop playback and discard everything locked but not (fully) presented."""
        self.sched.interrupt(self.next_lock)  # synchronously, before any await
        self._switch_pending, self._switch_target = False, None  # a hard cut supersedes a pending switch
        cut = self._mark_dropped(range(self.next_lock))
        self.director.on_interrupted(cut)
        self._decisions_at_interrupt = self._decisions
        await self.transport.stop_playback()

    def _mark_dropped(self, requests) -> list:
        """Mark locked-but-not-fully-presented requests as dropped (never shown); returns their scripts."""
        cut = []
        in_flight = getattr(self.transport, "in_flight", lambda: None)()  # (k, ci, t_start) playing now
        for k in requests:
            if len(self.presented.get(k, ())) < self.n_chunks and k not in self.dropped:
                if k in self.scripts:
                    cut.append(self.scripts[k])
                if in_flight and in_flight[0] == k:
                    self._audible_before_cut(k, in_flight[1], in_flight[2])
                self.dropped.add(k)
                self._claims.pop(k, None)  # a claim that is never heard is not a claim
                self.director.ledger.mark_generated_not_presented(
                    k, partially_shown=bool(self.presented.get(k)) or bool(in_flight and in_flight[0] == k))
                self.director.ledger.revert(k)  # its action was never (fully) shown: no state change
        return cut

    async def on_user_utterance(self, utt: Utterance, epoch: int | None = None) -> dict[str, Any]:
        """``epoch``: the input epoch when the utterance was *received* (queued inputs must not
        inherit a later barge-in's epoch); default = now."""
        return await self._on_user_utterance(utt, self._input_epoch if epoch is None else epoch)

    @property
    def input_epoch(self) -> int:
        return self._input_epoch

    async def _on_user_utterance(self, utt: Utterance, epoch: int) -> dict[str, Any]:
        correlation = {"request_id": utt.request_id} if utt.request_id is not None else {}
        self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text, **correlation)
        # A forget request must not recall the very fact it asks to erase into the responder.
        memories, memory_ids, recall_id = None, [], None
        if self.memory and not _FORGET.search(utt.text):
            hits_fn = getattr(self.memory, "recall_hits", None)
            if hits_fn is not None:
                hits = hits_fn(utt.text, mode=self.cfg.scope)
                memories, memory_ids = [h.rendered for h in hits], [h.id for h in hits]
                recall_id = getattr(hits, "recall_id", None)
            else:
                memories, memory_ids = self.memory.recall(utt.text, mode=self.cfg.scope), None
        elif self.memory and hasattr(self.memory, "no_recall"):
            # nothing recalled for a forget request; the responder prompt then contains no memory
            # (the director never injects memory notes), so the context is isolated
            recall_id = self._no_recall()
        if self.memory:
            self.memory.on_user_utterance(utt)
        if self.director.exercise is not None and not _FORGET.search(utt.text):
            graded = await self._grade_answer(utt, epoch)
            if graded is not None:
                self._drain_director_events(now())
                outcome = {**correlation, "applied": not bool(graded.get("superseded"))} if correlation else {}
                self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=graded,
                              chains={c.chain_id: c.status.value for c in self.director.chains.values()},
                              recalled=[], **outcome)
                return graded
        self.director.student_context = self._student_context()
        decision = await self.director.decide(utt, memories)
        term = (decision or {}).get("forget_term")
        applied = False
        if epoch != self._input_epoch:
            # The user barged in again while this decision was computed: it must not change the plan
            # (the newer utterance decides). An erasure request is still honoured.
            self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
        else:
            if term:  # the confirmation is spoken only after the erasure is verified (below)
                decision = {**decision, "steps": []}
            queued_before = {id(x) for x in self.director.queue}
            self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
            applied = True
            self._decisions += 1  # only applied decisions end the post-interruption wait
            answer_segs = [x for x in self.director.queue if id(x) not in queued_before and x.line]
            if self.answer_boards and (decision or {}).get("kind") == "content" \
                    and self.director.answer_board_missing(decision) \
                    and decision.get("_teaching_quality", {}).get("status") != "held":
                segs = [x for x in answer_segs if x.board is None]
                if segs:  # the responder left it out: write one now and show it from the next unlocked line
                    self._spawn(self._answer_board(utt.text, segs, utt.request_id), "answer_board")
            elif self.answer_boards and (decision or {}).get("kind") == "content":
                boards = {id(x.board): x.board for x in answer_segs if x.board is not None}
                for board in boards.values():
                    self._spawn(self._judge_answer_figures(board,
                        [x.line for x in answer_segs if x.board is board], utt.request_id), "answer_figures")
            self._make_figures()
            kind = (decision or {}).get("kind")
            if self.teaching:  # classroom workflows are persona-gated (D-068): a live persona answers as content/chat
                if kind == "lesson" and self.director.exercise is not None and self.director.exercise.source != "lesson":
                    self._remind_existing_exercise(utt.request_id)  # finish the standalone question before a new lesson
                elif kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
                    topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
                    self._start_lesson(topic, utt.lesson_context, utt.request_id)
                elif kind == "lesson_stop":
                    self._stop_lesson()
                elif kind == "exercise" and self.director.exercise is not None:
                    self._remind_existing_exercise(utt.request_id)  # one exercise at a time: the open one first
                elif kind == "exercise":
                    topic = utt.lesson_context["topic"] if utt.lesson_context else \
                        str((decision or {}).get("topic") or "").strip() or self.director.lesson_title or "刚才讲的内容"
                    self._spawn(self._give_exercise(topic, utt.lesson_context, input_epoch=epoch,
                                                    profile_epoch=self._profile_epoch, plan_version=self.director.plan_version,
                                                    request_id=utt.request_id), "exercise")
                elif self.director.exercise is not None:
                    self._remind_existing_exercise(utt.request_id)  # a question while an exercise waits: back to it afterwards
                if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
                    changed = self.student.apply_update(decision["profile_update"])
                    if changed:
                        self._save_profile()
                        self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
                        self._emit_profile()
        self._drain_director_events(now())  # before the erasure, so its redaction covers these events
        if term and self.memory is not None and hasattr(self.memory, "forget"):
            complete = await self._erase(term)
            line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
            self.director.say_verified(line)  # a verified statement: not subject to the narration guard
        if term:  # the decision itself names erased terms
            raw = json.dumps(decision, ensure_ascii=False)
            for x in sorted(self.director.erased_terms, key=len, reverse=True):
                raw = raw.replace(x, "[已删除]")
            decision = json.loads(raw)
        outcome = {**correlation, "applied": applied} if correlation else {}
        self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
                      chains={c.chain_id: c.status.value for c in self.director.chains.values()},
                      recalled=list(memories or []), **outcome)
        return decision

    async def _erase(self, term: str) -> bool:
        async with self._erase_lock:  # erasures are serialized; each owns the erasure gate
            return await self._erase_locked(term)

    async def _erase_locked(self, term: str) -> bool:
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
            # Stop what the viewer could still see or hear first, then do the (slow) storage work.
            await self._drop_unpresented()
            self.camera_off()  # discard queued camera frames and invalidate late verdicts
            # Pending QC may hold (and later log) the erased content: invalidate and drain it first.
            self._qc_epoch += 1
            pending = [t for t in self._aux]
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            self._answer_figure_boards.clear()
            forget_async = getattr(self.memory, "forget_async", None)
            report = await forget_async(term) if forget_async is not None else self.memory.forget(term)
            # Redact every erased value, not only the responder's keyword (e.g. "妹妹" names the fact,
            # "杭州" is its value); report.terms holds them in memory only.
            terms = sorted({term, *(getattr(report, "terms", None) or [])}, key=len, reverse=True)
            purged = sum(self.director.purge(x) for x in terms)
            purged += self._erase_learning(terms)
            acknowledge("unsent_scripts", True, f"controller items purged: {purged}")
            # The responder is stateless per call; its context is rebuilt from purged state.
            acknowledge("llm_context", True, "stateless responder; memory notes and chains purged")
            for x in terms:
                for k, sc in self.scripts.items():
                    sc.transcript = sc.transcript.replace(x, "[已删除]")
                    sc.action = sc.action.replace(x, "[已删除]")
                    sc.corrections = [c.replace(x, "[已删除]") for c in sc.corrections]
                    if sc.board and (board_mentions(sc.board, x)
                                     or sc.board.get("key") in self.director.erased_board_keys):
                        sc.board = None  # queued media must not restore an erased image collection
                    if x in self.prompts.get(k, ""):
                        self.prompts[k] = self.prompts[k].replace(x, "[已删除]")
                self.log.redact(x)  # in memory and in the JSONL file
            await self._drop_unpresented()
            self.director.ledger.generated_not_presented.clear()  # erased content must not be bridged to
            for k in [k for k in self.chunks if k in self.dropped]:
                self._evict(k)  # unshown media may carry the erased speech
            try:
                self._anchored = False  # a reset generator starts a new anchor shot
                confirm = getattr(self.gen, "reset_confirmed", None)
                ok = await confirm() if confirm is not None else (await self.gen.reset()) is None
                acknowledge("generator_state", bool(ok),
                            "workers confirmed reset; adapter prompt buffers cleared" if ok
                            else "worker reset not confirmed in time")
            except Exception as e:  # noqa: BLE001
                acknowledge("generator_state", False, f"reset failed: {e}")
            recorder = getattr(self.transport, "recorder", None)
            if recorder is None and self.gen_recorder is not None:
                ok = await asyncio.to_thread(self.gen_recorder.discard)
                self.gen_recorder = self.gen_recorder_factory() if (ok and self.gen_recorder_factory) else None
                acknowledge("recordings", ok, "generated-stream recording deleted" if ok else "recording files remain")
            elif recorder is None:
                acknowledge("recordings", True, "event log redacted; no media recording")
            else:  # presented audio/video cannot be redacted: delete the recording, stop recording
                ok = await asyncio.to_thread(recorder.discard)
                restart = getattr(self.transport, "restart_recording", None)
                if ok and restart is not None:
                    restart()  # later (post-erasure) content is recorded in a new part file
                if self.gen_recorder is not None:  # the generated-stream recording holds it too
                    ok = await asyncio.to_thread(self.gen_recorder.discard) and ok
                    self.gen_recorder = self.gen_recorder_factory() if self.gen_recorder_factory else None
                acknowledge("recordings", ok, f"recording {getattr(recorder, 'path', '')} deleted; "
                            + ("continuing in a new part" if restart else "session no longer recorded")
                            if ok else "recording files remain")
        finally:
            complete = report is not None and getattr(report, "complete", True)
            if complete:
                self._ready.set()
            # else: fail closed — locking stays paused (no new content) until an operator resolves it
        pending = list(getattr(report, "pending_targets", []) or [])
        self.log.emit(EventType.PLAYBACK_STOP, now(), erasure=True,
                      deleted=len(getattr(report, "deleted_ids", []) or []),
                      kinds=getattr(report, "kinds", None), controller_purged=purged,
                      generator_reset=True, erasure_complete=complete, pending_targets=pending)
        if not complete:
            self.log.emit(EventType.ERROR, now(), where="erasure",
                          error="erasure incomplete: session paused (fail closed)",
                          detail=str(getattr(report, "errors", "")), pending_targets=pending)
        self._maybe_finish()
        return complete

    def snapshot(self) -> dict[str, Any]:
        """Compact live state for the web demo panel (no media, no prompts)."""
        d = self.director
        return {
            "chains": [{"id": c.chain_id, "status": c.status.value, "kind": c.kind.value, "intent": c.final_intent,
                        "revisions": len(c.revisions), "steps": [x for x in c.steps if x],
                        "step_index": c.step_index, "requests": list(c.requests[-6:])}
                       for c in list(d.chains.values())[-12:]],
            "next_lock": self.next_lock, "plan_version": d.plan_version,
            "lambda_s": round(self.sched.lambda_estimate(), 2), "listening": d.listening,
            "awaiting_decision": d.awaiting_decision, "erasure_gate_open": self._ready.is_set(),
            "queued_segments": len(d.queue), "mode": d.mode.value,
            "exercise": ({"concept": d.exercise.concept, "kind": d.exercise.kind,
                          "question": d.exercise.question, "option_texts": list(d.exercise.options),
                          "options": [o[:1] for o in d.exercise.options],
                          **d.exercise.presentation(),
                          **({"request_id": d.exercise.request_id} if d.exercise.request_id is not None else {})}
                         if d.exercise is not None else None),
        }

    def open_chains(self) -> list[str]:
        return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]
