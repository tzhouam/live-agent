"""Core data types shared by every component.

The names follow docs/research_proposal_zh.md (v2.11): a *request* is one 5-second
TaoMate-H3 generation unit (4 chunks); a *BlockScript* is our internal description of
one request; an *intent chain* is the scoring unit for instruction following.
All times are monotonic seconds on the shared presentation timeline unless noted.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def now() -> float:
    return time.monotonic()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- persona


@dataclass(frozen=True)
class CanonProfile:
    """Persona canon: fields repeated verbatim in every request; never rewritten by an LLM."""

    persona_id: str
    subject: str  # e.g. "a young East Asian woman (S1) in a green hanfu, ..."
    scene: str
    camera: str
    voice: str
    language: str = "Chinese"  # tag inside <d>[...]</d>
    speech_language: str = "Mandarin"  # used in the soundscape description
    negative: str = (
        "No other person or human voice appears. "
        "No captions or readable text appear anywhere in frame."
    )


# --------------------------------------------------------------------------- scripts


@dataclass
class CheckQuestion:
    """A verifiable yes/no question generated at compile time (online VQQA)."""

    qid: str
    text: str
    kind: str = "action"  # action | speech | identity | scene
    deadline_s: float = 15.0


@dataclass
class BlockScript:
    """Internal description of one 5-second request (see proposal §9)."""

    request_index: int
    plan_version: int
    canon: CanonProfile
    action: str  # must match a capability-manifest entry (or "" for idle)
    transcript: str  # spoken line; "" for silence
    soundscape: str = "Quiet room tone."
    corrections: list[str] = field(default_factory=list)  # forward corrections / textual drift fixes
    checks: list[CheckQuestion] = field(default_factory=list)
    chain_ids: list[str] = field(default_factory=list)  # intent chains this request serves
    provenance: dict[str, Any] = field(default_factory=dict)
    capability_ids: list[str] = field(default_factory=list)
    scene_state: str = ""  # props in their current places + pose (ledger), restated every request
    scene_guard: str = ""  # negative generated from the prop inventory (no duplicates, nothing new)


# --------------------------------------------------------------------------- instructions


class ChainStatus(str, enum.Enum):
    OPEN = "open"
    COMPLIED = "complied"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"  # user withdrew: excluded from the primary denominator
    CAPACITY_SKIPPED = "capacity_skipped"  # dropped by admission control: counts as failure
    REFUSED = "refused"  # compiler refused / degraded: counts as failure
    PRESENTED = "presented"  # open loop (A1): all planned segments shown; compliance unjudged


class TaskKind(str, enum.Enum):
    ACTION = "action"
    CONTENT = "content"
    MULTISTEP = "multistep"
    CORRECTION = "correction"
    MEMORY = "memory"
    CHAT = "chat"


@dataclass
class Utterance:
    uid: str
    speaker: str  # "user" | "persona" | "viewer:<id>"
    text: str
    t_end: float  # VAD endpoint on the shared timeline
    session_id: str = ""
    scope: str = "private"


@dataclass
class IntentChain:
    """Scoring unit: one instruction plus the user's later revisions (proposal §14.3)."""

    chain_id: str
    kind: TaskKind
    opened_by: str  # utterance id
    final_intent: str
    clock_origin: float  # end of the opening or latest revising utterance
    revisions: list[str] = field(default_factory=list)
    status: ChainStatus = ChainStatus.OPEN
    steps: list[str] = field(default_factory=list)  # for multistep
    step_index: int = 0
    first_compliant_t: float | None = None
    requests: list[int] = field(default_factory=list)


# --------------------------------------------------------------------------- timeline


class EventType(str, enum.Enum):
    UTTERANCE_END = "utterance_end"
    LOCK = "lock"  # P_k: script frozen
    TEACHER_START = "teacher_start"
    TEACHER_DONE = "teacher_done"
    STUDENT_START = "student_start"
    CHUNK_READY = "chunk_ready"
    CHUNK_PRESENTED = "chunk_presented"  # client presentation ack (start of chunk)
    CHUNK_PRESENTED_END = "chunk_presented_end"
    REQUEST_DONE = "request_done"
    VERDICT = "verdict"
    INTERRUPT = "interrupt"
    PLAYBACK_STOP = "playback_stop"
    COMPLETION_CLAIM = "completion_claim"
    REFUSAL = "refusal"
    CAPACITY_SKIP = "capacity_skip"
    REPAIR = "repair"
    SPEECH_ONSET = "speech_onset"
    AUDIT = "audit"  # pre-generation script audit (proposal §15)
    NARRATION_GUARD = "narration_guard"  # completion wording removed from an unverified line
    CONTINUITY = "continuity"  # prop counts on presented frames vs the ledger (and the correction queued)
    ERROR = "error"
    OBSERVATION_END = "observation_end"


@dataclass
class TimelineEvent:
    type: EventType
    t: float
    request_index: int | None = None
    chunk_index: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- generation


@dataclass
class Chunk:
    """One generated chunk (audio+video) of a request."""

    request_index: int
    chunk_index: int  # 0..3 within the request
    n_frames: int
    fps: float
    video: Any = None  # np.ndarray [T,H,W,3] uint8, or None for mock
    audio: Any = None  # np.ndarray [S, C] float32
    sample_rate: int = 32000
    encoded: bytes | None = None  # fMP4 fragment, if the generator encodes
    t_ready: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)  # e.g. prompt, session id

    @property
    def duration_s(self) -> float:
        return self.n_frames / self.fps


# --------------------------------------------------------------------------- QC


class VerdictLabel(str, enum.Enum):
    COMPLIED = "complied"
    NOT_COMPLIED = "not_complied"
    UNKNOWN = "unknown"


@dataclass
class Verdict:
    qid: str
    request_index: int
    label: VerdictLabel
    confidence: float
    rationale: str = ""
    t_evidence: float = 0.0  # E: presentation time of the last frame needed
    t_verdict: float = 0.0
