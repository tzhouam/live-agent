"""Adapter from live_agent.memory.MemoryStore to the orchestrator's MemoryPort.

Scope rules (review findings 12/13, round 2):

* The bridge's **session mode** ("private" 1:1 or "public" livestream) is required at
  construction (from the server's authenticated session) and can never change: a call
  naming another mode raises :class:`ScopeViolationError`. ``Utterance.scope`` is never
  trusted; every write uses the session scope.
* Persona lines carry lineage. ``on_persona_line(..., source_ids=[...], lineage=...)``:

  - ``lineage="complete"``: ``source_ids`` is the full list of memory inputs;
  - ``lineage="none"``: the caller asserts the line had no memory inputs (no ids);
  - default (``lineage=None``): unknown. The bridge then links the line to every memory
    recalled and every turn ingested in this session (a conservative superset, so
    erasure and correction still cascade to it), plus any ``source_ids`` given.

  A **public** line is stored only with complete lineage ("complete" / "none") and no
  private input; otherwise nothing is written and None is returned (see
  ``scope_violations``). Private lines with unknown lineage are stored privately.
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
from live_agent.memory.store import ErasureReport, MemoryStore, ScopeViolationError
from live_agent.types import Utterance

log = logging.getLogger("live_agent.memory_bridge")

# External state that can hold erased content (proposal §5.6 erasure list). Each must ack.
DEFAULT_PURGE_TARGETS = ("llm_context", "unsent_scripts", "generator_state", "recordings")


@dataclass
class RecallHit:
    id: str
    text: str
    tags: dict[str, Any]
    rendered: str  # the string form passed to the director


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

    def recall_hits(self, text: str, *, mode: str) -> list[RecallHit]:
        """Retrieval with record ids; the ids are remembered as this session's lineage superset."""
        self._check_mode(mode)
        res = self.store.retrieve(text, self._mode, user_id=self.user_id if self._mode == "private" else None,
                                  stream_id=self.stream_id, k=self.recall_k)
        out = []
        for h in res.hits:
            t = h.tags
            out.append(RecallHit(h.record.id, h.record.text, t,
                                 f"[{t.get('kind')}/{t.get('claim_type')}/{t.get('status', 'active')}] {h.record.text}"))
            self._recalled[h.record.id] = None
        return out

    def recall(self, text: str, *, mode: str) -> list[str]:
        return [h.rendered for h in self.recall_hits(text, mode=mode)]

    # ------------------------------------------------------------------ writes

    def on_user_utterance(self, utt: Utterance) -> None:
        res = self.store.ingest_user_utterance(utt, user_id=self.user_id, stream_id=self.stream_id,
                                               mode=self._mode)
        for rec in [res.episode, *res.facts, res.generated_event]:
            if rec is not None:
                self._ingested[rec.id] = None

    def on_persona_line(self, text: str, *, session_id: str, scope: str,
                        source_ids: Iterable[str] | None = None, lineage: str | None = None,
                        request_index: int | None = None) -> Record | None:
        """Log a persona line in the session scope with its lineage (see module docstring).

        Returns None (nothing written, reason in ``scope_violations``) if the line would
        be public without complete lineage or with a private input, or if an explicit
        source was erased meanwhile.
        """
        self._check_mode(scope)
        if lineage not in (None, "complete", "none"):
            raise ValueError("lineage must be None (unknown), 'complete' or 'none'")
        wanted = list(dict.fromkeys(source_ids or ()))
        parents = self.store.existing_ids(wanted)
        if len(parents) != len(wanted):
            return self._violation(text, "source memory no longer exists (erased)",
                                   sorted(set(wanted) - set(parents)))
        if lineage is None:
            if self._mode == "public":
                return self._violation(text, "public persona line without complete source lineage", parents)
            parents = self.store.existing_ids([*parents, *self._recalled, *self._ingested])
            lineage = "session_superset"
        try:
            return self.store.record_generated_event(
                text, session_id, self.write_scope, user_id=self.user_id, derived_from=parents,
                request_index=request_index, lineage=lineage)
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

    @staticmethod
    def acknowledge_erasure(report: ErasureReport, target: str, ok: bool = True, detail: str = "") -> bool:
        """Ack one purge target (e.g. after ``gen.reset()``); returns ``report.complete``."""
        report.acknowledge(target, ok, detail)
        return report.complete

    def _erasure_hook(self, report: ErasureReport) -> bool:
        # Callbacks must return a truthy ack; any missing ack fails the erasure closed.
        acks = [cb(report) for cb in self.on_erasure]
        return all(bool(a) for a in acks)


__all__ = ["DEFAULT_PURGE_TARGETS", "MemoryBridge", "RecallHit"]
