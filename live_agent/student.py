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
import math
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
    manual: bool = False  # the estimate was set by a teacher on the profile page (until the next graded exercise)


@dataclass
class StudentProfile:
    student_id: str
    name: str = ""
    grade: str = ""  # e.g. 初二
    exams: list[Exam] = field(default_factory=list)
    concepts: dict[str, Concept] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)  # graded exercises, newest last (bounded)
    version: int = 0  # bumped on every save: an editor saving an older version is refused (no lost updates)
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
                   history=list(d.get("history") or [])[-100:], version=int(d.get("version") or 0), path=path)

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
            self.version += 1
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
        """Where the estimate comes from: "manual" (a teacher set it), "exercise" (graded answers), "exam" (a
        prior), None (unknown)."""
        c = self.concepts.get(concept)
        if c is not None and c.manual and c.mastery is not None:
            return "manual"
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
        if m >= MASTERED and (c is None or (c.attempts < 3 and not c.manual)):
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
        c.manual = False  # evidence now
        c.updated = time.strftime("%Y-%m-%d")
        if misconception and not correct:
            c.notes = (c.notes + [str(misconception)[:40]])[-3:]
        self.history = (self.history + [{"concept": c.name, "correct": bool(correct), "question": question[:80],
                                         "answer": answer[:40], "t": time.strftime("%Y-%m-%d %H:%M")}])[-100:]
        return {"concept": c.name, "correct": bool(correct), "before": before, "after": c.mastery,
                "level": self.level(c.name)}

    def edit_concepts(self, edits: Any) -> list[str]:
        """Profile page edits: [{"name", "subject"?, "mastery"? (0-1, or null to clear), "delete"?, "rename"?}]."""
        changed = []
        for e in edits if isinstance(edits, list) else []:
            if not isinstance(e, dict) or not str(e.get("name") or "").strip():
                continue
            name = str(e["name"]).strip()[:20]
            if e.get("delete"):
                if self.concepts.pop(name, None) is not None:
                    changed.append(name)
                continue
            c = self._concept(name, str(e.get("subject") or "")[:12])
            if "subject" in e:
                c.subject = str(e.get("subject") or "")[:12]
            if "mastery" in e:
                m = e["mastery"]
                if m is None:
                    c.mastery, c.manual = None, False
                else:
                    try:
                        c.mastery, c.manual = round(max(0.0, min(1.0, float(m))), 3), True
                    except (TypeError, ValueError):
                        continue
                c.updated = time.strftime("%Y-%m-%d")
            new = str(e.get("rename") or "").strip()[:20]
            if new and new != name and new not in self.concepts:
                self.concepts[new] = self.concepts.pop(name)
                self.concepts[new].name = new
            changed.append(name)
        return changed

    def page_edit(self, body: dict) -> None:
        """One save from the profile page, validated as a whole before anything changes (a bad field refuses the
        save with ValueError; nothing is half-applied)."""
        body = validate_page_edit(body)
        self.update_basics({k: body[k] for k in ("name", "grade", "exams") if k in body})
        for e in body.get("concepts") or []:
            if e.get("delete"):  # a concept named by an exam comes back from the exam unless removed there too
                for ex in self.exams:
                    ex.weak = [w for w in ex.weak if w != e["name"]]
        self.edit_concepts(body.get("concepts"))
        if body.get("clear_history"):
            self.clear_exercises()

    def clear_exercises(self) -> None:
        """Erase the exercise evidence: history, attempt counts, misconception notes and exercise-based estimates
        (teacher-set estimates stay)."""
        self.history = []
        for c in self.concepts.values():
            c.attempts = c.correct = 0
            c.notes = []
            if not c.manual:
                c.mastery = None

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
        return {"id": self.student_id, "name": self.name, "grade": self.grade, "version": self.version,
                "exams": [{"subject": e.subject, "name": e.name, "score": e.score, "full": e.full, "date": e.date,
                           "weak": e.weak} for e in self.exams],
                "concepts": [{"name": n, "mastery": self.mastery(n), "level": self.level(n), "source": self.source(n),
                              "subject": self.concepts[n].subject if n in self.concepts else "",
                              "notes": self.concepts[n].notes if n in self.concepts else [],
                              "attempts": self.concepts[n].attempts if n in self.concepts else 0,
                              "correct": self.concepts[n].correct if n in self.concepts else 0}
                             for n in names][:60],
                "history": list(reversed(self.history[-30:]))}


def validate_page_edit(body: Any) -> dict:
    """The profile page's save request, checked field by field; returns it with the grade normalised."""
    from live_agent.curriculum import grade_name, parse_grade

    if not isinstance(body, dict):
        raise ValueError("body must be an object")
    out = dict(body)

    def text(v, n, what):
        if v is None:
            return ""
        if not isinstance(v, (str, int, float)) or len(str(v)) > n:
            raise ValueError(f"{what}: at most {n} characters")
        return str(v).strip()

    def number(v, what, lo=None, hi=None):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{what}: must be a number")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise ValueError(f"{what}: out of range")
        return float(v)

    if "name" in out:
        out["name"] = text(out["name"], 20, "name")
    if "grade" in out:
        g = text(out["grade"], 12, "grade")
        if g:
            n = parse_grade(g)
            if n is None:
                raise ValueError("grade: not recognised (e.g. 小学三年级, 初二, 高一)")
            g = grade_name(n)
        out["grade"] = g
    if "exams" in out:
        if not isinstance(out["exams"], list) or len(out["exams"]) > 20:
            raise ValueError("exams: a list of at most 20")
        for e in out["exams"]:
            if not isinstance(e, dict):
                raise ValueError("exams: each exam is an object")
            full = number(e.get("full", 100) or 100, "exam full score", 1, 1000)
            number(e.get("score"), "exam score", 0, full)
            text(e.get("subject"), 12, "exam subject"), text(e.get("name"), 20, "exam name")
            text(e.get("date"), 10, "exam date")
            weak = e.get("weak") or []
            if not isinstance(weak, list) or len(weak) > 10:
                raise ValueError("exam weak points: a list of at most 10")
            for w in weak:
                text(w, 16, "exam weak point")
    if "concepts" in out and out["concepts"] is not None:
        if not isinstance(out["concepts"], list) or len(out["concepts"]) > 100:
            raise ValueError("concepts: a list of at most 100 edits")
        for c in out["concepts"]:
            if not isinstance(c, dict) or not text(c.get("name"), 20, "concept name"):
                raise ValueError("concepts: each edit needs a name of 1-20 characters")
            c["name"] = text(c.get("name"), 20, "concept name")
            if "mastery" in c and c["mastery"] is not None:
                number(c["mastery"], "mastery", 0.0, 1.0)
            text(c.get("rename"), 20, "concept rename"), text(c.get("subject"), 12, "concept subject")
    if "clear_history" in out and not isinstance(out["clear_history"], bool):
        raise ValueError("clear_history: true or false")
    return out


class ProfileStore:
    """One shared, in-memory profile per student for the whole server: live sessions and the profile page edit the
    same object (a session's exercise result and a teacher's edit never overwrite each other), every change is
    saved, and listeners (open sessions) are told so their page can refresh."""

    def __init__(self, store: Path, seeds: Path | None, allowed: list[str]):
        self.store, self.seeds, self.allowed = Path(store), seeds, list(dict.fromkeys(allowed))
        self._profiles: dict[str, StudentProfile] = {}
        self._listeners: dict[str, list] = {}
        self.resets: dict[str, int] = {}  # per student: sessions compare it to invalidate grading started before

    def get(self, student_id: str) -> StudentProfile | None:
        if student_id not in self.allowed:
            return None
        if student_id not in self._profiles:
            self._profiles[student_id] = StudentProfile.load(student_id, self.store, self.seeds)
        return self._profiles[student_id]

    def exists(self, student_id: str) -> bool:
        return (self.store / f"{student_id}.json").exists()

    def subscribe(self, student_id: str, fn) -> None:
        self._listeners.setdefault(student_id, []).append(fn)

    def unsubscribe(self, student_id: str, fn) -> None:
        if fn in self._listeners.get(student_id, []):
            self._listeners[student_id].remove(fn)

    def changed(self, student_id: str, source=None) -> None:
        """Save and notify every listener except ``source`` (the one that made the change)."""
        p = self._profiles.get(student_id)
        if p is None:
            return
        p.save()
        for fn in list(self._listeners.get(student_id, [])):
            if fn is not source:
                fn()

    def reset(self, student_id: str) -> StudentProfile | None:
        """Back to the seed profile (or empty): the saved copy is replaced by the seed (with a newer version, so an
        editor holding the old one is refused). ``resets`` tells open sessions to drop profile work in flight."""
        if student_id not in self.allowed:
            return None
        self.resets[student_id] = self.resets.get(student_id, 0) + 1
        old = self._profiles.get(student_id)
        (self.store / f"{student_id}.json").unlink(missing_ok=True)
        fresh = StudentProfile.load(student_id, self.store, self.seeds)
        fresh.version = (old.version if old is not None else 0) + 1
        if old is not None:  # keep the object identity: sessions hold a reference to it
            old.__dict__.update({k: v for k, v in fresh.__dict__.items() if k != "path"})
            fresh = old
        self._profiles[student_id] = fresh
        self.changed(student_id)
        return fresh


__all__ = ["Concept", "Exam", "LEVELS_CN", "ProfileStore", "StudentProfile"]
