"""Record model for long-term memory (proposal §5.6).

Working context (prompt, recent turns, presented-content summary) and inference caches
(TaoMate-H3 KV, LLM KV) are deliberately *not* modelled here: they live and die with a
session and must never be confused with long-term memory.

Scopes
------
``private:<user_id>``  one user's private conversation data.
``public:<stream_id>`` data from one public livestream (viewer chat, public persona lines).
``canon``              persona canon anchors; the only thing a public session may boot from.

Every record carries ``source_scopes``: the union of its own scope and the
``source_scopes`` of everything it was derived from. Retrieval filters on
``source_scopes`` (never on ``scope`` alone), so a "public" ledger entry that was
derived from a private conversation can never be read in public mode.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


class Kind(str, enum.Enum):
    USER_FACT = "user_fact"  # semantic: subject, predicate, value, valid_from/to, confidence
    EPISODE = "episode"  # append-only turn log (user / viewer turns)
    LEDGER = "ledger"  # persona / world continuity; canonical anchors are immutable
    GENERATED_EVENT = "generated_event"  # everything the persona said or showed; never promoted
    CANDIDATE_BELIEF = "candidate_belief"  # agent inference pending confirmation
    PROCEDURAL = "procedural"  # A²RD-style success / failure prompt-library entry
    SUMMARY = "summary"  # sleep-time consolidation output (derived artifact)


class ClaimType(str, enum.Enum):
    OWN_ASSERTION = "own_assertion"
    QUOTE_OF_PERSONA = "quote_of_persona"
    QUESTION = "question"
    HYPOTHETICAL = "hypothetical"  # includes jokes / role-play
    AGENT_INFERENCE = "agent_inference"
    VIEWER_CLAIM = "viewer_claim"
    SYSTEM_OBSERVATION = "system_observation"  # also used for persona output (speaker="persona")


class Status(str, enum.Enum):
    ACTIVE = "active"  # usable
    PENDING = "pending"  # needs explicit user confirmation (echo, conflict, candidate belief)
    SUPERSEDED = "superseded"  # bi-temporal history: valid_to is set, kept for audit
    STALE = "stale"  # derived artifact whose source was corrected; must be regenerated
    REJECTED = "rejected"  # user declined a pending candidate


# Conflict-resolution priority (higher wins): user-asserted > system-observed >
# agent-inferred > viewer-claimed. Anything else never resolves a fact.
CLAIM_PRIORITY: dict[ClaimType, int] = {
    ClaimType.OWN_ASSERTION: 4,
    ClaimType.SYSTEM_OBSERVATION: 3,
    ClaimType.AGENT_INFERENCE: 2,
    ClaimType.VIEWER_CLAIM: 1,
}

# Predicates that hold one value at a time; a new value is a correction or a conflict.
SINGLE_VALUED = {"lives_in", "name", "works_at", "age", "birthday"}


def is_single_valued(predicate: str | None) -> bool:
    return bool(predicate) and (predicate in SINGLE_VALUED or predicate.startswith("favorite"))


CANON = "canon"


def private_scope(user_id: str) -> str:
    return f"private:{user_id}"


def public_scope(stream_id: str) -> str:
    return f"public:{stream_id}"


def validate_scope(scope: str) -> str:
    if scope == CANON:
        return scope
    head, sep, tail = scope.partition(":")
    if sep and tail and head in ("private", "public"):
        return scope
    raise ValueError(f"invalid scope {scope!r}; expected private:<user>, public:<stream> or canon")


def is_private(scope: str) -> bool:
    return scope.startswith("private:")


@dataclass
class Provenance:
    source_id: str = ""  # utterance / frame / request id that produced the record
    speaker: str = ""  # "user" | "persona" | "viewer:<id>" | "agent" | "system"
    session_id: str = ""
    timestamp: float = 0.0  # wall-clock seconds of the source event
    extractor_version: str = ""
    user_id: str = ""  # owning user (for erasure), "" if none

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> Provenance:
        return cls(**json.loads(s)) if s else cls()


@dataclass
class Record:
    id: str
    kind: Kind
    scope: str
    source_scopes: frozenset[str]
    claim_type: ClaimType
    text: str
    provenance: Provenance
    derived_from: tuple[str, ...] = ()
    created_at: float = 0.0
    # semantic fields (user_fact / candidate_belief; optional elsewhere)
    subject: str | None = None
    predicate: str | None = None
    value: str | None = None
    valid_from: float | None = None
    valid_to: float | None = None
    confidence: float = 1.0
    status: Status = Status.ACTIVE
    echo: bool = False
    importance: float = 0.5
    immutable: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def tags(self) -> dict[str, Any]:
        """Compact provenance / claim-type tags for prompt rendering."""
        return {
            "kind": self.kind.value,
            "claim_type": self.claim_type.value,
            "scope": self.scope,
            "speaker": self.provenance.speaker,
            "status": self.status.value,
            "echo": self.echo,
            "source_id": self.provenance.source_id,
        }

    def is_valid_at(self, t: float) -> bool:
        start_ok = self.valid_from is None or self.valid_from <= t
        return start_ok and (self.valid_to is None or t < self.valid_to)


def union_scopes(own: str, parents: Iterable[Record]) -> frozenset[str]:
    out = {own}
    for p in parents:
        out |= p.source_scopes
    return frozenset(out)
