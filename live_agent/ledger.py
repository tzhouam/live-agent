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
    """One physical object of the scene. ``home`` (canon) is where it belongs; ``location`` is where it is now."""

    name: str
    location: str  # e.g. "open and lying flat on the desk in front of her"
    carrier: str | None = None  # "S1" when held
    noun: str = ""  # prompt noun, e.g. "round silk fan" (defaults to name)
    label: str = ""  # judge noun (中文), e.g. "团扇"; empty = never counted
    home: str = ""  # canon place; an effect "home" returns the prop here
    count: int = 1  # how many exist (the continuity check expects exactly this many)

    def __post_init__(self) -> None:
        self.noun = self.noun or self.name
        self.home = self.home or self.location


HOME = "home"


BRIDGE_MAX_CHARS = 200  # = the prompt compiler's correction limit (h3_compiler._clean max_len)


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
        self.bridge_request: int | None = None  # request carrying the bridge (divergence kept until shown)
        self.partially_shown: set[int] = set()
        self.room: str = ""  # scene without its props (props are rendered from their current state)
        # side effects of locked actions not yet verified: request index -> effects. Later requests are
        # compiled against committed + pending state (the action is already in the video); a failed or
        # dropped action is reverted, a verified one committed.
        self.pending: dict[int, list[dict]] = {}

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
        if d.get("props"):  # structured inventory: rendered from state in every prompt, checked on frames
            props = [PropState(p["name"], p["home"], noun=p.get("noun", ""), label=p.get("label", ""),
                               home=p["home"], count=int(p.get("count", 1))) for p in d["props"]]
        else:  # legacy personas: free-text scene only, nothing rendered or counted
            props = [PropState("book", "open on the desk"), PropState("teacup", "on the desk"),
                     PropState("teapot", "on the desk")]
        ledger = cls(canon, props)
        ledger.room = d.get("room", "") if d.get("props") else ""
        if d.get("pose"):
            ledger.pose = d["pose"]
        return ledger

    # ---------------------------------------------------------------- updates
    def record_request(self, request_index: int, action: str, transcript: str) -> None:
        self.history.append(RequestState(request_index, action, transcript))

    def redact(self, term: str) -> int:
        """Erasure: remove a term from per-request history (it feeds continuity / bridging text)."""
        n = 0
        for r in self.history:
            for f in ("action", "transcript", "notes"):
                v = getattr(r, f)
                if term in v:
                    setattr(r, f, v.replace(term, "[已删除]"))
                    n += 1
        return n

    def mark_presented(self, request_index: int) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.presented = True
        if request_index in self.generated_not_presented:
            self.generated_not_presented.remove(request_index)

    def mark_fully_presented(self, request_index: int) -> None:
        if self.bridge_request is not None and request_index == self.bridge_request:
            # the whole bridge request has been shown: the divergence is reconciled
            self.generated_not_presented.clear()
            self.partially_shown.clear()
            self.bridge_request = None

    def unseen(self) -> list[RequestState]:
        """Generated-but-unpresented requests (their action and speech exist in generator state)."""
        return [r for r in self.history if r.request_index in self.generated_not_presented]

    def mark_generated_not_presented(self, request_index: int, partially_shown: bool = False) -> None:
        """Interrupt case (proposal §10.5, option 3): content exists in generator state but was not
        (fully) shown. ``partially_shown``: some chunks were already seen/heard."""
        if request_index not in self.generated_not_presented:
            self.generated_not_presented.append(request_index)
        if partially_shown:
            self.partially_shown.add(request_index)
        if self.bridge_request is not None and request_index == self.bridge_request:
            self.bridge_request = None  # the bridge itself was cut: bridge again next time

    # ---------------------------------------------------------------- scene state
    def _apply(self, props: dict[str, tuple[str, str | None]], pose: str, effects: list[dict]) -> str:
        for e in effects:
            if "pose" in e:
                pose = e["pose"]
            name = e.get("prop")
            if name in props:
                where = e.get("state", HOME)
                if where == HOME:
                    props[name] = (self.props[name].home, None)
                else:
                    props[name] = (where, e.get("carrier"))
        return pose

    def state_for(self, request_index: int) -> tuple[dict[str, tuple[str, str | None]], str]:
        """(prop -> (location, carrier), pose) at the start of ``request_index``: committed state plus the
        pending effects of earlier locked actions."""
        props = {n: (p.location, p.carrier) for n, p in self.props.items()}
        pose = self.pose
        for k in sorted(self.pending):
            if k < request_index:
                pose = self._apply(props, pose, self.pending[k])
        return props, pose

    def expect(self, request_index: int, effects: list[dict]) -> None:
        """A request with a state-changing action was locked (its effects hold for later requests)."""
        effects = [e for e in effects or [] if isinstance(e, dict)]
        if effects:
            self.pending[request_index] = effects

    def commit(self, request_index: int) -> None:
        """The action of ``request_index`` was verified on presented frames: its effects become canon state."""
        effects = self.pending.pop(request_index, None)
        if not effects:
            return
        props = {n: (p.location, p.carrier) for n, p in self.props.items()}
        self.pose = self._apply(props, self.pose, effects)
        for n, (loc, carrier) in props.items():
            self.props[n].location, self.props[n].carrier = loc, carrier

    def revert(self, request_index: int) -> None:
        """The action failed or was never shown: later requests must not assume its effects."""
        self.pending.pop(request_index, None)

    def apply_verified_action(self, intent: str) -> None:  # legacy hook (effects now come from the manifest)
        return None

    def fill(self, phrase: str, request_index: int) -> str:
        """Replace ``{prop}`` placeholders of a capability phrase with the prop's current place."""
        if "{" not in phrase:
            return phrase
        props, _ = self.state_for(request_index)
        for name, (loc, _c) in props.items():
            phrase = phrase.replace("{" + name + "}", loc)
        return phrase

    def inventory_sentence(self, request_index: int) -> str:
        """Every prop, each once, in its current place: identical wording while nothing moves, so the
        scene reads the same in every request (the model copies what the text keeps constant)."""
        if not self.room:
            return ""
        props, pose = self.state_for(request_index)
        items = [f"the {self.props[n].noun} {loc}" for n, (loc, _c) in props.items()]
        return (f"S1 is {pose}. Exactly these objects are in the scene, one of each, each in its place: "
                + "; ".join(items))

    def duplicate_guard(self) -> str:
        """Negative sentence generated from the inventory: nothing doubles, nothing new appears."""
        if not self.room:
            return ""
        nouns = [p.noun for p in self.props.values()][:6]
        return (f"Each object appears exactly once: no second {', no second '.join(nouns)}, "
                "and no new objects appear on the desk or in her hands")

    def expected_counts(self) -> dict[str, int]:
        """Judge noun -> expected count for the props the continuity check counts."""
        return {p.label: p.count for p in self.props.values() if p.label}

    def continuity_fix(self, label: str, found: int, request_index: int) -> str | None:
        """One correction sentence (<= 200 chars) for a prop the frames show the wrong number of times."""
        prop = next((p for p in self.props.values() if p.label == label), None)
        if prop is None:
            return None
        loc = self.state_for(request_index)[0][prop.name][0]
        if found > prop.count:
            s = f"There is only one {prop.noun}, {loc}; the extra {prop.noun} is gone"
        else:
            s = f"The {prop.noun} is clearly visible {loc}"
        return s[:BRIDGE_MAX_CHARS]

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
        """If generated-but-unshown content exists, return an explicit bridging instruction that
        names what the viewer did not see (so later video does not silently continue from it)."""
        if not self.generated_not_presented or self.bridge_request is not None:
            return None
        unseen = [r for r in self.unseen() if r.request_index not in self.partially_shown]
        cut = [r for r in self.unseen() if r.request_index in self.partially_shown]
        acts = [r.action for r in unseen if r.action]
        said = [r.transcript for r in unseen if r.transcript]
        parts = []
        if acts:
            parts.append("S1 did not do the following on screen and does not continue it: " + "; ".join(acts))
        if said:
            parts.append("S1 did not say the following aloud and does not refer to it: " + " / ".join(said))
        if cut:  # partly seen/heard: which part is unknown at text level, so only stop it
            parts.append("S1 stops what she was doing mid-way ("
                         + "; ".join(r.action or "speaking" for r in cut) + ") and does not finish it")
        parts.append("S1 calmly returns to her previous posture and looks into the lens")
        note = ". ".join(parts)
        if len(note) > BRIDGE_MAX_CHARS:
            # the compiler rejects corrections longer than 200 characters: keep the full list out
            # of the prompt (it stays in the ledger/log) and say only what must not continue
            note = ("S1 does not continue or refer to the interrupted action or line; "
                    "S1 calmly returns to her previous posture and looks into the lens")
        return note

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
            "pending": {str(k): v for k, v in self.pending.items()},
            "props": {k: asdict(v) for k, v in self.props.items()},
            "history": [asdict(h) for h in self.history[-20:]],
            "generated_not_presented": list(self.generated_not_presented),
        }
