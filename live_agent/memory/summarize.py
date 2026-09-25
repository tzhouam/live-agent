"""Pluggable sleep-time summarisers used by :meth:`MemoryStore.consolidate`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .schema import ClaimType, Kind, Record


@runtime_checkable
class Summarizer(Protocol):
    version: str

    def summarize(self, records: Sequence[Record]) -> str:
        ...


class ExtractiveSummarizer:
    """Deterministic default: lists active facts, then user turns, then persona lines.

    Lines keep their provenance label so a summary never launders persona output or
    quotes into apparent user assertions.
    """

    version = "extractive-v1"

    def __init__(self, max_chars: int = 600) -> None:
        self.max_chars = max_chars

    def summarize(self, records: Sequence[Record]) -> str:
        facts = [r for r in records if r.kind == Kind.USER_FACT]
        turns = [r for r in records if r.kind == Kind.EPISODE]
        persona = [r for r in records if r.kind == Kind.GENERATED_EVENT]
        lines: list[str] = []
        for r in facts:
            lines.append(f"[fact:{r.claim_type.value}] {r.subject} {r.predicate} {r.value}")
        for r in turns:
            tag = "user" if r.claim_type == ClaimType.OWN_ASSERTION else f"user:{r.claim_type.value}"
            lines.append(f"[{tag}] {r.text}")
        for r in persona:
            lines.append(f"[persona said] {r.text}")
        out: list[str] = []
        n = 0
        for ln in lines:
            if n + len(ln) > self.max_chars:
                break
            out.append(ln)
            n += len(ln) + 1
        return "\n".join(out)
