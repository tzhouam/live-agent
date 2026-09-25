"""E2 task-suite format (one JSON object per line) and loader/validator.

A task is a scripted user session. Each scripted utterance carries its chain annotation
(``new`` / ``revision`` / ``withdrawal`` / ``none``) and, for ``new`` and ``revision``,
the intent the chain has *after* that utterance; scoring uses the final one.

Task line::

    {"task_id": "E2-A01", "suite": "e2_committed", "kind": "action",
     "persona": "hanfu_scholar_study", "title": "喝茶", "category": "single_action",
     "utterances": [
       {"offset_s": 2.0, "text": "请喝口茶吧。", "annotation": "new", "chain": "c1",
        "barge_in": false,
        "intent": {"kind": "action", "intent": "端起茶杯喝一口茶",
                   "checks": ["人物端起茶杯", "茶杯送到嘴边作饮用动作"]}}],
     "duration_s": 25.0}

Intent fields: ``kind`` (action | content | multistep); content adds ``content_type``
(qa | explain | sing), optional ``prereg_duration_s`` (defaults qa 10 / explain 30 /
sing 30 s) and a ``rubric``; multistep adds ``steps`` = [{"intent", "checks"}, ...].
``offset_s`` is the scripted *start* of the utterance relative to session start.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from live_agent.eval.scoring import CONTENT_DURATION_S

ANNOTATIONS = ("new", "revision", "withdrawal", "none")
TASK_KINDS = ("action", "content", "multistep", "correction")
CATEGORIES = (
    "single_action",
    "content_qa",
    "content_explain",
    "content_sing",
    "multistep",
    "mid_correction",
    "goal_change",
    "barge_in",
    "deictic_correction",
)

# Composition of the full E2 suite (80 tasks x 5 seeds). *Proposed target*; the committed
# 30-task file is the first tranche.
SUITE_TARGETS: dict[str, int] = {
    "single_action": 24,
    "content_qa": 8,
    "content_explain": 6,
    "content_sing": 6,
    "multistep": 16,
    "mid_correction": 5,
    "goal_change": 5,
    "barge_in": 5,
    "deictic_correction": 5,
}


@dataclass
class ScriptedUtterance:
    offset_s: float
    text: str
    annotation: str = "new"
    chain: str | None = None
    intent: dict[str, Any] | None = None
    barge_in: bool = False


@dataclass
class Task:
    task_id: str
    kind: str
    title: str
    category: str
    utterances: list[ScriptedUtterance]
    persona: str = "hanfu_scholar_study"
    suite: str = ""
    duration_s: float | None = None
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def final_intents(self) -> dict[str, dict[str, Any] | None]:
        """chain label -> final intent (None if the chain ends withdrawn)."""
        out: dict[str, dict[str, Any] | None] = {}
        for u in self.utterances:
            if u.annotation in ("new", "revision"):
                out[u.chain] = u.intent
            elif u.annotation == "withdrawal":
                out[u.chain] = None
        return out


class TaskError(ValueError):
    pass


def _check_intent(tid: str, it: dict[str, Any] | None) -> None:
    if not it or it.get("kind") not in ("action", "content", "multistep"):
        raise TaskError(f"{tid}: intent needs kind action|content|multistep: {it}")
    if it["kind"] == "content":
        if it.get("content_type") not in CONTENT_DURATION_S:
            raise TaskError(f"{tid}: content intent needs content_type qa|explain|sing")
        if not it.get("rubric"):
            raise TaskError(f"{tid}: content intent needs a preregistered rubric")
    elif it["kind"] == "multistep":
        steps = it.get("steps") or []
        if len(steps) < 2 or not all(s.get("checks") for s in steps):
            raise TaskError(f"{tid}: multistep needs >= 2 steps, each with checks")
    elif not it.get("checks"):
        raise TaskError(f"{tid}: action intent needs checks")


def validate_task(t: Task) -> None:
    if t.kind not in TASK_KINDS:
        raise TaskError(f"{t.task_id}: bad kind {t.kind}")
    if t.category not in CATEGORIES:
        raise TaskError(f"{t.task_id}: bad category {t.category}")
    if not t.utterances:
        raise TaskError(f"{t.task_id}: no utterances")
    open_: set[str] = set()
    last = -1.0
    for u in t.utterances:
        if u.offset_s < last:
            raise TaskError(f"{t.task_id}: utterance offsets must be non-decreasing")
        last = u.offset_s
        if u.annotation not in ANNOTATIONS:
            raise TaskError(f"{t.task_id}: bad annotation {u.annotation}")
        if u.annotation == "none":
            continue
        if not u.chain:
            raise TaskError(f"{t.task_id}: annotated utterance needs a chain label")
        if u.annotation == "new":
            if u.chain in open_:
                raise TaskError(f"{t.task_id}: chain {u.chain} opened twice")
            open_.add(u.chain)
            _check_intent(t.task_id, u.intent)
        else:
            if u.chain not in open_:
                raise TaskError(f"{t.task_id}: {u.annotation} of unopened chain {u.chain}")
            if u.annotation == "revision":
                _check_intent(t.task_id, u.intent)


def task_from_dict(d: dict[str, Any]) -> Task:
    known = {"task_id", "kind", "title", "category", "utterances", "persona", "suite",
             "duration_s", "notes"}
    t = Task(
        task_id=d["task_id"],
        kind=d["kind"],
        title=d.get("title", ""),
        category=d["category"],
        utterances=[ScriptedUtterance(**u) for u in d["utterances"]],
        persona=d.get("persona", "hanfu_scholar_study"),
        suite=d.get("suite", ""),
        duration_s=d.get("duration_s"),
        notes=d.get("notes", ""),
        extra={k: v for k, v in d.items() if k not in known},
    )
    validate_task(t)
    return t


def load_suite(path: str | Path) -> list[Task]:
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(task_from_dict(json.loads(line)))
    ids = [t.task_id for t in tasks]
    dup = [i for i, c in Counter(ids).items() if c > 1]
    if dup:
        raise TaskError(f"duplicate task ids: {dup}")
    return tasks


def suite_counts(tasks: list[Task]) -> dict[str, dict[str, int]]:
    """Current vs target count per category (targets are *proposed targets*)."""
    c = Counter(t.category for t in tasks)
    return {k: {"current": c.get(k, 0), "target": v} for k, v in SUITE_TARGETS.items()}
