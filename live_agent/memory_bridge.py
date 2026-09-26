"""Adapter from live_agent.memory.MemoryStore to the orchestrator's MemoryPort.

Scope rules (review findings 12/13, round 2):

* The bridge's **session mode** ("private" 1:1 or "public" livestream) is required at
  construction (from the server's authenticated session) and can never change: a call
  naming another mode raises :class:`ScopeViolationError`. ``Utterance.scope`` is never
  trusted; every write uses the session scope.
* Persona lines carry lineage, computed by the bridge from a **recall token** rather
  than asserted by the caller. Every ``recall_hits`` call returns a :class:`RecallResult`
  (a list of hits) with a ``recall_id``; the bridge records which ids it handed out under
  that token. ``no_recall()`` issues a token for a decision made without memories (e.g. a
  forget request). ``on_persona_line(..., recall_id=token)`` then uses exactly the ids of
  that recall as the line's parents (lineage "complete", or "none" if it was empty); every
  id must still exist and be readable in this session.

  - A **public** line is stored only with a valid token of this bridge and no private
    input; caller-asserted ``lineage`` / ``source_ids`` without a token are refused.
  - A public line from an **empty** token (``no_recall()``) is refused if a private
    context was possible (:meth:`MemoryBridge.private_context_risk`: a private scope was
    recalled / ingested through this bridge, or a private record of this user was written
    to the store since the bridge was created), unless the token was issued with
    ``no_recall(isolated_context=True)`` -- the orchestrator's assertion that the
    responder's context for that decision held no memory notes.
  - A **private** line without a token keeps the earlier behaviour: ``lineage="complete"``
    with ``source_ids`` is accepted as given; otherwise (unknown) the line is linked to
    every memory recalled and every turn ingested this session (a conservative superset,
    so erasure and correction still cascade to it).

  Refused lines are not written; None is returned and the reason is in ``scope_violations``.
* Erasure is complete only when every required purge target acked (see
  :class:`live_agent.memory.ErasureReport`); the orchestrator acks its targets with
  :meth:`MemoryBridge.acknowledge_erasure`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from live_agent.memory.schema import Record
from live_agent.memory.store import (
    ErasureInProgressError,
    ErasureReport,
    MemoryStore,
    ScopeViolationError,
    SpeakerRoleError,
)
from live_agent.types import Utterance, new_id

log = logging.getLogger("live_agent.memory_bridge")

# External state that can hold erased content (proposal §5.6 erasure list). Each must ack.
DEFAULT_PURGE_TARGETS = ("llm_context", "unsent_scripts", "generator_state", "recordings")


@dataclass
class RecallHit:
    id: str
    text: str
    tags: dict[str, Any]
    rendered: str  # the string form passed to the director


class RecallResult(list):
    """``list[RecallHit]`` plus the ``recall_id`` token to pass to ``on_persona_line``."""

    def __init__(self, hits: Iterable[RecallHit] = (), recall_id: str = "") -> None:
        super().__init__(hits)
        self.recall_id = recall_id

    @property
    def ids(self) -> list[str]:
        return [h.id for h in self]


class MemoryBridge:
    def __init__(self, db_path: str, *, user_id: str, stream_id: str, session_id: str, mode: str,
                 store: MemoryStore | None = None,
                 required_purge_targets: Sequence[str] = DEFAULT_PURGE_TARGETS, recall_k: int = 6):
        if mode not in ("private", "public"):
            raise ValueError(f"session mode must be 'private' or 'public', got {mode!r}")
        self.store = store or MemoryStore(db_path)
        self.user_id = user_id
        self.stream_id = stream_id
        self.session_id = session_id
        self._mode = mode
        self.required_purge_targets = tuple(required_purge_targets)
        self.recall_k = recall_k
        # ordered sets of this session's memory inputs (the unknown-lineage superset)
        self._recalled: dict[str, None] = {}
        self._ingested: dict[str, None] = {}
        self._recalls: dict[str, tuple[str, ...]] = {}  # recall token -> ids handed out under it
        self._isolated: set[str] = set()  # empty tokens issued with isolated_context=True
        self._seen_scopes: set[str] = set()  # source scopes of everything recalled / ingested here
        self._t0 = self.store.clock()
        self._deferred: list[Utterance] = []  # turns received while forget_async runs
        self.scope_violations: list[dict[str, Any]] = []
        self.on_erasure: list[Callable[[ErasureReport], Any]] = []
        self.store.register_purge_target("bridge_callbacks", self._erasure_hook)

    # ------------------------------------------------------------------ session scope

    @property
    def mode(self) -> str:
        return self._mode

    def _check_mode(self, mode: str) -> None:
        if mode != self._mode:
            raise ScopeViolationError(f"caller mode {mode!r} differs from the session mode {self._mode!r}")

    @property
    def write_scope(self) -> str:
        return MemoryStore.session_write_scope(self._mode, self.user_id, self.stream_id)

    # ------------------------------------------------------------------ recall

    def recall_hits(self, text: str, *, mode: str) -> RecallResult:
        """Retrieval with record ids and a ``recall_id`` token (see module docstring); the ids
        are also remembered as this session's lineage superset."""
        self._check_mode(mode)
        if self.store.erasing:  # nothing is recalled while an erasure runs
            return RecallResult([], self.no_recall())
        res = self.store.retrieve(text, self._mode, user_id=self.user_id if self._mode == "private" else None,
                                  stream_id=self.stream_id, k=self.recall_k)
        out = []
        for h in res.hits:
            t = h.tags
            out.append(RecallHit(h.record.id, h.record.text, t,
                                 f"[{t.get('kind')}/{t.get('claim_type')}/{t.get('status', 'active')}] {h.record.text}"))
            self._recalled[h.record.id] = None
            self._seen_scopes |= h.record.source_scopes
        token = new_id("recall")
        self._recalls[token] = tuple(h.id for h in out)
        return RecallResult(out, token)

    def no_recall(self, *, isolated_context: bool = False) -> str:
        """Token for a decision made without any recalled memory (lineage "none").

        ``isolated_context=True`` asserts that the responder's context for this decision
        held no memory notes at all (fresh context); see :meth:`private_context_risk` for
        when a public session needs it."""
        token = new_id("recall")
        self._recalls[token] = ()
        if isolated_context:
            self._isolated.add(token)
        return token

    def private_context_risk(self) -> list[str]:
        """Why a responder context in this session might carry this user's private data:
        a private scope among the records recalled / ingested through this bridge, or a
        private record of this user written to the store since this bridge was created
        (e.g. a concurrent private session of the same user). Empty = none observed."""
        why = sorted(s for s in self._seen_scopes if s.startswith("private:"))
        n = self.store.db.execute(
            "SELECT count(*) FROM records WHERE owner = ? AND scope LIKE 'private:%' AND created_at >= ?",
            [self.user_id, self._t0]).fetchone()[0]
        if n:
            why.append(f"{n} private record(s) of this user written during this session")
        return why

    def recall(self, text: str, *, mode: str) -> list[str]:
        return [h.rendered for h in self.recall_hits(text, mode=mode)]

    # ------------------------------------------------------------------ writes

    def on_user_utterance(self, utt: Utterance) -> None:
        if self.store.erasing:  # ingested after the erasure finishes (forget_async)
            self._deferred.append(utt)
            return
        try:
            res = self.store.ingest_user_utterance(utt, user_id=self.user_id, stream_id=self.stream_id,
                                                   mode=self._mode)
        except (ScopeViolationError, SpeakerRoleError) as e:  # e.g. a viewer event in a private session
            self._violation(utt.text, f"utterance not stored: {e}", [])
            return
        for rec in [res.episode, *res.facts, res.generated_event]:
            if rec is not None:
                self._ingested[rec.id] = None
                self._seen_scopes |= rec.source_scopes

    def on_persona_line(self, text: str, *, session_id: str, scope: str, recall_id: str | None = None,
                        source_ids: Iterable[str] | None = None, lineage: str | None = None,
                        request_index: int | None = None) -> Record | None:
        """Log a persona line in the session scope with its lineage (see module docstring).

        Returns None (nothing written, reason in ``scope_violations``) if the line would
        be public without a valid recall token or with a private input, or if a source
        was erased meanwhile.
        """
        self._check_mode(scope)
        if self.store.erasing:
            return self._violation(text, "erasure in progress", [])
        if lineage not in (None, "complete", "none"):
            raise ValueError("lineage must be None (unknown), 'complete' or 'none'")
        if recall_id is not None:
            return self._line_from_token(text, session_id, recall_id, source_ids, request_index)
        if self._mode == "public":
            return self._violation(text, "public persona line without a recall token (lineage unverifiable)", [])
        wanted = list(dict.fromkeys(source_ids or ()))
        parents = self.store.existing_ids(wanted)
        if len(parents) != len(wanted):
            return self._violation(text, "source memory no longer exists (erased)",
                                   sorted(set(wanted) - set(parents)))
        if lineage is None:  # private session only (public returned above)
            parents = self.store.existing_ids([*parents, *self._recalled, *self._ingested])
            lineage = "session_superset"
        try:
            return self.store.record_generated_event(
                text, session_id, self.write_scope, user_id=self.user_id, derived_from=parents,
                request_index=request_index, lineage=lineage)
        except ScopeViolationError as e:
            return self._violation(text, str(e), parents)

    def _line_from_token(self, text: str, session_id: str, recall_id: str,
                         source_ids: Iterable[str] | None, request_index: int | None) -> Record | None:
        handed = self._recalls.get(recall_id)
        if handed is None:
            return self._violation(text, f"unknown recall token {recall_id!r} (not issued by this session)", [])
        if source_ids is not None and not set(source_ids) <= set(handed):
            return self._violation(text, "source_ids were not handed out under this recall token",
                                   sorted(set(source_ids) - set(handed)))
        parents = self.store.existing_ids(handed)
        if len(parents) != len(handed):
            return self._violation(text, "source memory no longer exists (erased)", sorted(set(handed) - set(parents)))
        if self._mode == "public" and not handed and recall_id not in self._isolated:
            risk = self.private_context_risk()
            if risk:
                return self._violation(text, "public line with empty lineage while private context was possible "
                                       f"({'; '.join(risk)}); pass no_recall(isolated_context=True) only if the "
                                       "responder context held no memory notes", [])
        uid = self.user_id if self._mode == "private" else None
        unreadable = [r.id for r in self.store._load(parents)
                      if not self.store.scope_readable(r.source_scopes, self._mode, uid, self.stream_id)]
        if unreadable:
            return self._violation(text, "source not readable in this session", unreadable)
        try:
            return self.store.record_generated_event(
                text, session_id, self.write_scope, user_id=self.user_id, derived_from=parents,
                request_index=request_index, lineage="complete" if parents else "none")
        except ScopeViolationError as e:
            return self._violation(text, str(e), parents)

    def _violation(self, text: str, reason: str, ids: list[str]) -> None:
        self.scope_violations.append({"reason": reason, "ids": ids, "chars": len(text)})
        log.error("persona line not recorded: %s", reason)

    # ------------------------------------------------------------------ erasure

    def forget(self, term: str) -> ErasureReport:
        report = self.store.forget(term, self.user_id, reason="user_request",
                                   require=self.required_purge_targets)
        for rid in report.deleted_ids:
            self._recalled.pop(rid, None)
            self._ingested.pop(rid, None)
        return report

    async def forget_async(self, term: str) -> ErasureReport:
        """:meth:`forget` with the DB work in a worker thread (see ``MemoryStore.forget_async``).
        While it runs, recall returns nothing, persona lines are not recorded and user turns
        are deferred; deferred turns are ingested once the erasure has finished."""
        try:
            report = await self.store.forget_async(term, self.user_id, reason="user_request",
                                                   require=self.required_purge_targets)
        finally:
            deferred, self._deferred = self._deferred, []
            for utt in deferred:
                try:
                    self.on_user_utterance(utt)
                except ErasureInProgressError:  # a concurrent erasure: keep it for the next one
                    self._deferred.append(utt)
        for rid in report.deleted_ids:
            self._recalled.pop(rid, None)
            self._ingested.pop(rid, None)
        return report

    def pending_erasures(self) -> list[dict[str, Any]]:
        """This user's unfinished erasures (see ``MemoryStore.pending_erasures``)."""
        return self.store.pending_erasures(self.user_id)

    def resume_erasure(self, receipt_id: str) -> ErasureReport:
        """Retry the pending purge targets of an unfinished erasure (no new deletion)."""
        return self.store.forget(receipt_id, self.user_id, resume=receipt_id)

    async def resume_erasure_async(self, receipt_id: str) -> ErasureReport:
        return await self.store.forget_async(receipt_id, self.user_id, resume=receipt_id)

    @staticmethod
    def acknowledge_erasure(report: ErasureReport, target: str, ok: bool = True, detail: str = "") -> bool:
        """Ack one purge target (e.g. after ``gen.reset()``); returns ``report.complete``."""
        report.acknowledge(target, ok, detail)
        return report.complete

    def _erasure_hook(self, report: ErasureReport) -> bool:
        # Callbacks must return a truthy ack; any missing ack fails the erasure closed.
        acks = [cb(report) for cb in self.on_erasure]
        return all(bool(a) for a in acks)


__all__ = ["DEFAULT_PURGE_TARGETS", "MemoryBridge", "RecallHit", "RecallResult"]
