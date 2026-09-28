# Codex review: adaptive lessons and teacher exercises (commit 8433281, decision D-038)

You are reviewing a change to a real-time digital-teacher demo (Python, asyncio). A video model renders the teacher
in ~5 s requests; a director pops one spoken line per request; lessons are generated section by section by an LLM
and wait in a lesson backlog; a board beside the video shows points/formulas. The change adds:

1. `live_agent/student.py`: a saved student profile (grade, exams with lost-point concepts, per-concept mastery,
   exercise history) used to adapt planning; EMA mastery update; erasure (`purge`).
2. `live_agent/exercise.py`: exercises (choice / short), rule grading then LLM grading, feedback lines.
3. `live_agent/lesson.py`: adaptive outline (per-section concepts, depth, exercise flag) and sections (profile,
   this lesson's mistakes, exercise spec); exercise lines appended after a section's summary.
4. Director/orchestrator/app/page wiring (diff inlined): the lesson backlog pauses while an exercise waits; the
   next utterance is graded first (answer vs side question); feedback is applied as a reply and the answer is shown;
   the next section is generated after the answer; silence -> reminder, then the answer; the page shows the profile
   and answer buttons.

Please find **correctness bugs and design risks**, most severe first. Focus on:
- state machine races: barge-in / soft switch cuts (`on_interrupted`), `exercise` set on pop, lesson backlog gating,
  requeue of cut lines, the idle timer, stop_lesson, erasure while an exercise waits, grading superseded by a newer
  utterance (epoch), an asked exercise during a lesson;
- grading errors (rule grader false positives/negatives on realistic Chinese answers, LLM output handling);
- privacy: the profile is personal data (private sessions only, erasure coverage, what reaches logs/prompts/page);
- the mastery model and thresholds (they are labelled proposed; say if the labelling or behaviour is misleading);
- anything that could stall the lesson forever or loop.
For each finding give: file:line (or function), a concrete failure scenario, severity (high/medium/low), and a fix.
Do not restate what the code does; skip style nits. If something is fine, you need not mention it.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: live_agent/student.py =====
"""Saved student profile: grade, exam scores and per-concept understanding, used to adapt lessons and exercises.

The profile is personal data: it lives in ``.cache/students/<id>.json`` (git-ignored), is read and written only in
a private session, is summarised (never copied whole) into planning prompts, and is covered by erasure.

Understanding of a concept is a mastery estimate in [0, 1]:
- prior: 0.4 for a concept an exam lost points on, else the latest exam score ratio in that subject, else unknown;
- each graded exercise moves it toward 1 (correct) or 0 (wrong) by ``RATE`` (an exponential moving average, a
  simple, explainable stand-in for knowledge tracing [proposed; not calibrated]).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

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
        tmp = self.path.with_suffix(".tmp")
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
        exams = sorted(self.exams, key=lambda e: e.date)
        if any(concept in e.weak for e in exams):
            return 0.4
        same = [e for e in exams if subject and e.subject == subject]
        return same[-1].ratio if same else None

    def mastery(self, concept: str) -> float | None:
        c = self.concepts.get(concept)
        if c is not None and c.mastery is not None:
            return c.mastery
        return self.prior(concept, c.subject if c else "")

    def level(self, concept: str) -> str:
        m = self.mastery(concept)
        if m is None:
            return "unknown"
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
        if term and term in self.name:
            self.name, n = "", n + 1
        return n

    # ------------------------------------------------------------ prompts and page
    def _mastery_text(self, name: str) -> str:
        m, c = self.mastery(name), self.concepts.get(name)
        s = f"{name}：{LEVELS_CN[self.level(name)]}"
        if m is not None:
            s += f"（掌握度 {m:.2f}"
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
        if self.name or self.grade:
            parts.append(f"学生：{self.name or '同学'}，{self.grade or '年级未知'}")
        for e in sorted(self.exams, key=lambda e: e.date)[-4:]:
            s = f"考试：{e.date + ' ' if e.date else ''}{e.subject}{e.name} {e.score:g}/{e.full:g}"
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
                "concepts": [{"name": n, "mastery": self.mastery(n), "level": self.level(n),
                              "attempts": self.concepts[n].attempts if n in self.concepts else 0,
                              "correct": self.concepts[n].correct if n in self.concepts else 0}
                             for n in names][:30]}


__all__ = ["Concept", "Exam", "LEVELS_CN", "StudentProfile"]

===== FILE: live_agent/exercise.py =====
"""Exercises the teacher gives: shown on the board, answered by voice or text, graded, fed back into the profile.

An exercise is either multiple choice (graded by rule: the letter, or the option's text) or a short answer
(exact match by rule, else graded by the LLM against the reference answer). A pending exercise pauses the
lesson: the next lesson line waits until the student answers (or says they do not know).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from live_agent.lesson import Board, LessonLine, spoken
from live_agent.llm import ChatLLM, parse_json

LETTERS = "ABCD"
SKIP = re.compile(r"不会|不知道|跳过|不懂|想不出|没思路|算了")

EXERCISE_PROMPT = """你是中学老师「{name}」。请给学生出一道关于「{topic}」的练习题。
学生档案：
{profile}
难度按学生情况定：这个知识点薄弱就出基础题（直接用定义或公式一步能做），基本理解出中等题，已掌握出稍有变化的题；按学生年级出题。
{exercise_spec}"""

EXERCISE_SPEC = """练习题格式（只输出 JSON）：
{{"exercise": {{"concept": 考查的概念（用档案里已有的概念名，没有就写一个不超过 8 字的名称）, "subject": 学科,
  "type": "choice" 或 "short", "question": 题目（不超过 {q_chars} 字，公式写在 $...$ 里）,
  "options": ["A. …", "B. …", "C. …", "D. …"]（选择题才有，每项不超过 20 字）,
  "answer": 选择题写字母（如 "B"），简答题写最简答案（一个数、一个词或一个式子）,
  "explanation": [讲解为什么，1-2 句，每句不超过 {chars} 个汉字，口语化，公式用中文读出来；不要只重复选哪个]}}}}
选择题的错误选项要对应常见的错误想法。"""

GRADE_PROMPT = """你是老师，正在批改学生的口头回答。
题目：{question}
{options}参考答案：{answer}
讲解：{explanation}
学生说：「{said}」
先判断学生这句话是不是在回答这道题（是答案、写出了结果或说不会，都算回答；问别的问题、聊别的事不算）。
是回答时判断对错（意思对、等价的式子或数值都算对）；错了用一句话指出学生的错误想法。
只输出 JSON：{{"is_answer": true 或 false, "correct": true 或 false, "misconception": 错误想法（答对时为 null）,
"feedback": [老师回应，2-3 句，每句不超过 {chars} 个汉字，口语化：答对先肯定再点出关键；答错先鼓励，再讲正确思路和答案；公式用中文读出来]}}"""


@dataclass
class Exercise:
    concept: str
    question: str
    answer: str
    kind: str = "short"  # "choice" | "short"
    options: list[str] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    subject: str = ""
    key: str = "x"
    source: str = "lesson"  # "lesson" (pauses the lesson) | "asked" (the student asked for one)

    @classmethod
    def from_dict(cls, d: Any, key: str, source: str = "lesson") -> Exercise | None:
        if not isinstance(d, dict):
            return None
        q, ans = str(d.get("question") or "").strip(), str(d.get("answer") or "").strip()
        if not q or not ans:
            return None
        expl = d.get("explanation") or []
        expl = [str(x) for x in (expl if isinstance(expl, list) else [expl]) if str(x).strip()]
        ex = cls(concept=str(d.get("concept") or "").strip()[:20] or "练习", question=q[:120], answer=ans[:60],
                 explanation=expl[:3], subject=str(d.get("subject") or "")[:12], key=key, source=source)
        opts = [str(x).strip()[:40] for x in (d.get("options") or []) if str(x).strip()][:4]
        if str(d.get("type") or "") == "choice" or opts:
            letter = ans.upper()[:1]
            if len(opts) < 2 or letter not in LETTERS[: len(opts)]:
                return None
            ex.kind, ex.answer = "choice", letter
            ex.options = [o if re.match(r"^[A-D][.．、:：]", o) else f"{LETTERS[i]}. {o}" for i, o in enumerate(opts)]
        return ex

    def board(self, reveal_answer: bool = False) -> Board:
        items = [self.question, *self.options]
        if reveal_answer:
            items.append(f"答案：{self.answer_text()}")
        return Board(key=self.key + ("a" if reveal_answer else ""), title=f"练习 · {self.concept}"[:24], items=items)

    def answer_text(self) -> str:
        if self.kind == "choice":
            i = LETTERS.index(self.answer)
            return self.options[i] if i < len(self.options) else self.answer
        return self.answer

    def lines(self, chars: int) -> list[LessonLine]:
        """The teacher poses it: the board shows the question (and options)."""
        b = self.board()
        out = [LessonLine("我们来做一道练习。", b, None, gesture=True)]
        out += [LessonLine(p, b, None) for p in spoken(self.question, chars)]  # question and options all shown
        out.append(LessonLine("选项在黑板上，选好了告诉我。" if self.kind == "choice" else "想好了把答案告诉我。", b, None))
        for ln in out:  # any of them opens the exercise: an answer given while it is still being read out counts
            ln.exercise = self
        return out


def _norm(s: str) -> str:
    s = re.sub(r"^(我觉得|我选|选|答案是|答案|应该是|是)", "", s.strip())
    s = re.sub(r"^\s*[a-zA-Z]\s*[=＝]", "", s)  # "x = 3" -> "3"
    return re.sub(r"[\s，。,.!！?？$:：=＝]", "", s).lower()


def quick_grade(ex: Exercise, said: str) -> dict | None:
    """Rule grading when it is unambiguous; None when the LLM must judge."""
    text = said.strip()
    if SKIP.search(text) and len(text) <= 12:
        return {"is_answer": True, "correct": False, "skipped": True, "misconception": None}
    if ex.kind == "choice":
        letters = set(re.findall(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", text))
        if len(letters) == 1 and len(text) <= 16:
            got = letters.pop().upper()
            return {"is_answer": True, "correct": got == ex.answer, "given": got, "misconception": None}
        for i, o in enumerate(ex.options):  # the option's own text ("选相等的那个" is left to the LLM)
            body = re.sub(r"^[A-D][.．、:：]\s*", "", o)
            if body and _norm(body) == _norm(text):
                return {"is_answer": True, "correct": LETTERS[i] == ex.answer, "given": LETTERS[i],
                        "misconception": None}
        return None
    if _norm(text) and _norm(text) == _norm(ex.answer):
        return {"is_answer": True, "correct": True, "misconception": None}
    return None


async def grade(llm: ChatLLM, ex: Exercise, said: str, chars: int = 22) -> dict:
    """Grade the student's reply: rules first, then the LLM. Always returns is_answer / correct / feedback."""
    r = quick_grade(ex, said)
    if r is not None:
        r["feedback"] = feedback_lines(ex, r, chars)
        return r
    opts = ("选项：" + " ".join(ex.options) + "\n") if ex.options else ""
    raw = await llm.chat([{"role": "user", "content": GRADE_PROMPT.format(
        question=ex.question, options=opts, answer=ex.answer_text(), explanation="".join(ex.explanation) or "无",
        said=said[:200], chars=chars)}], max_tokens=400, temperature=0.0, json_mode=True)
    d = parse_json(raw)
    r = {"is_answer": bool(d.get("is_answer")), "correct": bool(d.get("correct")),
         "misconception": (str(d["misconception"])[:40] if d.get("misconception") else None)}
    if r["is_answer"]:
        said_fb = [p for x in (d.get("feedback") or []) for p in spoken(str(x), chars)][:4]
        r["feedback"] = feedback_lines(ex, r, chars, said_fb)
    return r


def feedback_lines(ex: Exercise, r: dict, chars: int, llm_lines: list[str] | None = None) -> list[str]:
    """What the teacher says after grading: praise or the correct answer, then the explanation."""
    if llm_lines:
        lines = list(llm_lines)
        if not r["correct"] and ex.kind == "choice" and not any(ex.answer in x for x in lines):
            lines.insert(1 if len(lines) > 1 else 0, f"正确答案是 {ex.answer}。")
        return lines
    expl = [p for x in ex.explanation for p in spoken(x, chars)][:3]
    if r.get("skipped"):
        head = ["没关系，我们一起来看。"]
        head += [f"答案是 {ex.answer}。"] if ex.kind == "choice" else spoken(f"答案是{ex.answer}。", chars)
        return head + expl
    if r["correct"]:
        return ["答对了，很好！"] + expl[:2]
    head = [f"不太对哦，正确答案是 {ex.answer}。"] if ex.kind == "choice" else \
        ["不太对哦，我们看一下。"] + spoken(f"答案是{ex.answer}。", chars)
    return head + expl


async def make_exercise(llm: ChatLLM, *, name: str, topic: str, profile: str, key: str, chars: int = 22,
                        source: str = "asked") -> Exercise:
    raw = await llm.chat([{"role": "user", "content": EXERCISE_PROMPT.format(
        name=name, topic=topic, profile=profile, exercise_spec=EXERCISE_SPEC.format(chars=chars, q_chars=60))}],
        max_tokens=600, temperature=0.5, json_mode=True)
    d = parse_json(raw)
    ex = Exercise.from_dict(d.get("exercise", d), key=key, source=source)
    if ex is None:
        raise ValueError("no usable exercise in the reply")
    return ex


__all__ = ["EXERCISE_SPEC", "Exercise", "feedback_lines", "grade", "make_exercise", "quick_grade"]

===== FILE: live_agent/lesson.py =====
"""Long-form teaching: a lesson plan generated section by section, spoken line by line, with a board.

The video model cannot draw legible text, so the board (title, points, formulas) is rendered by the page next to
the video. Every spoken line names the board point it explains; the board state travels with the request that
speaks the line and is shown when that request starts playing, so board and speech stay aligned.

Generation is incremental (outline first, then one section at a time while the previous one plays): a whole
lesson is thousands of output tokens, i.e. minutes at a hosted model's ~40 tokens/s [measured locally].
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from live_agent.llm import ChatLLM, parse_json

MAX_ITEMS = 6
ITEM_CHARS = 60
# section depth chosen by the outline from the student's profile: (spoken lines, instruction)
DEPTHS = {
    "review": ("4-6", "这一节是复习，学生已经掌握：只讲 1-2 条要点，每条一两句，快速带过，不举新例子。"),
    "core": ("14-20", "这一节是重点，学生这里薄弱或考试失分：放慢，每条要点先讲直观理解，再举一个具体的例子或算一道例题，指出常见错误。"),
    "new": ("10-18", "这一节是新内容，正常讲解。"),
}

OUTLINE_PROMPT = """你是中学老师「{name}」，要给学生上一节关于「{topic}」的课。人设：{bio}
学生档案（年级、考试成绩、各概念的掌握情况）：
{profile}
请按这个学生的情况因材施教，设计课程大纲，只输出 JSON：
{{"title": 课程标题（不超过 16 字）, "plan_note": 一句话说明你根据档案怎么安排的（给老师自己看，不念出来）,
 "sections": [{{"title": 小节标题（不超过 14 字）, "goal": 这一节要讲清楚什么（一句话）,
   "concepts": [这一节讲的概念，档案里已有的概念用完全相同的名字，每个不超过 8 字],
   "depth": "review"（已掌握，一两句带过）或 "core"（薄弱或考试失分，重点讲、放慢、多举例）或 "new"（新内容，正常讲）,
   "exercise": true 或 false（讲完这一节出一道练习）}}],
 "intro": [开场白，2-3 句]}}
要求：3-5 个小节，由浅入深；讲解深度、用词和例子符合学生的年级；学生已掌握的前置概念只安排简短复习或不讲，薄弱的、考试失分的概念多安排时间；
整节课 1-3 道练习，放在薄弱概念和重点小节后面；没有档案时按{default_grade}的一般水平讲。
开场白先说今天学什么，再说分几部分讲，知道学生情况时可以自然地提一句（如「上次考试这里丢了分，今天重点讲」）；每句开场白不超过 {chars} 个汉字。
学生之前的对话（只作参考）：{context}"""

SECTION_PROMPT = """你是中学老师「{name}」，正在上「{title}」这节课。人设：{bio}
现在讲第 {i}/{n} 节「{section}」，目标：{goal}。
前面已经讲过：{covered}
请写这一节的板书和讲稿，只输出 JSON：
{{"board": {{"title": 小节标题}},
 "points": [{{"text": 一条板书要点, "lines": [讲这条要点时老师说的话，按顺序]}}],
 "summary": [这一节的小结句]}}
板书要求：3-{max_items} 条要点，每条不超过 {item_chars} 个字，简洁像真正的板书；公式用 LaTeX 写在 $...$ 里（如 $x^2+y^2=r^2$）。
对齐要求：每句讲稿都放在它正在讲的那条要点下面；讲完一条再讲下一条；只属于整节的小结放在 summary 里。
讲稿要求：
1. 每条要点讲 2-4 句：先说要点，再解释原因，再举生活中的例子或算一个小例题。
2. 每句不超过 {chars} 个汉字，口语化；公式和符号全部用中文读出来（如「a 加 b 的和的平方」「x 的平方」），讲稿里不要出现 $、LaTeX、括号、加减乘除号或等号。
3. 直接从这一节的内容讲起，不要打招呼，不要重复开场白或前面讲过的话。
   配图由系统按要点另外判断和绘制；讲图形、图像或结构时可以说「看黑板上的图」，但不要描述图里没有的细节。
4. summary 写 1-2 句，简短小结这一节{outro}。
5. 讲稿总共 {n_lines} 句。
因材施教：{adapt}{exercise_req}"""


FIGURE_JUDGE_PROMPT = """你是教学设计专家。下面是「{title}」这一节的板书要点，以及老师讲每条要点时说的话。
请逐条判断：这条要点是否复杂到需要一张解释图，学生光听讲、看文字不容易理解。
需要图的典型情况：几何图形和空间关系；函数图像和数量变化；细胞、分子、器官等结构；有多个步骤、阶段或循环的过程；实验装置；多个量的对比。
讲解里说到「看黑板上的图」「这个形状」「这条曲线」的，必须配图。
不需要图的：定义复述、简单事实、结论小结、鼓励和提问。每节最多 {max_figs} 张图，优先给最难懂的要点。
只输出 JSON：{{"points": [{{"i": 要点序号, "complexity": 1-3（1 简单，2 一般，3 抽象或空间关系复杂）, "need": true 或 false, "why": 一句理由, "figure": 需要时写配图，否则 null}}]}}
配图写法：
- 函数图像、坐标系里的点：{{"plot": {{"functions": ["x**2-2*x-3"], "x": [-3, 5], "points": [{{"x": -1, "y": 0, "label": "x₁"}}], "title": 图标题}}, "caption": 图注}}
  （functions 用 Python 写法：x**2、2*x、sqrt(x)、sin(x)；图会被精确画出）
- 几何图形（三角形、正方形、多边形，按比例精确画在方格上）：{{"plot": {{"polygons": [{{"points": [[0,0],[4,0],[0,3]], "label": "直角三角形", "sides": ["4", "5", "3"]}}], "grid": true}}, "caption": 图注}}
  （points 是顶点坐标，sides 依次标注每条边：第 i 条边从第 i 个顶点到下一个顶点）
- 插图、结构、流程、实验装置示意：{{"prompt": 配图描述, "caption": 图注}}；prompt 具体写清画什么、怎么摆放，要标注的文字都放在「」里
  （如：一片绿叶，太阳的箭头标注「阳光」，根部箭头标注「水」）；这类图由图像模型画，画不准数学关系，几何图形和函数图像一律用 plot。
caption 不超过 16 个字。
要点和讲解：
{points}"""


@dataclass
class Figure:
    """One explanatory figure: an exact plot spec or an illustration prompt, for one board point (None = the board)."""

    point: int | None
    prompt: str = ""
    plot: dict | None = None
    caption: str = ""
    url: str = ""  # set once drawn; boards locked after that show it
    why: str = ""  # the judgement that asked for it
    board_key: str = ""
    queued: bool = False  # handed to the drawer once (never twice)


@dataclass
class Board:
    key: str  # changes when the board is rewritten (a new section / answer)
    title: str
    items: list[str] = field(default_factory=list)  # raw text with $...$ LaTeX
    figures: list[Figure] = field(default_factory=list)  # per point (judged) or for the whole board

    def view(self, reveal: int | None, progress: tuple[int, int] | None = None) -> dict[str, Any]:
        """What the page shows: items up to ``reveal`` (all when None), the ``reveal``-th highlighted, with the
        spoken line's position within that point (``progress``)."""
        v = {"key": self.key, "title": html.escape(self.title), "items": [render_item(x) for x in self.items],
             "reveal": reveal}
        if progress is not None and reveal is not None:
            v["progress"] = list(progress)
        fig = self.figure_for(reveal)
        if fig is not None:
            v["figure"] = {"url": fig.url, "caption": html.escape(fig.caption)}
        return v

    def figure_for(self, reveal: int | None) -> Figure | None:
        """The figure of the point being explained, else the board's own figure; never another point's figure
        (it would illustrate something she is not talking about)."""
        ready = [f for f in self.figures if f.url]
        exact = [f for f in ready if reveal is not None and f.point == reveal]
        whole = [f for f in ready if f.point is None]
        return (exact or whole or [None])[0]


@dataclass
class LessonLine:
    text: str
    board: Board | None  # None: a plain line (keeps whatever the board shows)
    item: int | None  # board point this line explains (None: whole board, e.g. an intro line or a summary)
    gesture: bool = False  # first line of a point: present the board
    progress: tuple[int, int] | None = None  # (this line, lines about the point), 1-based: shown on the board
    exercise: Any = None  # exercise.Exercise posed by this line: the lesson waits for the answer after it


@dataclass
class Outline:
    title: str
    sections: list[dict]  # title, goal, concepts, depth (review / core / new), exercise
    intro: list[str]
    note: str = ""  # how the plan was adapted to the student (for the log and page, not spoken)


def set_figure(board: Board, fig, point: int | None = None, why: str = "") -> Figure | None:
    """Attach a figure request (an exact plot spec or an illustration prompt) to ``board`` for ``point``."""
    if not isinstance(fig, dict):
        return None
    plot = fig.get("plot")
    f = Figure(point=point, caption=str(fig.get("caption") or "")[:20], why=str(why)[:60], board_key=board.key)
    if isinstance(plot, dict) and (plot.get("functions") or plot.get("points") or plot.get("polygons")):
        f.plot = plot
    elif str(fig.get("prompt") or "").strip():
        f.prompt = str(fig["prompt"]).strip()[:400]
    else:
        return None
    board.figures.append(f)
    return f


def render_item(text: str) -> str:
    """Board text -> safe HTML: plain text escaped, **bold**, $...$ LaTeX as MathML (text fallback)."""
    out = []
    for i, part in enumerate(re.split(r"\$([^$]+)\$", text)):
        if i % 2:
            out.append(_math(part))
        else:
            esc = html.escape(part)
            out.append(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc))
    return "".join(out)


def _math(tex: str) -> str:
    try:
        from latex2mathml.converter import convert

        return convert(tex)
    except Exception:  # noqa: BLE001 - never lose the point: show the source
        return f"<code>{html.escape(tex)}</code>"


_SAY = [(r"\(([^()]*[+＋][^()]*)\)\s*(的)?(平方|²|\^\s*2)", r"\1的和的平方"),
        (r"\(([^()]*[-−－][^()]*)\)\s*(的)?(平方|²|\^\s*2)", r"\1的差的平方"),
        (r"\^\s*2|²", "的平方"), (r"\^\s*3|³", "的立方"), (r"√\s*", "根号"),
        (r"\s*[+＋]\s*", "加"), (r"(?<=[0-9a-zA-Z方])\s*[-−－]\s*(?=[0-9a-zA-Z])", "减"),
        (r"\s*[×✕*]\s*", "乘"), (r"\s*[÷]\s*", "除以"), (r"\s*[=＝]\s*", "等于"), (r"[()（）\[\]{}]", "")]


def _say(text: str) -> str:
    """Symbols a speech model mispronounces (heard: '(a+b)平方' -> 'a a b 平方', CER 0.15) read out in Chinese."""
    for pat, rep in _SAY:
        text = re.sub(pat, rep, text)
    return text


def spoken(text: str, chars: int) -> list[str]:
    """A spoken line: no LaTeX/markup/symbols, split at punctuation into pieces of at most ``chars`` characters
    (a fragment shorter than 6 characters is merged into its neighbour, up to ``chars`` + 4)."""
    # inline LaTeX is read out, not dropped (dropping left "公式是 ，记住它。"): commands and braces go, symbols are said
    text = re.sub(r"\$([^$]*)\$", lambda m: re.sub(r"\\[a-zA-Z]+|[{}]", "", m.group(1)), text or "")
    text = text.replace("\\", "").strip()
    text = _say(text).replace("*", "").strip()
    if not text:
        return []
    pieces, cur = [], ""
    for tok in re.split(r"(?<=[，。！？；：,.!?;])", text):
        if not tok:
            continue
        if len(cur) + len(tok) <= chars:
            cur += tok
        else:
            if cur:
                pieces.append(cur)
            while len(tok) > chars:
                pieces.append(tok[:chars])
                tok = tok[chars:]
            cur = tok
    if cur:
        pieces.append(cur)
    merged: list[str] = []
    for p in pieces:  # no 5-second request for "列式子：" alone
        if merged and (len(p) < 6 or len(merged[-1]) < 6) and len(merged[-1]) + len(p) <= chars + 4:
            merged[-1] += p
        else:
            merged.append(p)
    return merged


class LessonPlanner:
    def __init__(self, llm: ChatLLM, *, name: str, bio: str, chars: int = 22):
        self.llm, self.name, self.bio, self.chars = llm, name, bio, chars

    async def outline(self, topic: str, context: str = "", profile=None) -> Outline:
        """``profile``: a student.StudentProfile (None: no saved profile, an average student of ``default_grade``)."""
        raw = await self.llm.chat([{"role": "user", "content": OUTLINE_PROMPT.format(
            name=self.name, topic=topic, bio=self.bio, chars=self.chars, context=context or "无",
            profile=profile.summary() if profile is not None else "无（新学生，没有档案）",
            default_grade=(profile.grade if profile is not None and profile.grade else "初中"))}],
            max_tokens=900, temperature=0.4, json_mode=True)
        d = parse_json(raw)
        sections = []
        for s in d.get("sections") or []:
            if isinstance(s, dict) and s.get("title"):
                s["concepts"] = [str(c).strip()[:12] for c in (s.get("concepts") or []) if str(c).strip()][:4]
                s["depth"] = s.get("depth") if s.get("depth") in DEPTHS else "new"
                s["exercise"] = bool(s.get("exercise"))
                sections.append(s)
        sections = sections[:6]
        if not sections:
            raise ValueError("lesson outline without sections")
        intro = [p for x in d.get("intro") or [] for p in spoken(str(x), self.chars)][:4]
        return Outline(title=str(d.get("title") or topic)[:24], sections=sections, intro=intro,
                       note=str(d.get("plan_note") or "")[:120])

    async def section(self, outline: Outline, i: int, covered: list[str], profile=None,
                      mistakes: list[str] | None = None) -> list[LessonLine]:
        """One section; with a profile its depth, examples and exercise follow the student's understanding of
        the section's concepts, and ``mistakes`` (this lesson's wrong answers so far) are addressed first."""
        from live_agent.exercise import EXERCISE_SPEC, Exercise

        sec = outline.sections[i]
        last = i == len(outline.sections) - 1
        depth = sec.get("depth") if sec.get("depth") in DEPTHS else "new"
        adapt = [DEPTHS[depth][1]]
        if profile is not None:
            if profile.grade:
                adapt.append(f"学生是{profile.grade}，用这个年级听得懂的说法和例子。")
            adapt.append(f"学生对本节概念的掌握：{profile.concept_notes(sec.get('concepts') or [])}。")
        if mistakes:
            adapt.append(f"学生刚才的练习做错了：{'；'.join(mistakes[-2:])}。本节第一条要点先用一两句换个说法把这个错误纠正过来。")
        want_ex = bool(sec.get("exercise"))
        ex_req = ("\n6. 讲完出一道练习，考查本节最重要的概念，难度按学生的掌握度定（薄弱出基础题，已掌握出稍有变化的题）；"
                  "在 JSON 里加字段 \"exercise\"。" + EXERCISE_SPEC.format(chars=self.chars, q_chars=60)) if want_ex else ""
        raw = await self.llm.chat([{"role": "user", "content": SECTION_PROMPT.format(
            name=self.name, bio=self.bio, title=outline.title, i=i + 1, n=len(outline.sections),
            section=sec["title"], goal=sec.get("goal", ""), covered="；".join(covered) or "（这是第一节）",
            max_items=MAX_ITEMS, item_chars=ITEM_CHARS, chars=self.chars, n_lines=DEPTHS[depth][0],
            adapt="".join(adapt), exercise_req=ex_req,
            outro="，并告诉学生这节课就讲到这里、有问题随时问" if last else "，并引出下一节")}],
            max_tokens=2000 if want_ex else 1500, temperature=0.4, json_mode=True)
        d = parse_json(raw)
        b = d.get("board") or {}
        # nested format: every sentence sits under the point it explains (alignment by structure, not by index)
        groups: list[tuple[str, list[str]]] = []
        for pt in d.get("points") or []:
            if isinstance(pt, dict) and str(pt.get("text") or "").strip():
                groups.append((str(pt["text"])[:ITEM_CHARS], [str(x) for x in pt.get("lines") or []]))
        if not groups:  # older flat format: {"board": {"items": [...]}, "lines": [{"text", "item"}]}
            items = [str(x)[:ITEM_CHARS] for x in (b.get("items") or []) if str(x).strip()]
            by = {j: [] for j in range(len(items))}
            for ln in d.get("lines") or []:
                if isinstance(ln, dict) and isinstance(ln.get("item"), int) and ln["item"] in by:
                    by[ln["item"]].append(str(ln.get("text", "")))
            groups = [(items[j], by[j]) for j in range(len(items))]
        groups = groups[:MAX_ITEMS]
        board = Board(key=f"s{i}", title=str(b.get("title") or sec["title"])[:24], items=[g[0] for g in groups])
        set_figure(board, b.get("figure"))
        lines: list[LessonLine] = []
        for j, (_, said) in enumerate(groups):
            pieces = [p for x in said for p in spoken(x, self.chars)]
            for n, piece in enumerate(pieces):
                lines.append(LessonLine(piece, board, j, gesture=(n == 0), progress=(n + 1, len(pieces))))
        for x in d.get("summary") or []:  # the whole section: every point shown, none highlighted
            lines += [LessonLine(p, board, None) for p in spoken(str(x), self.chars)]
        if not any(ln.item is not None for ln in lines):
            raise ValueError(f"lesson section {i} without lines")
        if want_ex:  # posed after the summary; the lesson waits for the answer (a bad exercise is left out)
            raw_ex = d.get("exercise")
            if isinstance(raw_ex, dict) and not raw_ex.get("concept") and sec.get("concepts"):
                raw_ex["concept"] = sec["concepts"][0]
            ex = Exercise.from_dict(raw_ex, key=f"x{i}")
            if ex is not None:
                lines += ex.lines(self.chars)
        return lines

    async def judge_figures(self, lines: list[LessonLine], max_figs: int = 3) -> list[dict]:
        """Per board point: is it complex enough to need an explanatory figure? Attaches the figures to the board
        and returns the judgements (point, complexity, need, why) for the log."""
        board = next((ln.board for ln in lines if ln.board is not None), None)
        if board is None or not board.items:
            return []
        said = {j: [] for j in range(len(board.items))}
        for ln in lines:
            if ln.item is not None and ln.item in said:
                said[ln.item].append(ln.text)
        points = "\n".join(f"{j}. {board.items[j]}：{''.join(said[j])}" for j in range(len(board.items)))
        raw = await self.llm.chat([{"role": "user", "content": FIGURE_JUDGE_PROMPT.format(
            title=board.title, max_figs=max_figs, points=points)}], max_tokens=1200, temperature=0.2, json_mode=True)
        out = []
        for d in parse_json(raw).get("points") or []:
            if not isinstance(d, dict) or not isinstance(d.get("i"), int) or not 0 <= d["i"] < len(board.items):
                continue
            room = sum(1 for f in board.figures if f.point is not None) < max_figs
            fig = set_figure(board, d.get("figure"), point=d["i"], why=str(d.get("why") or "")) \
                if d.get("need") and room else None
            out.append({"point": d["i"], "complexity": d.get("complexity"), "need": fig is not None,
                        "why": str(d.get("why") or "")[:60],
                        "kind": ("plot" if fig and fig.plot else "illustration" if fig else None)})
        return out

    def intro_lines(self, outline: Outline) -> list[LessonLine]:
        board = Board(key="outline", title=outline.title, items=[s["title"] for s in outline.sections])
        return [LessonLine(x, board, None) for x in outline.intro] or \
            [LessonLine(f"今天我们来学{outline.title}。"[: self.chars], board, None)]


__all__ = ["Board", "LessonLine", "LessonPlanner", "Outline", "render_item", "spoken"]

===== FILE: docs/reviews/adaptive1_diff.patch =====
commit 8433281d35af33365b9a5b34beb5d35cbd697c7e
Author: tzhouam <tzhouam@connect.ust.hk>
Date:   Mon Sep 28 11:29:25 2026 +0800

    Adaptive lessons from a saved student profile; teacher exercises graded into it (D-038)
    
    Student profile (grade, exams, per-concept mastery) adapts the outline (depth per
    section, where to pose exercises) and each section; exercises pause the lesson, are
    graded by rule or LLM, update mastery, and the next section addresses the mistake.
    Page: profile panel with editing, answer buttons. Also fixes the spoken form of
    (a+b)^2 and minus after a Chinese character.
    
    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

diff --git a/configs/persona_teacher/canon.json b/configs/persona_teacher/canon.json
index 7111044..4055327 100644
--- a/configs/persona_teacher/canon.json
+++ b/configs/persona_teacher/canon.json
@@ -49,11 +49,13 @@
   "speak": "explain",
   "present": "present_board"
  },
- "responder_style": "教学规则（优先于上面的示例风格）：\na) 学生问知识、概念或题目时，kind 写 \"content\"：第一句直接给出答案或结论；接着用 1-3 句讲原因或举一个生活中的例子；最后一句简短地确认学生是否明白，或留一个小思考题。总共 2-5 个 step，每个 line 按上面的字数限制、按意思断句。\nb) 答案必须准确；不确定就坦诚说不确定，不编造。公式和符号用口语读出来（如「a 的平方加 b 的平方」），不要写符号。\nc) 学生说「没听懂」或答错时，先鼓励，再换一种更简单的说法或例子重新讲。\nd) 学生追问时，接着上一个问题讲，不要重复已经讲过的内容。\ne) 和学习无关的请求，简短友好地回应，再把话题引回学习。\nf) 称呼学生为「同学」，知道名字时用名字。\ng) 学生要求系统地学一个主题（「给我上一节…的课」「系统讲讲…」「教我…」）时，kind 写 \"lesson\"，并加字段 \"topic\"（主题，不超过 12 字）；steps 只写一句开场（如「好，我们来上一节光合作用。」），详细讲解和板书由备课系统生成，不要自己写。\nh) 学生说「不用讲了」「停一下课」「先不上课了」时，kind 写 \"lesson_stop\"，steps 写一句回应。\ni) 上课中学生插问时，按 a) 简短回答（2-4 句），不要重复课程内容，也不要说「我们接着讲」（系统会自动接回课程）。\nj) 回答里有公式、步骤或要点时，可加字段 \"board\": {\"title\": 标题, \"items\": [板书要点，每条不超过 30 字，公式写在 $...$ 里]}，板书显示在老师旁边的黑板上；line 里仍然把公式用中文读出来。需要图时在 board 里加 \"figure\"：函数图像写 {\"plot\": {\"functions\": [\"x**2-1\"], \"x\": [-3, 3], \"points\": [{\"x\": 1, \"y\": 0, \"label\": \"A\"}]}, \"caption\": 图注}（精确绘制）；插图、结构示意写 {\"prompt\": 具体画什么、标注放在「」里, \"caption\": 图注}。",
+ "responder_style": "教学规则（优先于上面的示例风格）：\na) 学生问知识、概念或题目时，kind 写 \"content\"：第一句直接给出答案或结论；接着用 1-3 句讲原因或举一个生活中的例子；最后一句简短地确认学生是否明白，或留一个小思考题。总共 2-5 个 step，每个 line 按上面的字数限制、按意思断句。\nb) 答案必须准确；不确定就坦诚说不确定，不编造。公式和符号用口语读出来（如「a 的平方加 b 的平方」），不要写符号。\nc) 学生说「没听懂」或答错时，先鼓励，再换一种更简单的说法或例子重新讲。\nd) 学生追问时，接着上一个问题讲，不要重复已经讲过的内容。\ne) 和学习无关的请求，简短友好地回应，再把话题引回学习。\nf) 称呼学生为「同学」，知道名字时用名字。\ng) 学生要求系统地学一个主题（「给我上一节…的课」「系统讲讲…」「教我…」）时，kind 写 \"lesson\"，并加字段 \"topic\"（主题，不超过 12 字）；steps 只写一句开场（如「好，我们来上一节光合作用。」），详细讲解和板书由备课系统生成，不要自己写。\nh) 学生说「不用讲了」「停一下课」「先不上课了」时，kind 写 \"lesson_stop\"，steps 写一句回应。\ni) 上课中学生插问时，按 a) 简短回答（2-4 句），不要重复课程内容，也不要说「我们接着讲」（系统会自动接回课程）。\nj) 回答里有公式、步骤或要点时，可加字段 \"board\": {\"title\": 标题, \"items\": [板书要点，每条不超过 30 字，公式写在 $...$ 里]}，板书显示在老师旁边的黑板上；line 里仍然把公式用中文读出来。需要图时在 board 里加 \"figure\"：函数图像写 {\"plot\": {\"functions\": [\"x**2-1\"], \"x\": [-3, 3], \"points\": [{\"x\": 1, \"y\": 0, \"label\": \"A\"}]}, \"caption\": 图注}（精确绘制）；插图、结构示意写 {\"prompt\": 具体画什么、标注放在「」里, \"caption\": 图注}。\nk) 学生要老师出题、要练习（「给我出道题」「考考我」「我想练练…」）时，kind 写 \"exercise\"，并加字段 \"topic\"（考查的知识点，不超过 12 字；没说就用正在讲的内容）；steps 只写一句（如「好，我给你出一道题。」），题目由出题系统按学生档案生成，不要自己出。\nl) 学生说自己的年级、名字或考试成绩（「我期中数学考了 78」「因式分解丢了分」）时，除了正常回应，再加字段 \"profile_update\": {\"grade\": 年级或 null, \"name\": 名字或 null, \"exam\": {\"subject\": 学科, \"name\": 考试名称, \"score\": 分数, \"full\": 满分（默认 100）, \"weak\": [丢分的知识点]} 或 null}，只写学生明确说的内容。\nm) 系统提示里「学生档案」给出了学生的年级、成绩和掌握情况时，回答的深度和例子按学生水平来；学生薄弱的知识点讲得更细。",
  "responder_examples": [
   "用户：老师，为什么天空是蓝色的？ → {\"relation\":\"chat\",\"target_chain\":null,\"kind\":\"content\",\"steps\":[{\"intent\":\"\",\"line\":\"因为阳光被空气散射了。\"},{\"intent\":\"\",\"line\":\"蓝光波长短，最容易被散射。\"},{\"intent\":\"\",\"line\":\"满天都是蓝光，天空就是蓝的。\"},{\"intent\":\"\",\"line\":\"想想傍晚为什么是红色的？\"}],\"memory_note\":null,\"forget_term\":null}",
   "用户：给我上一节光合作用的课 → {\"relation\": \"new\", \"target_chain\": null, \"kind\": \"lesson\", \"topic\": \"光合作用\", \"steps\": [{\"intent\": \"\", \"line\": \"好，我们来上一节光合作用。\"}], \"memory_note\": null, \"forget_term\": null}",
   "用户：一元二次方程怎么解？ → {\"relation\":\"chat\",\"target_chain\":null,\"kind\":\"content\",\"steps\":[{\"intent\":\"\",\"line\":\"常用配方法和求根公式。\"},{\"intent\":\"\",\"line\":\"x 等于负 b 加减根号 b 方减四 ac，\"},{\"intent\":\"\",\"line\":\"再除以二 a。\"},{\"intent\":\"\",\"line\":\"先算判别式，看有几个实数根。\"},{\"intent\":\"\",\"line\":\"要不要一起做一道题？\"}],\"memory_note\":null,\"forget_term\":null}",
+  "用户：考考我完全平方公式 → {\"relation\": \"chat\", \"target_chain\": null, \"kind\": \"exercise\", \"topic\": \"完全平方公式\", \"steps\": [{\"intent\": \"\", \"line\": \"好，我给你出一道题。\"}], \"memory_note\": null, \"forget_term\": null}",
+  "用户：我这次期中数学考了 72 分，因式分解错了好几道 → {\"relation\": \"chat\", \"target_chain\": null, \"kind\": \"chat\", \"profile_update\": {\"grade\": null, \"name\": null, \"exam\": {\"subject\": \"数学\", \"name\": \"期中考试\", \"score\": 72, \"full\": 100, \"weak\": [\"因式分解\"]}}, \"steps\": [{\"intent\": \"\", \"line\": \"谢谢你告诉我，别灰心。\"}, {\"intent\": \"\", \"line\": \"因式分解我们可以专门练一练。\"}], \"memory_note\": null, \"forget_term\": null}",
   "用户：勾股定理是什么？ → {\"relation\": \"chat\", \"target_chain\": null, \"kind\": \"content\", \"board\": {\"title\": \"勾股定理\", \"items\": [\"直角三角形：两直角边 $a$、$b$，斜边 $c$\", \"$a^2+b^2=c^2$\", \"例：$3^2+4^2=5^2$\"]}, \"steps\": [{\"intent\": \"\", \"line\": \"直角三角形两条直角边的平方和，\"}, {\"intent\": \"\", \"line\": \"等于斜边的平方。\"}, {\"intent\": \"\", \"line\": \"比如三、四、五这组边长。\"}, {\"intent\": \"\", \"line\": \"你能再找一组这样的数吗？\"}], \"memory_note\": null, \"forget_term\": null}",
   "用户：老师，指一下黑板 → {\"relation\":\"new\",\"target_chain\":null,\"kind\":\"action\",\"steps\":[{\"intent\":\"point_board\",\"line\":\"好，我们看黑板这里。\"}],\"memory_note\":null,\"forget_term\":null}",
   "用户（上一个问题是天空为什么是蓝色的）：我没听懂 → {\"relation\": \"chat\", \"target_chain\": null, \"kind\": \"content\", \"steps\": [{\"intent\": \"\", \"line\": \"没关系，我换个说法。\"}, {\"intent\": \"\", \"line\": \"阳光像一群不同颜色的小球。\"}, {\"intent\": \"\", \"line\": \"蓝色小球最容易被空气弹开。\"}, {\"intent\": \"\", \"line\": \"弹得满天都是，天就是蓝的。\"}, {\"intent\": \"\", \"line\": \"这样好理解吗？\"}], \"memory_note\": null, \"forget_term\": null}",
@@ -67,6 +69,8 @@
   "老师，为什么天空是蓝色的？",
   "一元二次方程怎么解？",
   "我没听懂，能再讲一遍吗？",
-  "先不上课了"
+  "先不上课了",
+  "给我上一节完全平方公式的课",
+  "考考我完全平方公式"
  ]
-}
+}
\ No newline at end of file
diff --git a/live_agent/director/director.py b/live_agent/director/director.py
index 34663f5..a82c02d 100644
--- a/live_agent/director/director.py
+++ b/live_agent/director/director.py
@@ -66,6 +66,7 @@ class Segment:
     lesson: bool = False  # a lesson line (kept in the lesson backlog across questions)
     gesture: bool = False  # present the board (first line about a point)
     progress: tuple[int, int] | None = None  # (line, lines) within the board point: shown on the board
+    exercise: Any = None  # exercise.Exercise this line poses: once locked, the director waits for the answer
 
 
 @dataclass
@@ -73,6 +74,7 @@ class DirectorEvents:
     """Things the orchestrator must log (consumed by the eval schema)."""
 
     refusals: list[tuple[str, str]] = field(default_factory=list)  # (chain_id, reason)
+    exercise_timeouts: list[str] = field(default_factory=list)  # exercises answered by the teacher after silence
     degradations: list[tuple[str, str]] = field(default_factory=list)
     completion_claims: list[tuple[str, int, int | None]] = field(default_factory=list)  # (chain, request, step)
     capacity_skips: list[tuple[str, int]] = field(default_factory=list)  # (chain_id, revision)
@@ -144,6 +146,13 @@ class Director:
         self.present_intent: str | None = None  # gesture toward the board for a point's first line
         self._answer_boards = 0
         self.pending_figures: list = []  # lesson.Figure objects to draw (orchestrator)
+        # the exercise waiting for the student's answer (set when the line posing it is locked); while a lesson
+        # exercise waits, the lesson backlog does not advance
+        self.student_context = ""  # student profile summary for the responder (set by the orchestrator)
+        self.exercise = None
+        self._exercise_idle = 0  # idle requests since the exercise was posed (reminder, then the answer)
+        self.exercise_reminder_after = 8  # requests (~40 s at ~5 s per request) [proposed]
+        self.exercise_reveal_after = 18  # requests (~90 s): the teacher shows the answer and moves on [proposed]
         self.plan_version = 0
         self.queue: deque[Segment] = deque()
         self.held: dict[str, dict[int, list[Segment]]] = {}  # multistep: steps not yet released
@@ -247,6 +256,8 @@ class Director:
         else:
             sys = OPEN_LOOP_SYSTEM.format(name=self.persona_name, bio=self.persona_bio, chars=CHARS_PER_REQUEST,
                                           open_chains=open_chains or "无", memories=memories or "无")
+        if self.student_context:  # the saved student profile (private sessions): answers match the student's level
+            sys += "\n学生档案：\n" + self.student_context
         history = [{"role": role, "content": text} for role, text in self.dialogue]
         raw = await self.llm.chat([{"role": "system", "content": sys}, *history,
                                    {"role": "user", "content": utt.text}], json_mode=True)
@@ -366,6 +377,9 @@ class Director:
         to the front of the lesson backlog (in order) and the lesson resumes after the interruption."""
         cut_lessons = [self._lesson_locked.pop(sc.request_index) for sc in sorted(scripts, key=lambda x: x.request_index)
                        if sc.request_index in self._lesson_locked]
+        # lines posing an exercise that is already closed (answered meanwhile: a soft switch cuts after grading)
+        # are not said again
+        cut_lessons = [x for x in cut_lessons if x.exercise is None or x.exercise is self.exercise]
         for seg in reversed(cut_lessons):
             self.lesson_backlog.appendleft(seg)
         if cut_lessons:
@@ -645,7 +659,8 @@ class Director:
             if seg.min_request <= request_index:
                 del self.queue[i]
                 return seg
-        if self.lesson_backlog and not self.listening:
+        if self.lesson_backlog and not self.listening and (
+                self.exercise is None or self.lesson_backlog[0].exercise is self.exercise):
             nxt = self.lesson_backlog[0]
             if self._lesson_resume:  # back from a question: say so before continuing
                 self._lesson_resume = False
@@ -666,14 +681,67 @@ class Director:
                                          if not f.url and all(f is not g for g in self.pending_figures)]
             self.lesson_backlog.append(Segment(chain_id=None, plan_version=self.plan_version, line=ln.text,
                                                board=ln.board, reveal=ln.item, lesson=True, gesture=ln.gesture,
-                                               progress=getattr(ln, "progress", None)))
+                                               progress=getattr(ln, "progress", None),
+                                               exercise=getattr(ln, "exercise", None)))
 
     def nudge(self, line: str) -> None:
         """A short line to win back a distracted student: spoken next (before the next lesson line), gesturing at the
         board; not a reply, so the lesson does not announce a resume after it."""
         self.queue.appendleft(Segment(chain_id=None, plan_version=self.plan_version, line=line, gesture=True))
 
+    def pose_exercise(self, lines) -> None:
+        """An exercise the student asked for (outside the lesson flow): its lines are spoken next."""
+        for ln in lines:
+            self.queue.append(Segment(chain_id=None, plan_version=self.plan_version, line=ln.text, board=ln.board,
+                                      reveal=ln.item, gesture=ln.gesture, exercise=getattr(ln, "exercise", None)))
+
+    def close_exercise(self, queued_before: set[int]) -> None:
+        """The answer was graded and its feedback applied as a reply: the segments queued since ``queued_before``
+        (ids) show the answer on the board; the lesson then continues without a "we continue" announcement."""
+        ex, self.exercise = self.exercise, None
+        if ex is None:
+            return
+        board = ex.board(reveal_answer=True)
+        for seg in self.queue:
+            if seg.board is None and id(seg) not in queued_before:
+                seg.board = board
+        # lines of the question not yet spoken (answered early, or cut and re-queued) are dropped
+        self.lesson_backlog = deque(x for x in self.lesson_backlog if x.exercise is not ex)
+        self.queue = deque(x for x in self.queue if x.exercise is not ex)
+        self._lesson_resume = False
+
+    def _exercise_wait(self) -> Segment | None:
+        """Nothing to say while an exercise waits: remind once, and after a long silence show the answer and move
+        on (a silent student must not stall the lesson). Not graded: silence is no evidence either way."""
+        from live_agent.exercise import feedback_lines
+
+        ex = self.exercise
+        self._exercise_idle += 1
+        if self._exercise_idle == self.exercise_reminder_after:
+            return Segment(chain_id=None, plan_version=self.plan_version, line="想好了吗？说出答案，不会也没关系。",
+                           board=ex.board(), gesture=True)
+        if self._exercise_idle < self.exercise_reveal_after:
+            return None
+        lines = ["我们一起来看这道题。"] + feedback_lines(ex, {"correct": False, "skipped": True}, CHARS_PER_REQUEST)[1:]
+        before = {id(x) for x in self.queue}
+        for line in lines:
+            self.queue.append(Segment(chain_id=None, plan_version=self.plan_version, line=line))
+        self.events.exercise_timeouts.append(ex.concept)
+        self.close_exercise(before)
+        return self.queue.popleft() if self.queue else None
+
+    def remind_exercise(self) -> None:
+        """After a reply to something else while an exercise waits: bring the student back to it."""
+        if self.exercise is not None and not any(x.exercise is self.exercise
+                                                 for x in (*self.lesson_backlog, *self.queue)):
+            self.queue.append(Segment(chain_id=None, plan_version=self.plan_version,
+                                      line="我们回到刚才这道练习，想好了告诉我。", board=self.exercise.board(),
+                                      gesture=True))
+            self._lesson_resume = False
+
     def stop_lesson(self) -> None:
+        if self.exercise is not None and getattr(self.exercise, "source", "") == "lesson":
+            self.exercise = None
         self.lesson_backlog.clear()
         self._lesson_locked.clear()
         self._lesson_resume = False
@@ -681,6 +749,11 @@ class Director:
 
     def next_script(self, request_index: int) -> BlockScript:
         seg = self._pop_segment(request_index)
+        if seg is not None and seg.exercise is not None:
+            self.exercise = seg.exercise  # posed: the lesson waits for the answer after its last line
+            self._exercise_idle = 0
+        elif seg is None and self.exercise is not None and not self.listening:
+            seg = self._exercise_wait()
         follow_through = ""
         if seg is None:
             intent = self.listen_intent if self.listening else self.idle_intent
diff --git a/live_agent/orchestrator.py b/live_agent/orchestrator.py
index 6ed92b6..3b0f195 100644
--- a/live_agent/orchestrator.py
+++ b/live_agent/orchestrator.py
@@ -165,6 +165,10 @@ class Orchestrator:
         self._episode: tuple[str | None, int] = (None, 0)  # (stable state, nudges given in this episode)
         self.image_maker = None  # board_images.ImageMaker (illustrations), set by the app when configured
         self.figure_dir = None  # where exact plots are drawn (board_plot); set by the app
+        self.student = None  # student.StudentProfile (private sessions): adapts lessons, records exercise results
+        self._lesson_mistakes: list[str] = []  # this lesson's wrong answers, addressed by the next section
+        self._exercises = 0
+        self._shown_exercise = None  # the exercise the page was last told about
         self._rng = random.Random(self.cfg.seed)
         self._chain_costs: list[float] = []
         self._checked: set[int] = set()
@@ -367,6 +371,7 @@ class Orchestrator:
                 self.sched.observe_timing(tm)
             self._locking = k  # from popping the segment until the lock is recorded
             script = self.director.next_script(k)
+            self._exercise_changed()
             self._audit(script)
             try:
                 prompt = compile_prompt(script, first_request=(k == 0))
@@ -457,6 +462,8 @@ class Orchestrator:
     def _drain_director_events(self, t: float) -> None:
         ev = self.director.events
         rev = lambda cid: len(self.director.chains[cid].revisions) if cid in self.director.chains else None  # noqa: E731
+        for concept in self._drain(ev.exercise_timeouts):
+            self.log.emit(EventType.LESSON, t, stage="exercise_timeout", concept=concept)
         for chain_id, reason in self._drain(ev.refusals):
             self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason, revision=rev(chain_id))
         for chain_id, reason in self._drain(ev.degradations):
@@ -1011,6 +1018,80 @@ class Orchestrator:
         self.director.pending_figures += [f for f in board.figures if not f.url]
         self._make_figures()
 
+    # ------------------------------------------------------------------ exercises
+    async def _grade_answer(self, utt: Utterance, epoch: int) -> dict | None:
+        """While an exercise waits: is this utterance its answer? If so grade it, speak the feedback, update the
+        student profile and return the decision for the log; None: not an answer (the responder handles it)."""
+        from live_agent.exercise import grade
+
+        d = self.director
+        ex = d.exercise
+        try:
+            r = await grade(d.llm, ex, utt.text)
+        except Exception as e:  # noqa: BLE001 - grading failed: the responder answers as usual
+            self.log.emit(EventType.LESSON, now(), stage="grading_failed", error=str(e)[:160])
+            return None
+        if not r.get("is_answer"):
+            return None
+        decision = {"relation": "chat", "target_chain": None, "kind": "chat", "memory_note": None,
+                    "forget_term": None, "steps": [{"intent": "", "line": x} for x in r.get("feedback") or []],
+                    "exercise_result": {"correct": r["correct"], "concept": ex.concept}}
+        if epoch != self._input_epoch or d.exercise is not ex:
+            self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
+            return decision
+        before = {id(x) for x in d.queue}
+        d.apply(utt, decision)
+        d.close_exercise(before)
+        self._decisions += 1
+        change = None
+        if self.student is not None:
+            change = self.student.record_exercise(ex.concept, r["correct"], question=ex.question, answer=utt.text,
+                                                  misconception=r.get("misconception") or "", subject=ex.subject)
+            self.student.save()
+        if not r["correct"] and ex.source == "lesson":
+            self._lesson_mistakes.append(ex.concept + (f"（{r['misconception']}）" if r.get("misconception") else ""))
+        self.log.emit(EventType.LESSON, now(), stage="exercise_graded", concept=ex.concept, correct=r["correct"],
+                      skipped=bool(r.get("skipped")), misconception=r.get("misconception"), mastery=change)
+        self._emit_profile()
+        self._exercise_changed()
+        return decision
+
+    async def _give_exercise(self, topic: str) -> None:
+        """The student asked for an exercise: one on ``topic`` at the level the profile suggests."""
+        from live_agent.exercise import make_exercise
+
+        d = self.director
+        self._exercises += 1
+        profile = self.student.summary() if self.student is not None else "无（新学生，没有档案）"
+        try:
+            ex = await make_exercise(d.llm, name=d.persona_name, topic=topic, profile=profile,
+                                     key=f"q{self._exercises}")
+        except Exception as e:  # noqa: BLE001
+            self.log.emit(EventType.LESSON, now(), stage="exercise_failed", topic=topic, error=str(e)[:160])
+            d.say_verified("抱歉，这道题我没出好，你可以换个问法。")
+            return
+        lines = ex.lines(22)
+        d.pose_exercise(lines[1:])  # the responder already said it will give one
+        self.log.emit(EventType.LESSON, now(), stage="exercise", concept=ex.concept, exercise=ex.question,
+                      options=ex.options, kind=ex.kind)
+
+    def _exercise_changed(self) -> None:
+        """Tell the page when an exercise opens or closes (its answer buttons); the 2 Hz state snapshot is only
+        sent in gaps between events, which a lesson rarely leaves."""
+        ex = self.director.exercise
+        if ex is self._shown_exercise:
+            return
+        self._shown_exercise = ex
+        if ex is None:
+            self.log.emit(EventType.LESSON, now(), stage="exercise_closed")
+        else:
+            self.log.emit(EventType.LESSON, now(), stage="exercise_open", concept=ex.concept,
+                          options=[o[:1] for o in ex.options])
+
+    def _emit_profile(self) -> None:
+        if self.student is not None:
+            self.log.emit(EventType.LESSON, now(), stage="profile", profile=self.student.view())
+
     def _stop_lesson(self) -> None:
         if self._lesson_task is not None and not self._lesson_task.done():
             self._lesson_task.cancel()
@@ -1026,7 +1107,7 @@ class Orchestrator:
         planner = LessonPlanner(d.llm, name=d.persona_name, bio=d.persona_bio)
         context = "；".join(t for r, t in d.dialogue if r == "user")[-300:]
         try:
-            outline = await planner.outline(topic, context)
+            outline = await planner.outline(topic, context, profile=self.student)
         except Exception as e:  # noqa: BLE001
             self.log.emit(EventType.LESSON, now(), stage="outline_failed", topic=topic, error=str(e)[:160])
             d.add_lesson_lines([LessonLine("抱歉，这节课我还没准备好，你可以先问我问题。", None, None)])
@@ -1034,26 +1115,42 @@ class Orchestrator:
         d.lesson_title = outline.title
         d.add_lesson_lines(planner.intro_lines(outline))
         self.log.emit(EventType.LESSON, now(), stage="outline", topic=topic, title=outline.title,
-                      sections=[s["title"] for s in outline.sections])
+                      sections=[s["title"] for s in outline.sections],
+                      plan=[{"title": s["title"], "concepts": s.get("concepts", []), "depth": s.get("depth"),
+                             "exercise": s.get("exercise", False)} for s in outline.sections],
+                      note=outline.note, adaptive=self.student is not None)
         covered: list[str] = []
+        waiting_for = None  # the previous section's exercise: its result shapes the next section
         for i in range(len(outline.sections)):
-            while len(d.lesson_backlog) >= self.cfg.lesson_lookahead and not self._stop.is_set():
+            while not self._stop.is_set() and (
+                    len(d.lesson_backlog) >= self.cfg.lesson_lookahead
+                    or (waiting_for is not None and (d.exercise is waiting_for
+                                                     or any(x.exercise is waiting_for for x in d.lesson_backlog)))):
                 await asyncio.sleep(0.5)
+            waiting_for = None
             lines = None
             for attempt in range(2):
                 try:
-                    lines = await planner.section(outline, i, covered)
+                    lines = await planner.section(outline, i, covered, profile=self.student,
+                                                  mistakes=list(self._lesson_mistakes))
                     break
                 except Exception as e:  # noqa: BLE001 - retry once, then skip the section
                     self.log.emit(EventType.LESSON, now(), stage="section_failed", section=i, attempt=attempt,
                                   error=str(e)[:160])
             if lines:
+                self._lesson_mistakes.clear()  # addressed by this section
                 d.add_lesson_lines(lines)
+                if self.student is not None and outline.sections[i].get("concepts"):
+                    self.student.mark_taught(outline.sections[i]["concepts"])
+                    self.student.save()
                 self._make_figures()
                 self._spawn(self._judge_figures(planner, lines), "figure_judgement")
+                ex = next((ln.exercise for ln in lines if getattr(ln, "exercise", None) is not None), None)
+                waiting_for = ex if self.student is not None else None  # adapt the next section to the answer
                 self.log.emit(EventType.LESSON, now(), stage="section", section=i,
                               title=outline.sections[i]["title"], lines=len(lines),
-                              points=len(lines[0].board.items))
+                              points=len(lines[0].board.items), depth=outline.sections[i].get("depth"),
+                              exercise=(ex.question if ex is not None else None))
             covered.append(outline.sections[i]["title"])
         self.log.emit(EventType.LESSON, now(), stage="planned", title=outline.title)
 
@@ -1119,6 +1216,15 @@ class Orchestrator:
             recall_id = self._no_recall()
         if self.memory:
             self.memory.on_user_utterance(utt)
+        if self.director.exercise is not None and not _FORGET.search(utt.text):
+            graded = await self._grade_answer(utt, epoch)
+            if graded is not None:
+                self._drain_director_events(now())
+                self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=graded,
+                              chains={c.chain_id: c.status.value for c in self.director.chains.values()},
+                              recalled=[])
+                return graded
+        self.director.student_context = self.student.summary() if self.student is not None else ""
         decision = await self.director.decide(utt, memories)
         term = (decision or {}).get("forget_term")
         if epoch != self._input_epoch:
@@ -1136,6 +1242,17 @@ class Orchestrator:
                 self._start_lesson(str(decision["topic"]).strip())
             elif kind == "lesson_stop":
                 self._stop_lesson()
+            elif kind == "exercise":
+                self._spawn(self._give_exercise(str((decision or {}).get("topic") or "").strip()
+                                                or self.director.lesson_title or "刚才讲的内容"), "exercise")
+            elif self.director.exercise is not None:
+                self.director.remind_exercise()  # a question while an exercise waits: back to it afterwards
+            if self.student is not None and (decision or {}).get("profile_update"):
+                changed = self.student.apply_update(decision["profile_update"])
+                if changed:
+                    self.student.save()
+                    self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
+                    self._emit_profile()
         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
         if term and self.memory is not None and hasattr(self.memory, "forget"):
             complete = await self._erase(term)
@@ -1182,6 +1299,10 @@ class Orchestrator:
             # "杭州" is its value); report.terms holds them in memory only.
             terms = sorted({term, *(getattr(report, "terms", None) or [])}, key=len, reverse=True)
             purged = sum(self.director.purge(x) for x in terms)
+            if self.student is not None:
+                purged += sum(self.student.purge(x) for x in terms)
+                self.student.save()
+                self._lesson_mistakes = [m for m in self._lesson_mistakes if not any(x in m for x in terms)]
             acknowledge("unsent_scripts", True, f"controller items purged: {purged}")
             # The responder is stateless per call; its context is rebuilt from purged state.
             acknowledge("llm_context", True, "stateless responder; memory notes and chains purged")
@@ -1253,6 +1374,8 @@ class Orchestrator:
             "lambda_s": round(self.sched.lambda_estimate(), 2), "listening": d.listening,
             "awaiting_decision": d.awaiting_decision, "erasure_gate_open": self._ready.is_set(),
             "queued_segments": len(d.queue), "mode": d.mode.value,
+            "exercise": ({"concept": d.exercise.concept, "kind": d.exercise.kind,
+                          "options": [o[:1] for o in d.exercise.options]} if d.exercise is not None else None),
         }
 
     def open_chains(self) -> list[str]:
diff --git a/live_agent/server/app.py b/live_agent/server/app.py
index 09a0e62..a7bf574 100644
--- a/live_agent/server/app.py
+++ b/live_agent/server/app.py
@@ -34,6 +34,7 @@ import io
 from fractions import Fraction
 import json
 import logging
+import re
 from pathlib import Path
 
 import numpy as np
@@ -53,6 +54,7 @@ STATIC = Path(__file__).parent / "static"
 
 
 BOARD_IMAGES = Path(__file__).resolve().parents[2] / ".cache" / "board_images"
+STUDENT_SEEDS = Path(__file__).resolve().parents[2] / "configs" / "students"  # example profiles (fictional)
 
 
 def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
@@ -108,7 +110,9 @@ PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_
                 "audibility", "revision", "speaker", "uid", "counts", "expected", "wrong", "target", "gave_up", "anchor_removed", "stage",
                 "title", "sections", "section", "lines", "points", "board", "seconds",
                 "attempt", "labels",
-                "point", "judgements", "state", "stable", "nudge")
+                "point", "judgements", "state", "stable", "nudge",
+                "plan", "note", "adaptive", "depth", "exercise", "concept", "correct", "skipped", "misconception",
+                "mastery", "profile", "changed", "options", "topic")
 
 
 def panel_event(ev, t0: float) -> dict | None:
@@ -422,6 +426,12 @@ def build_app(args: argparse.Namespace) -> FastAPI:
 
                 orch.image_maker = ImageMaker(args.image_url, BOARD_IMAGES)
             orch.figure_dir = BOARD_IMAGES  # exact plots need no model
+            student_id = str(hello.get("student") or args.student)
+            if mode == "private" and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", student_id):
+                # personal data: only a private session reads or updates the saved profile
+                from live_agent.student import StudentProfile
+
+                orch.student = StudentProfile.load(student_id, Path(args.student_store), STUDENT_SEEDS)
             if getattr(judge, "vlm", None) is not None:  # the camera focus check uses the judge's VLM (opt-in)
                 from live_agent.attention import AttentionMonitor
 
@@ -464,7 +474,8 @@ def build_app(args: argparse.Namespace) -> FastAPI:
                                            "responder": "rules" if args.llm_url == "scripted" else args.llm_model,
                                            "asr": bool(args.asr_url), "persona": canon.get("display_name", ""),
                                            "examples": canon.get("examples", []),
-                                           "attention": orch.attention is not None},
+                                           "attention": orch.attention is not None,
+                                           "student": orch.student.view() if orch.student is not None else None},
                                           ensure_ascii=False))
 
             async def handle_inputs() -> None:
@@ -535,6 +546,10 @@ def build_app(args: argparse.Namespace) -> FastAPI:
                         pass
                 elif t == "camera_off":
                     orch.camera_off()
+                elif t == "profile" and orch.student is not None and isinstance(data.get("profile"), dict):
+                    orch.student.update_basics(data["profile"])  # name, grade, exams (mastery comes from exercises)
+                    orch.student.save()
+                    orch._emit_profile()
                 elif t == "video_codec" and data.get("codec") == "jpeg":
                     transport.video_codec = "jpeg"  # the page failed to decode H.264
         except WebSocketDisconnect:
@@ -617,6 +632,8 @@ def main() -> None:
     p.add_argument("--image-url", default="", help="board figure server (Qwen-Image via vLLM-Omni), empty: none")
     p.add_argument("--video-codec", default="auto", choices=["auto", "jpeg"],
                    help="auto: H.264 segments to pages that can decode them (WebCodecs), else JPEG frames")
+    p.add_argument("--student", default="demo", help="student profile id for private sessions (the page may pick one)")
+    p.add_argument("--student-store", default=str(BOARD_IMAGES.parent / "students"), help="saved student profiles (personal data)")
     p.add_argument("--host", default="127.0.0.1")
     p.add_argument("--port", type=int, default=8200)
     # Generator options (--taomate-*, --omni-*) are parsed by the adapters (taomate_h3.py, vllm_omni_h3.py).
diff --git a/live_agent/server/static/index.html b/live_agent/server/static/index.html
index e951ce2..fd84ca2 100644
--- a/live_agent/server/static/index.html
+++ b/live_agent/server/static/index.html
@@ -26,6 +26,20 @@
   main { display:grid; grid-template-columns:minmax(300px, 1fr) minmax(300px, 400px); gap:16px; padding:16px;
          max-width:1920px; margin:0 auto; }
   @media (max-width: 860px) { main { grid-template-columns:1fr; } }
+  .prof .who { font-weight:600; }
+  .prof .exams { margin:4px 0 8px; padding-left:18px; color:var(--muted); font-size:13px; }
+  .prof .cp { display:grid; grid-template-columns:minmax(70px, 7em) 1fr 3.4em; gap:6px; align-items:center; font-size:13px; margin:3px 0; }
+  .prof .bar { height:8px; border-radius:4px; background:var(--chip); overflow:hidden; }
+  .prof .bar i { display:block; height:100%; background:var(--info); }
+  .prof .cp.weak .bar i { background:var(--bad); } .prof .cp.partial .bar i { background:var(--warn); }
+  .prof .cp.mastered .bar i { background:var(--ok); } .prof .cp.unknown .bar i { background:var(--line); }
+  .prof .cp .v { color:var(--muted); text-align:right; font-variant-numeric:tabular-nums; }
+  .prof .cp.flash { animation:flash 1.6s ease-out; }
+  @keyframes flash { from { background:var(--chip); } to { background:transparent; } }
+  .prof form { display:grid; gap:6px; margin-top:8px; }
+  .prof form textarea { min-height:5.5em; font:inherit; font-size:13px; padding:6px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--ink); }
+  .prof form input { font:inherit; padding:4px 6px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--ink); }
+  .chip.answer { border:1px solid var(--accent); font-weight:600; }
   .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px; min-width:0; }
   .stage { display:flex; flex-direction:column; gap:12px; min-width:0; }
   .screen { position:relative; background:var(--stage); border-radius:10px; display:flex; justify-content:center;
@@ -125,6 +139,7 @@
       <div class="row" style="margin-bottom:8px">
         <label>会话 <select id="mode"><option value="private">一对一私聊</option><option value="public">测试直播</option></select></label>
         <label>用户 <input type="text" id="uid" value="user-1" style="flex:0;width:110px;min-width:90px"></label>
+        <label title="私聊会话读取并更新这个学生的档案">学生 <input type="text" id="sid" value="demo" style="flex:0;width:80px;min-width:70px"></label>
         <button class="primary" id="connect">连接</button>
         <button id="disconnect" disabled>断开</button>
       </div>
@@ -144,6 +159,10 @@
   </section>
 
   <aside class="panel">
+    <div class="card prof" id="profCard">
+      <h2>学生档案 <button id="profEdit" hidden style="float:right;font-size:12px">编辑</button></h2>
+      <div id="prof"><div class="empty">私聊会话连接后显示学生的年级、成绩和各知识点掌握度；课程和练习按档案调整。</div></div>
+    </div>
     <div class="card">
       <h2>实时指标</h2>
       <div class="stats">
@@ -227,7 +246,7 @@ $("connect").onclick = () => {
   ws.onopen = async () => {
     // H.264 segments need ~1/6 of the bandwidth of per-frame JPEG (a remote bridge cannot carry JPEG in real time)
     const video_codecs = (await h264Supported()) ? ["h264"] : [];
-    ws.send(JSON.stringify({type: "hello", mode: $("mode").value, user_id: $("uid").value, video_codecs}));
+    ws.send(JSON.stringify({type: "hello", mode: $("mode").value, user_id: $("uid").value, student: $("sid").value.trim(), video_codecs}));
     ["talk","text","send","disconnect"].forEach(id => $(id).disabled = false);
     document.querySelectorAll(".chip").forEach(b => b.disabled = false);
     $("connect").disabled = true; $("overlay").textContent = "正在启动生成…";
@@ -294,7 +313,8 @@ async function onMessage(ev) {
 
 function onStatus(m) {
   setConn("会话中", true);
-  if (Array.isArray(m.examples) && m.examples.length) setChips(m.examples, true);
+  if (Array.isArray(m.examples) && m.examples.length) { personaChips = m.examples; setChips(m.examples, true); }
+  showProfile(m.student);
   $("cam").hidden = !m.attention; $("cam").disabled = false;
   const b = $("badges"); b.querySelectorAll(".badge:not(#conn)").forEach(x => x.remove());
   const items = [
@@ -313,7 +333,56 @@ function onStatus(m) {
 }
 
 // ---------------------------------------------------------------- panel
+// ---------------------------------------------------------------- student profile and exercises
+let personaChips = EXAMPLES, profile = null, exerciseKey = "", lastGraded = null;
+const LEVEL = {mastered: "已掌握", partial: "基本理解", weak: "薄弱", unknown: "未评估"};
+function showProfile(p, flash) {
+  profile = p || null;
+  $("profEdit").hidden = !p;
+  const el = $("prof");
+  if (!p) { el.innerHTML = `<div class="empty">此会话不使用学生档案（测试直播模式不读取个人数据）。</div>`; return; }
+  const exams = (p.exams || []).slice(-4).map(e => `<li>${esc(e.date || "")} ${esc(e.subject)}${esc(e.name)} <b>${e.score}</b>/${e.full}` +
+    (e.weak && e.weak.length ? ` · 失分：${esc(e.weak.join("、"))}` : "") + "</li>").join("");
+  const cps = (p.concepts || []).map(c => `<div class="cp ${esc(c.level)}${flash === c.name ? " flash" : ""}" title="${esc(LEVEL[c.level] || c.level)}${c.attempts ? `，练习 ${c.correct}/${c.attempts} 对` : ""}">
+      <span>${esc(c.name)}</span><span class="bar"><i style="width:${Math.round((c.mastery ?? 0) * 100)}%"></i></span>
+      <span class="v">${c.mastery == null ? "–" : Math.round(c.mastery * 100) + "%"}</span></div>`).join("");
+  el.innerHTML = `<div class="who">${esc(p.name || "同学")} · ${esc(p.grade || "年级未填")}</div>` +
+    (exams ? `<ul class="exams">${exams}</ul>` : `<div class="meta">还没有考试成绩</div>`) +
+    (cps || `<div class="meta">还没有知识点记录：做练习后会出现</div>`);
+}
+function examLines(p) { return (p.exams || []).map(e => `${e.subject} ${e.name} ${e.score}/${e.full} ${(e.weak || []).join(",")}`.trim()).join("\n"); }
+$("profEdit").onclick = () => {
+  if (!profile || $("profForm")) return;
+  const f = document.createElement("form"); f.id = "profForm";
+  f.innerHTML = `<label>名字 <input name="name" value="${esc(profile.name)}"></label>
+    <label>年级 <input name="grade" value="${esc(profile.grade)}" placeholder="如 初二"></label>
+    <label>考试成绩（每行：学科 考试 分数/满分 失分点,失分点）<textarea name="exams">${esc(examLines(profile))}</textarea></label>
+    <div><button class="primary" type="submit">保存</button> <button type="button" id="profCancel">取消</button></div>`;
+  $("prof").appendChild(f);
+  $("profCancel").onclick = () => f.remove();
+  f.onsubmit = (ev) => {
+    ev.preventDefault();
+    const exams = f.exams.value.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
+      const m = l.match(/^(\S+)\s+(\S+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*(.*)$/);
+      return m ? {subject: m[1], name: m[2], score: +m[3], full: +(m[4] || 100),
+                  weak: m[5].split(/[,，、\s]+/).filter(Boolean)} : null;
+    }).filter(Boolean);
+    send({type: "profile", profile: {name: f.name.value.trim(), grade: f.grade.value.trim(), exams}});
+    f.remove();
+  };
+};
+function showExercise(ex) {  // answer buttons while an exercise waits; the persona's examples otherwise
+  const key = ex ? ex.concept + (ex.options || []).join("") : "";
+  if (key === exerciseKey) return;
+  exerciseKey = key;
+  const live = ws && ws.readyState === 1;
+  if (!ex) { setChips(personaChips, live); return; }
+  setChips([...(ex.options || []).map(o => "选 " + o), "我不会"], live);
+  document.querySelectorAll("#chips .chip").forEach(b => b.classList.add("answer"));
+}
+
 function onState(s) {
+  showExercise(s.exercise);
   $("sLambda").textContent = typeof s.lambda_s === "number" ? s.lambda_s.toFixed(1) : "–";
   $("sReq").textContent = s.next_lock ?? "–";
   const flags = [];
@@ -399,8 +468,29 @@ function onEvent(m) {
                  figure_judgement: `配图判断「${d.title || ""}」：` + (d.judgements || []).map(j =>
                    `第 ${j.point + 1} 条 复杂度 ${j.complexity ?? "?"} ${j.need ? "→ 配图" : "→ 不配"}${j.why ? "（" + j.why + "）" : ""}`).join("；"),
                  figure: `第 ${(d.point ?? 0) + 1} 条的配图已画好（${d.kind === "plot" ? "精确作图" : "插图"}）`,
-                 figure_failed: `配图失败：${d.error || ""}`}[d.stage];
+                 figure_failed: `配图失败：${d.error || ""}`,
+                 exercise: `出题（${d.concept || ""}）：${d.exercise || ""}`,
+                 exercise_failed: `出题失败：${d.error || ""}`,
+                 exercise_timeout: `练习「${d.concept || ""}」无人作答，老师讲解后继续`,
+                 grading_failed: `批改失败：${d.error || ""}`,
+                 profile_updated: `学生档案已更新（${(d.changed || []).join("、")}）`}[d.stage];
       if (s) feed(t, d.stage.endsWith("failed") ? "bad" : "", "备课", s);
+      if (d.stage === "outline" && d.plan) {
+        const dep = {review: "复习", core: "重点", new: "新课"};
+        feed(t, "", d.adaptive ? "因材施教" : "教案", (d.note ? d.note + "；" : "") + d.plan.map((x, i) =>
+          `${i + 1}.${x.title}[${dep[x.depth] || x.depth}${x.exercise ? "+练习" : ""}]`).join(" "));
+      }
+      if (d.stage === "section" && d.exercise) feed(t, "", "练习", `本节后出题：${d.exercise}`);
+      if (d.stage === "exercise_graded") {
+        const m = d.mastery;
+        feed(t, d.correct ? "ok" : "bad", "批改", `${d.concept}：${d.skipped ? "不会" : d.correct ? "答对" : "答错"}` +
+             (d.misconception ? `（${d.misconception}）` : "") +
+             (m && m.after != null ? ` · 掌握度 ${m.before == null ? "–" : Math.round(m.before * 100) + "%"} → ${Math.round(m.after * 100)}%` : ""));
+      }
+      if (d.stage === "profile" && d.profile) showProfile(d.profile, (d.profile.concepts || []).length ? lastGraded : null);
+      if (d.stage === "exercise_graded") lastGraded = d.concept;
+      if (d.stage === "exercise_open") showExercise({concept: d.concept, options: d.options || []});
+      if (d.stage === "exercise_closed") showExercise(null);
       break;
     }
     case "attention": {

===== FILE: tests/test_student.py =====
"""Adaptive teaching: the saved student profile (grade, exams, per-concept mastery) shapes the lesson plan; the
teacher's exercises pause the lesson, are graded (rules, then the LLM) and update the profile."""

from __future__ import annotations

import asyncio
import json

import test_pipeline as tp
import test_teacher_persona as tt
from live_agent.exercise import Exercise, grade, quick_grade
from live_agent.lesson import LessonPlanner
from live_agent.llm import ScriptedLLM
from live_agent.student import StudentProfile
from live_agent.types import EventType, Utterance, now

SEEDS = tt.CFG.parents[0] / "students"
CHOICE = {"concept": "完全平方公式", "type": "choice", "question": "$(a+b)^2$ 展开等于？",
          "options": ["A. $a^2+b^2$", "B. $a^2+2ab+b^2$", "C. $a^2+ab+b^2$"], "answer": "B",
          "explanation": ["两数和的平方，等于平方和再加两倍的乘积。"]}
OUTLINE = {"title": "完全平方公式", "plan_note": "期中考试这里失分，重点讲；整式乘法已掌握，只复习",
           "sections": [{"title": "复习整式乘法", "goal": "回顾", "concepts": ["整式乘法"], "depth": "review", "exercise": False},
                        {"title": "完全平方公式", "goal": "推导和使用", "concepts": ["完全平方公式"], "depth": "core",
                         "exercise": True}],
           "intro": ["今天我们学完全平方公式。"]}


def section(i):
    out = {"board": {"title": f"第{i}节"},
           "points": [{"text": f"要点{i}", "lines": [f"第{i}节讲要点。", f"第{i}节再举个例子。"]}],
           "summary": [f"第{i}节小结。"]}
    if i == 2:
        out["exercise"] = CHOICE
    return out


def planner_llm(messages):
    text = messages[-1]["content"]
    if "课程大纲" in text:
        return json.dumps(OUTLINE, ensure_ascii=False)
    return json.dumps(section(1 if "第 1/2 节" in text else 2), ensure_ascii=False)


def profile(tmp_path):
    return StudentProfile.load("demo", tmp_path, SEEDS)


def test_the_profile_loads_from_its_seed_and_exam_losses_set_a_low_prior(tmp_path):
    p = profile(tmp_path)
    assert p.grade == "初二" and p.level("整式乘法") == "mastered" and p.level("完全平方公式") == "weak"
    assert p.mastery("因式分解") == 0.4  # never practised, but the midterm lost points on it
    s = p.summary()
    assert "初二" in s and "期中考试 72/100" in s and "失分点：因式分解" in s
    assert s.index("完全平方公式") < s.index("整式乘法")  # weakest first


def test_exercises_move_mastery_and_the_profile_is_saved_and_erasable(tmp_path):
    p = profile(tmp_path)
    before = p.mastery("完全平方公式")
    up = p.record_exercise("完全平方公式", True, question="q", answer="B")
    assert up["before"] == before and up["after"] > before
    down = p.record_exercise("完全平方公式", False, misconception="漏了 2ab")
    assert down["after"] < up["after"] and p.concepts["完全平方公式"].notes[-1] == "漏了 2ab"
    p.save()
    again = StudentProfile.load("demo", tmp_path, SEEDS)  # the saved copy wins over the seed
    assert again.concepts["完全平方公式"].attempts == p.concepts["完全平方公式"].attempts
    assert again.purge("完全平方公式") >= 1 and "完全平方公式" not in again.concepts
    assert all("完全平方公式" not in json.dumps(h, ensure_ascii=False) for h in again.history)


def test_what_the_student_says_about_themselves_updates_the_profile(tmp_path):
    p = profile(tmp_path)
    changed = p.apply_update({"grade": "初三", "exam": {"subject": "数学", "name": "单元测", "score": 64, "weak": ["配方法"]}})
    assert changed == ["grade", "exam"] and p.grade == "初三" and p.level("配方法") == "weak"
    p.update_basics({"exams": [{"subject": "数学", "name": "期末", "score": "88"}, {"bad": 1}]})
    assert [(e.name, e.score) for e in p.exams] == [("期末", 88.0)]


def test_the_outline_and_sections_are_adapted_to_the_profile_and_carry_the_exercise(tmp_path):
    llm = ScriptedLLM(planner_llm)
    planner = LessonPlanner(llm, name="林老师", bio="")
    p = profile(tmp_path)
    outline = asyncio.run(planner.outline("完全平方公式", profile=p))
    prompt = llm.calls[0][-1]["content"]
    assert "期中考试 72/100" in prompt and "完全平方公式：薄弱" in prompt and "因材施教" in prompt
    assert outline.note.startswith("期中") and [s["depth"] for s in outline.sections] == ["review", "core"]
    review = asyncio.run(planner.section(outline, 0, [], profile=p))
    assert "复习" in llm.calls[1][-1]["content"] and "4-6" in llm.calls[1][-1]["content"]
    assert not any(ln.exercise for ln in review)
    core = asyncio.run(planner.section(outline, 1, ["复习整式乘法"], profile=p, mistakes=["整式乘法（符号错）"]))
    sp = llm.calls[2][-1]["content"]
    assert "重点" in sp and "初二" in sp and "漏了 2ab" in sp and "整式乘法（符号错）" in sp and '"exercise"' in sp
    posed = [ln for ln in core if ln.exercise is not None]
    assert posed and posed[0].text == "我们来做一道练习。" and core[-len(posed):] == posed  # after the summary
    assert posed[0].board.items[0] == CHOICE["question"] and posed[0].exercise.answer == "B"
    assert all(ln.item is None for ln in posed)  # the options are on the board while the question is read


def test_answers_are_graded_by_rule_when_unambiguous():
    ex = Exercise.from_dict(CHOICE, key="x1")
    assert quick_grade(ex, "选 B")["correct"] and not quick_grade(ex, "a")["correct"]
    assert quick_grade(ex, "$a^2+2ab+b^2$")["given"] == "B"  # the option's own text
    assert quick_grade(ex, "我不会")["skipped"]
    assert quick_grade(ex, "我觉得是 A 或者 B 吧，因为……") is None  # ambiguous: the LLM decides
    short = Exercise.from_dict({"concept": "方程", "question": "2x=6，x=?", "answer": "3"}, key="q1")
    assert short.kind == "short" and quick_grade(short, "x=3")["correct"]
    assert Exercise.from_dict({"question": "q", "options": ["A. 1", "B. 2"], "answer": "D"}, key="z") is None


def test_free_answers_and_side_questions_go_to_the_llm_grader():
    ex = Exercise.from_dict(CHOICE, key="x1")
    llm = ScriptedLLM(lambda m: json.dumps({"is_answer": True, "correct": False, "misconception": "漏了中间项",
                                            "feedback": ["思路不错，但漏了中间项。", "要加上两倍的 ab。"]},
                                           ensure_ascii=False))
    r = asyncio.run(grade(llm, ex, "应该是 a 方加 b 方吧"))
    assert r["is_answer"] and not r["correct"] and r["misconception"] == "漏了中间项"
    assert "正确答案是 B。" in r["feedback"]  # the right option is always said
    side = ScriptedLLM(lambda m: json.dumps({"is_answer": False, "correct": False}))
    assert not asyncio.run(grade(side, ex, "老师，这个公式是谁发现的？"))["is_answer"]


def _lesson_director():
    d, _, _ = tt._director(tt.ANSWER)
    planner = LessonPlanner(ScriptedLLM(planner_llm), name="林老师", bio="")
    outline = asyncio.run(planner.outline("完全平方公式"))
    d.lesson_title = outline.title
    d.add_lesson_lines(asyncio.run(planner.section(outline, 1, [])))
    d.add_lesson_lines(asyncio.run(planner.section(outline, 0, [])))  # the next section is already waiting
    return d


def test_a_posed_exercise_pauses_the_lesson_then_reminds_then_shows_the_answer():
    d = _lesson_director()
    said = [d.next_script(k).transcript for k in range(6)]  # two point lines, the summary, then the exercise
    assert said[3] == "我们来做一道练习。" and said[-1].startswith("选项在黑板上")
    assert d.exercise is not None and d.exercise.concept == "完全平方公式"
    waiting = [d.next_script(6 + k) for k in range(d.exercise_reminder_after)]
    assert all(not s.transcript for s in waiting[:-1])  # the next section waits for the answer
    assert waiting[-1].transcript.startswith("想好了吗") and waiting[-1].board["key"] == "x1"
    rest = [d.next_script(20 + k) for k in range(d.exercise_reveal_after - d.exercise_reminder_after + 3)]
    spoken = [s.transcript for s in rest if s.transcript]
    assert spoken[0] == "我们一起来看这道题。" and rest[-1].transcript.startswith("第1节")  # answer shown, lesson moves on
    assert d.exercise is None and any(s.board and s.board["key"] == "x1a" for s in rest)
    assert d.events.exercise_timeouts == ["完全平方公式"]


def test_the_answer_is_graded_the_profile_updated_and_the_lesson_continues(tmp_path):
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    lesson = _lesson_director()
    orch.director.lesson_backlog, orch.director.lesson_title = lesson.lesson_backlog, lesson.lesson_title
    d = orch.director
    for k in range(5):  # up to the question itself: the student answers before "选项在黑板上" is spoken
        d.next_script(k)
    assert d.exercise is not None
    before = orch.student.mastery("完全平方公式")
    asyncio.run(orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="选 B", t_end=now())))
    after = [d.next_script(5 + k).transcript for k in range(4)]
    assert after[0] == "答对了，很好！" and after[2].startswith("第1节")  # feedback, then the next section
    assert not any(t.startswith("选项在黑板上") for t in after)  # the rest of the question is dropped
    assert orch.student.mastery("完全平方公式") > before
    graded = [e.data for e in tp.events(orch, EventType.LESSON) if e.data["stage"] == "exercise_graded"]
    assert graded and graded[0]["correct"] and graded[0]["mastery"]["after"] > before
    assert StudentProfile.load("demo", tmp_path, SEEDS).concepts["完全平方公式"].attempts == 5  # saved


def test_a_side_question_during_an_exercise_is_answered_then_the_exercise_is_recalled(tmp_path):
    orch, _ = tp.build()
    d = orch.director

    def llm(messages):
        if messages[0]["role"] != "system":  # the grader: not an answer
            return json.dumps({"is_answer": False, "correct": False})
        return json.dumps({"relation": "chat", "kind": "content", "steps": [{"intent": "", "line": "是毕达哥拉斯。"}]},
                          ensure_ascii=False)
    d.llm.fn = llm
    d.exercise = Exercise.from_dict(CHOICE, key="x1")
    asyncio.run(orch.on_user_utterance(Utterance(uid="u2", speaker="user", text="这个公式谁发现的？", t_end=now())))
    said = [d.next_script(k).transcript for k in range(2)]
    assert said == ["是毕达哥拉斯。", "我们回到刚才这道练习，想好了告诉我。"] and d.exercise is not None


def test_asking_for_an_exercise_poses_one_at_the_profiles_level(tmp_path):
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    d = orch.director
    prompts = []

    def llm(messages):
        if messages[0]["role"] == "system":
            assert "学生档案" in messages[0]["content"] and "初二" in messages[0]["content"]
            return json.dumps({"relation": "chat", "kind": "exercise", "topic": "完全平方公式",
                               "steps": [{"intent": "", "line": "好，我给你出一道题。"}]}, ensure_ascii=False)
        prompts.append(messages[-1]["content"])
        return json.dumps({"exercise": CHOICE}, ensure_ascii=False)
    d.llm.fn = llm

    async def go():
        await orch.on_user_utterance(Utterance(uid="u3", speaker="user", text="考考我", t_end=now()))
        await asyncio.gather(*list(orch._aux))
    asyncio.run(go())
    assert "完全平方公式：薄弱" in prompts[0] and "基础题" in prompts[0]
    said = [d.next_script(k) for k in range(4)]
    assert said[0].transcript == "好，我给你出一道题。" and said[1].board["key"] == "q1"
    assert d.exercise is not None and d.exercise.source == "asked"


def test_a_question_line_cut_after_the_answer_is_not_said_again(tmp_path):
    # seen live: the soft switch cut "选项在黑板上…" after the answer was graded; it came back with "好，我们接着讲。"
    # and re-opened the closed exercise, pausing the lesson again
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    lesson = _lesson_director()
    orch.director.lesson_backlog, orch.director.lesson_title = lesson.lesson_backlog, lesson.lesson_title
    d = orch.director
    scripts = [d.next_script(k) for k in range(6)]  # the last one poses the exercise, not yet shown
    asyncio.run(orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="A", t_end=now())))
    d.on_interrupted([scripts[5]])  # the switch to the feedback drops it
    after = [d.next_script(6 + k).transcript for k in range(5)]
    assert after[0].startswith("不太对哦") and not any(t.startswith(("选项在黑板上", "好，我们接着讲")) for t in after)
    assert any(t.startswith("第1节") for t in after) and d.exercise is None


def test_the_section_after_an_exercise_is_written_after_the_answer_and_addresses_the_mistake(tmp_path):
    outline = {**OUTLINE, "sections": [{**OUTLINE["sections"][1], "title": "公式"},
                                       {"title": "应用", "goal": "用", "concepts": ["完全平方公式"], "depth": "new"}]}
    asked = []

    def llm(messages):
        text = messages[-1]["content"]
        if "课程大纲" in text:
            return json.dumps(outline, ensure_ascii=False)
        if "解释图" in text:  # the figure judge
            return json.dumps({"points": []})
        asked.append(text)
        return json.dumps(section(2 if "第 1/2 节" in text else 1), ensure_ascii=False)

    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    d = orch.director
    d.llm.fn = llm
    orch.cfg.lesson_lookahead = 100  # plenty of room: only the exercise holds the next section back

    async def go():
        task = asyncio.create_task(orch._lesson_loop("完全平方公式"))
        await asyncio.sleep(0.3)
        assert len(asked) == 1  # the section with the exercise; the next one waits for the answer
        for k in range(8):
            d.next_script(k)
        assert d.exercise is not None
        await orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="A", t_end=now()))
        await asyncio.wait_for(task, 5)
    asyncio.run(go())
    assert len(asked) == 2 and "学生刚才的练习做错了：完全平方公式" in asked[1]
