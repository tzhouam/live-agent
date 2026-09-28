"""Saved student profile: grade, exam scores and per-concept understanding, used to adapt lessons and exercises.

The profile is personal data: it lives in ``.cache/students/<id>.json`` (git-ignored), is read and written only in
a private session, is summarised (never copied whole) into planning prompts, and is covered by erasure.

Understanding of a concept is a mastery *estimate* in [0, 1] (shown as an estimate, never as a measured fact):
- prior: 0.4 for a concept the latest exam of its subject lost points on, else unknown (a subject score says
  nothing about one concept, so it sets no prior);
- each graded exercise moves it toward 1 (correct) or 0 (wrong) by ``RATE`` (an exponential moving average, a
  simple, explainable stand-in for knowledge tracing [proposed; not calibrated]).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_SAVE_LOCK = threading.Lock()  # one writer at a time per process (last writer wins across processes)
RATE = 0.35  # how far one exercise moves the estimate [proposed target, not calibrated]
MASTERED, WEAK = 0.8, 0.5  # level thresholds [proposed]
LEVELS_CN = {"mastered": "已掌握", "partial": "基本理解", "weak": "薄弱", "unknown": "未评估"}


@dataclass
class Exam:
    subject: str
    name: str
    score: float
    full: float = 100.0
    date: str = ""
    weak: list[str] = field(default_factory=list)  # concepts the exam lost points on

    @property
    def ratio(self) -> float:
        return max(0.0, min(1.0, self.score / self.full)) if self.full else 0.0


@dataclass
class Concept:
    name: str
    subject: str = ""
    mastery: float | None = None  # None: never assessed
    attempts: int = 0
    correct: int = 0
    taught: int = 0  # lessons that covered it
    notes: list[str] = field(default_factory=list)  # recent misconceptions (short, newest last)
    updated: str = ""


@dataclass
class StudentProfile:
    student_id: str
    name: str = ""
    grade: str = ""  # e.g. 初二
    exams: list[Exam] = field(default_factory=list)
    concepts: dict[str, Concept] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)  # graded exercises, newest last (bounded)
    path: Path | None = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------ storage
    @classmethod
    def from_dict(cls, d: dict, path: Path | None = None) -> StudentProfile:
        exams = [Exam(**{k: v for k, v in e.items() if k in Exam.__dataclass_fields__})
                 for e in d.get("exams") or [] if isinstance(e, dict) and "score" in e]
        concepts = {}
        for name, c in (d.get("concepts") or {}).items():
            c = dict(c) if isinstance(c, dict) else {}
            c["name"] = name
            concepts[name] = Concept(**{k: v for k, v in c.items() if k in Concept.__dataclass_fields__})
        return cls(student_id=str(d.get("student_id") or "student"), name=str(d.get("name") or ""),
                   grade=str(d.get("grade") or ""), exams=exams, concepts=concepts,
                   history=list(d.get("history") or [])[-100:], path=path)

    @classmethod
    def load(cls, student_id: str, store: Path, seed_dir: Path | None = None) -> StudentProfile:
        """The saved profile, else the seed profile (``seed_dir/<id>.json``), else an empty one."""
        path = Path(store) / f"{student_id}.json"
        for src in (path, (Path(seed_dir) / f"{student_id}.json") if seed_dir else None):
            if src is not None and src.exists():
                p = cls.from_dict(json.loads(src.read_text(encoding="utf-8")), path)
                p.student_id = student_id
                return p
        return cls(student_id=student_id, path=path)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("path", None)
        return d

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _SAVE_LOCK:
            tmp = self.path.with_name(f".{self.path.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)

    def update_basics(self, d: dict) -> None:
        """Student / teacher edits from the page: name, grade and exam scores (concept mastery is only ever
        changed by graded exercises and exam priors)."""
        if "name" in d:
            self.name = str(d["name"] or "")[:20]
        if "grade" in d:
            self.grade = str(d["grade"] or "")[:12]
        if isinstance(d.get("exams"), list):
            exams = []
            for e in d["exams"][:20]:
                if not isinstance(e, dict):
                    continue
                try:
                    exams.append(Exam(subject=str(e.get("subject") or "")[:12], name=str(e.get("name") or "")[:20],
                                      score=float(e["score"]), full=float(e.get("full") or 100),
                                      date=str(e.get("date") or "")[:10],
                                      weak=[str(x)[:16] for x in (e.get("weak") or []) if str(x).strip()][:10]))
                except (KeyError, TypeError, ValueError):
                    continue
            self.exams = exams

    def apply_update(self, d: Any) -> list[str]:
        """What the student said about themselves (the responder's ``profile_update``): grade, name, a new exam
        result. Returns what changed (for the log)."""
        if not isinstance(d, dict):
            return []
        changed = []
        if str(d.get("grade") or "").strip():
            self.grade = str(d["grade"]).strip()[:12]
            changed.append("grade")
        if str(d.get("name") or "").strip():
            self.name = str(d["name"]).strip()[:20]
            changed.append("name")
        e = d.get("exam")
        if isinstance(e, dict) and e.get("score") is not None:
            try:
                self.exams.append(Exam(subject=str(e.get("subject") or "")[:12], name=str(e.get("name") or "考试")[:20],
                                       score=float(e["score"]), full=float(e.get("full") or 100),
                                       date=str(e.get("date") or time.strftime("%Y-%m-%d"))[:10],
                                       weak=[str(x)[:16] for x in (e.get("weak") or []) if str(x).strip()][:10]))
                self.exams = self.exams[-20:]
                changed.append("exam")
            except (TypeError, ValueError):
                pass
        return changed

    # ------------------------------------------------------------ understanding
    def prior(self, concept: str, subject: str = "") -> float | None:
        """0.4 when the latest exam that tested the concept's subject lost points on it (an older loss that a
        later exam of that subject no longer lists does not count)."""
        latest: dict[str, Exam] = {}
        for e in sorted(self.exams, key=lambda e: e.date):
            latest[e.subject] = e
        return 0.4 if any(concept in e.weak for e in latest.values()) else None

    def source(self, concept: str) -> str | None:
        """Where the estimate comes from: "exercise" (graded answers), "exam" (a prior), None (unknown)."""
        c = self.concepts.get(concept)
        if c is not None and c.attempts and c.mastery is not None:
            return "exercise"
        return "exam" if self.mastery(concept) is not None else None

    def mastery(self, concept: str) -> float | None:
        c = self.concepts.get(concept)
        if c is not None and c.mastery is not None:
            return c.mastery
        return self.prior(concept, c.subject if c else "")

    def level(self, concept: str) -> str:
        """"mastered" needs graded exercises (at least 3), never a prior alone."""
        m = self.mastery(concept)
        if m is None:
            return "unknown"
        c = self.concepts.get(concept)
        if m >= MASTERED and (c is None or c.attempts < 3):
            return "partial"
        return "mastered" if m >= MASTERED else "partial" if m >= WEAK else "weak"

    def _concept(self, name: str, subject: str = "") -> Concept:
        name = str(name).strip()[:20]
        c = self.concepts.get(name)
        if c is None:
            c = self.concepts[name] = Concept(name=name, subject=subject)
        elif subject and not c.subject:
            c.subject = subject
        return c

    def record_exercise(self, concept: str, correct: bool, *, question: str = "", answer: str = "",
                        misconception: str = "", subject: str = "") -> dict:
        """One graded exercise: update the concept's mastery; returns the change for the log / page."""
        c = self._concept(concept, subject)
        before = self.mastery(c.name)
        m = before if before is not None else 0.5
        c.mastery = round(m + RATE * ((1.0 if correct else 0.0) - m), 3)
        c.attempts += 1
        c.correct += int(bool(correct))
        c.updated = time.strftime("%Y-%m-%d")
        if misconception and not correct:
            c.notes = (c.notes + [str(misconception)[:40]])[-3:]
        self.history = (self.history + [{"concept": c.name, "correct": bool(correct), "question": question[:80],
                                         "answer": answer[:40], "t": time.strftime("%Y-%m-%d %H:%M")}])[-100:]
        return {"concept": c.name, "correct": bool(correct), "before": before, "after": c.mastery,
                "level": self.level(c.name)}

    def mark_taught(self, concepts: list[str], subject: str = "") -> None:
        for name in concepts:
            if str(name).strip():
                self._concept(name, subject).taught += 1

    def purge(self, term: str) -> int:
        """Erasure: drop concepts, notes, exam entries and history rows that mention ``term``."""
        n = 0
        for name in [k for k in self.concepts if term in k]:
            del self.concepts[name]
            n += 1
        for c in self.concepts.values():
            keep = [x for x in c.notes if term not in x]
            n += len(c.notes) - len(keep)
            c.notes = keep
        keep_h = [h for h in self.history if term not in json.dumps(h, ensure_ascii=False)]
        n += len(self.history) - len(keep_h)
        self.history = keep_h
        keep_e = [e for e in self.exams if term not in e.name and term not in e.subject]
        n += len(self.exams) - len(keep_e)
        self.exams = keep_e
        for e in self.exams:
            if term in "".join(e.weak):
                e.weak = [w for w in e.weak if term not in w]
                n += 1
        for c in self.concepts.values():
            if term in c.subject:
                c.subject, n = "", n + 1
        if term and term in self.name:
            self.name, n = "", n + 1
        if term and term in self.grade:
            self.grade, n = "", n + 1
        keep_e = [e for e in self.exams if term not in json.dumps(asdict(e), ensure_ascii=False)]
        n += len(self.exams) - len(keep_e)
        self.exams = keep_e
        return n

    # ------------------------------------------------------------ prompts and page
    def _mastery_text(self, name: str) -> str:
        m, c = self.mastery(name), self.concepts.get(name)
        s = f"{name}：{LEVELS_CN[self.level(name)]}"
        if m is not None:
            s += f"（估计掌握度 {m:.2f}" + ("，仅据考试失分" if self.source(name) == "exam" else "")
            if c is not None and c.attempts:
                s += f"，练习 {c.correct}/{c.attempts} 对"
            s += "）"
        if c is not None and c.notes:
            s += f"，最近的错误：{c.notes[-1]}"
        return s

    def summary(self, limit: int = 16) -> str:
        """Planning context: grade, recent exams, understanding per concept (weakest first)."""
        if not (self.grade or self.exams or self.concepts):
            return "无（新学生，没有档案）"
        parts = []
        # minimal: what the plan needs (grade, recent results, understanding); no dates; the name only as a form of
        # address
        if self.name or self.grade:
            parts.append(f"学生：{self.name or '同学'}，{self.grade or '年级未知'}")
        for e in sorted(self.exams, key=lambda e: e.date)[-4:]:
            s = f"考试：{e.subject}{e.name} {e.score:g}/{e.full:g}"
            if e.weak:
                s += f"，失分点：{'、'.join(e.weak)}"
            parts.append(s)
        names = sorted(set(self.concepts) | {w for e in self.exams for w in e.weak},
                       key=lambda n: (self.mastery(n) is None, self.mastery(n) or 0.0))[:limit]
        if names:
            parts.append("概念掌握情况：" + "；".join(self._mastery_text(n) for n in names))
        return "\n".join(parts)

    def concept_notes(self, concepts: list[str]) -> str:
        """For one section: how well the student knows each of its concepts."""
        known = [self._mastery_text(n) for n in concepts if str(n).strip()]
        return "；".join(known) or "无记录"

    def view(self) -> dict[str, Any]:
        """For the page panel."""
        names = sorted(set(self.concepts) | {w for e in self.exams for w in e.weak},
                       key=lambda n: (self.mastery(n) is None, -(self.mastery(n) or 0.0)))
        return {"id": self.student_id, "name": self.name, "grade": self.grade,
                "exams": [{"subject": e.subject, "name": e.name, "score": e.score, "full": e.full, "date": e.date,
                           "weak": e.weak} for e in self.exams],
                "concepts": [{"name": n, "mastery": self.mastery(n), "level": self.level(n), "source": self.source(n),
                              "attempts": self.concepts[n].attempts if n in self.concepts else 0,
                              "correct": self.concepts[n].correct if n in self.concepts else 0}
                             for n in names][:30]}


__all__ = ["Concept", "Exam", "LEVELS_CN", "StudentProfile"]
