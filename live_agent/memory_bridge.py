"""Adapter from live_agent.memory.MemoryStore to the orchestrator's MemoryPort.

Scope rules (review findings 12/13):

* The bridge's **session mode** ("private" 1:1 or "public" livestream) is authoritative
  for every write. Pass it at construction (``mode=``, from the server's authenticated
  session); if omitted it is pinned by the first orchestrator call that names a mode
  (``recall(mode=...)`` / ``on_persona_line(scope=...)``, both ``OrchestratorConfig.scope``).
  Until pinned, writes are private (fail closed). ``Utterance.scope`` is never trusted.
* Persona lines carry lineage: ``on_persona_line(..., source_ids=[...])`` stores the
  memory ids the line was conditioned on as parents. With ``source_ids=None`` the lineage
  is unknown, so the bridge links the line to *every* memory recalled in this session
  (a conservative superset: erasure and correction still cascade to it) and writes it
  in the session scope. A public write with a private input is refused (returns None).
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
    def __init__(self, db_path: str, *, user_id: str, stream_id: str, session_id: str,
                 store: MemoryStore | None = None, mode: str | None = None,
                 required_purge_targets: Sequence[str] = DEFAULT_PURGE_TARGETS, recall_k: int = 6):
        self.store = store or MemoryStore(db_path)
        self.user_id = user_id
        self.stream_id = stream_id
        self.session_id = session_id
        self._mode: str | None = None
        if mode is not None:
            self._pin(mode)
        self.required_purge_targets = tuple(required_purge_targets)
        self.recall_k = recall_k
        self._recalled: dict[str, None] = {}  # ordered set of memory ids recalled this session
        self.scope_violations: list[dict[str, Any]] = []
        self.mode_mismatches = 0
        self.on_erasure: list[Callable[[ErasureReport], Any]] = []
        self.store.register_purge_target("bridge_callbacks", self._erasure_hook)

    # ------------------------------------------------------------------ session scope

    @property
    def mode(self) -> str | None:
        return self._mode

    def _pin(self, mode: str) -> str:
        if mode not in ("private", "public"):
            raise ValueError(f"session mode must be 'private' or 'public', got {mode!r}")
        if self._mode is None:
            self._mode = mode
        elif mode != self._mode:
            self.mode_mismatches += 1
            log.warning("caller mode %r differs from session mode %r; session mode wins", mode, self._mode)
        return self._mode

    @property
    def write_scope(self) -> str:
        return MemoryStore.session_write_scope(self._mode, self.user_id, self.stream_id)

    def _scope(self, mode: str) -> str:  # kept for compatibility; writes ignore ``mode`` beyond pinning
        self._pin(mode)
        return self.write_scope

    # ------------------------------------------------------------------ recall

    def recall_hits(self, text: str, *, mode: str) -> list[RecallHit]:
        """Retrieval with record ids; the ids are remembered as this session's lineage superset."""
        session_mode = self._pin(mode)
        read_mode = "public" if "public" in (mode, session_mode) else "private"  # never widen reads
        res = self.store.retrieve(text, read_mode, user_id=self.user_id if read_mode == "private" else None,
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
        self.store.ingest_user_utterance(utt, user_id=self.user_id, stream_id=self.stream_id,
                                         mode=self._mode or "private")

    def on_persona_line(self, text: str, *, session_id: str, scope: str,
                        source_ids: Iterable[str] | None = None,
                        request_index: int | None = None) -> Record | None:
        """Log a persona line in the session scope with its lineage.

        ``source_ids``: ids of the memories (``recall_hits(...).id``) the line was
        conditioned on. ``None`` = unknown: linked to all memories recalled this session.
        Returns None (nothing written, violation recorded) if the line would be public but
        an input is private, or if an explicit source was erased meanwhile.
        """
        self._pin(scope)
        if source_ids is None:
            parents, lineage = self.store.existing_ids(self._recalled), "session_recall_superset"
        else:
            wanted = list(dict.fromkeys(source_ids))
            parents, lineage = self.store.existing_ids(wanted), "explicit"
            if len(parents) != len(wanted):
                return self._violation(text, "source memory no longer exists (erased)",
                                       sorted(set(wanted) - set(parents)))
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
