"""Capability manifest: what the generator is *measured* to render reliably (proposal §8, §14.2).

Each entry maps an intent (e.g. "drink_tea") to the exact English action phrase that
goes into the H3 prompt, plus calibrated statistics from experiment E1. The compiler
only emits entries whose status is at least ``executed`` and whose success rate is
above threshold; everything else is degraded (e.g. to a verbal reply) or refused.
Refusals and degradations are logged and count as failures in scoring.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


class Status(str, enum.Enum):
    DOCUMENTED = "documented"
    CODE_READ = "code_read"
    EXECUTED = "executed"  # rendered at least once in M0/M1
    CALIBRATED = "calibrated"  # E1 statistics available

    @property
    def rank(self) -> int:
        return ["documented", "code_read", "executed", "calibrated"].index(self.value)


@dataclass
class Capability:
    cap_id: str
    intent: str  # canonical intent key, e.g. "drink_tea"
    phrase: str  # exact action phrase used in the prompt
    aliases: list[str] = field(default_factory=list)  # user-language triggers (中文/English)
    status: Status = Status.DOCUMENTED
    p_success: float | None = None  # E1: fraction judged compliant within deadline
    p_ci: tuple[float, float] | None = None
    tvc_median_s: float | None = None
    side_effects: list[str] = field(default_factory=list)
    check_question: str = ""  # default QC question for this action
    degrade_to: str = ""  # verbal fallback line when refused/degraded

    def usable(self, min_status: Status, min_p: float) -> bool:
        if self.status.rank < min_status.rank:
            return False
        if self.status == Status.CALIBRATED and (self.p_success or 0.0) < min_p:
            return False
        if self.p_success is not None and self.p_success < min_p:  # measured (e.g. judge-only E1) below threshold
            return False
        return True


class Decision(str, enum.Enum):
    EMIT = "emit"
    DEGRADE = "degrade"
    REFUSE = "refuse"


@dataclass
class CompileResult:
    decision: Decision
    capability: Capability | None
    reason: str


class CapabilityManifest:
    def __init__(self, caps: list[Capability], *, min_status: Status = Status.EXECUTED, min_p: float = 0.6):
        self.caps = {c.cap_id: c for c in caps}
        self.min_status = min_status
        self.min_p = min_p

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: str | Path, **kw) -> CapabilityManifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        caps = []
        for d in data["capabilities"]:
            d = dict(d)
            d["status"] = Status(d.get("status", "documented"))
            if d.get("p_ci") is not None:
                d["p_ci"] = tuple(d["p_ci"])
            caps.append(Capability(**d))
        return cls(caps, min_status=Status(data.get("min_status", kw.get("min_status", "executed"))),
                   min_p=data.get("min_p", kw.get("min_p", 0.6)))

    def save(self, path: str | Path) -> None:
        out = {
            "min_status": self.min_status.value,
            "min_p": self.min_p,
            "capabilities": [
                {**asdict(c), "status": c.status.value} for c in self.caps.values()
            ],
        }
        Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ lookup
    def match(self, text: str) -> Capability | None:
        """Find the capability whose intent or alias occurs in ``text`` (longest alias wins)."""
        best: tuple[int, Capability] | None = None
        low = text.lower()
        for c in self.caps.values():
            for a in [c.intent, *c.aliases]:
                if a and a.lower() in low and (best is None or len(a) > best[0]):
                    best = (len(a), c)
        return best[1] if best else None

    def by_intent(self, intent: str) -> Capability | None:
        for c in self.caps.values():
            if c.intent == intent:
                return c
        return None

    def decide(self, intent: str) -> CompileResult:
        cap = self.by_intent(intent)
        if cap is None:
            return CompileResult(Decision.REFUSE, None, f"no capability for intent {intent!r}")
        if cap.usable(self.min_status, self.min_p):
            return CompileResult(Decision.EMIT, cap, "ok")
        if cap.degrade_to:
            return CompileResult(Decision.DEGRADE, cap, f"status={cap.status.value} p={cap.p_success}")
        return CompileResult(Decision.REFUSE, cap, f"status={cap.status.value} p={cap.p_success}")

    def update_from_calibration(self, cap_id: str, *, successes: int, trials: int,
                                ci: tuple[float, float], tvc_median_s: float | None,
                                validated: bool = False) -> None:
        """Record an E1 estimate. Only human-validated labels (judge agreement checked on the 20%
        sample) make a capability ``calibrated``; a judge-only pass marks it ``executed``."""
        c = self.caps[cap_id]
        c.status = Status.CALIBRATED if validated else Status.EXECUTED
        c.p_success = successes / trials if trials else 0.0
        c.p_ci = ci
        c.tvc_median_s = tvc_median_s
