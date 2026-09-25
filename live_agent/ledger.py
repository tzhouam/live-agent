"""State ledger: online CANVAS + A²RD continuity layer (proposal §8.2 layer 3, §10.4).

The ledger keeps
- the immutable canon (persona appearance, scene, camera, voice) -- never overwritten;
- the *current* state that may legitimately change (props and who holds them, pose,
  whether the book is open, what was last done/said) -- updated only from events that
  were *presented* (and, for claimed completions, verified);
- per-request textual state (A²RD style) for audit and for composing the next request.

It produces the canon block for each BlockScript and the textual drift corrections
("the hairpin is jade, not gold") used by the text-correction intervention.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from live_agent.types import CanonProfile


@dataclass
class PropState:
    name: str
    location: str  # e.g. "on the desk"
    carrier: str | None = None  # "S1" when held


@dataclass
class RequestState:
    request_index: int
    action: str
    transcript: str
    presented: bool = False
    verified: dict[str, str] = field(default_factory=dict)  # qid -> verdict label
    identity_score: float | None = None
    notes: str = ""


class StateLedger:
    def __init__(self, canon: CanonProfile, props: list[PropState] | None = None):
        self._canon = canon
        self.props: dict[str, PropState] = {p.name: p for p in (props or [])}
        self.pose: str = "seated at the desk"
        self.history: list[RequestState] = []
        self.generated_not_presented: list[int] = []  # requests generated but never shown

    # ---------------------------------------------------------------- canon
    @property
    def canon(self) -> CanonProfile:
        return self._canon  # frozen dataclass: cannot be mutated

    @classmethod
    def from_config(cls, path: str | Path) -> StateLedger:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        canon = CanonProfile(
            persona_id=d["persona_id"], subject=d["subject"], scene=d["scene"],
            camera=d["camera"], voice=d["voice"], language=d.get("language", "Chinese"),
            speech_language=d.get("speech_language", "Mandarin"),
            negative=d.get("negative", CanonProfile.__dataclass_fields__["negative"].default),
        )
        props = [PropState("book", "open on the desk"), PropState("teacup", "on the desk"),
                 PropState("teapot", "on the desk")]
        return cls(canon, props)

    # ---------------------------------------------------------------- updates
    def record_request(self, request_index: int, action: str, transcript: str) -> None:
        self.history.append(RequestState(request_index, action, transcript))

    def mark_presented(self, request_index: int) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.presented = True
        if request_index in self.generated_not_presented:
            self.generated_not_presented.remove(request_index)

    def mark_generated_not_presented(self, request_index: int) -> None:
        """Interrupt case (proposal §10.5, option 3): content exists in generator state but was not shown."""
        if request_index not in self.generated_not_presented:
            self.generated_not_presented.append(request_index)

    def apply_verified_action(self, intent: str) -> None:
        """Update prop/pose state after an action was *verified* on presented frames."""
        if intent == "stand_up":
            self.pose = "standing beside the desk"
        elif intent in ("put_down_book",):
            self.props.setdefault("book", PropState("book", "on the desk")).location = "closed on the desk"
            self.props["book"].carrier = None
        elif intent == "pick_up_book":
            self.props.setdefault("book", PropState("book", "")).carrier = "S1"
            self.props["book"].location = "held open in her hands"
        elif intent == "drink_tea":
            self.props.setdefault("teacup", PropState("teacup", "on the desk")).location = "on the desk"

    def record_verdict(self, request_index: int, qid: str, label: str) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.verified[qid] = label

    # ---------------------------------------------------------------- prompt helpers
    def continuity_sentence(self) -> str:
        """Current (non-canon) state restated each request, e.g. pose and held props."""
        held = [p.name for p in self.props.values() if p.carrier == "S1"]
        parts = [f"S1 is {self.pose}"]
        if held:
            parts.append("holding the " + " and the ".join(held))
        return ", ".join(parts)

    def bridging_note(self) -> str | None:
        """If generated-but-unshown content exists, return an explicit bridging instruction."""
        if not self.generated_not_presented:
            return None
        return "S1 calmly returns to her previous posture and looks into the lens"

    @staticmethod
    def drift_correction(attribute: str, correct: str, wrong: str | None = None) -> str:
        """Textual drift correction (intervention 1 in proposal §10.4)."""
        if wrong:
            return f"Her {attribute} is {correct}, not {wrong}"
        return f"Her {attribute} is {correct}"

    def snapshot(self) -> dict:
        return {
            "canon": asdict(self._canon),
            "pose": self.pose,
            "props": {k: asdict(v) for k, v in self.props.items()},
            "history": [asdict(h) for h in self.history[-20:]],
            "generated_not_presented": list(self.generated_not_presented),
        }
