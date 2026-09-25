"""Adapter from live_agent.memory.MemoryStore to the orchestrator's MemoryPort."""

from __future__ import annotations

from collections.abc import Callable

from live_agent.memory.store import ErasureReport, MemoryStore
from live_agent.types import Utterance


class MemoryBridge:
    def __init__(self, db_path: str, *, user_id: str, stream_id: str, session_id: str,
                 store: MemoryStore | None = None):
        self.store = store or MemoryStore(db_path)
        self.user_id = user_id
        self.stream_id = stream_id
        self.session_id = session_id
        self.on_erasure: list[Callable[[ErasureReport], None]] = []
        self.store.erasure_hooks.append(self._erasure_hook)

    def _scope(self, mode: str) -> str:
        return f"private:{self.user_id}" if mode == "private" else f"public:{self.stream_id}"

    def recall(self, text: str, *, mode: str) -> list[str]:
        res = self.store.retrieve(text, mode, user_id=self.user_id if mode == "private" else None,
                                  stream_id=self.stream_id, k=6)
        out = []
        for h in res.hits:
            t = h.tags
            out.append(f"[{t.get('kind')}/{t.get('claim_type')}/{t.get('status', 'active')}] {h.record.text}")
        return out

    def on_user_utterance(self, utt: Utterance) -> None:
        self.store.ingest_user_utterance(utt, user_id=self.user_id, stream_id=self.stream_id)

    def on_persona_line(self, text: str, *, session_id: str, scope: str) -> None:
        self.store.record_generated_event(text, session_id, self._scope(scope), user_id=self.user_id)

    def forget(self, term: str) -> ErasureReport:
        return self.store.forget(term, self.user_id, reason="user_request")

    def _erasure_hook(self, report: ErasureReport) -> None:
        for cb in self.on_erasure:
            cb(report)
