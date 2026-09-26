"""Session-log schema (JSONL) for E2 scoring. Human-readable spec: ``SCHEMA.md``.

One file = one session = one task x one seed x one condition. Line 1 is a ``session``
header; every other line is an event. All times are seconds on the shared presentation
timeline (the same clock as ``live_agent.types.now``), not wall-clock.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# event type -> required fields (besides "type")
REQUIRED: dict[str, tuple[str, ...]] = {
    "session": ("session_id", "condition", "task_id", "seed"),
    "utterance": ("uid", "speaker", "text", "t_start", "t_end"),
    "chain_annotation": ("uid", "action", "chain_id"),
    "lock": ("t", "request"),
    "chunk_presented": ("request", "chunk", "t_start", "t_end"),
    "verdict": ("source", "label"),
    "completion_claim": ("chain_id", "t"),
    "refusal": ("chain_id", "t"),
    "capacity_skip": ("chain_id", "t"),
    "speech_onset": ("t", "on_topic"),
    "visual_ack": ("t", "uid"),
    "playback_stop": ("t",),
    "repair_assignment": ("chain_id", "arm", "failure_request", "target_request"),
    "observation_end": ("t",),
    # one annotator's raw, independent label (kept for agreement statistics; never scored)
    "rating": ("annotator", "chain_id", "label"),
    # an adjudicated audio sweep of the session's recording for completion claims
    "claim_sweep": ("source",),
}

ANNOTATION_ACTIONS = ("new", "revision", "withdrawal")
VERDICT_LABELS = ("complied", "not_complied", "unknown")
VERDICT_SOURCES = ("adjudicated", "human", "judge")
REFUSAL_KINDS = ("refused", "degraded")
REPAIR_ARMS = ("forward_correction", "repeat")
ONSET_SOURCES = ("script", "adjudicated", "human")
SESSION_MODES = ("simulation", "generator_path", "browser")
CLAIM_SOURCES = ("system", "adjudicated")


class SchemaError(ValueError):
    pass


@dataclass
class SessionLog:
    meta: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def session_id(self) -> str:
        return str(self.meta["session_id"])

    @property
    def condition(self) -> str:
        return str(self.meta["condition"])

    @property
    def task_id(self) -> str:
        return str(self.meta["task_id"])

    @property
    def seed(self) -> int:
        return int(self.meta["seed"])

    def of_type(self, *types: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] in types]


def validate_event(ev: dict[str, Any]) -> None:
    typ = ev.get("type")
    if typ not in REQUIRED:
        raise SchemaError(f"unknown event type {typ!r}: {ev}")
    missing = [k for k in REQUIRED[typ] if k not in ev]
    if missing:
        raise SchemaError(f"{typ} event missing {missing}: {ev}")
    if typ == "chain_annotation" and ev["action"] not in ANNOTATION_ACTIONS:
        raise SchemaError(f"bad annotation action {ev['action']!r}")
    if typ == "verdict":
        if ev["label"] not in VERDICT_LABELS:
            raise SchemaError(f"bad verdict label {ev['label']!r}")
        if ev["source"] not in VERDICT_SOURCES:
            raise SchemaError(f"bad verdict source {ev['source']!r}")
        if "claim_id" not in ev and "chain_id" not in ev:
            raise SchemaError(f"verdict needs chain_id or claim_id: {ev}")
    if typ == "refusal" and ev.get("kind", "refused") not in REFUSAL_KINDS:
        raise SchemaError(f"bad refusal kind {ev.get('kind')!r}")
    if typ == "repair_assignment" and ev["arm"] not in REPAIR_ARMS:
        raise SchemaError(f"bad repair arm {ev['arm']!r}")
    if typ == "completion_claim" and ev.get("source", "system") not in CLAIM_SOURCES:
        raise SchemaError(f"bad completion_claim source {ev.get('source')!r}")
    if typ == "claim_sweep" and ev["source"] != "adjudicated":
        raise SchemaError(f"claim_sweep source must be 'adjudicated': {ev}")
    if typ == "rating" and ev["label"] not in VERDICT_LABELS:
        raise SchemaError(f"bad rating label {ev['label']!r}")
    if typ == "speech_onset":
        if ev.get("source", "script") not in ONSET_SOURCES:
            raise SchemaError(f"bad speech_onset source {ev.get('source')!r}")
        if ev["on_topic"] not in (True, False, None):
            raise SchemaError(f"speech_onset on_topic must be true/false/null: {ev}")
    if typ == "session" and ev.get("mode") is not None and ev["mode"] not in SESSION_MODES:
        raise SchemaError(f"bad session mode {ev['mode']!r} (expected one of {SESSION_MODES})")


def _sort_key(ev: dict[str, Any]) -> float:
    for k in ("t", "t_end", "t_evidence", "t_start"):
        if k in ev and ev[k] is not None:
            return float(ev[k])
    return float("-inf")


def parse_session(records: Iterable[dict[str, Any]]) -> SessionLog:
    records = list(records)
    if not records or records[0].get("type") != "session":
        raise SchemaError("first record must be a 'session' header")
    meta = dict(records[0])
    validate_event(meta)
    events = []
    for ev in records[1:]:
        validate_event(ev)
        events.append(dict(ev))
    events.sort(key=_sort_key)  # stable: equal times keep file order
    return SessionLog(meta=meta, events=events)


def load_session(path: str | Path) -> SessionLog:
    with open(path, encoding="utf-8") as f:
        recs = [json.loads(line) for line in f if line.strip()]
    return parse_session(recs)


class SessionLogWriter:
    """Append-only JSONL writer; the orchestrator and the simulated user share one."""

    def __init__(self, path: str | Path, **meta: Any):
        self.path = Path(path)
        header = {"type": "session", "schema_version": SCHEMA_VERSION, **meta}
        validate_event(header)
        self._f = open(self.path, "w", encoding="utf-8")
        self.write(header)

    def write(self, ev: dict[str, Any]) -> None:
        validate_event(ev)
        self._f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> SessionLogWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
