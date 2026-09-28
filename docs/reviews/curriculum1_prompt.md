# Codex review: student profile page and course knowledge base (commits b429013..5b8a67c, decisions D-039, D-040)

You are reviewing a change to a real-time digital-teacher demo (Python, asyncio, FastAPI). A video model renders the
teacher in ~5 s requests; a director pops one spoken line (<= 22 Chinese characters) per request; lessons are
planned by an LLM (outline, then one section at a time) and shown on a board beside the video. A saved student
profile (grade, exams, per-concept mastery) adapts lessons and is updated by graded exercises (D-038, reviewed
earlier as round adaptive1). This change adds:

1. **D-039, profile page** (`live_agent/server/static/profile.html`, `/profile`, `/api/students/...` in
   `live_agent/server/app.py`, `ProfileStore` in `live_agent/student.py`; diff inlined): teachers or students edit
   name, grade, exams, concept estimates (teacher-set until the next graded exercise), delete concepts, clear
   history, reset to the seed. One in-memory profile per allowed id shared by the editor and live sessions;
   versioned saves (409 on a stale version); open lesson pages refresh on edits.
2. **D-040, course knowledge base**: `configs/curriculum/*.json` (national curriculum per subject: per stage the
   standard's domains and paraphrased requirements, per grade textbook chapters, prerequisites, experiments) and
   `pedagogy.json` (per grade 1-12: learner traits, methods, content amount, tone, sentence length, vocabulary,
   examples, praise/correction, exercise style). `live_agent/curriculum.py` parses grades, finds where a topic is
   taught (string/bigram match, else an LLM picks chapters from a 16k-character index; picks must match a real
   chapter; cached), attaches the closest requirement (similarity floor), flags a topic above/below the student's
   grade, and renders the grade's teaching profile into planner/section/exercise/answer prompts. Data was
   researched from the MOE 2022 compulsory-education standards, the 2017/2020 senior-high standards and textbook
   tables of contents; sources and estimates are listed in each file. `tools/check_curriculum.py` validates files.

Inlined: `live_agent/curriculum.py`, `tests/test_curriculum.py`, `tools/check_curriculum.py`, the code diff of
the other files (`docs/reviews/curriculum1_diff.patch`), `configs/curriculum/pedagogy.json` and `math.json` in
full, and a generated summary of every subject file (`docs/reviews/curriculum1_data_summary.txt`: validator
output, then per grade the chapter count and first chapters, stages and domains, notes). The other subject files
are not inlined (about 330 KB); judge them from the summary.

Please find **correctness bugs and design risks**, most severe first. Focus on:
- `parse_grade` / `grade_name` edge cases on realistic inputs (e.g. "初中二年级", "高中一年级", "九年级", "十年级",
  "大一", "幼儿园", "二年级下", free text in a profile), and what a wrong grade does downstream;
- topic lookup and locator: false matches that would mislead the planner (wrong subject, wrong grade, a
  requirement that does not belong to the topic), the above/below-grade notes firing wrongly, cache keys, prompt
  injection through a topic string, LLM output handling, cost/latency on the lesson start path;
- how the grade profile reaches prompts (size, conflicts with the persona's fixed 22-character line limit and
  other prompt rules, "clean" stripping source tags) and whether the planner's role change by grade is sound;
- the profile page and API: access control (single shared token + id allow-list), input validation (types,
  sizes, mastery range, grade text), version/409 logic and races with live grading, reset/erasure interplay with
  D-038's `purge`/epoch, XSS in `profile.html` and in the lesson page's profile view;
- data quality and labelling in the curriculum files as far as the inlined material shows: grade/stage mapping
  (especially senior high, where 选择性必修 is not tied to a grade), claims presented as cited that look like
  estimates, requirements that are not paraphrases of a standard, missing grades;
- research-standard issues: numbers must be labelled cited / measured locally / estimate / proposed target.
For each finding give: file:line (or function), a concrete failure scenario, severity (high/medium/low), and a fix.
Do not restate what the code does; skip style nits. If something is fine, you need not mention it.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: live_agent/curriculum.py =====
"""Course knowledge base: the national curriculum (grades 1-12) and a teaching profile per grade.

Data lives in ``configs/curriculum/*.json`` (one file per subject, plus ``pedagogy.json``), researched from the 2022
compulsory-education standards and the 2017/2020 senior-high standards, with per-grade topics from the textbook
tables of contents; every file lists its sources and which parts are estimates. This module finds where a lesson
topic sits in the curriculum (subject, grade, the standard's requirements, prerequisites) and how a teacher should
teach a given grade (methods, amount of content, tone), and renders both as prompt context.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def parse_grade(text: str | int | None) -> int | None:
    """"初二" -> 8, "高一" -> 10, "小学三年级" / "三年级" -> 3, "8年级" / "grade 8" -> 8; None if unknown."""
    if isinstance(text, int):
        return text if 1 <= text <= 12 else None
    s = str(text or "").strip().lower()
    if not s:
        return None
    m = re.search(r"(初|高)([一二三123])", s)
    if m:
        n = _CN_NUM.get(m.group(2)) or int(m.group(2))
        return (6 if m.group(1) == "初" else 9) + n
    m = re.search(r"(\d{1,2})\s*年级|grade\s*(\d{1,2})|^(\d{1,2})$", s)
    if m:
        n = int(next(g for g in m.groups() if g))
        return n if 1 <= n <= 12 else None
    m = re.search(r"([一二三四五六七八九]|十[一二]?)年级", s)
    if m:
        w = m.group(1)
        n = 10 + (_CN_NUM.get(w[1], 0) if len(w) > 1 else 0) if w.startswith("十") else _CN_NUM[w]
        return n if 1 <= n <= 12 else None
    return None


def grade_name(g: int) -> str:
    if g <= 6:
        return f"小学{'一二三四五六'[g - 1]}年级"
    return ("初" if g <= 9 else "高") + "一二三"[(g - 7) % 3]


_CITE = re.compile(r"[（(]\s*s\d+(?:[、,，\s]*s?\d+)*(?:第\S{1,6}页)?\s*[）)]")


def clean(text: Any) -> str:
    """Prompt text without the data's source tags ("（s2、s7）"): those are for audit, not for the teacher to say."""
    return _CITE.sub("", str(text)).strip()


def _prefix(a: str, b: str) -> str:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n]


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def _norm(s: str) -> str:
    return re.sub(r"[\s·、，,（）()《》“”\"']", "", str(s)).lower()


@dataclass
class Match:
    subject: str
    grade: int | None
    topic: str  # the curriculum's own wording
    stage: str = ""
    domain: str = ""
    requirements: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    basis: str = ""  # textbook / standard / estimate
    score: float = 0.0
    grades: tuple | None = None  # a standard's stage range when no single grade is known
    sim: float = 0.0  # lexical similarity to the asked topic (1 = same wording)


class Curriculum:
    def __init__(self, subjects: list[dict], pedagogy: dict | None = None):
        self.subjects = subjects
        self.pedagogy = pedagogy or {}

    @classmethod
    def load(cls, directory: str | Path) -> Curriculum:
        d = Path(directory)
        subjects, pedagogy = [], {}
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                if f.stem == "pedagogy":
                    pedagogy = data
                elif isinstance(data, dict) and data.get("subject"):
                    subjects.append(data)
        return cls(subjects, pedagogy)

    def __bool__(self) -> bool:
        return bool(self.subjects or self.pedagogy)

    # ------------------------------------------------------------ where does a topic sit
    def lookup(self, topic: str, grade: int | None = None, limit: int = 3) -> list[Match]:
        """Curriculum entries for ``topic``: textbook topics by character-pair similarity (so "函数的单调性" finds
        the senior-high function unit rather than grade 8's "函数"), then the standard's requirements that name it;
        nearest to the student's grade first."""
        q = _norm(topic)
        if len(q) < 2:
            return []
        qb = _bigrams(q)
        latin = bool(re.fullmatch(r"[a-z0-9 .'-]+", q))
        qwords = [w for w in re.findall(r"[a-z]{3,}", str(topic).lower()) if len(w) >= 4] or [q]
        found: list[Match] = []
        for subj in self.subjects:
            name = subj.get("subject", "")
            prereq = {(_norm(k)): v for k, v in (subj.get("prerequisites") or {}).items()}
            covered: list[tuple[int, int]] = []
            for g, entry in (subj.get("grade_topics") or {}).items():
                g_int = parse_grade(int(g)) if str(g).isdigit() else parse_grade(g)
                for t in (entry or {}).get("topics") or []:
                    nt = _norm(t)
                    if latin:  # letter pairs are meaningless for English words: whole words only
                        words = set(re.findall(r"[a-z]{3,}", str(t).lower()))
                        sim = 1.0 if nt == q else 0.9 if q in nt else 0.6 if any(len(_prefix(w, x)) >= min(5, len(x))
                                                                                  for w in words for x in qwords) else 0.0
                    else:
                        sim = 1.0 if nt == q else len(qb & _bigrams(nt)) / max(len(qb), 1)
                    if q in nt and len(q) >= 2:
                        sim = max(sim, 0.9)
                    elif nt and nt in q:
                        sim = max(sim, 0.6)  # the unit named inside the question ("圆" in "圆的面积")
                    if sim < 0.5:
                        continue
                    stage, domain, reqs = self._requirements(subj, g_int, q, t)
                    found.append(Match(name, g_int, t, stage, domain, reqs, prereq.get(nt) or prereq.get(q) or [],
                                       (entry or {}).get("basis", ""), score=1.0 + sim, sim=sim))
                    covered.append((g_int or 0, g_int or 0))
            for st in subj.get("stages") or []:
                gs = st.get("grades") or []
                lo, hi = (gs[0], gs[-1]) if gs else (None, None)
                if lo is not None and any(lo <= a <= hi for a, _ in covered):
                    continue  # a textbook topic in this stage already says it (with its exact grade)
                for dom in st.get("domains") or []:
                    hits = [r for r in dom.get("requirements") or []
                            if q in _norm(r) or (not latin and len(qb & _bigrams(_norm(r))) / max(len(qb), 1) >= 0.75)]
                    if hits:
                        found.append(Match(name, None, topic, st.get("name", ""), dom.get("name", ""), hits[:3],
                                           prereq.get(q, []), "standard", score=1.6, grades=(lo, hi), sim=0.6))
        for m in found:
            g0 = m.grade if m.grade is not None else (m.grades[0] if m.grades else None)
            if grade is not None and g0 is not None:
                m.score -= 0.1 * abs(g0 - grade)
        found.sort(key=lambda m: -m.score)
        out, seen = [], set()
        for m in found:
            key = (m.subject, m.grade, m.topic, m.stage)
            if key not in seen:
                seen.add(key)
                out.append(m)
        return out[:limit]

    def _requirements(self, subj: dict, grade: int | None, q: str, also: str = "") -> tuple[str, str, list[str]]:
        """The stage containing ``grade`` and its requirements most similar to the topic ``q`` (and the chapter name
        ``also``); none below a similarity floor (a wrong requirement is worse than none)."""
        keys = [_bigrams(x) for x in (q, _norm(also)) if x]
        best: tuple[float, str, str, str] = (0.0, "", "", "")
        stage_name = ""
        for st in subj.get("stages") or []:
            gs = st.get("grades") or []
            if not (grade is None or (len(gs) == 2 and gs[0] <= grade <= gs[1]) or grade in gs):
                continue
            stage_name = stage_name or st.get("name", "")
            for dom in st.get("domains") or []:
                for r in dom.get("requirements") or []:
                    rb = _bigrams(_norm(r))
                    sim = max((len(k & rb) / max(len(k), 1) for k in keys), default=0.0)
                    nr = _norm(r)
                    if q and q in nr and re.search(re.escape(q) + r"(之?前|以前|为止)", nr) \
                            and nr.count(q) == 1:
                        sim = min(sim, 0.3)  # "至鸦片战争前": a period that ends where the topic starts
                    elif q and q in nr:
                        sim = max(sim, 0.95)
                    if sim > best[0]:
                        best = (sim, st.get("name", ""), dom.get("name", ""), r)
        if best[0] >= 0.5:
            return best[1], best[2], [best[3]]
        return stage_name, "", []

    # ------------------------------------------------------------ locating a topic with the model
    def index_text(self) -> str:
        """The whole curriculum as a compact chapter index (one line per subject and grade), for the locator."""
        if getattr(self, "_index", None) is None:
            lines = []
            for subj in self.subjects:
                for g, e in sorted((subj.get("grade_topics") or {}).items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                    topics = [re.sub(r"[（(][^）)]{0,12}[）)]$", "", str(t)).strip() for t in (e or {}).get("topics") or []]
                    lines.append(f"{subj.get('subject')}|{g}|" + "；".join(t for t in topics if t))
            self._index = "\n".join(lines)
        return self._index

    async def locate(self, llm, topic: str, grade: int | None = None) -> list[Match]:
        """Where ``topic`` is taught: exact wording by string match, else the model picks chapters from the index
        (textbooks name chapters, e.g. 运动和力的关系 for 牛顿第二定律). Answers must be copied from the index, so
        nothing is invented; results are cached per topic."""
        lexical = self.lookup(topic, grade)
        if any(m.sim >= 0.9 for m in lexical) or llm is None or not self.subjects:
            return lexical
        cache = self.__dict__.setdefault("_located", {})
        key = _norm(topic)
        if key not in cache:
            from live_agent.llm import parse_json

            raw = await llm.chat([{"role": "user", "content": LOCATE_PROMPT.format(
                topic=topic, index=self.index_text())}], max_tokens=300, temperature=0.0, json_mode=True)
            try:
                picks = parse_json(raw).get("matches") or []
            except ValueError:
                picks = []
            cache[key] = [p for p in picks if isinstance(p, dict)][:3]
        out = []
        for p in cache[key]:
            m = self._entry(str(p.get("subject") or ""), p.get("grade"), str(p.get("topic") or ""), topic)
            if m is not None:
                out.append(m)
        if grade is not None:
            out.sort(key=lambda m: abs((m.grade or grade) - grade))
        return out or lexical

    def _entry(self, subject: str, grade, chapter: str, topic: str) -> Match | None:
        """The index entry the locator named (verified: an invented chapter is dropped)."""
        g = parse_grade(int(grade)) if str(grade).isdigit() else parse_grade(grade)
        for subj in self.subjects:
            if subj.get("subject") != subject:
                continue
            e = (subj.get("grade_topics") or {}).get(str(g)) or {}
            nc = _norm(chapter)
            for t in e.get("topics") or []:
                nt = _norm(t)
                close = nc and (nt.startswith(nc) or nc in nt or (len(nc) >= 6 and nt in nc)
                                or len(_bigrams(nc) & _bigrams(nt)) / max(len(_bigrams(nc)), 1) >= 0.8)
                if close:  # the model copied (a close form of) a real chapter; anything else is dropped
                    stage, domain, reqs = self._requirements(subj, g, _norm(topic), t)
                    prereq = {(_norm(k)): v for k, v in (subj.get("prerequisites") or {}).items()}
                    return Match(subject, g, t, stage, domain, reqs, prereq.get(_norm(t)) or [], e.get("basis", ""),
                                 score=2.0, sim=0.95)
        return None

    async def topic_context_async(self, llm, topic: str, grade: int | None) -> str:
        return self._render(topic, await self.locate(llm, topic, grade), grade)

    # ------------------------------------------------------------ how to teach a grade
    def profile(self, grade: int | None) -> dict[str, Any]:
        grades = self.pedagogy.get("grades") or {}
        if grade is None or not grades:
            return {}
        return grades.get(str(grade)) or grades.get(str(min(max(grade, 1), 12))) or {}

    def teaching_context(self, grade: int | None) -> str:
        """Per-grade teaching guidance for prompts (methods, content per explanation, tone, sentence length)."""
        p = self.profile(grade)
        if not p:
            return ""
        parts = [f"学生是{grade_name(grade)}（{p.get('stage', '')}）。按这个年级的特点来教："]
        for key, label in (("methods", "教法"), ("content", "内容量"), ("tone", "语气"), ("examples", "例子"),
                           ("avoid", "避免")):
            v = p.get(key)
            if v:
                parts.append(f"{label}：{'；'.join(clean(x) for x in v) if isinstance(v, list) else clean(v)}")
        if p.get("vocabulary"):
            parts.append(f"用词：{clean(p['vocabulary'])}")
        if p.get("encouragement"):
            parts.append(f"表扬与纠错：{clean(p['encouragement'])}")
        return "\n".join(parts)

    def exercise_style(self, grade: int | None) -> str:
        return clean(self.profile(grade).get("exercise_style") or "")

    def topic_context(self, topic: str, grade: int | None) -> str:
        """Where the topic may sit in the curriculum, for the planner (candidates from lexical matching: the model
        uses the relevant ones); flags a topic above the student's grade only on a strong match."""
        return self._render(topic, self.lookup(topic, grade, limit=4), grade)

    def _render(self, topic: str, ms: list[Match], grade: int | None) -> str:
        if not ms:
            return ""
        lines = []
        for m in ms:
            s = f"「{m.topic}」：{m.subject}"
            if m.grade:
                s += f"，{grade_name(m.grade)}" + ("（教材）" if m.basis == "textbook" else "（估计）" if m.basis == "estimate" else "")
            elif m.grades and m.grades[0]:
                s += f"，课标{grade_name(m.grades[0])}" + (f"至{grade_name(m.grades[1])}" if m.grades[1] != m.grades[0] else "")
            if m.stage or m.domain:
                s += f"，{m.stage}{('·' + m.domain) if m.domain else ''}"
            if m.requirements:
                s += f"；课标要求：{'；'.join(clean(r) for r in m.requirements)}"
            if m.prerequisites:
                s += f"；前置知识：{'、'.join(m.prerequisites)}"
            lines.append(s)
        top = next((m for m in ms if m.grade is not None and m.sim >= 0.9), None)
        if top is None:
            pass
        elif grade is not None and top.grade is not None and top.grade > grade:
            lines.append(f"注意：这个内容一般在{grade_name(top.grade)}学，学生现在{grade_name(grade)}，"
                         f"要从学生已有的知识讲起，降低难度，必要时先补前置知识。")
        elif grade is not None and top.grade is not None and top.grade < grade - 2:
            lines.append(f"注意：这是{grade_name(top.grade)}的内容，学生已经{grade_name(grade)}，以复习和提高为主。")
        return "课程标准参考（系统检索到的相关条目，只采用和本课真正相关的）：\n" + "\n".join(lines)

    def summary(self) -> dict[str, Any]:
        return {"subjects": [{"subject": s.get("subject"), "grades": s.get("grades"),
                              "sources": len(s.get("sources") or []),
                              "topics": sum(len((e or {}).get("topics") or []) for e in (s.get("grade_topics") or {}).values())}
                             for s in self.subjects],
                "pedagogy_grades": sorted(int(g) for g in (self.pedagogy.get("grades") or {}) if str(g).isdigit())}


LOCATE_PROMPT = """下面是中国中小学课程目录（每行：学科|年级|这个年级的教材章节，章节之间用；分隔）。
请找出讲「{topic}」这个内容的章节，最多 3 个，最主要的放第一个；同一内容在不同学段都讲的（如初中和高中），各列一个。
topic 必须从目录里原样复制章节名，不要自己编；目录里没有相关章节就返回空列表。
只输出 JSON：{{"matches": [{{"subject": 学科（原样）, "grade": 年级数字, "topic": 章节名（原样）}}]}}
目录：
{index}"""


__all__ = ["Curriculum", "LOCATE_PROMPT", "Match", "grade_name", "parse_grade"]

===== FILE: tests/test_curriculum.py =====
"""Course knowledge base: grade parsing, topic lookup in the curriculum, per-grade teaching profiles in prompts."""

from __future__ import annotations

import asyncio
import json

from live_agent.curriculum import Curriculum, grade_name, parse_grade
from live_agent.lesson import LessonPlanner
from live_agent.llm import ScriptedLLM
from live_agent.student import StudentProfile

MATH = {"subject": "数学", "grades": [1, 12], "sources": [{"id": "s1", "title": "义务教育数学课程标准（2022年版）", "url": "u"}],
        "stages": [{"name": "第四学段", "grades": [7, 9], "domains": [
            {"name": "图形与几何", "requirements": ["探索勾股定理及其逆定理，并能运用它们解决简单问题"], "source": "s1"}]},
                   {"name": "第一学段", "grades": [1, 2], "domains": [
                       {"name": "数与代数", "requirements": ["能熟练口算20以内的加减法"], "source": "s1"}]}],
        "grade_topics": {"8": {"topics": ["勾股定理", "二次根式"], "basis": "textbook"},
                         "1": {"topics": ["20以内的进位加法"], "basis": "textbook"}},
        "prerequisites": {"勾股定理": ["平方与平方根", "三角形"]}}
PED = {"grades": {"1": {"stage": "小学低年级", "methods": ["游戏化", "儿歌"], "tone": ["亲切活泼", "称呼小朋友"],
                        "exercise_style": "看图选择"},
                  "8": {"stage": "初中", "methods": ["探究式"], "tone": ["平等对话"], "exercise_style": "选择题或一步计算"}}}


def kb(tmp_path):
    (tmp_path / "math.json").write_text(json.dumps(MATH, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "pedagogy.json").write_text(json.dumps(PED, ensure_ascii=False), encoding="utf-8")
    return Curriculum.load(tmp_path)


def test_grades_are_parsed_from_how_people_say_them():
    assert [parse_grade(x) for x in ["初二", "高一", "小学三年级", "三年级", "8年级", "grade 11", "十二年级", "", "大一"]] == \
        [8, 10, 3, 3, 8, 11, 12, None, None]
    assert grade_name(8) == "初二" and grade_name(3) == "小学三年级" and grade_name(12) == "高三"


def test_a_topic_is_found_with_its_grade_requirements_and_prerequisites(tmp_path):
    c = kb(tmp_path)
    m = c.lookup("勾股定理", grade=8)[0]
    assert (m.subject, m.grade, m.stage, m.domain) == ("数学", 8, "第四学段", "图形与几何")
    assert "勾股定理" in m.requirements[0] and m.prerequisites == ["平方与平方根", "三角形"]
    assert c.lookup("量子力学") == []


def test_a_topic_above_the_students_grade_is_flagged(tmp_path):
    c = kb(tmp_path)
    ctx = c.topic_context("勾股定理", 5)
    assert "一般在初二学" in ctx and "降低难度" in ctx
    assert "以复习和提高为主" in c.topic_context("20以内的进位加法", 8)


def test_the_teaching_profile_follows_the_grade(tmp_path):
    c = kb(tmp_path)
    assert "游戏化" in c.teaching_context(1) and "小朋友" in c.teaching_context(1)
    assert "探究式" in c.teaching_context(8) and c.teaching_context(None) == ""


def test_the_planner_gets_the_curriculum_and_a_grade_role(tmp_path):
    c = kb(tmp_path)
    out = {"title": "勾股定理", "sections": [{"title": "定理", "role": "main"}], "intro": ["今天学勾股定理。"]}
    llm = ScriptedLLM(lambda m: json.dumps(out, ensure_ascii=False))
    p = StudentProfile(student_id="x", grade="小学五年级")
    asyncio.run(LessonPlanner(llm, name="林老师", bio="", curriculum=c).outline("勾股定理", profile=p))
    prompt = llm.calls[0][-1]["content"]
    assert prompt.startswith("你是小学老师") and "课程标准参考" in prompt and "一般在初二学" in prompt


def test_the_locator_maps_a_topic_to_a_chapter_and_drops_invented_ones(tmp_path):
    c = kb(tmp_path)
    replies = iter([json.dumps({"matches": [{"subject": "数学", "grade": 8, "topic": "二次根式"},
                                            {"subject": "数学", "grade": 8, "topic": "不存在的章节"}]}, ensure_ascii=False)])
    llm = ScriptedLLM(lambda m: next(replies))
    ms = asyncio.run(c.locate(llm, "根号的化简", 8))
    assert [m.topic for m in ms] == ["二次根式"]  # the invented chapter is dropped
    assert "数学|8|勾股定理；二次根式" in llm.calls[0][-1]["content"]
    assert [m.topic for m in asyncio.run(c.locate(llm, "根号的化简", 8))] == ["二次根式"]  # cached: no second call
    assert len(llm.calls) == 1
    assert asyncio.run(c.locate(llm, "勾股定理", 8))[0].topic == "勾股定理" and len(llm.calls) == 1  # exact: no model

===== FILE: tools/check_curriculum.py =====
"""Validate curriculum knowledge-base files (configs/curriculum/*.json) and report coverage.

    python3 tools/check_curriculum.py [dir]

Checks: required fields, every "source" reference points to a listed source with a URL, grade ranges are within
1-12, per-grade topics cover the subject's grade span; reports how many topics rest on a textbook, the standard,
or an estimate. Exit code 1 on a structural error (missing fields, dangling source ids, bad grades).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def check_subject(d: dict, name: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for key in ("subject", "grades", "sources", "stages", "grade_topics"):
        if key not in d:
            errors.append(f"{name}: missing '{key}'")
    ids = {s.get("id") for s in d.get("sources") or []}
    for s in d.get("sources") or []:
        if not str(s.get("url") or "").startswith("http"):
            warnings.append(f"{name}: source {s.get('id')} has no URL")
    lo, hi = (d.get("grades") or [1, 12])[:2]
    if not (1 <= lo <= hi <= 12):
        errors.append(f"{name}: grades {d.get('grades')} out of 1-12")
    for st in d.get("stages") or []:
        gs = st.get("grades") or []
        if not gs or any(not isinstance(g, int) or not 1 <= g <= 12 for g in gs):
            errors.append(f"{name}: stage {st.get('name')} has grades {gs}")
        for dom in st.get("domains") or []:
            if dom.get("source") and any(x.strip() not in ids for x in str(dom["source"]).split(",")):
                errors.append(f"{name}: stage {st.get('name')} / {dom.get('name')} cites unknown source {dom['source']}")
    gt = d.get("grade_topics") or {}
    missing = [g for g in range(lo, hi + 1) if str(g) not in gt]
    if missing:
        warnings.append(f"{name}: no topics for grades {missing}")
    for g, e in gt.items():
        if not str(g).isdigit() or not 1 <= int(g) <= 12:
            errors.append(f"{name}: grade_topics key {g!r}")
        if (e or {}).get("source") and any(x.strip() not in ids for x in str(e["source"]).split(",")):
            errors.append(f"{name}: grade {g} cites unknown source {e['source']}")
        if not (e or {}).get("topics"):
            warnings.append(f"{name}: grade {g} has no topics")
    return errors, warnings


def main(directory: str = "configs/curriculum") -> int:
    d = Path(directory)
    errors, warnings = [], []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            errors.append(f"{f.name}: invalid JSON ({e})")
            continue
        if f.stem == "pedagogy":
            ids = {s.get("id") for s in data.get("sources") or []}
            grades = data.get("grades") or {}
            miss = [g for g in range(1, 13) if str(g) not in grades]
            if miss:
                warnings.append(f"pedagogy: no profile for grades {miss}")
            for g, p in grades.items():
                for key in ("methods", "tone", "content"):
                    if not p.get(key):
                        warnings.append(f"pedagogy: grade {g} has no '{key}'")
                for s in p.get("sources") or []:
                    if s not in ids:
                        errors.append(f"pedagogy: grade {g} cites unknown source {s}")
            print(f"pedagogy: grades {sorted(int(g) for g in grades if str(g).isdigit())}, sources {len(ids)}")
            continue
        e, w = check_subject(data, f.name)
        errors += e
        warnings += w
        basis = Counter((v or {}).get("basis", "?") for v in (data.get("grade_topics") or {}).values())
        n_topics = sum(len((v or {}).get("topics") or []) for v in (data.get("grade_topics") or {}).values())
        print(f"{f.name}: {data.get('subject')} grades {data.get('grades')}, stages {len(data.get('stages') or [])}, "
              f"topics {n_topics}, grade basis {dict(basis)}, sources {len(data.get('sources') or [])}")
    for w in warnings:
        print("WARN", w)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))

===== FILE: docs/reviews/curriculum1_diff.patch =====
diff --git a/live_agent/lesson.py b/live_agent/lesson.py
index 9daaf5c..7d6fe70 100644
--- a/live_agent/lesson.py
+++ b/live_agent/lesson.py
@@ -26,10 +26,10 @@ DEPTHS = {
     "new": ("10-18", "这一节是新内容，正常讲解。"),
 }
 
-OUTLINE_PROMPT = """你是中学老师「{name}」，要给学生上一节关于「{topic}」的课。人设：{bio}
+OUTLINE_PROMPT = """你是{role}「{name}」，要给学生上一节关于「{topic}」的课。人设：{bio}
 学生档案（年级、考试成绩、各概念的掌握情况）：
 {profile}
-请按这个学生的情况因材施教，设计课程大纲，只输出 JSON：
+{curriculum}请按这个学生的情况因材施教，设计课程大纲，只输出 JSON：
 {{"title": 课程标题（不超过 16 字）, "plan_note": 一句话说明你根据档案怎么安排的（给老师自己看，不念出来）,
  "sections": [{{"title": 小节标题（不超过 14 字）, "goal": 这一节要讲清楚什么（一句话）,
    "concepts": [这一节讲的概念，档案里已有的概念用完全相同的名字，每个不超过 8 字],
@@ -46,7 +46,7 @@ OUTLINE_PROMPT = """你是中学老师「{name}」，要给学生上一节关于
 开场白先说今天学什么，再说分几部分讲，知道学生情况时可以自然地提一句（如「上次考试这里丢了分，今天重点讲」）；每句开场白不超过 {chars} 个汉字。
 学生之前的对话（只作参考）：{context}"""
 
-SECTION_PROMPT = """你是中学老师「{name}」，正在上「{title}」这节课。人设：{bio}
+SECTION_PROMPT = """你是{role}「{name}」，正在上「{title}」这节课。人设：{bio}
 现在讲第 {i}/{n} 节「{section}」，目标：{goal}。
 前面已经讲过：{covered}
 请写这一节的板书和讲稿，只输出 JSON：
@@ -255,14 +255,39 @@ def spoken(text: str, chars: int) -> list[str]:
 
 
 class LessonPlanner:
-    def __init__(self, llm: ChatLLM, *, name: str, bio: str, chars: int = 22):
+    def __init__(self, llm: ChatLLM, *, name: str, bio: str, chars: int = 22, curriculum=None):
         self.llm, self.name, self.bio, self.chars = llm, name, bio, chars
+        self.curriculum = curriculum  # curriculum.Curriculum: where the topic sits, how to teach the grade
+
+    def _grade(self, profile) -> int | None:
+        from live_agent.curriculum import parse_grade
+
+        return parse_grade(profile.grade) if profile is not None else None
+
+    def _role(self, profile) -> str:
+        g = self._grade(profile)
+        return "小学老师" if g is not None and g <= 6 else "高中老师" if g is not None and g >= 10 else "中学老师"
+
+    async def _curriculum_block(self, topic: str, profile) -> str:
+        if not self.curriculum:
+            return ""
+        g = self._grade(profile)
+        try:
+            where = await self.curriculum.topic_context_async(self.llm, topic, g)
+        except Exception:  # noqa: BLE001 - the locator failed: plan without the curriculum reference
+            where = self.curriculum.topic_context(topic, g)
+        parts = [where, self.curriculum.teaching_context(g)]
+        text = "\n".join(x for x in parts if x)
+        return (text + "\n") if text else ""
 
     async def outline(self, topic: str, context: str = "", profile=None) -> Outline:
         """``profile``: a student.StudentProfile (None: no saved profile, an average student of ``default_grade``)."""
+        curriculum = await self._curriculum_block(topic, profile)
+        self.last_curriculum = curriculum  # for the log
         raw = await self.llm.chat([{"role": "user", "content": OUTLINE_PROMPT.format(
-            name=self.name, topic=topic, bio=self.bio, chars=self.chars, context=context or "无",
+            name=self.name, topic=topic, bio=self.bio, chars=self.chars, context=context or "无", role=self._role(profile),
             profile=profile.summary() if profile is not None else "无（新学生，没有档案）",
+            curriculum=curriculum,
             default_grade=(profile.grade if profile is not None and profile.grade else "初中"))}],
             max_tokens=900, temperature=0.4, json_mode=True)
         d = parse_json(raw)
@@ -299,18 +324,25 @@ class LessonPlanner:
         last = i == len(outline.sections) - 1
         depth = sec.get("depth") if sec.get("depth") in DEPTHS else "new"
         adapt = [DEPTHS[depth][1]]
+        want_ex = bool(sec.get("exercise"))
         if profile is not None:
             if profile.grade:
                 adapt.append(f"学生是{profile.grade}，用这个年级听得懂的说法和例子。")
             adapt.append(f"学生对本节概念的掌握：{profile.concept_notes(sec.get('concepts') or [])}。")
             adapt.append(f"只讲本节和「{outline.title}」的内容；学生其他薄弱的知识点不要展开，需要用到时一句话带过。")
+        if self.curriculum and profile is not None:
+            teach = self.curriculum.teaching_context(self._grade(profile))
+            if teach:
+                adapt.append("\n" + teach + "\n")
+            ex_style = self.curriculum.exercise_style(self._grade(profile))
+            if want_ex and ex_style:
+                adapt.append(f"练习题的形式：{ex_style}。")
         if mistakes:
             adapt.append(f"学生刚才的练习做错了：{'；'.join(mistakes[-2:])}。本节第一条要点先用一两句换个说法把这个错误纠正过来。")
-        want_ex = bool(sec.get("exercise"))
         ex_req = ("\n6. 讲完出一道练习，考查本节最重要的概念，难度按学生的掌握度定（薄弱出基础题，已掌握出稍有变化的题）；"
                   "在 JSON 里加字段 \"exercise\"。" + EXERCISE_SPEC.format(chars=self.chars, q_chars=60)) if want_ex else ""
         raw = await self.llm.chat([{"role": "user", "content": SECTION_PROMPT.format(
-            name=self.name, bio=self.bio, title=outline.title, i=i + 1, n=len(outline.sections),
+            name=self.name, bio=self.bio, title=outline.title, i=i + 1, n=len(outline.sections), role=self._role(profile),
             section=sec["title"], goal=sec.get("goal", ""), covered="；".join(covered) or "（这是第一节）",
             max_items=MAX_ITEMS, item_chars=ITEM_CHARS, chars=self.chars, n_lines=DEPTHS[depth][0],
             adapt="".join(adapt), exercise_req=ex_req,
diff --git a/live_agent/orchestrator.py b/live_agent/orchestrator.py
index 703fa7f..b1cdece 100644
--- a/live_agent/orchestrator.py
+++ b/live_agent/orchestrator.py
@@ -172,6 +172,8 @@ class Orchestrator:
         self.image_maker = None  # board_images.ImageMaker (illustrations), set by the app when configured
         self.figure_dir = None  # where exact plots are drawn (board_plot); set by the app
         self.student = None  # student.StudentProfile (private sessions): adapts lessons, records exercise results
+        self.profile_store = None  # student.ProfileStore shared with the profile page (set by the app)
+        self.curriculum = None  # curriculum.Curriculum: course knowledge base (grade profiles, standards; set by the app)
         self._lesson_mistakes: list[str] = []  # this lesson's wrong answers, addressed by the next section
         self._exercises = 0
         self._shown_exercise = None  # the exercise the page was last told about
@@ -1058,7 +1060,7 @@ class Orchestrator:
         if self.student is not None:
             change = self.student.record_exercise(ex.concept, r["correct"], question=ex.question, answer=utt.text,
                                                   misconception=r.get("misconception") or "", subject=ex.subject)
-            self.student.save()
+            self._save_profile()
         if not r["correct"] and (ex.source == "lesson" or d.lesson_title):
             self._lesson_mistakes.append(ex.concept + (f"（{r['misconception']}）" if r.get("misconception") else ""))
         self.log.emit(EventType.LESSON, now(), stage="exercise_graded", concept=ex.concept, correct=r["correct"],
@@ -1074,7 +1076,14 @@ class Orchestrator:
         d = self.director
         self._exercises += 1
         profile_epoch, plan = self._profile_epoch, d.plan_version
-        profile = self.student.summary() if self.student is not None else "无（新学生，没有档案）"
+        profile = self._student_context() or "无（新学生，没有档案）"
+        if self.curriculum and self.student is not None:
+            from live_agent.curriculum import parse_grade
+
+            g = parse_grade(self.student.grade)
+            profile += "\n" + self.curriculum.topic_context(topic, g)
+            if self.curriculum.exercise_style(g):
+                profile += f"\n这个年级的练习形式：{self.curriculum.exercise_style(g)}"
         try:
             ex = await make_exercise(d.llm, name=d.persona_name, topic=topic, profile=profile,
                                      key=f"q{self._exercises}")
@@ -1119,7 +1128,7 @@ class Orchestrator:
                                                            if s.board is None or s.board.key not in (ex.key, ex.key + "a"))
         if self.student is not None:
             n += sum(self.student.purge(x) for x in terms)
-            self.student.save()
+            self._save_profile()
             self._emit_profile()  # the page drops what it showed
         self._lesson_mistakes = [m for m in self._lesson_mistakes if not any(x in m for x in terms)]
         return n
@@ -1142,6 +1151,30 @@ class Orchestrator:
         self.log.emit(EventType.LESSON, now(), stage="answer_board", title=b.title, board=b.key,
                       seconds=round(now() - t0, 2), lines=len(waiting))
 
+    def _student_context(self) -> str:
+        """What the responder knows about the student: the profile, and how to talk to a student of this grade."""
+        if self.student is None:
+            return ""
+        ctx = self.student.summary()
+        if self.curriculum:
+            from live_agent.curriculum import parse_grade
+
+            teach = self.curriculum.teaching_context(parse_grade(self.student.grade))
+            if teach:
+                ctx += "\n" + teach
+        return ctx
+
+    def _save_profile(self) -> None:
+        """Save through the shared store (other sessions and the profile page see the change), else directly."""
+        if self.profile_store is not None:
+            self.profile_store.changed(self.student.student_id, source=self.on_profile_edited)
+        else:
+            self.student.save()
+
+    def on_profile_edited(self) -> None:
+        """Someone else (the profile page, another session) changed this student's profile: refresh the page."""
+        self._emit_profile()
+
     def _emit_profile(self) -> None:
         """The page gets the profile view directly; the durable log records only that it changed."""
         if self.student is None:
@@ -1164,7 +1197,7 @@ class Orchestrator:
         from live_agent.lesson import LessonLine, LessonPlanner
 
         d = self.director
-        planner = LessonPlanner(d.llm, name=d.persona_name, bio=d.persona_bio)
+        planner = LessonPlanner(d.llm, name=d.persona_name, bio=d.persona_bio, curriculum=self.curriculum)
         context = "；".join(t for r, t in d.dialogue if r == "user")[-300:]
         try:
             outline = await planner.outline(topic, context, profile=self.student)
@@ -1203,7 +1236,7 @@ class Orchestrator:
                 d.add_lesson_lines(lines)
                 if self.student is not None and outline.sections[i].get("concepts"):
                     self.student.mark_taught(outline.sections[i]["concepts"])
-                    self.student.save()
+                    self._save_profile()
                 self._make_figures()
                 self._spawn(self._judge_figures(planner, lines), "figure_judgement")
                 ex = next((ln.exercise for ln in lines if getattr(ln, "exercise", None) is not None), None)
@@ -1285,7 +1318,7 @@ class Orchestrator:
                               chains={c.chain_id: c.status.value for c in self.director.chains.values()},
                               recalled=[])
                 return graded
-        self.director.student_context = self.student.summary() if self.student is not None else ""
+        self.director.student_context = self._student_context()
         decision = await self.director.decide(utt, memories)
         term = (decision or {}).get("forget_term")
         if epoch != self._input_epoch:
@@ -1319,7 +1352,7 @@ class Orchestrator:
             if self.student is not None and (decision or {}).get("profile_update"):
                 changed = self.student.apply_update(decision["profile_update"])
                 if changed:
-                    self.student.save()
+                    self._save_profile()
                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
                     self._emit_profile()
         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
diff --git a/live_agent/server/app.py b/live_agent/server/app.py
index c981105..331bee6 100644
--- a/live_agent/server/app.py
+++ b/live_agent/server/app.py
@@ -38,7 +38,7 @@ import re
 from pathlib import Path
 
 import numpy as np
-from fastapi import FastAPI, WebSocket, WebSocketDisconnect
+from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
 from fastapi.responses import HTMLResponse
 
 from live_agent.capability import CapabilityManifest, Status
@@ -54,6 +54,7 @@ STATIC = Path(__file__).parent / "static"
 
 
 BOARD_IMAGES = Path(__file__).resolve().parents[2] / ".cache" / "board_images"
+CURRICULUM = Path(__file__).resolve().parents[2] / "configs" / "curriculum"  # national standards + grade profiles
 STUDENT_SEEDS = Path(__file__).resolve().parents[2] / "configs" / "students"  # example profiles (fictional)
 
 
@@ -267,6 +268,21 @@ def build_app(args: argparse.Namespace) -> FastAPI:
 
     app.state.shared_gen = None
     app.state.session_lock = asyncio.Lock()
+    from live_agent.student import ProfileStore
+
+    # one shared copy per student for sessions and the profile page; only ids on the allow-list are reachable
+    profiles = ProfileStore(Path(args.student_store), STUDENT_SEEDS,
+                            [x for x in (args.students or args.student).split(",")
+                             if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", x)])
+    app.state.profiles = profiles
+    from live_agent.curriculum import Curriculum
+
+    curriculum = Curriculum.load(CURRICULUM)  # course knowledge base (empty if not present)
+    app.state.curriculum = curriculum
+
+    @app.get("/api/curriculum")
+    async def curriculum_summary() -> dict:
+        return curriculum.summary()
 
     @app.on_event("startup")
     async def _startup() -> None:
@@ -347,6 +363,52 @@ def build_app(args: argparse.Namespace) -> FastAPI:
     async def index() -> HTMLResponse:
         return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))
 
+    # ---------------------------------------------------------------- student profiles (personal data)
+    @app.get("/profile")
+    async def profile_page() -> HTMLResponse:
+        return HTMLResponse((STATIC / "profile.html").read_text(encoding="utf-8"))
+
+    def _profile_or_404(student_id: str):
+        p = profiles.get(student_id)
+        if p is None:
+            raise HTTPException(404, "unknown student")
+        return p
+
+    def _full(p) -> dict:
+        return {**p.view(), "saved": profiles.exists(p.student_id)}
+
+    @app.get("/api/students")
+    async def list_students() -> dict:
+        out = []
+        for sid in profiles.allowed:
+            p = profiles.get(sid)
+            out.append({"id": sid, "name": p.name, "grade": p.grade, "saved": profiles.exists(sid)})
+        return {"students": out}
+
+    @app.get("/api/students/{student_id}")
+    async def get_student(student_id: str) -> dict:
+        return _full(_profile_or_404(student_id))
+
+    @app.put("/api/students/{student_id}")
+    async def put_student(student_id: str, body: dict = Body(...)) -> dict:
+        """Edit name / grade / exams / concept estimates. ``version`` must be the one the editor loaded: a lesson
+        may have graded an exercise meanwhile, and that result must not be overwritten silently."""
+        p = _profile_or_404(student_id)
+        if body.get("version") != p.version:
+            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
+        p.update_basics({k: body[k] for k in ("name", "grade", "exams") if k in body})
+        p.edit_concepts(body.get("concepts"))
+        if body.get("clear_history"):
+            p.history = []
+        profiles.changed(student_id)
+        return _full(p)
+
+    @app.post("/api/students/{student_id}/reset")
+    async def reset_student(student_id: str) -> dict:
+        """Delete the saved profile: back to the example seed (or empty)."""
+        _profile_or_404(student_id)
+        return _full(profiles.reset(student_id))
+
     @app.websocket("/ws")
     async def ws_endpoint(ws: WebSocket) -> None:
         await ws.accept()
@@ -426,18 +488,20 @@ def build_app(args: argparse.Namespace) -> FastAPI:
 
                 orch.image_maker = ImageMaker(args.image_url, BOARD_IMAGES)
             orch.figure_dir = BOARD_IMAGES  # exact plots need no model
-            orch.answer_boards = bool(canon.get("board"))  # a persona with a board writes one for every knowledge answer
+            orch.answer_boards = bool(canon.get("board"))
+            orch.curriculum = curriculum  # a persona with a board writes one for every knowledge answer
             # the page may pick a profile only from the server's allow-list: the demo has one shared access token and no
             # per-student accounts, so the operator decides which profiles this deployment exposes
             allowed = [x for x in (args.students or args.student).split(",") if x]
             student_id = str(hello.get("student") or args.student)
             if student_id not in allowed:
                 student_id = args.student
-            if mode == "private" and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", student_id) and student_id in allowed:
-                # personal data: only a private session reads or updates the saved profile
-                from live_agent.student import StudentProfile
-
-                orch.student = StudentProfile.load(student_id, Path(args.student_store), STUDENT_SEEDS)
+            if mode == "private" and student_id in allowed:
+                # personal data: only a private session reads or updates the saved profile (the shared copy)
+                orch.student = profiles.get(student_id)
+                orch.profile_store = profiles
+                if orch.student is not None:
+                    profiles.subscribe(student_id, orch.on_profile_edited)
             if getattr(judge, "vlm", None) is not None:  # the camera focus check uses the judge's VLM (opt-in)
                 from live_agent.attention import AttentionMonitor
 
@@ -555,7 +619,7 @@ def build_app(args: argparse.Namespace) -> FastAPI:
                     orch.camera_off()
                 elif t == "profile" and orch.student is not None and isinstance(data.get("profile"), dict):
                     orch.student.update_basics(data["profile"])  # name, grade, exams (mastery comes from exercises)
-                    orch.student.save()
+                    orch._save_profile()
                     orch._emit_profile()
                 elif t == "video_codec" and data.get("codec") == "jpeg":
                     transport.video_codec = "jpeg"  # the page failed to decode H.264
@@ -568,6 +632,8 @@ def build_app(args: argparse.Namespace) -> FastAPI:
                 if worker is not None:
                     worker.cancel()
                 if orch is not None:
+                    if orch.student is not None:
+                        profiles.unsubscribe(orch.student.student_id, orch.on_profile_edited)
                     await orch.stop()
                 if transport.recorder is not None:
                     await asyncio.to_thread(transport.recorder.close)  # mux video + audio
diff --git a/live_agent/server/static/index.html b/live_agent/server/static/index.html
index 5a40c2d..3f86aa3 100644
--- a/live_agent/server/static/index.html
+++ b/live_agent/server/static/index.html
@@ -140,6 +140,7 @@
         <label>会话 <select id="mode"><option value="private">一对一私聊</option><option value="public">测试直播</option></select></label>
         <label>用户 <input type="text" id="uid" value="user-1" style="flex:0;width:110px;min-width:90px"></label>
         <label title="私聊会话读取并更新这个学生的档案">学生 <input type="text" id="sid" value="demo" style="flex:0;width:80px;min-width:70px"></label>
+        <a href="/profile" target="_blank" id="profLink" style="align-self:center">档案管理</a>
         <button class="primary" id="connect">连接</button>
         <button id="disconnect" disabled>断开</button>
       </div>
@@ -160,7 +161,7 @@
 
   <aside class="panel">
     <div class="card prof" id="profCard">
-      <h2>学生档案 <button id="profEdit" hidden style="float:right;font-size:12px">编辑</button></h2>
+      <h2>学生档案 <button id="profEdit" hidden style="float:right;font-size:12px">管理档案 ↗</button></h2>
       <div id="prof"><div class="empty">私聊会话连接后显示学生的年级、成绩和各知识点掌握度；课程和练习按档案调整。</div></div>
     </div>
     <div class="card">
@@ -355,27 +356,7 @@ function showProfile(p, flash) {
     (exams ? `<ul class="exams">${exams}</ul>` : `<div class="meta">还没有考试成绩</div>`) +
     (cps ? `<div class="meta">知识点掌握度（估计值，未校准；悬停看依据）</div>` + cps : `<div class="meta">还没有知识点记录：做练习后会出现</div>`);
 }
-function examLines(p) { return (p.exams || []).map(e => `${e.subject} ${e.name} ${e.score}/${e.full} ${(e.weak || []).join(",")}`.trim()).join("\n"); }
-$("profEdit").onclick = () => {
-  if (!profile || $("profForm")) return;
-  const f = document.createElement("form"); f.id = "profForm";
-  f.innerHTML = `<label>名字 <input name="name" value="${esc(profile.name)}"></label>
-    <label>年级 <input name="grade" value="${esc(profile.grade)}" placeholder="如 初二"></label>
-    <label>考试成绩（每行：学科 考试 分数/满分 失分点,失分点）<textarea name="exams">${esc(examLines(profile))}</textarea></label>
-    <div><button class="primary" type="submit">保存</button> <button type="button" id="profCancel">取消</button></div>`;
-  $("prof").appendChild(f);
-  $("profCancel").onclick = () => f.remove();
-  f.onsubmit = (ev) => {
-    ev.preventDefault();
-    const exams = f.exams.value.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
-      const m = l.match(/^(\S+)\s+(\S+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*(.*)$/);
-      return m ? {subject: m[1], name: m[2], score: +m[3], full: +(m[4] || 100),
-                  weak: m[5].split(/[,，、\s]+/).filter(Boolean)} : null;
-    }).filter(Boolean);
-    send({type: "profile", profile: {name: f.name.value.trim(), grade: f.grade.value.trim(), exams}});
-    f.remove();
-  };
-};
+$("profEdit").onclick = () => window.open(`/profile?student=${encodeURIComponent(profile ? profile.id : $("sid").value)}`, "_blank");
 function showExercise(ex) {  // answer buttons while an exercise waits; the persona's examples otherwise
   const key = ex ? ex.concept + (ex.options || []).join("") : "";
   if (key === exerciseKey) return;
diff --git a/live_agent/server/static/profile.html b/live_agent/server/static/profile.html
new file mode 100644
index 0000000..e3cc4bc
--- /dev/null
+++ b/live_agent/server/static/profile.html
@@ -0,0 +1,355 @@
+<!doctype html>
+<html lang="zh-CN">
+<head>
+<meta charset="utf-8">
+<meta name="viewport" content="width=device-width, initial-scale=1">
+<title>学生档案管理</title>
+<style>
+  :root {
+    --bg:#f5f1e8; --panel:#fffdf7; --ink:#1d1b17; --muted:#6f685b; --line:#ddd4c2; --accent:#9d3a22;
+    --ok:#2f7d4f; --bad:#b3372a; --warn:#a86b12; --info:#2d5d8a; --chip:#efe8d8; --manual:#6b4fa0;
+  }
+  @media (prefers-color-scheme: dark) {
+    :root:not([data-theme="light"]) {
+      --bg:#161512; --panel:#1f1d19; --ink:#ede7da; --muted:#a39b8b; --line:#34302a; --accent:#e0795b;
+      --ok:#5fbf86; --bad:#ec7a6c; --warn:#e2a64a; --info:#7fb0e0; --chip:#2a2722; --manual:#b39ae0;
+    }
+  }
+  * { box-sizing:border-box; }
+  body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.5 "Noto Sans SC",system-ui,sans-serif; }
+  header { display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; justify-content:space-between;
+           padding:12px 16px; border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); z-index:2; }
+  h1 { margin:0; font:600 18px "Noto Serif SC",serif; }
+  h2 { margin:0 0 10px; font:600 15px "Noto Serif SC",serif; display:flex; justify-content:space-between; align-items:center; gap:8px; }
+  main { max-width:1100px; margin:0 auto; padding:16px; display:grid; gap:16px; }
+  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px; min-width:0; }
+  .row { display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; }
+  label { display:flex; flex-direction:column; gap:3px; font-size:12px; color:var(--muted); }
+  input, select { font:inherit; font-size:14px; color:var(--ink); background:var(--bg); border:1px solid var(--line);
+                  border-radius:8px; padding:5px 8px; min-width:0; }
+  input:focus, select:focus, button:focus-visible { outline:2px solid var(--info); outline-offset:1px; }
+  input[type=number] { width:5.5em; }
+  button { font:inherit; font-size:13px; border:1px solid var(--line); background:var(--chip); color:var(--ink);
+           border-radius:8px; padding:5px 12px; cursor:pointer; white-space:nowrap; }
+  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; font-weight:600; }
+  button.ghost { background:transparent; }
+  button.danger { color:var(--bad); background:transparent; border-color:var(--bad); }
+  button:disabled { opacity:.5; cursor:default; }
+  a { color:var(--info); }
+  .muted { color:var(--muted); font-size:12px; }
+  .status { font-size:13px; color:var(--muted); }
+  .status.dirty { color:var(--warn); font-weight:600; }
+  .status.err { color:var(--bad); font-weight:600; }
+  .status.ok { color:var(--ok); }
+  .empty { color:var(--muted); font-size:13px; padding:6px 0; }
+  /* exams: one editable row per exam; stacks on narrow screens */
+  .exam { display:grid; grid-template-columns: 6em 1fr 9.5em 5.5em 5.5em 1.4fr 3.5em auto; gap:8px; align-items:end;
+          padding:8px 0; border-bottom:1px dashed var(--line); }
+  .exam .pct { font-variant-numeric:tabular-nums; color:var(--muted); padding-bottom:6px; text-align:right; }
+  .exam input { width:100%; }
+  @media (max-width: 820px) {
+    .exam { grid-template-columns: 1fr 1fr; }
+    .exam .pct { text-align:left; }
+  }
+  /* concepts */
+  .concept { display:grid; grid-template-columns: minmax(7em, 1.1fr) 6em minmax(140px, 2fr) 4.2em minmax(9em, 1.3fr) auto;
+             gap:10px; align-items:center; padding:8px 0; border-bottom:1px dashed var(--line); }
+  .concept .name { font-weight:600; overflow-wrap:anywhere; }
+  .concept input[type=range] { width:100%; }
+  /* the slider is the bar: its colour is the level; untested concepts show a faint slider */
+  .concept.weak input[type=range] { accent-color:var(--bad); } .concept.partial input[type=range] { accent-color:var(--warn); }
+  .concept.mastered input[type=range] { accent-color:var(--ok); } .concept.unknown input[type=range] { opacity:.35; }
+  .bar { height:8px; border-radius:4px; background:var(--chip); overflow:hidden; }
+  .bar i { display:block; height:100%; }
+  .weak .bar i { background:var(--bad); } .partial .bar i { background:var(--warn); }
+  .mastered .bar i { background:var(--ok); } .unknown .bar i { background:var(--line); }
+  .v { font-variant-numeric:tabular-nums; text-align:right; }
+  .src { font-size:12px; color:var(--muted); }
+  .src.manual { color:var(--manual); font-weight:600; }
+  .concept.removed { opacity:.45; text-decoration:line-through; }
+  .concept.changed .name::after { content:" ●"; color:var(--warn); }
+  @media (max-width: 820px) {
+    .concept { grid-template-columns: 1fr auto; }
+    .concept .grow { grid-column: 1 / -1; }
+  }
+  .legend { display:flex; flex-wrap:wrap; gap:10px; font-size:12px; color:var(--muted); margin-bottom:6px; }
+  .legend span::before { content:""; display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:4px; vertical-align:-1px; }
+  .legend .l-weak::before { background:var(--bad); } .legend .l-partial::before { background:var(--warn); }
+  .legend .l-mastered::before { background:var(--ok); } .legend .l-unknown::before { background:var(--line); }
+  .hist { width:100%; border-collapse:collapse; font-size:13px; }
+  .hist th, .hist td { text-align:left; padding:5px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
+  .hist th { color:var(--muted); font-weight:500; }
+  .hist .ok { color:var(--ok); } .hist .bad { color:var(--bad); }
+  .tablewrap { overflow-x:auto; }
+  .actions { position:sticky; bottom:0; background:var(--bg); border-top:1px solid var(--line); padding:10px 16px;
+             display:flex; flex-wrap:wrap; gap:8px; justify-content:space-between; align-items:center; }
+  .note { font-size:12px; color:var(--muted); border-left:3px solid var(--line); padding:2px 8px; margin:0 0 10px; }
+</style>
+</head>
+<body>
+<header>
+  <h1>学生档案管理</h1>
+  <div class="row">
+    <label>学生 <select id="student" aria-label="选择学生"></select></label>
+    <a id="back" href="/">← 返回课堂</a>
+  </div>
+</header>
+
+<main>
+  <p class="note">档案是个人数据，只在「一对一私聊」课堂中使用。老师按档案调整讲课的深浅、例子和练习；学生做练习后掌握度会自动更新。
+    掌握度都是<b>估计值</b>（规则未经校准），这里可以手动修正。</p>
+
+  <section class="card" aria-labelledby="h-basic">
+    <h2 id="h-basic">基本信息</h2>
+    <div class="row">
+      <label>名字 <input id="name" maxlength="20" placeholder="如 小明"></label>
+      <label>年级 <input id="grade" maxlength="12" list="grades" placeholder="如 初二"></label>
+      <datalist id="grades"></datalist>
+      <span class="muted" id="meta"></span>
+    </div>
+  </section>
+
+  <section class="card" aria-labelledby="h-exams">
+    <h2 id="h-exams">考试成绩 <button id="addExam">＋ 添加考试</button></h2>
+    <div class="muted" style="margin-bottom:4px">失分知识点用顿号或逗号分开；老师会按最近一次考试的失分点重点讲。</div>
+    <div id="exams"></div>
+  </section>
+
+  <section class="card" aria-labelledby="h-concepts">
+    <h2 id="h-concepts">知识点掌握度（估计）</h2>
+    <div class="legend"><span class="l-weak">薄弱 &lt;50%</span><span class="l-partial">基本理解</span>
+      <span class="l-mastered">已掌握 ≥80%（需 3 道以上练习或老师设定）</span><span class="l-unknown">未评估</span></div>
+    <div id="concepts"></div>
+    <div class="row" style="margin-top:10px">
+      <label>新知识点 <input id="newName" maxlength="20" placeholder="如 因式分解"></label>
+      <label>学科 <input id="newSubject" maxlength="12" placeholder="如 数学" style="width:7em"></label>
+      <label>估计掌握度 % <input id="newMastery" type="number" min="0" max="100" placeholder="留空=未评估"></label>
+      <button id="addConcept" style="align-self:end">＋ 添加知识点</button>
+    </div>
+  </section>
+
+  <section class="card" aria-labelledby="h-hist">
+    <h2 id="h-hist">最近的练习 <label style="flex-direction:row;align-items:center;gap:6px;font-size:13px;color:var(--ink)">
+      <input type="checkbox" id="clearHist"> 保存时清空练习记录</label></h2>
+    <div class="tablewrap"><table class="hist"><thead><tr><th>时间</th><th>知识点</th><th>结果</th><th>题目</th><th>学生回答</th></tr></thead>
+      <tbody id="hist"></tbody></table></div>
+  </section>
+</main>
+
+<div class="actions">
+  <span class="status" id="status" role="status" aria-live="polite">载入中…</span>
+  <div class="row">
+    <button class="danger" id="reset" title="删除保存的档案，恢复为示例档案（或空档案）">恢复为初始档案</button>
+    <button class="ghost" id="discard" disabled>放弃修改</button>
+    <button class="primary" id="save" disabled>保存</button>
+  </div>
+</div>
+
+<script>
+const $ = (id) => document.getElementById(id);
+const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
+const LEVEL = {mastered: "已掌握", partial: "基本理解", weak: "薄弱", unknown: "未评估"};
+const GRADES = ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"];
+$("grades").innerHTML = GRADES.map(g => `<option value="${g}">`).join("");
+
+let sid = new URLSearchParams(location.search).get("student") || "";
+let server = null;          // the profile as last loaded
+let exams = [];             // editable copy
+let edits = new Map();      // concept name -> {mastery?, delete?, subject?}
+let dirty = false;
+
+function setStatus(text, cls) { const el = $("status"); el.textContent = text; el.className = "status " + (cls || ""); }
+function markDirty() {
+  dirty = true; $("save").disabled = false; $("discard").disabled = false;
+  setStatus("有未保存的修改", "dirty");
+}
+function clean() { dirty = false; $("save").disabled = true; $("discard").disabled = true; }
+
+async function api(path, opts) {
+  const r = await fetch(path, {headers: {"Content-Type": "application/json"}, ...opts});
+  if (!r.ok) { const e = new Error((await r.json().catch(() => ({}))).detail || r.statusText); e.status = r.status; throw e; }
+  return r.json();
+}
+
+async function loadList() {
+  const {students} = await api("/api/students");
+  if (!students.length) { setStatus("服务器没有开放任何学生档案", "err"); return; }
+  if (!students.some(s => s.id === sid)) sid = students[0].id;
+  $("student").innerHTML = students.map(s =>
+    `<option value="${esc(s.id)}"${s.id === sid ? " selected" : ""}>${esc(s.name || s.id)}${s.grade ? " · " + esc(s.grade) : ""} (${esc(s.id)})</option>`).join("");
+  await load();
+}
+
+async function load() {
+  server = await api(`/api/students/${encodeURIComponent(sid)}`);
+  exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
+  edits = new Map(); $("clearHist").checked = false;
+  history.replaceState(null, "", `?student=${encodeURIComponent(sid)}`);
+  $("back").href = "/";
+  render(); clean();
+  setStatus(`已载入 · 版本 ${server.version}${server.saved ? "" : " · 尚未保存过（显示的是初始档案）"}`, "ok");
+}
+
+function render() {
+  $("name").value = server.name || ""; $("grade").value = server.grade || "";
+  $("meta").textContent = `档案编号 ${server.id} · 版本 ${server.version}`;
+  renderExams(); renderConcepts(); renderHistory();
+}
+
+function renderExams() {
+  const el = $("exams");
+  if (!exams.length) { el.innerHTML = `<div class="empty">还没有考试成绩。</div>`; return; }
+  el.innerHTML = exams.map((e, i) => {
+    const pct = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
+    return `<div class="exam" data-i="${i}">
+      <label>学科 <input data-k="subject" value="${esc(e.subject)}" maxlength="12"></label>
+      <label>考试 <input data-k="name" value="${esc(e.name)}" maxlength="20" placeholder="如 期中考试"></label>
+      <label>日期 <input data-k="date" type="date" value="${esc(e.date)}"></label>
+      <label>分数 <input data-k="score" type="number" min="0" step="0.5" value="${esc(e.score)}"></label>
+      <label>满分 <input data-k="full" type="number" min="1" step="1" value="${esc(e.full)}"></label>
+      <label>失分知识点 <input data-k="weak" value="${esc(e.weak)}" placeholder="如 因式分解、浮力"></label>
+      <span class="pct">${pct}</span>
+      <button class="ghost" data-del="${i}" aria-label="删除这次考试">删除</button></div>`;
+  }).join("");
+}
+$("exams").addEventListener("input", (ev) => {
+  const row = ev.target.closest(".exam"), k = ev.target.dataset.k;
+  if (!row || !k) return;
+  const e = exams[+row.dataset.i];
+  e[k] = (k === "score" || k === "full") ? (ev.target.value === "" ? "" : +ev.target.value) : ev.target.value;
+  if (k === "score" || k === "full") row.querySelector(".pct").textContent = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
+  markDirty();
+});
+$("exams").addEventListener("click", (ev) => {
+  const i = ev.target.dataset.del;
+  if (i === undefined) return;
+  exams.splice(+i, 1); renderExams(); markDirty();
+});
+$("addExam").onclick = () => {
+  exams.push({subject: "", name: "", date: new Date().toISOString().slice(0, 10), score: "", full: 100, weak: ""});
+  renderExams(); markDirty();
+  $("exams").lastElementChild.querySelector("input").focus();
+};
+
+function srcText(c) {
+  if (c.source === "manual") return `<span class="src manual">老师设定</span>`;
+  if (c.source === "exercise") return `<span class="src">练习 ${c.correct}/${c.attempts} 对</span>`;
+  if (c.source === "exam") return `<span class="src">据考试失分推断</span>`;
+  return `<span class="src">未评估</span>`;
+}
+function levelOf(m, c) {
+  if (m == null) return "unknown";
+  if (m >= 0.8) return (c.attempts >= 3 || c.source === "manual" || edits.get(c.name)?.mastery != null) ? "mastered" : "partial";
+  return m >= 0.5 ? "partial" : "weak";
+}
+function renderConcepts() {
+  const el = $("concepts");
+  const list = server.concepts.slice();
+  for (const [name, e] of edits) if (e.added && !list.some(c => c.name === name))
+    list.push({name, subject: e.subject || "", mastery: null, source: null, attempts: 0, correct: 0, notes: []});
+  if (!list.length) { el.innerHTML = `<div class="empty">还没有知识点记录。做练习或在下面添加。</div>`; return; }
+  el.innerHTML = list.map(c => {
+    const e = edits.get(c.name) || {};
+    const m = "mastery" in e ? e.mastery : c.mastery;
+    const lvl = levelOf(m, c);
+    const pct = m == null ? "–" : (c.source === "exam" && !("mastery" in e) ? "≈" : "") + Math.round(m * 100) + "%";
+    const src = "mastery" in e ? (e.mastery == null ? `<span class="src">将清除</span>` : `<span class="src manual">老师设定（未保存）</span>`) : srcText(c);
+    return `<div class="concept ${lvl}${e.delete ? " removed" : ""}${Object.keys(e).length ? " changed" : ""}" data-name="${esc(c.name)}">
+      <span class="name">${esc(c.name)}</span>
+      <span class="muted">${esc(c.subject || "")}</span>
+      <span class="grow"><input type="range" min="0" max="100" value="${m == null ? 50 : Math.round(m * 100)}" aria-label="${esc(c.name)} 掌握度"
+               title="拖动即由老师设定掌握度"></span>
+      <span class="v">${pct}</span>
+      <span class="grow">${src}${c.notes && c.notes.length ? `<div class="muted">最近的错误：${esc(c.notes[c.notes.length - 1])}</div>` : ""}
+        <div class="muted">${LEVEL[lvl]}</div></span>
+      <span class="row" style="gap:4px">
+        <button class="ghost" data-act="clear" title="清除估计（变为未评估）">清除</button>
+        <button class="ghost" data-act="${e.delete ? "undo" : "delete"}">${e.delete ? "撤销" : "删除"}</button></span></div>`;
+  }).join("");
+}
+$("concepts").addEventListener("input", (ev) => {
+  if (ev.target.type !== "range") return;
+  const name = ev.target.closest(".concept").dataset.name;
+  edits.set(name, {...(edits.get(name) || {}), mastery: +ev.target.value / 100, delete: false});
+  const row = ev.target.closest(".concept");
+  row.querySelector(".v").textContent = ev.target.value + "%";
+  markDirty();
+});
+$("concepts").addEventListener("change", (ev) => { if (ev.target.type === "range") renderConcepts(); });
+$("concepts").addEventListener("click", (ev) => {
+  const act = ev.target.dataset.act; if (!act) return;
+  const name = ev.target.closest(".concept").dataset.name, e = edits.get(name) || {};
+  if (act === "clear") edits.set(name, {...e, mastery: null, delete: false});
+  if (act === "delete") edits.set(name, {...e, delete: true});
+  if (act === "undo") { const {delete: _, ...rest} = e; Object.keys(rest).length ? edits.set(name, rest) : edits.delete(name); }
+  renderConcepts(); markDirty();
+});
+$("addConcept").onclick = () => {
+  const name = $("newName").value.trim(); if (!name) { $("newName").focus(); return; }
+  const raw = $("newMastery").value.trim();
+  const e = {added: true, subject: $("newSubject").value.trim()};
+  if (raw !== "") e.mastery = Math.max(0, Math.min(100, +raw)) / 100;
+  edits.set(name, e);
+  $("newName").value = ""; $("newMastery").value = "";
+  renderConcepts(); markDirty();
+};
+
+function renderHistory() {
+  const h = server.history || [];
+  $("hist").innerHTML = h.length ? h.map(x => `<tr><td>${esc(x.t)}</td><td>${esc(x.concept)}</td>
+      <td class="${x.correct ? "ok" : "bad"}">${x.correct ? "答对" : "答错"}</td><td>${esc(x.question)}</td><td>${esc(x.answer)}</td></tr>`).join("")
+    : `<tr><td colspan="5" class="empty">还没有练习记录。</td></tr>`;
+}
+
+["name", "grade"].forEach(id => $(id).addEventListener("input", markDirty));
+$("clearHist").addEventListener("change", markDirty);
+
+$("save").onclick = async () => {
+  const bad = exams.find(e => !String(e.subject).trim() || e.score === "" || !(e.full > 0));
+  if (bad) { setStatus("每次考试都要填写学科、分数和满分", "err"); return; }
+  const body = {
+    version: server.version, name: $("name").value.trim(), grade: $("grade").value.trim(),
+    exams: exams.map(e => ({subject: e.subject.trim(), name: e.name.trim(), date: e.date, score: +e.score, full: +e.full,
+                            weak: String(e.weak).split(/[、,，;；\s]+/).filter(Boolean)})),
+    concepts: [...edits].map(([name, e]) => ({name, ...(e.delete ? {delete: true} : {}),
+      ...("mastery" in e && !e.delete ? {mastery: e.mastery} : {}), ...(e.added ? {subject: e.subject} : {})})),
+    clear_history: $("clearHist").checked,
+  };
+  $("save").disabled = true; setStatus("保存中…");
+  try {
+    server = await api(`/api/students/${encodeURIComponent(sid)}`, {method: "PUT", body: JSON.stringify(body)});
+    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
+    edits = new Map(); $("clearHist").checked = false; render(); clean();
+    setStatus(`已保存 · 版本 ${server.version} · 正在上课的页面会自动更新`, "ok");
+  } catch (err) {
+    $("save").disabled = false;
+    if (err.status === 409) setStatus("保存失败：你编辑时档案被更新了（例如课堂上刚批改了一道练习）。请「放弃修改」重新载入后再改。", "err");
+    else setStatus("保存失败：" + err.message, "err");
+  }
+};
+$("discard").onclick = () => load().catch(e => setStatus("载入失败：" + e.message, "err"));
+$("reset").onclick = async () => {
+  if (!confirm(`确定把「${server.name || sid}」的档案恢复为初始档案吗？保存的成绩、掌握度和练习记录都会删除。`)) return;
+  try { server = await api(`/api/students/${encodeURIComponent(sid)}/reset`, {method: "POST"}); await load(); setStatus("已恢复为初始档案", "ok"); }
+  catch (err) { setStatus("恢复失败：" + err.message, "err"); }
+};
+$("student").onchange = async () => {
+  if (dirty && !confirm("有未保存的修改，切换学生会丢弃它们。继续吗？")) { $("student").value = sid; return; }
+  sid = $("student").value; await load();
+};
+window.addEventListener("beforeunload", (ev) => { if (dirty) { ev.preventDefault(); ev.returnValue = ""; } });
+
+// while nothing is being edited, follow changes made by a running lesson (graded exercises)
+setInterval(async () => {
+  if (dirty || !server || document.hidden) return;
+  try {
+    const now = await api(`/api/students/${encodeURIComponent(sid)}`);
+    if (now.version !== server.version) { server = now; exams = now.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
+      render(); setStatus(`已自动更新（课堂中有新的练习结果）· 版本 ${now.version}`, "ok"); }
+  } catch (_) { /* offline for a moment: try again next time */ }
+}, 5000);
+
+loadList().catch(e => setStatus("载入失败：" + e.message, "err"));
+</script>
+</body>
+</html>
diff --git a/live_agent/student.py b/live_agent/student.py
index f71947b..07c32fd 100644
--- a/live_agent/student.py
+++ b/live_agent/student.py
@@ -50,6 +50,7 @@ class Concept:
     taught: int = 0  # lessons that covered it
     notes: list[str] = field(default_factory=list)  # recent misconceptions (short, newest last)
     updated: str = ""
+    manual: bool = False  # the estimate was set by a teacher on the profile page (until the next graded exercise)
 
 
 @dataclass
@@ -60,6 +61,7 @@ class StudentProfile:
     exams: list[Exam] = field(default_factory=list)
     concepts: dict[str, Concept] = field(default_factory=dict)
     history: list[dict] = field(default_factory=list)  # graded exercises, newest last (bounded)
+    version: int = 0  # bumped on every save: an editor saving an older version is refused (no lost updates)
     path: Path | None = field(default=None, repr=False, compare=False)
 
     # ------------------------------------------------------------ storage
@@ -74,7 +76,7 @@ class StudentProfile:
             concepts[name] = Concept(**{k: v for k, v in c.items() if k in Concept.__dataclass_fields__})
         return cls(student_id=str(d.get("student_id") or "student"), name=str(d.get("name") or ""),
                    grade=str(d.get("grade") or ""), exams=exams, concepts=concepts,
-                   history=list(d.get("history") or [])[-100:], path=path)
+                   history=list(d.get("history") or [])[-100:], version=int(d.get("version") or 0), path=path)
 
     @classmethod
     def load(cls, student_id: str, store: Path, seed_dir: Path | None = None) -> StudentProfile:
@@ -97,6 +99,7 @@ class StudentProfile:
             return
         self.path.parent.mkdir(parents=True, exist_ok=True)
         with _SAVE_LOCK:
+            self.version += 1
             tmp = self.path.with_name(f".{self.path.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
             tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
             tmp.replace(self.path)
@@ -157,8 +160,11 @@ class StudentProfile:
         return 0.4 if any(concept in e.weak for e in latest.values()) else None
 
     def source(self, concept: str) -> str | None:
-        """Where the estimate comes from: "exercise" (graded answers), "exam" (a prior), None (unknown)."""
+        """Where the estimate comes from: "manual" (a teacher set it), "exercise" (graded answers), "exam" (a
+        prior), None (unknown)."""
         c = self.concepts.get(concept)
+        if c is not None and c.manual and c.mastery is not None:
+            return "manual"
         if c is not None and c.attempts and c.mastery is not None:
             return "exercise"
         return "exam" if self.mastery(concept) is not None else None
@@ -175,7 +181,7 @@ class StudentProfile:
         if m is None:
             return "unknown"
         c = self.concepts.get(concept)
-        if m >= MASTERED and (c is None or c.attempts < 3):
+        if m >= MASTERED and (c is None or (c.attempts < 3 and not c.manual)):
             return "partial"
         return "mastered" if m >= MASTERED else "partial" if m >= WEAK else "weak"
 
@@ -197,6 +203,7 @@ class StudentProfile:
         c.mastery = round(m + RATE * ((1.0 if correct else 0.0) - m), 3)
         c.attempts += 1
         c.correct += int(bool(correct))
+        c.manual = False  # evidence now
         c.updated = time.strftime("%Y-%m-%d")
         if misconception and not correct:
             c.notes = (c.notes + [str(misconception)[:40]])[-3:]
@@ -205,6 +212,37 @@ class StudentProfile:
         return {"concept": c.name, "correct": bool(correct), "before": before, "after": c.mastery,
                 "level": self.level(c.name)}
 
+    def edit_concepts(self, edits: Any) -> list[str]:
+        """Profile page edits: [{"name", "subject"?, "mastery"? (0-1, or null to clear), "delete"?, "rename"?}]."""
+        changed = []
+        for e in edits if isinstance(edits, list) else []:
+            if not isinstance(e, dict) or not str(e.get("name") or "").strip():
+                continue
+            name = str(e["name"]).strip()[:20]
+            if e.get("delete"):
+                if self.concepts.pop(name, None) is not None:
+                    changed.append(name)
+                continue
+            c = self._concept(name, str(e.get("subject") or "")[:12])
+            if "subject" in e:
+                c.subject = str(e.get("subject") or "")[:12]
+            if "mastery" in e:
+                m = e["mastery"]
+                if m is None:
+                    c.mastery, c.manual = None, False
+                else:
+                    try:
+                        c.mastery, c.manual = round(max(0.0, min(1.0, float(m))), 3), True
+                    except (TypeError, ValueError):
+                        continue
+                c.updated = time.strftime("%Y-%m-%d")
+            new = str(e.get("rename") or "").strip()[:20]
+            if new and new != name and new not in self.concepts:
+                self.concepts[new] = self.concepts.pop(name)
+                self.concepts[new].name = new
+            changed.append(name)
+        return changed
+
     def mark_taught(self, concepts: list[str], subject: str = "") -> None:
         for name in concepts:
             if str(name).strip():
@@ -284,13 +322,69 @@ class StudentProfile:
         """For the page panel."""
         names = sorted(set(self.concepts) | {w for e in self.exams for w in e.weak},
                        key=lambda n: (self.mastery(n) is None, -(self.mastery(n) or 0.0)))
-        return {"id": self.student_id, "name": self.name, "grade": self.grade,
+        return {"id": self.student_id, "name": self.name, "grade": self.grade, "version": self.version,
                 "exams": [{"subject": e.subject, "name": e.name, "score": e.score, "full": e.full, "date": e.date,
                            "weak": e.weak} for e in self.exams],
                 "concepts": [{"name": n, "mastery": self.mastery(n), "level": self.level(n), "source": self.source(n),
+                              "subject": self.concepts[n].subject if n in self.concepts else "",
+                              "notes": self.concepts[n].notes if n in self.concepts else [],
                               "attempts": self.concepts[n].attempts if n in self.concepts else 0,
                               "correct": self.concepts[n].correct if n in self.concepts else 0}
-                             for n in names][:30]}
+                             for n in names][:60],
+                "history": list(reversed(self.history[-30:]))}
+
+
+class ProfileStore:
+    """One shared, in-memory profile per student for the whole server: live sessions and the profile page edit the
+    same object (a session's exercise result and a teacher's edit never overwrite each other), every change is
+    saved, and listeners (open sessions) are told so their page can refresh."""
 
+    def __init__(self, store: Path, seeds: Path | None, allowed: list[str]):
+        self.store, self.seeds, self.allowed = Path(store), seeds, list(dict.fromkeys(allowed))
+        self._profiles: dict[str, StudentProfile] = {}
+        self._listeners: dict[str, list] = {}
 
-__all__ = ["Concept", "Exam", "LEVELS_CN", "StudentProfile"]
+    def get(self, student_id: str) -> StudentProfile | None:
+        if student_id not in self.allowed:
+            return None
+        if student_id not in self._profiles:
+            self._profiles[student_id] = StudentProfile.load(student_id, self.store, self.seeds)
+        return self._profiles[student_id]
+
+    def exists(self, student_id: str) -> bool:
+        return (self.store / f"{student_id}.json").exists()
+
+    def subscribe(self, student_id: str, fn) -> None:
+        self._listeners.setdefault(student_id, []).append(fn)
+
+    def unsubscribe(self, student_id: str, fn) -> None:
+        if fn in self._listeners.get(student_id, []):
+            self._listeners[student_id].remove(fn)
+
+    def changed(self, student_id: str, source=None) -> None:
+        """Save and notify every listener except ``source`` (the one that made the change)."""
+        p = self._profiles.get(student_id)
+        if p is None:
+            return
+        p.save()
+        for fn in list(self._listeners.get(student_id, [])):
+            if fn is not source:
+                fn()
+
+    def reset(self, student_id: str) -> StudentProfile | None:
+        """Back to the seed profile (or empty): the saved copy is deleted."""
+        if student_id not in self.allowed:
+            return None
+        old = self._profiles.get(student_id)
+        (self.store / f"{student_id}.json").unlink(missing_ok=True)
+        fresh = StudentProfile.load(student_id, self.store, self.seeds)
+        fresh.version = (old.version if old is not None else 0) + 1
+        if old is not None:  # keep the object identity: sessions hold a reference to it
+            old.__dict__.update({k: v for k, v in fresh.__dict__.items() if k != "path"})
+            fresh = old
+        self._profiles[student_id] = fresh
+        self.changed(student_id)
+        return fresh
+
+
+__all__ = ["Concept", "Exam", "LEVELS_CN", "ProfileStore", "StudentProfile"]
diff --git a/tests/test_student.py b/tests/test_student.py
index dc6c5cf..c9e26e5 100644
--- a/tests/test_student.py
+++ b/tests/test_student.py
@@ -379,8 +379,8 @@ def test_the_teacher_persona_requires_a_board_for_knowledge_answers():
     replies = [json.loads(x.split(" → ", 1)[1]) for x in canon["responder_examples"]]
     assert all(r["board"]["items"] for r in replies if r["kind"] == "content")
     # no knowledge example is one of the page's one-click questions: those answers would be replayed, not composed
-    asked = {x.split(" → ", 1)[0].removeprefix("用户：") for x in canon["responder_examples"]}
-    content_q = {q for q, r in zip(asked, replies) if r["kind"] == "content"}
+    asked = [x.split(" → ", 1)[0].removeprefix("用户：") for x in canon["responder_examples"]]
+    content_q = [q for q, r in zip(asked, replies) if r["kind"] == "content"]
     assert not any(q in chip or chip in q for q in content_q for chip in canon["examples"])
 
 
@@ -397,3 +397,51 @@ def test_a_reply_copying_an_example_is_composed_again():
     d2, llm2, _ = tt._director(fresh)
     asyncio.run(d2.decide(Utterance(uid="u8", speaker="user", text="杠杆为什么能省力？", t_end=now()), None))
     assert len(llm2.calls) == 1  # an answer in its own words is used as it is
+
+
+# ---------------------------------------------------------------- profile page (API) and shared store
+def _client(tmp_path, students="demo,e2e"):
+    from types import SimpleNamespace
+
+    from fastapi.testclient import TestClient
+
+    from live_agent.server.app import build_app
+    args = SimpleNamespace(config=str(tt.CFG), student="demo", students=students, student_store=str(tmp_path),
+                           record=False, generator="mock", log_dir=str(tmp_path / "logs"))
+    return TestClient(build_app(args))
+
+
+def test_the_profile_page_edits_a_profile_with_version_checks(tmp_path):
+    c = _client(tmp_path)
+    assert c.get("/profile").status_code == 200
+    assert [s["id"] for s in c.get("/api/students").json()["students"]] == ["demo", "e2e"]
+    assert c.get("/api/students/someone-else").status_code == 404  # not on the allow-list
+    p = c.get("/api/students/demo").json()
+    body = {"version": p["version"], "grade": "初三", "exams": [{"subject": "数学", "name": "期末", "score": 91, "weak": ["函数"]}],
+            "concepts": [{"name": "完全平方公式", "mastery": 0.7}, {"name": "光合作用", "delete": True},
+                         {"name": "一次函数", "subject": "数学"}]}
+    q = c.put("/api/students/demo", json=body).json()
+    assert q["grade"] == "初三" and q["version"] == p["version"] + 1 and [e["name"] for e in q["exams"]] == ["期末"]
+    cp = {x["name"]: x for x in q["concepts"]}
+    assert cp["完全平方公式"]["mastery"] == 0.7 and cp["完全平方公式"]["source"] == "manual"
+    assert "光合作用" not in cp and cp["一次函数"]["source"] is None and cp["函数"]["source"] == "exam"
+    assert c.put("/api/students/demo", json=body).status_code == 409  # stale version: refused, not overwritten
+    saved = StudentProfile.load("demo", tmp_path, SEEDS)
+    assert saved.grade == "初三" and saved.concepts["完全平方公式"].manual
+    r = c.post("/api/students/demo/reset").json()  # back to the seed (saved again with a newer version)
+    assert r["grade"] == "初二" and r["version"] > q["version"] and "光合作用" in {x["name"] for x in r["concepts"]}
+
+
+def test_sessions_and_the_page_share_one_profile_and_listeners_are_told(tmp_path):
+    from live_agent.student import ProfileStore
+    store = ProfileStore(tmp_path, SEEDS, ["demo"])
+    a, b = store.get("demo"), store.get("demo")
+    assert a is b and store.get("other") is None
+    told = []
+    store.subscribe("demo", lambda: told.append("session"))
+    a.record_exercise("勾股定理", True)
+    store.changed("demo")  # a page edit / another session: the open session hears about it
+    assert told == ["session"] and StudentProfile.load("demo", tmp_path, SEEDS).concepts["勾股定理"].attempts == 4
+    v = a.version
+    store.reset("demo")
+    assert store.get("demo") is a and a.version > v and a.concepts["勾股定理"].attempts == 3  # same object, seed data

===== FILE: configs/curriculum/pedagogy.json =====
{
 "sources": [
  {
   "id": "s1",
   "title": "义务教育课程方案（2022年版）（教育部，第8页“教学时间”：小学每课时按40分钟、初中按45分钟计算）",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202204/W020220420582343217634.pdf",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s2",
   "title": "教育部教材局：义务教育课程方案和课程标准（2022年版）情况介绍（“加强了学段衔接……一至二年级注重活动化、游戏化、生活化的学习设计”）",
   "url": "http://www.moe.gov.cn/fbh/live/2022/54382/sfcl/202204/t20220421_620077.html",
   "kind": "official_explainer",
   "accessed": "2026-09-28"
  },
  {
   "id": "s3",
   "title": "义务教育语文课程标准（2022年版）（学段要求：第一学段识字1600个左右、第二学段累计2500个左右、第三学段累计3000个左右；教学建议：创设真实而富有意义的学习情境、注意幼小衔接、减缓坡度）",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202204/W020220420582344386456.pdf",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s4",
   "title": "义务教育数学课程标准（2022年版）（教学建议：第一学段通过直观辨认感知图形，第二学段感悟抽象，第三学段从度量角度加深认识，第四学段由感性上升为理性、逐步形成推理能力；第一至三学段以主题式学习为主，第四学段可采用项目式学习；倡导启发式、探究式、参与式、互动式）",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202204/W020220510531636118932.pdf",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s5",
   "title": "普通高中课程方案（2017年版2020年修订）（每课时按45分钟计；创设与生活关联的、任务导向的真实情境，促进自主、合作、探究地学习；学生发展与生涯规划指导）",
   "url": "https://www.ictr.edu.cn/Uploads/File/2022/04/28/1.%E6%99%AE%E9%80%9A%E9%AB%98%E4%B8%AD%E8%AF%BE%E7%A8%8B%E6%96%B9%E6%A1%88%EF%BC%882017%E5%B9%B4%E7%89%882020%E5%B9%B4%E4%BF%AE%E8%AE%A2%EF%BC%89.20220428175806.pdf",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s6",
   "title": "普通高中数学、物理、语文课程标准（2017年版2020年修订）（教育部发布压缩包；数学：逻辑推理是数学严谨性的基本保证，创设合适的教学情境、启发思考；物理：建构模型、比较—概括—抽象、基于证据和逻辑；语文：学习任务群、自主合作探究、专题学习与项目学习）",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202006/W020200603315372317586.zip",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s7",
   "title": "教育部关于大力推进幼儿园与小学科学衔接的指导意见（2021）（一年级上学期设为入学适应期；国家课程主要采取游戏化、生活化、综合化等方式实施，减缓教学进度）",
   "url": "http://www.moe.gov.cn/srcsite/A06/s3327/202104/t20210408_525137.html",
   "kind": "official_explainer",
   "accessed": "2026-09-28"
  },
  {
   "id": "s8",
   "title": "中小学心理健康教育指导纲要（2012年修订）（分小学低、中、高年级及初中、高中五阶段规定重点：学习习惯与规则意识→自我认识与探究兴趣→青春期、学习动机→自我评价与情绪管理→人生理想、考试压力与生涯选择）",
   "url": "http://www.moe.gov.cn/srcsite/A06/s3325/201212/t20121211_145679.html",
   "kind": "official_explainer",
   "accessed": "2026-09-28"
  },
  {
   "id": "s9",
   "title": "中办国办《关于进一步减轻义务教育阶段学生作业负担和校外培训负担的意见》（小学一、二年级不布置家庭书面作业；三至六年级书面作业平均不超过60分钟；初中不超过90分钟；分层、弹性作业）",
   "url": "http://www.moe.gov.cn/jyb_xxgk/moe_1777/moe_1778/202107/t20210724_546576.html",
   "kind": "official_explainer",
   "accessed": "2026-09-28"
  },
  {
   "id": "s10",
   "title": "Piaget's theory of cognitive development（Wikipedia 综述：具体运算阶段约7–11岁，只能对具体对象和事件进行逻辑推理；形式运算阶段约11岁开始、14–15岁趋于完成，能进行抽象、假设性推理）",
   "url": "https://en.wikipedia.org/wiki/Piaget%27s_theory_of_cognitive_development",
   "kind": "research",
   "accessed": "2026-09-28"
  },
  {
   "id": "s11",
   "title": "Sustained attention and inhibitory control: age and sex related difference in children and adolescents using a CPT with distracting events（Front Psychol 2025;16:1609537：持续注意在童年早期快速提高、青少年期趋于平台，6–16岁呈非线性发展）",
   "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12406707/",
   "kind": "research",
   "accessed": "2026-09-28"
  },
  {
   "id": "s12",
   "title": "Brain Balance: Normal Attention Span Expectations by Age（科普性经验法则：每岁2–3分钟，如6岁12–18分钟、8岁16–24、10岁20–30、12岁24–36、14岁28–42、16岁32–48；证据等级低，仅作参考）",
   "url": "https://www.brainbalancecenters.com/blog/normal-attention-span-expectations-by-age",
   "kind": "other",
   "accessed": "2026-09-28"
  },
  {
   "id": "s13",
   "title": "清华大学出版社 心理学教材 第三章“注意”（注意起伏周期约8–10秒；广义注意稳定性：听课时对象不断变换但服从同一任务，单调刺激易致分心）",
   "url": "https://www.tup.tsinghua.edu.cn/upload/books/yz/071628-01.pdf",
   "kind": "research",
   "accessed": "2026-09-28"
  }
 ],
 "class_minutes": {
  "primary": 40,
  "junior": 45,
  "senior": 45,
  "source": "s1（小学、初中），s5（高中）"
 },
 "grades": {
  "1": {
   "stage": "小学低年级（第一学段）",
   "learner": [
    "刚完成幼小衔接，正从“游戏活动为主”转向“课堂教学为主”（s7）",
    "具体形象思维为主，处于前运算向具体运算过渡期，需实物和图像支撑（s10）",
    "有意注意时间短、易被新奇刺激吸引，单调讲授很快分心（s12、s13）",
    "识字量有限：第一学段结束时约认识1600字，一年级字更少，主要靠听和拼音（s3）"
   ],
   "attention_minutes": "10-15（估计：按每岁2–3分钟经验法则约12–18分钟，被动看视频取下限）",
   "methods": [
    "游戏化、生活化、活动化学习（s2、s7）",
    "故事情境、儿歌口诀、角色扮演（s3）",
    "直观教具：实物、图片、动画演示，边看边数（s4）",
    "讲3–5分钟就插入一次互动（举手、跟读、指一指）",
    "大量即时表扬和小奖励（贴纸、星星）"
   ],
   "content": [
    "一次只讲一个小知识点，一节课1–2个点",
    "每个点配一个生活实物或图片",
    "同一内容换2–3种说法重复",
    "以“零起点”教学，不默认孩子已学过（s7）"
   ],
   "tone": [
    "亲切活泼，像大姐姐/大哥哥讲故事",
    "称呼“小朋友们”“你”，多用叠词和拟声词（圆圆的、咚咚咚）",
    "句子很短，一句一个意思，约10字",
    "语速慢、停顿多，重要词说两遍",
    "多用问句邀请参与：“你猜猜看？”"
   ],
   "sentence_chars": 10,
   "vocabulary": "只用口语常用词和课本已出现的词；避免书面语、成语堆砌和抽象术语（如“概念”“性质”）；数学术语仅限“加、减、比大小、多、少”等教材用语，必要时用“就是……”解释",
   "examples": [
    "水果、糖果、玩具、小动物",
    "数手指、分苹果、排队",
    "熟悉的场景：家、教室、操场、超市"
   ],
   "encouragement": "每次回答都给具体表扬（“你数得真仔细！”）；答错时不说“错了”，改说“差一点点，我们再一起数一数”，先肯定再示范正确做法，保护自信和兴趣",
   "exercise_style": "口头回答一个数或一个字、看图选择（2–3个选项）、跟读、指一指、动手摆一摆；课后不布置家庭书面作业（s9）",
   "avoid": [
    "连续讲授超过5分钟不互动",
    "一次讲多个知识点或超标、赶进度（s7）",
    "长句、抽象定义、书面语",
    "批评式纠错、与他人比较"
   ],
   "sources": [
    "s1",
    "s2",
    "s3",
    "s4",
    "s7",
    "s8",
    "s9",
    "s10",
    "s12"
   ]
  },
  "2": {
   "stage": "小学低年级（第一学段）",
   "learner": [
    "已适应小学课堂，但仍以具体形象思维为主（s10）",
    "注意力比一年级稍长，仍依赖兴趣和新奇感（s12）",
    "开始独立识字，能借助拼音读、能讲简短故事（s3）",
    "重点是学习习惯、规则意识和对学习的兴趣（s8）"
   ],
   "attention_minutes": "12-15（估计：经验法则7–8岁约14–24分钟，视频被动听讲取下限）",
   "methods": [
    "情境化、游戏化教学（s2、s3）",
    "故事+提问、猜谜、闯关小游戏",
    "直观操作：画图、摆小棒、动画演示（s4）",
    "朗读、复述、表演等学生喜闻乐见的形式（s3）",
    "每4–5分钟一次互动"
   ],
   "content": [
    "一次讲一个点，一节课2个左右的小点",
    "先实物/图，再引出简单符号或算式",
    "讲完立刻一个小练习巩固"
   ],
   "tone": [
    "温暖活泼、有鼓励感",
    "称呼“小朋友们”或“同学们”，可偶尔用叠词",
    "句子短，约12字，一句一事",
    "多用“我们一起……”“你发现了吗？”"
   ],
   "sentence_chars": 12,
   "vocabulary": "口语常用词为主，可引入教材中的基本术语（如“乘法”“厘米”）但必须配例子解释；避免成语串、长修饰语和抽象词",
   "examples": [
    "分糖果、买文具、排座位",
    "时钟、人民币、东南西北（第一学段主题活动）",
    "动物故事、童话人物"
   ],
   "encouragement": "具体表扬努力和方法（“你想到用画图，真聪明！”）；错误时温和提示“再看看这里”，给一个小台阶让孩子自己改对",
   "exercise_style": "看图列式、口头说理由一句话、选择题2–3项、连一连；校内小练习即可，不布置家庭书面作业（s9）",
   "avoid": [
    "长时间单向讲解",
    "用考试和分数施压",
    "一次给多步复杂指令",
    "讽刺或比较性批评"
   ],
   "sources": [
    "s2",
    "s3",
    "s4",
    "s8",
    "s9",
    "s10",
    "s12"
   ]
  },
  "3": {
   "stage": "小学中年级（第二学段）",
   "learner": [
    "进入具体运算阶段，能对具体事物进行逻辑推理，但抽象、假设性思维尚未发展（s10）",
    "开始“了解自我、认识自我”，探究兴趣增强（s8）",
    "识字量明显增长（第二学段累计约2500字），可以阅读短文字（s3）",
    "注意力约15–20分钟，仍需变换活动（s12、s13）"
   ],
   "attention_minutes": "15-20（估计：经验法则8–9岁约16–27分钟）",
   "methods": [
    "情境+问题驱动：从一个生活问题引出新知（s3、s4）",
    "在具体情境中感悟抽象（第二学段，s4）",
    "动手操作、画图、小实验",
    "主题式学习，把知识融入主题活动（s4）",
    "小组讨论式提问（虚拟：“你会怎么想？”）"
   ],
   "content": [
    "一次讲一个核心点，可带一个延伸",
    "先例子后规律，规律用一句话总结",
    "每段讲解6–8分钟后穿插练习或提问"
   ],
   "tone": [
    "亲切、鼓励、带一点好奇心",
    "称呼“同学们”，少用叠词",
    "句子约15字，可有简单因果（因为……所以……）",
    "多提开放小问题：“为什么会这样？”"
   ],
   "sentence_chars": 15,
   "vocabulary": "可用教材规范术语（如“分数”“周长”“段落”），首次出现时解释并举例；避免高年级或初中术语、过多成语",
   "examples": [
    "校园生活、购物找零、测量身边物体",
    "科学小实验、自然观察",
    "短小的寓言和童话"
   ],
   "encouragement": "表扬具体的思考过程；错误视为“发现问题的机会”，引导学生自己检查哪一步出了问题，再给提示",
   "exercise_style": "一步或两步应用题、看图填空、说说理由、简单判断对错；书面作业量适中（三至六年级平均不超过60分钟，s9）",
   "avoid": [
    "直接给结论不让思考",
    "抽象定义先行",
    "超过8分钟不互动",
    "过度幼儿化的语气（会让学生觉得被当小孩）"
   ],
   "sources": [
    "s3",
    "s4",
    "s8",
    "s9",
    "s10",
    "s12",
    "s13"
   ]
  },
  "4": {
   "stage": "小学中年级（第二学段）",
   "learner": [
    "具体运算阶段，分类、比较、推理能力增强（s10）",
    "自主参与意识和集体意识增强，喜欢表达自己的看法（s8）",
    "能用普通话较流利朗读、初步学会默读和略读（s3）",
    "能在具体情境中逐步感悟图形和数量的抽象（s4）"
   ],
   "attention_minutes": "15-20（估计：经验法则9–10岁约18–30分钟）",
   "methods": [
    "问题情境导入+探究（s3、s4）",
    "画图、表格、数轴等直观工具",
    "主题式学习与跨学科小任务（s4）",
    "对比辨析：两个相近概念放一起比较"
   ],
   "content": [
    "一节课1–2个核心点",
    "先具体例子→归纳规律→再举一反例",
    "每个点后配2–3道由易到难的小题"
   ],
   "tone": [
    "亲切、清楚、有节奏",
    "称呼“同学们”",
    "句子约16字，可用“先……再……最后……”组织步骤",
    "适当设悬念激发好奇"
   ],
   "sentence_chars": 16,
   "vocabulary": "教材术语可直接使用并简要解释；可以出现少量常见成语；避免抽象的逻辑术语（如“充分条件”）",
   "examples": [
    "面积测量教室、统计班级数据",
    "购物、时间安排、路线图",
    "历史小故事、科普短文"
   ],
   "encouragement": "表扬方法和坚持；纠错时先问“你是怎么想的？”，找到思路中的对的部分，再指出需要修正的一步",
   "exercise_style": "两步应用题、简单统计表填空、口头解释一个规律、选择+说明理由",
   "avoid": [
    "只讲不练",
    "一次讲超过2个新概念",
    "给出没有例子的定义",
    "语气过于严肃或说教"
   ],
   "sources": [
    "s3",
    "s4",
    "s8",
    "s10",
    "s12"
   ]
  },
  "5": {
   "stage": "小学高年级（第三学段）",
   "learner": [
    "具体运算阶段后期，开始向抽象思维过渡，但仍需具体支撑（s10）",
    "开始进入青春期前期，自尊心增强，在意同伴评价（s8）",
    "累计识字约3000字，能独立阅读较长文本、查资料（s3）",
    "能从度量角度理解概念，关注图形关系和数量关系（s4）"
   ],
   "attention_minutes": "20-25（估计：经验法则10–11岁约20–33分钟）",
   "methods": [
    "探究式：提出问题→猜想→验证→总结（s4）",
    "在具体情境中抽象出规律，由具体到半抽象",
    "主题式/跨学科学习（s4）",
    "启发式提问，让学生先想再讲"
   ],
   "content": [
    "一节课2个左右核心点，可有一个拓展",
    "讲解中出现初步的符号表达和一般化",
    "每8–10分钟一个小结或练习"
   ],
   "tone": [
    "平等、尊重、带点幽默",
    "称呼“同学们”，把学生当“小大人”",
    "句子约18字，可有简单的复合句",
    "多用“你能发现什么规律？”等启发句"
   ],
   "sentence_chars": 18,
   "vocabulary": "规范学科术语可直接使用（如“比例”“方程”“说明文”），新术语给定义+例子；避免初中及以上术语，避免幼儿化叠词",
   "examples": [
    "折扣、行程、比例尺地图",
    "科学探究小实验",
    "社会生活与传统文化故事"
   ],
   "encouragement": "公开表扬要真诚具体，避免空洞夸奖；纠错时保护面子，用“很多同学都会在这里卡住”来正常化错误，再讲清道理",
   "exercise_style": "多步应用题、简单说理、判断并改错、小型探究任务（如调查并做统计）",
   "avoid": [
    "过度幼儿化的称呼和语气",
    "当众贬低错误",
    "只要答案不问理由",
    "堆砌知识点"
   ],
   "sources": [
    "s3",
    "s4",
    "s8",
    "s10",
    "s12"
   ]
  },
  "6": {
   "stage": "小学高年级（第三学段）",
   "learner": [
    "向形式运算过渡的起点，部分学生可做初步抽象推理（s10）",
    "开展初步青春期教育；需要正确对待成绩、体验成功（s8）",
    "要为初中学习生活做好准备（s8）",
    "能进行较长时间的专注学习（s12）"
   ],
   "attention_minutes": "20-25（估计：经验法则11–12岁约22–36分钟）",
   "methods": [
    "探究式+讨论式",
    "引导学生用自己的话概括规律",
    "小初衔接：初步引入符号、推理和论证表达（s2、s4）",
    "综合性学习与简单研究报告（s3）"
   ],
   "content": [
    "一节课2–3个相关要点，突出知识之间的联系",
    "可出现简单的一般化结论和字母表示",
    "讲解后有归纳小结和变式练习"
   ],
   "tone": [
    "尊重、理性、适度幽默",
    "称呼“同学们”",
    "句子约20字，可用条件和转折句",
    "少用夸张的拟声和叠词"
   ],
   "sentence_chars": 20,
   "vocabulary": "使用规范学科术语；可引入少量初中衔接用语（如“代数式”“论据”）并解释；避免艰深的学术词汇",
   "examples": [
    "生活中的数据与比例",
    "科学现象解释",
    "名人故事、传统文化"
   ],
   "encouragement": "肯定思考过程和进步；纠错时聚焦于“哪一步推理不严密”，鼓励自查；避免在比较中批评",
   "exercise_style": "多步推理题、说明理由的填空、开放性小问题、简单项目任务",
   "avoid": [
    "当孩子对待",
    "只给结论",
    "过度重复已掌握内容",
    "忽视学生情绪变化"
   ],
   "sources": [
    "s2",
    "s3",
    "s4",
    "s8",
    "s10",
    "s12"
   ]
  },
  "7": {
   "stage": "初中（第四学段）",
   "learner": [
    "进入形式运算阶段起始期，开始能理解抽象概念和假设情境，但仍不稳定（s10）",
    "需适应中学学习环境和要求，发展学习方法（s8）",
    "认识青春期生理、心理特征，自我意识强、渴望被尊重（s8）",
    "对图形的认识由感性上升为理性，逐步形成推理能力（s4）"
   ],
   "attention_minutes": "20-25（估计：经验法则12–13岁约24–39分钟，视频讲授宜分段）",
   "methods": [
    "探究式、启发式、互动式教学（s4）",
    "大单元与项目式学习（第四学段可采用项目式学习，s4）",
    "从具体情境引出抽象概念，再回到应用",
    "概念辨析、正反例对比"
   ],
   "content": [
    "一节课2–3个要点，注意与小学知识衔接",
    "概念先给情境，再给规范定义",
    "每10分钟左右一次提问或小练习"
   ],
   "tone": [
    "平等、真诚、像学长或年轻老师",
    "称呼“同学们”，可用“你”",
    "句子约22字，逻辑连接词清楚（因为、所以、如果、那么）",
    "避免说教，用提问代替命令"
   ],
   "sentence_chars": 22,
   "vocabulary": "使用规范学科术语（如“有理数”“实验变量”“论点”），新术语给定义+例子；避免高中专业术语和生僻学术词",
   "examples": [
    "生活中的数学模型（温度、海拔、收支）",
    "物理/生物现象与小实验",
    "时事与社会现象（适度）"
   ],
   "encouragement": "表扬要具体、克制、真诚，避免“好棒”式空洞夸奖；纠错时尊重自尊心，指出错误原因并给出改正思路，鼓励面对挫折（s8）",
   "exercise_style": "概念辨析选择题、两三步推理题、说明理由的简答、小型探究/项目任务",
   "avoid": [
    "幼儿化语气和叠词",
    "纯灌输、只讲不问",
    "当众批评或贴标签",
    "内容量过大无梳理"
   ],
   "sources": [
    "s4",
    "s8",
    "s10",
    "s12"
   ]
  },
  "8": {
   "stage": "初中（第四学段）",
   "learner": [
    "形式运算能力发展中，能进行初步的假设—推理（s10）",
    "青春期情绪波动明显，需要情绪管理与积极体验（s8）",
    "持续注意在童年期快速提高、青少年期趋于平台（s11）",
    "分化明显，需分层要求"
   ],
   "attention_minutes": "25-30（估计：经验法则13–14岁约26–42分钟）",
   "methods": [
    "探究式：提出问题—作出假设—设计验证—得出结论（s4）",
    "项目式、跨学科主题学习（s2、s4）",
    "逻辑推理和证明的初步训练",
    "分层提问：基础题+挑战题"
   ],
   "content": [
    "一节课2–3个要点，强调知识结构和联系",
    "给出推理过程而不只给结论",
    "讲解后小结知识结构图"
   ],
   "tone": [
    "理性、清楚、尊重",
    "称呼“同学们”",
    "句子约24字，允许复合句，但重点句仍要简短",
    "适度幽默，避免居高临下"
   ],
   "sentence_chars": 24,
   "vocabulary": "使用完整的初中学科术语；可引入“证明”“函数”“变量”等抽象术语并举例；避免大学术语",
   "examples": [
    "一次函数与生活中的计费",
    "物理中的力、电路实例",
    "议论文中的生活论据"
   ],
   "encouragement": "肯定努力和策略；纠错时说明错误类型（概念、计算、审题），给改正路径，培养应对挫折能力（s8）",
   "exercise_style": "推理题、证明题入门、实验设计题、开放性问答、分层练习",
   "avoid": [
    "幼稚化表达",
    "机械重复训练（s9）",
    "只讲技巧不讲道理",
    "讽刺和比较"
   ],
   "sources": [
    "s2",
    "s4",
    "s8",
    "s9",
    "s10",
    "s11",
    "s12"
   ]
  },
  "9": {
   "stage": "初中（第四学段）毕业年级",
   "learner": [
    "形式运算能力进一步发展，可进行较系统的抽象推理（s10）",
    "面临中考和升学选择，需把握升学方向、培养职业规划意识（s8）",
    "学习压力增大，需积极应对失败和挫折（s8）",
    "持续注意趋于成熟（s11）"
   ],
   "attention_minutes": "25-30（估计：经验法则14–15岁约28–45分钟）",
   "methods": [
    "专题复习与知识结构梳理",
    "探究式+讲练结合",
    "典型例题分析与变式训练",
    "错题归因与方法总结"
   ],
   "content": [
    "一节课可覆盖一个专题的2–4个要点",
    "强调知识网络和方法迁移",
    "例题由基础到综合，梯度清楚"
   ],
   "tone": [
    "沉稳、理性、给人信心",
    "称呼“同学们”",
    "句子约25字，逻辑严密，结论明确",
    "减少焦虑性表达，多用“我们一步一步来”"
   ],
   "sentence_chars": 25,
   "vocabulary": "完整使用初中学科术语与规范表述；可提及高中衔接概念但标注“了解即可”",
   "examples": [
    "中考典型情境题",
    "综合实践与跨学科问题",
    "社会热点与科技进展"
   ],
   "encouragement": "强调进步和方法，而不是分数；纠错时帮学生分类归因并制定改进办法，缓解考试焦虑",
   "exercise_style": "综合题、多步推理和证明、限时小测、错题重做与变式",
   "avoid": [
    "制造焦虑或恐吓式动员",
    "题海战术和重复性作业（s9）",
    "忽视方法总结",
    "语气说教"
   ],
   "sources": [
    "s4",
    "s8",
    "s9",
    "s10",
    "s11"
   ]
  },
  "10": {
   "stage": "高中（高一）",
   "learner": [
    "进入高中需适应新的学习要求与更高抽象度（s8）",
    "形式运算阶段，可进行抽象与假设—演绎推理，但个体差异大（s10）",
    "开始考虑选科与生涯规划（s5、s8）",
    "能在比较复杂的情境中思考（s6）"
   ],
   "attention_minutes": "30-35（估计：经验法则15–16岁约30–48分钟，但讲授质量影响更大）",
   "methods": [
    "创设与生活关联、任务导向的真实情境（s5）",
    "自主、合作、探究学习（s5）",
    "启发思考、把握学科本质（s6）",
    "建构模型、比较—概括—抽象（s6）"
   ],
   "content": [
    "一节课3–4个要点，形成完整的知识单元",
    "概念—定理—推导—应用的完整链条",
    "强调严谨定义和适用条件（s6）"
   ],
   "tone": [
    "理性、严谨、平等交流",
    "称呼“同学们”或“大家”",
    "句子约28字，允许较长的逻辑句，但每段一个中心",
    "用准确术语，避免含糊"
   ],
   "sentence_chars": 28,
   "vocabulary": "完整使用高中学科规范术语（如“集合”“函数的单调性”“物理模型”）；避免未学的大学术语；首次出现要给严格定义",
   "examples": [
    "物理模型（质点、匀变速运动）",
    "数学建模的生活问题",
    "文学文本与思辨话题"
   ],
   "encouragement": "肯定思维品质（严谨、有创见）；纠错时指出逻辑漏洞或概念误用，引导独立反思",
   "exercise_style": "推导证明、建模应用题、开放探究问题、简答论证",
   "avoid": [
    "只给公式不讲推导",
    "逻辑跳步",
    "空泛鼓励",
    "低龄化语气"
   ],
   "sources": [
    "s5",
    "s6",
    "s8",
    "s10",
    "s12"
   ]
  },
  "11": {
   "stage": "高中（高二）",
   "learner": [
    "抽象与逻辑推理能力较成熟（s10）",
    "形成自我意识，树立人生理想（s8）",
    "选科后学习更专、更深",
    "需要应对学习压力、提高学习效率（s8）"
   ],
   "attention_minutes": "30-40（估计）",
   "methods": [
    "专题学习、比较阅读、项目学习（s6）",
    "论证与质疑：鼓励提出反例和不同解法（s5）",
    "科学探究：基于证据和逻辑作出解释（s6）",
    "大单元整体设计"
   ],
   "content": [
    "一节课3–4个要点，可有一定深度拓展",
    "强调推理严谨、条件完整",
    "讲清方法与思想（如等效、化归）"
   ],
   "tone": [
    "理性、严谨、有思想深度",
    "称呼“同学们”",
    "句子约30字，结构清晰（首先、其次、因此）",
    "可引用学科史和前沿激发兴趣"
   ],
   "sentence_chars": 30,
   "vocabulary": "高中规范术语全面使用；可适度引入学科史与前沿概念并说明层次；避免口语化不准确表达",
   "examples": [
    "学科史上的经典实验与证明",
    "社会、科技议题的数据分析",
    "经典文学与思辨文本"
   ],
   "encouragement": "表扬独立思考和严密论证；纠错时让学生自己找到推理漏洞，强调“严谨求实”的科学精神（s5）",
   "exercise_style": "证明与推导、综合应用、论述题、探究设计",
   "avoid": [
    "只讲套路不讲本质",
    "结论不给依据",
    "过度夸奖",
    "内容过浅"
   ],
   "sources": [
    "s5",
    "s6",
    "s8",
    "s10"
   ]
  },
  "12": {
   "stage": "高中（高三）毕业年级",
   "learner": [
    "形式运算成熟，能系统组织知识（s10）",
    "面临高考压力与升学就业选择，需克服考试焦虑（s8）",
    "需要系统复习和知识网络化",
    "自主学习能力强，重视效率"
   ],
   "attention_minutes": "30-40（估计）",
   "methods": [
    "专题复习与知识网络构建",
    "典型题精讲+变式",
    "错因分析与策略总结",
    "限时训练后讲评"
   ],
   "content": [
    "一节课一个专题，3–5个要点",
    "重点在联系、方法和易错点",
    "讲解精炼、密度较高"
   ],
   "tone": [
    "沉稳、精准、高效",
    "称呼“同学们”",
    "句子约30字，表达简洁，结论先行",
    "给人信心，避免制造焦虑"
   ],
   "sentence_chars": 30,
   "vocabulary": "完整使用高中规范术语与考试规范表述；避免超纲内容，或明确标注“拓展”",
   "examples": [
    "高考真题类型情境",
    "跨模块综合问题",
    "现实问题建模"
   ],
   "encouragement": "肯定进步和策略，降低焦虑；纠错时精准归因并给出可执行的改进步骤，帮助应对挫折（s8）",
   "exercise_style": "综合题、限时训练、错题重做、论述与证明题",
   "avoid": [
    "恐吓式动员",
    "没有重点的大面积复习",
    "空洞励志",
    "逻辑不严谨的讲解"
   ],
   "sources": [
    "s5",
    "s6",
    "s8",
    "s10"
   ]
  }
 },
 "notes": [
  "引用（cited）：课时40/45/45分钟（s1第8页、s5）；一二年级活动化、游戏化、生活化（s2、s7）；识字量1600/2500/3000（s3）；数学各学段由直观到推理的进阶与主题式/项目式学习（s4）；高中真实情境、自主合作探究、逻辑推理与严谨（s5、s6）；各学段心理发展重点（s8）；作业量规定（s9）；皮亚杰阶段年龄（s10）。",
  "编辑估计（estimate）：所有 attention_minutes 均为估计，依据科普性经验法则“每岁2–3分钟”（s12，证据等级低）并针对被动看视频下调；s11 只支持“持续注意6–16岁非线性提高、青少年期趋稳”的定性结论，不提供分钟数。",
  "编辑估计（estimate）：sentence_chars（10→30字）、每节课要点数量、“每3–10分钟插入一次互动”等节奏建议均为编辑估计，未见官方标准给出数值，建议上线后用学生测评校准。",
  "注意：课标原文是扫描版PDF，引用内容为逐页查看图像所得；另有 Bradbury 2016（Adv Physiol Educ）质疑“讲课10–15分钟注意力极限”的说法，仅见检索摘要、未能打开原文，故未列为来源，但提示分钟数不应视为硬性上限，教师讲授质量影响更大。",
  "tone、methods、avoid 中的具体措辞（如称呼“小朋友们”、叠词、拟声词）是依据上述学段特点整理的编辑建议，不是官方原文。"
 ]
}
===== FILE: configs/curriculum/math.json =====
{
 "subject": "数学",
 "grades": [
  1,
  12
 ],
 "sources": [
  {
   "id": "s1",
   "title": "义务教育数学课程标准（2022年版）（教育部，PDF全文）",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202204/W020220420582346895190.pdf",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s2",
   "title": "教育部关于印发义务教育课程方案和课程标准（2022年版）的通知",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202204/t20220420_619921.html",
   "kind": "official_explainer",
   "accessed": "2026-09-28"
  },
  {
   "id": "s3",
   "title": "普通高中数学课程标准（2017年版2020年修订）（PDF全文，浙江师范大学转载）",
   "url": "https://aeq.zjnu.edu.cn/_upload/article/files/0a/1f/7ca305bb4dd39f15ee4bd431f595/10b2f569-154b-4397-a33d-d2880c2d2d11.pdf",
   "kind": "standard",
   "accessed": "2026-09-28"
  },
  {
   "id": "s4",
   "title": "教育部关于印发普通高中课程方案和语文等学科课程标准（2017年版2020年修订）的通知",
   "url": "http://www.moe.gov.cn/srcsite/A26/s8001/202006/t20200603_462199.html",
   "kind": "official_explainer",
   "accessed": "2026-09-28"
  },
  {
   "id": "s5",
   "title": "人教版 一年级数学上册（2024秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs1s_2024/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s6",
   "title": "人教版 一年级数学下册（2025春版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs1x_2025/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s7",
   "title": "人教版 二年级数学上册（2025秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs2s_2025/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s8",
   "title": "人教版 二年级数学下册（2026春版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs2x_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s9",
   "title": "人教版 三年级数学上册（2025秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs3s_2025/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s10",
   "title": "人教版 三年级数学下册（2026春版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs3x_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s11",
   "title": "人教版 四年级数学上册（2026秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs4s_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s12",
   "title": "人教版 四年级数学下册（旧版，2013版课标教材）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs4x_new/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s13",
   "title": "人教版 五年级数学上册（2026秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs5s_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s14",
   "title": "人教版 五年级数学下册（旧版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs5x_new/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s15",
   "title": "人教版 六年级数学上册（2026秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs6s_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s16",
   "title": "人教版 六年级数学下册（旧版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xs6x_new/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s17",
   "title": "人教版 七年级数学上册（2024秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xc7s_2024/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s18",
   "title": "人教版 七年级数学下册（2025春版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xc7x_2025/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s19",
   "title": "人教版 八年级数学上册（2025秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xc8s_2025/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s20",
   "title": "人教版 八年级数学下册（2026春版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xc8x_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s21",
   "title": "人教版 九年级数学上册（2026秋版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xc9s_2026/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s22",
   "title": "人教版 九年级数学下册（旧版）目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/xc9x/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s23",
   "title": "人教A版 普通高中教科书 数学 必修第一册 目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/gzabx1/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s24",
   "title": "人教A版 普通高中教科书 数学 必修第二册 目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/gzabx2/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s25",
   "title": "人教A版 普通高中教科书 数学 选择性必修第一册 目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/gzaxzxbx1/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s26",
   "title": "人教A版 普通高中教科书 数学 选择性必修第二册 目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/gzaxzxbx2/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  },
  {
   "id": "s27",
   "title": "人教A版 普通高中教科书 数学 选择性必修第三册 目录（电子课本网转载人教社教材目录）",
   "url": "http://www.dzkbw.com/books/rjb/shuxue/gzaxzxbx3/",
   "kind": "textbook",
   "accessed": "2026-09-28"
  }
 ],
 "core_competencies": [
  {
   "name": "会用数学的眼光观察现实世界",
   "summary": "义务教育核心素养总述之一：主要表现为抽象能力（小学为数感、量感、符号意识）、几何直观、空间观念与创新意识。",
   "source": "s1"
  },
  {
   "name": "会用数学的思维思考现实世界",
   "summary": "主要表现为运算能力、推理能力（小学为推理意识），体会数学的严谨与逻辑。",
   "source": "s1"
  },
  {
   "name": "会用数学的语言表达现实世界",
   "summary": "主要表现为数据观念（小学为数据意识）、模型观念（小学为模型意识）与应用意识。",
   "source": "s1"
  },
  {
   "name": "小学阶段核心素养表现",
   "summary": "数感、量感、符号意识、运算能力、几何直观、空间观念、推理意识、数据意识、模型意识、应用意识、创新意识。",
   "source": "s1"
  },
  {
   "name": "初中阶段核心素养表现",
   "summary": "抽象能力、运算能力、几何直观、空间观念、推理能力、数据观念、模型观念、应用意识、创新意识。",
   "source": "s1"
  },
  {
   "name": "数学抽象",
   "summary": "从数量关系与空间形式中抽象出数学概念、规律和结构，并用数学语言表征。",
   "source": "s3"
  },
  {
   "name": "逻辑推理",
   "summary": "依据规则由已知事实和命题推出新命题，包括归纳、类比与演绎，是数学严谨性的保证。",
   "source": "s3"
  },
  {
   "name": "数学建模",
   "summary": "把现实问题抽象为数学问题，建立并求解模型、检验改进，最终解决实际问题。",
   "source": "s3"
  },
  {
   "name": "直观想象",
   "summary": "借助几何直观和空间想象感知事物形态与变化，用图形理解和解决数学问题。",
   "source": "s3"
  },
  {
   "name": "数学运算",
   "summary": "在明晰运算对象的基础上依据法则解决问题，包括理解对象、掌握法则、设计运算程序、求得结果。",
   "source": "s3"
  },
  {
   "name": "数据分析",
   "summary": "针对研究对象获取数据，运用统计方法整理、分析和推断，形成关于研究对象的知识。",
   "source": "s3"
  }
 ],
 "stages": [
  {
   "name": "第一学段",
   "grades": [
    1,
    2
   ],
   "domains": [
    {
     "name": "数与代数",
     "requirements": [
      "在情境中理解万以内数的意义和数位含义，知道算盘可表示多位数",
      "理解<、=、>的含义，会比较万以内数的大小",
      "了解四则运算的意义，感悟运算之间的关系",
      "探索加减法算理，会整数加减法；熟练口算20以内加减法和表内乘除法",
      "会口算简单的百以内加减法，会计算两位数和三位数的加减法",
      "在生活情境中用数和运算解决问题，解释结果的实际意义",
      "探索用数或符号表达简单情境中的变化规律"
     ],
     "source": "s1"
    },
    {
     "name": "图形与几何",
     "requirements": [
      "通过实物和模型辨认长方体、正方体、圆柱、球等立体图形",
      "辨认长方形、正方形、平行四边形、三角形、圆等平面图形并简单分类",
      "会用简单图形拼图，说出立体图形某个面对应的平面图形",
      "体会统一长度单位的重要性，认识米、厘米，会估测并测量长度"
     ],
     "source": "s1"
    },
    {
     "name": "统计与概率",
     "requirements": [
      "会对物体、图形或数据按一定标准分类，了解分类与标准的关系",
      "能用语言简单描述分类过程，形成初步的数据意识"
     ],
     "source": "s1"
    },
    {
     "name": "综合与实践",
     "requirements": [
      "主题活动：数学游戏分享，衔接幼儿园与小学",
      "欢乐购物街：认识人民币元角分及简单换算",
      "时间在哪里：认识时、分、秒，体会时间长短",
      "我的教室：用上下左右前后描述位置，认识东南西北",
      "身体上的尺子、数学连环画：测量与用数学记录生活"
     ],
     "source": "s1"
    }
   ],
   "teaching_suggestions": [
    "充分考虑幼儿园经验，设计活动化、游戏化、生活化的学习，做好幼小衔接",
    "数的认识借助小方块、圆片、小棒等实物对应表示数量，再过渡到数字符号",
    "10以内数的教学重点是体验从数量到数的抽象，理解十进制与位值",
    "让学生感悟加减运算在相同数位上进行，理解减法是加法的逆运算、乘法是加法的简便运算",
    "图形教学以直观感知为主，鼓励动手操作；测量教学先用非标准单位再用统一单位",
    "综合与实践宜设计多学时长程活动，关注过程性评价"
   ],
   "assessment": [
    "能认、读、写万以内的数并比较大小，理解四则运算含义，形成初步数感和运算能力",
    "能辨认常见立体与平面图形，会估测和测量长度，形成初步量感和空间观念",
    "能按标准对事物或数据分类，形成初步数据意识",
    "认识人民币、时间单位和基本方向，能尝试用数学方法解决生活问题",
    "对数学产生好奇心和兴趣，形成初步的合作交流与独立思考习惯"
   ]
  },
  {
   "name": "第二学段",
   "grades": [
    3,
    4
   ],
   "domains": [
    {
     "name": "数与代数",
     "requirements": [
      "认识万以上的数，了解十进制计数法，会用万、亿为单位表示大数",
      "掌握多位数的乘法，能计算两位数乘三位数、三位数除以两位数",
      "初步认识小数和分数，会同分母分数加减和一位小数加减",
      "理解四则运算意义，能进行整数四则混合运算（以两步为主，不超过三步）",
      "探索并理解加法、乘法交换律结合律和乘法分配律，会用字母表示运算律",
      "能选择合适单位进行简单估算，借助计算器解决问题并探索规律",
      "认识总量=分量+分量、总价=单价×数量、路程=速度×时间等数量关系",
      "在具体情境中了解等量的等量相等，形成初步推理意识"
     ],
     "source": "s1"
    },
    {
     "name": "图形与几何",
     "requirements": [
      "认识线段、射线和直线，知道两点之间线段最短，会用尺规作等长线段",
      "认识角，会用量角器量角、画角，认识直角、锐角、钝角、平角、周角",
      "认识千米、分米、毫米和面积单位厘米²、分米²、米²并会换算",
      "认识三角形和四边形并按特征分类，认识平行四边形、梯形",
      "认识周长和面积，掌握长方形、正方形的周长和面积公式",
      "辨认从不同方向观察简单物体所得的形状",
      "结合实例感受平移、旋转、轴对称现象"
     ],
     "source": "s1"
    },
    {
     "name": "统计与概率",
     "requirements": [
      "经历简单的数据收集、整理、描述和分析过程",
      "认识条形统计图，会用条形统计图表示和分析数据",
      "能读懂报纸、电视、互联网中的简单统计图表",
      "探索平均数的意义，能用平均数解决简单实际问题"
     ],
     "source": "s1"
    },
    {
     "name": "综合与实践",
     "requirements": [
      "年、月、日的秘密：认识24时计时法和年月日关系",
      "曹冲称象的故事：认识克、千克、吨，体会等量代换",
      "寻找“宝藏”：认识东北、西北、东南、西南方向",
      "度量衡的故事：了解度量衡统一的意义与计量单位历史"
     ],
     "source": "s1"
    }
   ],
   "teaching_suggestions": [
    "在认识整数基础上认识小数和分数，感悟计数单位与运算的一致性",
    "利用乘法理解算理与算法的关系，除法中体会除法是乘法的逆运算",
    "用归纳法探索运算律、用字母表示运算律，形成初步代数思维",
    "结合真实情境建立加法模型和乘法模型，估算重在解决实际问题",
    "图形的认识与测量有机融合，借助尺规作图探索三角形周长",
    "综合与实践可用问题引领，设计多学时长程活动并关注创新性评价"
   ],
   "assessment": [
    "能读写万以上数，初步认识小数分数，能进行整数四则运算和简单小数分数加减法",
    "能用四则混合运算解决问题，能用常见数量关系解决实际问题",
    "能描述三角形和四边形特征，计算长方形正方形周长面积，形成量感和几何直观",
    "能分析和表达数据信息，会用条形统计图和平均数，形成初步数据意识",
    "认识时间单位、质量单位和八个方向，尝试综合运用知识解决问题"
   ]
  },
  {
   "name": "第三学段",
   "grades": [
    5,
    6
   ],
   "domains": [
    {
     "name": "数与代数",
     "requirements": [
      "知道2、3、5的倍数特征，了解公倍数、公因数、奇数偶数、质数合数",
      "理解小数和分数的意义，会进行小数、分数的转化",
      "结合情境理解整数除法与分数的关系",
      "能进行简单的小数、分数四则运算和混合运算（不超过三步）",
      "根据情境理解等式的基本性质",
      "会选择合适的方法进行估算",
      "用字母表示事物的关系、性质和规律，感悟用字母表示的一般性",
      "理解比和比例，能解决按比例分配的简单问题",
      "认识成正比的量，能探索y=kx形式的规律和变化趋势"
     ],
     "source": "s1"
    },
    {
     "name": "图形与几何",
     "requirements": [
      "知道三角形任意两边之和大于第三边、三角形内角和是180°",
      "认识圆和扇形，会用圆规画圆，认识圆周率，探索圆的周长和面积公式",
      "认识千米²、公顷，探索平行四边形、三角形、梯形面积公式，会估计不规则图形面积",
      "了解体积（容积）及其单位并会换算，体验不规则物体体积的测量",
      "认识长方体、正方体、圆柱、圆锥及其展开图，掌握体积和表面积公式",
      "辨认简单物体从前面、侧面、上面看到的形状图",
      "能根据方向和距离确定位置，用有序数对（限自然数）表示点的位置",
      "了解比例尺，在方格纸上按比例放大缩小图形",
      "在方格纸上进行平移和旋转，认识轴对称图形和对称轴并补全图形"
     ],
     "source": "s1"
    },
    {
     "name": "统计与概率",
     "requirements": [
      "经历数据收集、整理、分析的过程，能合理解释结论",
      "认识折线统计图、扇形统计图，能选择合适的统计图表示数据",
      "结合具体情境探索百分数的意义，解决与百分数有关的问题",
      "通过实例感受简单随机现象，定性描述其发生可能性的大小"
     ],
     "source": "s1"
    },
    {
     "name": "综合与实践",
     "requirements": [
      "如何表达具有相反意义的量：在情境中了解负数",
      "校园平面图：综合运用比例尺、方向、测量绘制平面图",
      "体育中的数学：收集赛事数据，提出并解决数学问题",
      "项目学习：营养午餐、水是生命之源（调查、方案设计）"
     ],
     "source": "s1"
    }
   ],
   "teaching_suggestions": [
    "通过整数运算感悟数的性质，统筹整数、小数、分数运算，感悟计数单位与运算的一致性",
    "分数加减教学中理解通分是为得到相同计数单位",
    "用字母表示的教学要设计真实情境，形成初步代数思维",
    "比和比例借助照片放大缩小、配料比例等生活情境理解",
    "成正比的量引导用y/x=k和y=kx表达，并在方格纸上画图，为初中函数积累经验",
    "图形测量中运用转化思想推导面积公式，操作中理解体积表面积",
    "引导学生经历圆周长与直径之比为定值的探索，讲述祖冲之的故事",
    "第三学段可适当采用项目式学习"
   ],
   "assessment": [
    "认识自然数特征，理解小数和分数，能进行小数分数四则运算，感悟运算一致性",
    "能用字母表示数量关系和规律，理解比和比例，形成符号意识与推理意识",
    "能计算常见图形周长、面积、体积，描述图形位置和运动，形成空间观念和几何直观",
    "会用统计图表和百分数表达数据，对随机现象可能性作定性描述",
    "了解负数，初步学会用数学眼光观察并综合运用知识解决现实问题"
   ]
  },
  {
   "name": "第四学段",
   "grades": [
    7,
    8,
    9
   ],
   "domains": [
    {
     "name": "数与代数",
     "requirements": [
      "理解负数、有理数，借助数轴理解相反数和绝对值",
      "掌握有理数加减乘除乘方及简单混合运算（以三步以内为主），运用运算律",
      "了解无理数和实数，实数与数轴上的点一一对应",
      "了解平方根、算术平方根、立方根，会用根号表示并用计算器计算",
      "了解近似数，会进行简单近似计算",
      "了解二次根式、最简二次根式，会进行简单四则运算",
      "借助情境理解代数式，会代入求值，了解整数指数幂和科学记数法",
      "掌握整式加减、简单整式乘法，理解平方差和完全平方公式",
      "能用提公因式法、公式法（不超过二次）进行因式分解",
      "了解分式和最简分式，会约分、通分及简单分式四则运算",
      "能列方程解决实际问题，掌握等式基本性质，解一元一次方程和可化为一元一次方程的分式方程",
      "掌握消元法解二元一次方程组（*三元一次方程组选学）",
      "会用配方法、公式法、因式分解法解一元二次方程，会用判别式判断根的情况",
      "了解一元二次方程根与系数的关系，能检验方程解的合理性",
      "理解不等式的性质，会解一元一次不等式（组）并在数轴上表示解集",
      "了解常量、变量和函数的概念与表示法，会求自变量取值范围和函数值",
      "理解一次函数和正比例函数，会用待定系数法，理解k、b对图象的影响",
      "体会一次函数与二元一次方程的关系，用一次函数解决实际问题",
      "会画二次函数图象，用配方法求顶点、开口、对称轴和最值",
      "知道二次函数与一元二次方程的关系，用图象求近似解",
      "理解反比例函数y=k/x的图象和性质，并解决简单实际问题"
     ],
     "source": "s1"
    },
    {
     "name": "图形与几何",
     "requirements": [
      "了解点、线、面、角，掌握两点确定一条直线、两点之间线段最短",
      "会度量角，理解余角、补角、对顶角的性质",
      "理解垂线、垂线段，掌握平行线基本事实，探索并证明平行线判定与性质",
      "会基本尺规作图：作等角、角平分线、垂直平分线、过点作垂线和平行线",
      "理解三角形有关概念，证明三角形内角和定理及其推论",
      "掌握三角形全等的基本事实（SAS、ASA、SSS），证明AAS和HL",
      "证明角平分线、线段垂直平分线、等腰三角形和等边三角形的性质与判定",
      "探索勾股定理及其逆定理，用来解决简单实际问题",
      "掌握多边形内角和外角和公式，探索并证明平行四边形、矩形、菱形、正方形的性质与判定",
      "证明三角形中位线定理",
      "理解圆、弧、弦、圆心角、圆周角，证明垂径定理，探索圆周角定理",
      "了解点与圆、直线与圆的位置关系，掌握切线概念，了解三角形内心外心",
      "会计算弧长和扇形面积，了解正多边形与圆的关系",
      "了解定义、命题、定理、逆命题和反例，理解证明的必要性，会综合法证明",
      "理解轴对称、旋转、中心对称、平移的基本性质并进行图案设计",
      "了解比例性质和相似多边形，掌握相似三角形判定与性质，了解位似",
      "认识锐角三角函数sinA、cosA、tanA，记住30°、45°、60°的三角函数值，解直角三角形",
      "了解中心投影和平行投影，会画和判断简单物体的三视图，了解展开图",
      "理解平面直角坐标系，能用坐标描述位置和图形的对称、平移、位似变换"
     ],
     "source": "s1"
    },
    {
     "name": "统计与概率",
     "requirements": [
      "体会抽样的必要性，认识简单随机抽样",
      "会制作扇形统计图，能用统计图表有效描述数据",
      "理解平均数、中位数、众数，会计算加权平均数",
      "会计算离差平方和与方差，体会刻画离散程度的意义",
      "了解频数与频数分布，会画频数直方图并解释信息",
      "体会用样本平均数、样本方差估计总体",
      "会计算四分位数，了解四分位数与箱线图的关系",
      "通过表格、折线图、趋势图感受随机现象的变化趋势",
      "能用列表、画树状图列举简单随机事件的所有结果并计算概率",
      "知道通过大量重复试验可以用频率估计概率"
     ],
     "source": "s1"
    },
    {
     "name": "综合与实践",
     "requirements": [
      "以项目式学习为主，在真实情境中综合运用方程、函数、几何、统计等知识",
      "经历发现提出问题、建立模型、求解检验的完整过程",
      "能撰写研究报告，发展应用意识、模型观念与创新意识"
     ],
     "source": "s1"
    }
   ],
   "teaching_suggestions": [
    "把握数与式的整体性，借助数轴体会数形结合，通过字母运算建立符号意识",
    "方程与不等式教学要经历从实际问题中建立数量关系的过程，感悟算术与代数的差异",
    "函数教学借助平面直角坐标系描点，理解函数与方程、不等式的关系",
    "几何教学引导理解欧氏几何的基本思想：通过定义和基本事实确定论证起点，经历证明",
    "图形变化教学借助信息技术演示，理解对称、旋转、平移的不变性",
    "统计教学从实例出发，理解样本估计总体；概率教学由定性走向定量",
    "项目式学习要选合适项目，关注学生能否提出和解决问题，与信息科技等学科合作"
   ],
   "assessment": [
    "能从生活情境抽象出数与式、方程与不等式、函数，掌握运算方法并合理解释结果",
    "能用几何图形基本性质进行推理证明，初步掌握几何证明方法，发展几何直观与空间观念",
    "知道频数、频率和概率的意义，能进行简单的数据分析，形成数据观念",
    "能综合运用数学及其他学科知识提出问题、设计方案并作出合理解释",
    "增强学好数学的自信心，养成独立思考、合作探究、批判质疑的学习习惯"
   ]
  },
  {
   "name": "高中必修",
   "grades": [
    10
   ],
   "domains": [
    {
     "name": "预备知识",
     "requirements": [
      "了解集合含义，理解子集、并集、交集、补集，会用Venn图",
      "理解充分条件、必要条件、充要条件与全称量词、存在量词及其否定",
      "梳理等式性质，掌握不等式性质和基本不等式并求简单最值",
      "从函数观点看一元二次方程和不等式，借助二次函数求解一元二次不等式"
     ],
     "source": "s3"
    },
    {
     "name": "函数",
     "requirements": [
      "用集合语言和对应关系刻画函数，了解分段函数，会求简单定义域",
      "理解单调性、最值，了解奇偶性和周期性",
      "了解幂函数，掌握指数幂运算，理解指数函数、对数的概念与运算性质",
      "了解对数函数，知道其与指数函数互为反函数",
      "了解任意角与弧度制，借助单位圆理解三角函数定义、图象和性质，推导诱导公式",
      "理解同角三角函数关系，推导两角和差及二倍角公式并进行简单恒等变换",
      "了解y=Asin(ωx+φ)中参数的意义，用三角函数构建周期变化模型",
      "了解函数零点与方程解的关系和零点存在定理，会用二分法求近似解",
      "理解函数模型，比较指数、对数、一次函数增长差异，用函数建模解决问题"
     ],
     "source": "s3"
    },
    {
     "name": "几何与代数",
     "requirements": [
      "理解平面向量概念、线性运算、数量积及几何意义",
      "理解平面向量基本定理和坐标表示，用向量解决几何与物理问题",
      "借助向量推导余弦定理、正弦定理并解三角形",
      "理解复数概念、几何意义和四则运算（复数三角表示为选学）",
      "认识柱、锥、台、球结构特征，会画直观图，知道表面积和体积公式",
      "理解空间点、直线、平面的位置关系，掌握平行、垂直的判定与性质"
     ],
     "source": "s3"
    },
    {
     "name": "概率与统计",
     "requirements": [
      "理解简单随机抽样和分层抽样，了解获取数据的途径",
      "会用统计图表、百分位数、平均数、方差等估计总体",
      "理解样本空间、随机事件及其关系与运算，掌握古典概型",
      "了解概率的基本性质和事件的独立性，用频率估计概率和随机模拟"
     ],
     "source": "s3"
    },
    {
     "name": "数学建模活动与数学探究活动",
     "requirements": [
      "经历数学建模全过程：提出问题、建立模型、求解、检验、改进",
      "完成一个数学建模或数学探究课题并撰写报告"
     ],
     "source": "s3"
    }
   ],
   "teaching_suggestions": [
    "帮助学生完成从初中到高中数学学习的过渡，包括知识技能、方法习惯和能力态度",
    "教学目标制定要突出数学学科核心素养",
    "情境创设和问题设计要有利于发展核心素养",
    "整体把握教学内容，促进核心素养的连续性和阶段性发展",
    "既重视教更重视学，促进学生学会学习",
    "重视信息技术运用，实现信息技术与数学课程深度融合"
   ],
   "assessment": [
    "学业质量分三个水平，每个水平由六大核心素养的表现综合刻画",
    "学业质量水平一是高中毕业要求，是学业水平考试（合格性）的命题依据",
    "评价从情境与问题、知识与技能、思维与表达、交流与反思四个方面考查",
    "评价应关注过程与结果，注重多元方式和结果的合理利用"
   ]
  },
  {
   "name": "高中选择性必修",
   "grades": [
    11,
    12
   ],
   "domains": [
    {
     "name": "函数",
     "requirements": [
      "理解数列概念，掌握等差数列和等比数列的通项与前n项和，了解数学归纳法",
      "理解导数概念和几何意义，会求基本初等函数导数和简单复合函数导数",
      "用导数研究函数单调性、极值、最值，体会微积分的思想"
     ],
     "source": "s3"
    },
    {
     "name": "几何与代数",
     "requirements": [
      "理解空间向量及其运算、基本定理和坐标表示",
      "用空间向量研究直线平面位置关系及距离、夹角问题",
      "理解直线倾斜角与斜率，掌握直线方程的几种形式和距离公式",
      "掌握圆的标准方程和一般方程，判断直线与圆、圆与圆的位置关系",
      "掌握椭圆、双曲线、抛物线的定义、标准方程和简单几何性质"
     ],
     "source": "s3"
    },
    {
     "name": "概率与统计",
     "requirements": [
      "理解分类加法与分步乘法计数原理，掌握排列、组合和二项式定理",
      "了解条件概率、全概率公式，理解离散型随机变量分布列、均值和方差",
      "掌握二项分布和超几何分布，了解正态分布",
      "了解成对数据的相关性和样本相关系数，了解一元线性回归模型与最小二乘法",
      "了解2×2列联表与独立性检验"
     ],
     "source": "s3"
    },
    {
     "name": "数学建模活动与数学探究活动",
     "requirements": [
      "完成一个数学建模或数学探究课题，形成研究报告或小论文"
     ],
     "source": "s3"
    }
   ],
   "teaching_suggestions": [
    "依托函数、几何与代数、概率与统计三条主线整体设计单元教学",
    "注重知识的形成过程和数学文化的融入",
    "通过数学建模和探究活动发展学生提出、分析和解决问题的能力",
    "合理使用信息技术辅助探究图形、数据和函数性质"
   ],
   "assessment": [
    "学业质量水平二是高考的要求和命题依据",
    "学业质量水平三可作为大学自主招生的参考",
    "考试命题应以核心素养为导向，重视情境和问题的设计"
   ]
  }
 ],
 "grade_topics": {
  "1": {
   "topics": [
    "数学游戏（入学准备）",
    "5以内数的认识和加、减法",
    "6～10的认识和加、减法",
    "认识立体图形",
    "11～20的认识",
    "20以内的进位加法",
    "认识平面图形",
    "20以内的退位减法",
    "100以内数的认识",
    "100以内的口算加、减法",
    "100以内的笔算加、减法",
    "数量间的加减关系",
    "认识人民币（欢乐购物街）"
   ],
   "source": "s5,s6",
   "basis": "textbook"
  },
  "2": {
   "topics": [
    "分类与整理",
    "1～6的表内乘法",
    "1～6的表内除法",
    "认识东、南、西、北（校园小导游）",
    "厘米和米",
    "身体上的尺子",
    "7～9的表内乘、除法",
    "认识时间（时间在哪里）",
    "有余数的除法",
    "数量间的乘除关系",
    "万以内数的认识",
    "万以内的加法和减法",
    "数学连环画"
   ],
   "source": "s7,s8",
   "basis": "textbook"
  },
  "3": {
   "topics": [
    "观察物体",
    "混合运算",
    "毫米、分米和千米",
    "认识质量单位（曹冲称象的故事）",
    "多位数乘一位数",
    "数字编码",
    "线和角",
    "分数的初步认识",
    "搭配问题",
    "生活中的运动现象（平移、旋转）",
    "除数是一位数的除法",
    "长方形和正方形（周长）",
    "图形的面积",
    "数据的收集与整理",
    "年、月、日的秘密",
    "小数的初步认识"
   ],
   "source": "s9,s10",
   "basis": "textbook"
  },
  "4": {
   "topics": [
    "万以上数的认识",
    "角的度量",
    "多位数乘两位数",
    "加法模型和乘法模型",
    "平行四边形和梯形",
    "条形统计图",
    "寻找宝藏（方向与位置）",
    "四则运算",
    "运算律",
    "小数的意义和性质",
    "三角形（特性、分类、内角和）",
    "小数的加法和减法",
    "轴对称与平移",
    "平均数与复式条形统计图",
    "鸡兔同笼"
   ],
   "source": "s11,s12",
   "basis": "textbook"
  },
  "5": {
   "topics": [
    "观察简单组合体",
    "小数乘法",
    "小数除法",
    "图形的运动（平移、旋转、轴对称）",
    "用字母表示数和数量关系",
    "多边形的面积",
    "可能性",
    "因数与倍数",
    "长方体和正方体",
    "分数的意义和性质",
    "分数的加法和减法",
    "折线统计图",
    "找次品"
   ],
   "source": "s13,s14",
   "basis": "textbook"
  },
  "6": {
   "topics": [
    "确定位置",
    "分数乘法",
    "分数除法",
    "负数",
    "圆",
    "体育中的数学",
    "百分数",
    "百分数的应用（折扣、成数、税率、利率）",
    "圆柱与圆锥",
    "比例",
    "鸽巢问题",
    "小学数学总复习"
   ],
   "source": "s15,s16",
   "basis": "textbook"
  },
  "7": {
   "topics": [
    "有理数",
    "有理数的运算",
    "代数式",
    "整式的加减",
    "一元一次方程",
    "几何图形初步",
    "相交线与平行线",
    "实数",
    "平面直角坐标系",
    "二元一次方程组",
    "不等式与不等式组",
    "数据的收集、整理与描述"
   ],
   "source": "s17,s18",
   "basis": "textbook"
  },
  "8": {
   "topics": [
    "三角形",
    "全等三角形",
    "轴对称",
    "整式的乘法",
    "因式分解",
    "分式",
    "二次根式",
    "勾股定理",
    "四边形",
    "函数",
    "一次函数",
    "数据的分析"
   ],
   "source": "s19,s20",
   "basis": "textbook"
  },
  "9": {
   "topics": [
    "一元二次方程",
    "二次函数",
    "反比例函数",
    "旋转",
    "圆（圆的有关性质、弧长和扇形面积）",
    "直线与圆的位置关系",
    "相似",
    "锐角三角函数",
    "投影与视图",
    "概率初步"
   ],
   "source": "s21,s22",
   "basis": "textbook"
  },
  "10": {
   "topics": [
    "集合与常用逻辑用语",
    "一元二次函数、方程和不等式",
    "函数的概念与性质",
    "指数函数与对数函数",
    "三角函数",
    "平面向量及其应用",
    "复数",
    "立体几何初步",
    "统计",
    "概率"
   ],
   "source": "s23,s24",
   "basis": "textbook"
  },
  "11": {
   "topics": [
    "空间向量与立体几何",
    "直线和圆的方程",
    "圆锥曲线的方程",
    "数列",
    "一元函数的导数及其应用"
   ],
   "source": "s25,s26",
   "basis": "textbook"
  },
  "12": {
   "topics": [
    "计数原理",
    "随机变量及其分布",
    "成对数据的统计分析",
    "高考总复习"
   ],
   "source": "s27",
   "basis": "textbook"
  }
 },
 "prerequisites": {
  "20以内的进位加法": [
   "11～20的认识",
   "6～10的认识和加、减法"
  ],
  "20以内的退位减法": [
   "20以内的进位加法"
  ],
  "100以内的笔算加、减法": [
   "100以内数的认识",
   "100以内的口算加、减法"
  ],
  "1～6的表内乘法": [
   "100以内的口算加、减法"
  ],
  "1～6的表内除法": [
   "1～6的表内乘法"
  ],
  "有余数的除法": [
   "7～9的表内乘、除法"
  ],
  "万以内的加法和减法": [
   "万以内数的认识",
   "100以内的笔算加、减法"
  ],
  "多位数乘一位数": [
   "7～9的表内乘、除法",
   "万以内数的认识"
  ],
  "除数是一位数的除法": [
   "有余数的除法",
   "多位数乘一位数"
  ],
  "多位数乘两位数": [
   "多位数乘一位数"
  ],
  "四则运算": [
   "混合运算",
   "多位数乘两位数"
  ],
  "图形的面积": [
   "长方形和正方形（周长）",
   "7～9的表内乘、除法"
  ],
  "平行四边形和梯形": [
   "线和角",
   "角的度量"
  ],
  "小数的意义和性质": [
   "小数的初步认识",
   "万以上数的认识"
  ],
  "小数乘法": [
   "小数的意义和性质",
   "多位数乘两位数"
  ],
  "小数除法": [
   "小数乘法",
   "除数是一位数的除法"
  ],
  "多边形的面积": [
   "图形的面积",
   "平行四边形和梯形",
   "三角形（特性、分类、内角和）"
  ],
  "因数与倍数": [
   "7～9的表内乘、除法",
   "除数是一位数的除法"
  ],
  "分数的意义和性质": [
   "分数的初步认识",
   "因数与倍数"
  ],
  "分数的加法和减法": [
   "分数的意义和性质"
  ],
  "分数乘法": [
   "分数的加法和减法",
   "小数乘法"
  ],
  "分数除法": [
   "分数乘法"
  ],
  "百分数": [
   "分数除法",
   "小数除法"
  ],
  "长方体和正方体": [
   "图形的面积",
   "观察物体"
  ],
  "圆": [
   "多边形的面积",
   "小数乘法"
  ],
  "圆柱与圆锥": [
   "圆",
   "长方体和正方体"
  ],
  "比例": [
   "分数除法",
   "用字母表示数和数量关系"
  ],
  "有理数": [
   "负数",
   "分数的意义和性质"
  ],
  "有理数的运算": [
   "有理数",
   "运算律",
   "分数除法"
  ],
  "代数式": [
   "用字母表示数和数量关系",
   "有理数的运算"
  ],
  "整式的加减": [
   "代数式"
  ],
  "一元一次方程": [
   "整式的加减"
  ],
  "相交线与平行线": [
   "几何图形初步"
  ],
  "实数": [
   "有理数的运算"
  ],
  "平面直角坐标系": [
   "有理数",
   "确定位置"
  ],
  "二元一次方程组": [
   "一元一次方程"
  ],
  "不等式与不等式组": [
   "一元一次方程"
  ],
  "三角形": [
   "相交线与平行线",
   "三角形（特性、分类、内角和）"
  ],
  "全等三角形": [
   "三角形"
  ],
  "因式分解": [
   "整式的乘法"
  ],
  "分式": [
   "因式分解",
   "分数的加法和减法"
  ],
  "二次根式": [
   "实数",
   "整式的乘法"
  ],
  "勾股定理": [
   "二次根式",
   "三角形"
  ],
  "四边形": [
   "全等三角形",
   "相交线与平行线"
  ],
  "一次函数": [
   "函数",
   "平面直角坐标系",
   "二元一次方程组"
  ],
  "一元二次方程": [
   "因式分解",
   "二次根式"
  ],
  "二次函数": [
   "一次函数",
   "一元二次方程"
  ],
  "反比例函数": [
   "函数",
   "分式",
   "比例"
  ],
  "相似": [
   "比例",
   "全等三角形",
   "四边形"
  ],
  "锐角三角函数": [
   "相似",
   "勾股定理"
  ],
  "函数的概念与性质": [
   "集合与常用逻辑用语",
   "一次函数",
   "二次函数",
   "反比例函数"
  ],
  "指数函数与对数函数": [
   "函数的概念与性质",
   "二次根式"
  ],
  "三角函数": [
   "锐角三角函数",
   "函数的概念与性质",
   "圆（圆的有关性质、弧长和扇形面积）"
  ],
  "平面向量及其应用": [
   "三角函数",
   "平面直角坐标系"
  ],
  "复数": [
   "实数",
   "一元二次方程",
   "平面向量及其应用"
  ],
  "立体几何初步": [
   "投影与视图",
   "相交线与平行线",
   "圆柱与圆锥"
  ],
  "圆锥曲线的方程": [
   "直线和圆的方程",
   "一元二次函数、方程和不等式"
  ],
  "一元函数的导数及其应用": [
   "函数的概念与性质",
   "指数函数与对数函数",
   "三角函数",
   "数列"
  ],
  "随机变量及其分布": [
   "计数原理",
   "概率"
  ],
  "成对数据的统计分析": [
   "统计",
   "随机变量及其分布"
  ]
 },
 "notes": [
  "prerequisites 为编辑整理（editorial），依据一般数学知识逻辑与人教版编排顺序给出，非课程标准原文。",
  "s1 为教育部官网扫描版PDF（无文字层），内容经逐页阅读后转述；学段要求、学业质量、教学建议均为意译而非原文。",
  "义务教育课标按“六三”学制学段编排；“五四”学制按标准另行对应，本文件仅用六三学制。",
  "义务教育“数与代数”在小学分“数与运算”“数量关系”两主题，初中分“数与式”“方程与不等式”“函数”三主题；图形与几何、统计与概率亦有子主题，本文件按四大领域归并。",
  "2022版课标下小学不再要求解方程（新版五上为“用字母表示数和数量关系”），负数在第三学段以综合与实践主题呈现。",
  "人教社官网 pep.com.cn 访问时返回系统维护页，教材目录取自电子课本网（dzkbw.com）转载的人教版目录，建议后续以人教社官方目录核对。",
  "人教版新教材（依据2022版课标）分年度换版：截至2026秋，一至三年级、四至六年级上册、七至八年级、九年级上册为新版；四、五、六年级下册和九年级下册目录仍为旧版（预计2027年换新），相关年级的单元归属可能变化。",
  "新版四年级上册未见“除数是两位数的除法”单元、新版六年级上册未见单独的“比”与“位置与方向”单元，推测已调整至其他册次，待新版下册发布后核实。",
  "九年级“概率初步”在旧版位于九上，新版九上目录未含，暂列入九年级（位置为估计）；新版“反比例函数”已由九下移至九上。",
  "高中按人教A版映射：高一学必修第一、二册；高二学选择性必修第一、二册；选择性必修第三册常在高二下或高三上学习，电子课本网标注为高三，各地安排不一；“高考总复习”为高三通常安排（estimate）。",
  "高中选修课程（A～E类，含微积分、空间向量与代数、应用统计、大学先修课程等）未纳入 grade_topics；选修不作高考要求。",
  "高中课标另有2025年修订版的报道，本文件仍以2017年版2020年修订为准，未核验新修订内容。",
  "grade_topics 的 source 字段可能含两个来源编号（上册、下册），以逗号分隔。",
  "课标中标*的内容（如三元一次方程组、复数的三角表示）为选学，不作考试要求。"
 ]
}
===== FILE: docs/reviews/curriculum1_data_summary.txt =====
biology.json: 生物学 grades [7, 12], stages 7, topics 35, grade basis {'textbook': 4, 'estimate': 2}, sources 15
chemistry.json: 化学 grades [9, 12], stages 6, topics 33, grade basis {'textbook': 4}, sources 14
chinese.json: 语文 grades [1, 12], stages 7, topics 134, grade basis {'textbook': 12}, sources 27
english.json: 英语 grades [3, 12], stages 6, topics 124, grade basis {'textbook': 10}, sources 7
geography.json: 地理 grades [7, 12], stages 4, topics 200, grade basis {'textbook': 5}, sources 14
history.json: 历史 grades [7, 12], stages 4, topics 309, grade basis {'textbook': 6}, sources 16
information_technology.json: 信息科技/信息技术 grades [3, 12], stages 7, topics 206, grade basis {'estimate': 6, 'textbook': 3}, sources 13
math.json: 数学 grades [1, 12], stages 6, topics 135, grade basis {'textbook': 12}, sources 27
morality_politics.json: 道德与法治/思想政治 grades [1, 12], stages 7, topics 397, grade basis {'textbook': 12}, sources 30
pedagogy: grades [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], sources 13
physics.json: 物理 grades [8, 12], stages 8, topics 51, grade basis {'textbook': 5}, sources 15
science.json: 科学 grades [1, 6], stages 4, topics 57, grade basis {'textbook': 6}, sources 16
WARN geography.json: no topics for grades [9]
WARN information_technology.json: no topics for grades [9]

## configs/curriculum/biology.json: subject=生物学 grades=[7, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'experiments', 'notes']
  grade 7 basis=textbook n=4: 生物和细胞（认识生物、认识细胞、从细胞到生物体）；多种多样的生物（藻类与植物的类群、动物的类群、微生物、生物分类的方法）；植物的生活（被子植物的一生、植物体内的物质与能量变化）；人体生理与健康（一）（生殖和发育、营养、呼吸、物质运输、废物排出）
  grade 8 basis=textbook n=3: 人体生理与健康（二）（人体生命活动的调节、健康地生活）；生物与环境（生态系统、生态安全）；生命的延续和发展（生物的生殖、遗传与变异、进化、生物多样性及其保护）
  grade 9 basis=estimate n=1: 人教版（六三制）九年级无生物学新课；标准7-9年级学段内容已在七、八年级完成
  grade 10 basis=textbook n=12: 走近细胞；组成细胞的分子；细胞的基本结构；细胞的物质输入和输出；细胞的能量供应与利用；细胞的生命历程（必修1） …
  grade 11 basis=textbook n=13: 人体的内环境与稳态；神经调节；体液调节；免疫调节；植物生命活动的调节（选必1）；种群及其动态 …
  grade 12 basis=estimate n=2: 高考/等级性考试总复习（必修1-2、选择性必修1-3）；选修模块（学校自主开设）
  stage 义务教育阶段（初中生物学，标准为7-9年级学段；人教版七～八年级） grades=[7, 8] domains=['学习主题1：生物体的结构层次', '学习主题2：生物的多样性', '学习主题3：生物与环境', '学习主题4：植物的生活', '学习主题5：人体生理与健康', '学习主题6：遗传与进化', '学习主题7：生物学与社会·跨学科实践']
  stage 高中必修1：分子与细胞 grades=[10, 10] domains=['概念1：细胞是生物体结构与生命活动的基本单位', '概念2：细胞的生存需要能量和营养物质，并通过分裂实现增殖']
  stage 高中必修2：遗传与进化 grades=[10, 10] domains=['概念3：遗传信息控制生物性状，并代代相传', '概念4：生物的多样性和适应性是进化的结果']
  stage 高中选择性必修1：稳态与调节 grades=[11, 11] domains=['概念1：生命个体的结构与功能相适应，各结构协调统一共同完成复杂生命活动']
  stage 高中选择性必修2：生物与环境 grades=[11, 11] domains=['概念2：生态系统中的各种成分相互影响，共同实现系统的物质循环、能量流动和信息传递']
  stage 高中选择性必修3：生物技术与工程 grades=[11, 11] domains=['概念3：发酵工程利用微生物的特定功能规模化生产产品', '概念4：细胞工程通过细胞水平操作获得有用的生物体或产品', '概念5：基因工程赋予生物新的遗传特性', '概念6：生物技术在造福人类社会的同时也可能会带来安全与伦理问题']
  stage 高中选修课程（现实生活应用；职业规划前瞻；学业发展基础） grades=[10, 12] domains=['现实生活应用', '职业规划前瞻', '学业发展基础']
  notes: ["起始年级：义务教育生物学标准按7-9年级一个学段编写；人教版新教材（六三制）在七、八年级学完（s6），很多地区八年级结束时参加生物（与地理）学业水平考试（常见做法，本次未取官方文件，属估计）。", "地区差异：“五四”学制地区生物学开设年级不同（人教版另有五四学制版本，本次未核实其年级）；开设综合“科学”的地区（如浙江）生物内容并入科学7-9年级。", "义务教育生物学标准未列统一“学生必做实验”清单，而以各主题“学习活动建议”列出实验探究活动；高中标准以“应开展下列教学活动/实验”表述，并非“必做实验”名称。", "高中生物学标准2020年修订涉及正文（与物理、化学仅修订前言不同，s5）。必修2模块共4学分（建议高一开设）；选择性必修3模块各2学分；选修模块各1学分。", "高中年级对应（选必在高二）为常见安排而非标准规定。", "义务教育标准PDF为扫描件，内容经OCR后改写；人教版目录来源为第三方电子课本镜像站（dzkbw.com）。"]

## configs/curriculum/chemistry.json: subject=化学 grades=[9, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'experiments', 'notes']
  grade 9 basis=textbook n=12: 绪论 化学使世界变得更加绚丽多彩；走进化学世界；空气和氧气；物质构成的奥秘；自然界的水；化学反应的定量关系 …
  grade 10 basis=textbook n=8: 物质及其变化；海水中的重要元素——钠和氯；铁 金属材料；物质结构 元素周期律（必修一）；化工生产中的重要非金属元素；化学反应与能量 …
  grade 11 basis=textbook n=7: 化学反应的热效应；化学反应速率与化学平衡；水溶液中的离子反应与平衡；化学反应与电能（选必1）；原子结构与性质；分子结构与性质 …
  grade 12 basis=textbook n=6: 有机化合物的结构特点与研究方法；烃；烃的衍生物；生物大分子；合成高分子（选必3）；高考/等级性考试总复习
  stage 义务教育阶段（初中化学，标准不细分年级；人教版九年级） grades=[9, 9] domains=['学习主题1：科学探究与化学实验', '学习主题2：物质的性质与应用', '学习主题3：物质的组成与结构', '学习主题4：物质的化学变化', '学习主题5：化学与社会·跨学科实践']
  stage 高中必修（主题1-5） grades=[10, 10] domains=['主题1：化学科学与实验探究', '主题2：常见的无机物及其应用', '主题3：物质结构基础与化学反应规律', '主题4：简单的有机化合物及其应用', '主题5：化学与社会发展']
  stage 高中选择性必修1：化学反应原理 grades=[11, 11] domains=['主题1：化学反应与能量', '主题2：化学反应的方向、限度和速率', '主题3：水溶液中的离子反应与平衡']
  stage 高中选择性必修2：物质结构与性质 grades=[11, 11] domains=['主题1：原子结构与元素的性质', '主题2：微粒间的相互作用与物质的性质', '主题3：研究物质结构的方法与价值']
  stage 高中选择性必修3：有机化学基础 grades=[11, 12] domains=['主题1：有机化合物的组成与结构', '主题2：烃及其衍生物的性质与应用', '主题3：生物大分子及合成高分子']
  stage 高中选修课程（系列1实验化学；系列2化学与社会；系列3发展中的化学科学） grades=[10, 12] domains=['系列1：实验化学', '系列2：化学与社会', '系列3：发展中的化学科学']
  notes: ["起始年级：国家课程方案只规定7-9年级开设物理、化学、生物学（或科学）；“六三”学制下人教版化学只在九年级（上下两册，s6/s7）。", "地区差异：“五四”学制地区（人教版五四学制版本）化学在八、九年级各一册全一册（s8/s9），内容与六三制九年级上下册基本一致；开设综合“科学”的地区（如浙江）化学内容并入科学7-9年级。", "义务教育化学标准不细分年级；初中跨学科实践活动原则上不少于本学科总课时的10%（s1）。标准附录列出10个跨学科实践活动，人教版教材逐一对应安排。", "高中化学标准为2017年版2020年修订，化学学科修订仅涉及前言（s5）。必修不分模块共4学分，选择性必修3模块共6学分（每模块2学分），选修3个系列（每9学时0.5学分，最高4学分）。", "高中年级对应（高一必修、高二选必1/2、选必3跨高二高三）为常见安排而非标准规定，各省不同。", "义务教育标准PDF为扫描件，内容经OCR后改写概括；人教版目录来源为第三方电子课本镜像站（dzkbw.com），非人教社官网。"]

## configs/curriculum/chinese.json: subject=语文 grades=[1, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'notes']
  grade 1 basis=textbook n=11: 上册 入学教育：我是中国人、我爱我们的祖国、我是小学生、我爱学语文；上册 识字：天地人、金木水火土、口耳目手足、日月山川；上册 汉语拼音：a o e、i u ü、b p m f、d t n l、g k h、j q x、z c s、zh ch sh r、y w；上册 复韵母与鼻韵母：ai ei ui、ao ou iu、ie üe er、an en in un ün、ang eng ing ong；上册 阅读：秋天、江南、雪地里的小画家、四季、小小的船、影子、两件宝、比尾巴、乌鸦喝水、雨点儿；上册 识字：对韵歌、日月明、小书包、升国旗 …
  grade 2 basis=textbook n=11: 上册 阅读：小蝌蚪找妈妈、我是什么、植物妈妈有办法；快乐读书吧 读读童话故事；上册 识字：场景歌、树之歌、拍手歌、田家四季歌；上册 阅读：彩虹、去外婆家、数星星的孩子；古诗二首（登鹳雀楼、望庐山瀑布）、黄山奇石、日月潭、葡萄沟；上册 阅读：坐井观天、寒号鸟、我要的是葫芦；八角楼上、朱德的扁担、难忘的泼水节、刘胡兰；上册 阅读：古诗二首（江雪、敕勒歌）、雾在哪里、雪孩子；称赞、纸船和风筝、快乐的小河；下册 阅读：古诗二首（咏柳、村居）、找春天、开满鲜花的小路、邓小平爷爷植树 …
  grade 3 basis=textbook n=13: 上册：大青树下的小学、花的学校、不懂就要问；口语交际 我的暑假生活；习作 猜猜他是谁；上册：古诗三首（望洞庭、山行、夜书所见）、铺满金色巴掌的水泥道、秋天的雨；习作 写日记；上册 阅读策略单元（预测）：总也倒不了的老屋、犟龟、小狗学叫；习作 续写故事；上册：宝葫芦的秘密（节选）、在牛肚子里旅行、一块奶酪；习作 我来编童话；快乐读书吧 在那奇妙的王国里；上册 习作单元（观察）：搭船的鸟、金色的草地；习作 我们眼中的缤纷世界；上册：富饶的西沙群岛、海滨小城、美丽的小兴安岭；古诗三首（鹿柴、望天门山、饮湖上初晴后雨）、大自然的声音 …
  grade 4 basis=textbook n=13: 上册：观潮、繁星、现代诗二首；口语交际 我们与环境；习作 推荐一个好地方；上册 阅读策略单元（提问）：一个豆荚里的五粒豆、夜间飞行的秘密、方帽子店、田忌赛马；上册：古诗三首（暮江吟、题西林壁、雪梅）、爬山虎的脚、蟋蟀的住宅；习作 写观察日记；上册 神话：盘古开天地、精卫填海、普罗米修斯、女娲补天；快乐读书吧 很久很久以前；上册 习作单元：麻雀、爬天都峰；习作 生活万花筒；上册：长城、颐和园、秦兵马俑；习作 中国的世界文化遗产 …
  grade 5 basis=textbook n=13: 上册：桂花雨、落花生、珍珠鸟；口语交际 制定班级公约；习作 我的心爱之物；上册 阅读策略单元（提高阅读速度）：冀中的地道战、将相和、什么比猎豹的速度更快、“诺曼底号”遇难记；上册 民间故事：猎人海力布、牛郎织女；习作 故事新编；快乐读书吧 从前有座山；上册 爱国：古诗三首（示儿、题临安邸、己亥杂诗）、少年中国说（节选）、圆明园的毁灭、梅兰芳蓄须明志；上册 习作单元（说明文）：太阳、金字塔；习作 介绍一种事物；上册：慈母情深、父爱之舟、航天员写给孩子的信；古诗三首（山居秋暝、枫桥夜泊、早春呈水部张十八员外）、第一场雪、白鹭 …
  grade 6 basis=textbook n=14: 上册：草原、丁香结、古诗词三首（宿建德江、六月二十七日望湖楼醉书、西江月·夜行黄沙道中）；习作 变形记；上册 革命传统：七律·长征、狼牙山五壮士、开国大典、我的战友邱少云；口语交际 演讲；上册 阅读策略单元（有目的地阅读）：竹节人、宇宙生命之谜、故宫博物院；上册 小说：桥、穷人、金色的鱼钩；习作 笔尖流出的故事；快乐读书吧 笑与泪，经历与成长；上册 习作单元：灯光、盼；习作 围绕中心意思写；上册：只有一个地球、青山不老、三黑和土地、古诗三首（浪淘沙、江南春、书湖阴先生壁）；习作 学写倡议书 …
  grade 7 basis=textbook n=8: 上册 四季美景：春、济南的冬天、雨的四季、古代诗歌四首（观沧海、次北固山下、闻王昌龄左迁龙标遥有此寄、天净沙·秋思）；写作 热爱写作，学会观察；上册 亲情：秋天的怀念、散步、散文诗二首、《世说新语》二则（咏雪、陈太丘与友期行）；写作 学会记事；专题学习活动 有朋自远方来；上册 学习生活：从百草园到三味书屋、往事依依、再塑生命的人、《论语》十二章；写作 如何突出中心；整本书阅读《朝花夕拾》；上册 革命与修身：纪念白求恩、回忆我的母亲、梅岭三章、诫子书；写作 思路要清晰；专题学习活动 少年正是读书时；上册 活动·探究（人与动物）：猫、我的白鸽、大雁归来、狼；上册 想象：小圣施威降大圣、皇帝的新装、女娲造人、寓言四则；写作 发挥联想和想象；整本书阅读《西游记》 …
  grade 8 basis=textbook n=12: 上册 活动·探究（新闻）：消息二则、中国人首次进入自己的空间站、首届诺贝尔奖颁发、“飞天”凌空、一着惊海天、国行公祭，为佑世界和平；上册 人物传记：藤野先生、回忆鲁迅先生（节选）、天上有颗“南仁东星”、美丽的颜色；写作 学写传记；整本书阅读《红星照耀中国》；上册 山水古文：三峡、答谢中书书、记承天寺夜游、与朱元思书、唐诗五首；写作 学习描写景物；专题学习活动 人无信不立；上册 散文：背影、白杨礼赞、散文二篇、昆明的雨；写作 语言要连贯；整本书阅读《红岩》；上册 说明文：中国石拱桥、苏州园林、人民英雄永垂不朽、梦回繁华；写作 说明事物要抓住特征；专题学习活动 身边的文化遗产；上册 古诗文：《孟子》三章、愚公移山、周亚夫军细柳、诗词五首；写作 表达要得体 …
  grade 9 basis=textbook n=11: 上册 活动·探究（诗歌）：沁园春·雪、周总理，你在哪里、我爱这土地、乡愁、你是人间的四月天、我看；诗歌鉴赏、朗诵与创作；上册 议论文：培养德智体美劳全面发展的社会主义建设者和接班人、中国人失掉自信力了吗、谈骨气、创造宣言；写作 观点要明确；专题学习活动 君子自强不息；上册 古诗文：岳阳楼记、醉翁亭记、湖心亭看雪、诗词三首（行路难、酬乐天扬州初逢席上见赠、水调歌头）；写作 议论要言之有据；上册 小说：故乡、我的叔叔于勒、孤独之旅、蒲柳人家（节选）；写作 学写小小说；整本书阅读《简·爱》（怎样读外国小说）；上册 议论文：想和做、怀疑与学问、就英法联军远征中国致巴特勒上尉的信、精神的三间小屋；写作 论证要合理；专题学习活动 我们的数字时代；上册 古文：曹刿论战、邹忌讽齐王纳谏、陈涉世家、出师表、诗词曲五首；写作 学会深入思考；整本书阅读《唐诗三百首》 …
  grade 10 basis=textbook n=14: 必修上 青春激扬：沁园春·长沙、立在地球边上放号、红烛、峨日朵雪峰之侧、致云雀、百合花、哦，香雪；必修上 劳动光荣：喜看稻菽千重浪、心有一团火，温暖众人心、“探界者”钟扬、以工匠精神雕琢时代品质、芣苢、插秧歌；必修上 古诗词：短歌行、归园田居、梦游天姥吟留别、登高、琵琶行并序、念奴娇·赤壁怀古、永遇乐·京口北固亭怀古、声声慢；必修上 家乡文化生活（当代文化参与）；整本书阅读《乡土中国》；必修上 学习之道：劝学、师说、反对党八股（节选）、拿来主义、读书：目的和前提、上图书馆；必修上 自然情怀：故都的秋、荷塘月色、我与地坛（节选）、赤壁赋、登泰山记 …
  grade 11 basis=textbook n=8: 选择性必修上 革命与建设：中国人民站起来了、长征胜利万岁、大战中的插曲、别了，“不列颠尼亚”、县委书记的榜样——焦裕禄、在民族复兴的历史丰碑上；选择性必修上 先秦诸子：《论语》十二章、大学之道、人皆有不忍人之心、《老子》四章、五石之瓠、兼爱；选择性必修上 外国小说：大卫·科波菲尔、复活、老人与海、百年孤独（节选）；选择性必修上 逻辑的力量（学习活动单元，估计）；选择性必修中 理论经典：社会历史的决定性基础、改造我们的学习、人的正确思想是从哪里来的？、实践是检验真理的唯一标准、修辞立其诚、人应当坚持正义；选择性必修中 革命文学：记念刘和珍君、为了忘却的记念、包身工、荷花淀、小二黑结婚（节选）、党费 …
  grade 12 basis=textbook n=6: 选择性必修下 古代诗歌：氓、离骚（节选）、孔雀东南飞、蜀道难、蜀相、望海潮、扬州慢；选择性必修下 现当代作品：阿Q正传（节选）、边城（节选）、大堰河——我的保姆、再别康桥、风景谈、秦腔、茶馆（节选）；选择性必修下 古代散文：陈情表、项脊轩志、兰亭集序、归去来兮辞、种树郭橐驼传、石钟山记；选择性必修下 科学论著：自然选择的证明、宇宙的边疆、天文学上的旷世之争；古诗词诵读（拟行路难、客至、登快阁、临安春雨初霁）；选修学习任务群专题（依学校开设）：汉字汉语、中华传统文化、革命传统作品、现当代作家作品、跨文化、学术论著专题研讨；高考复习（估计）：文言文与古诗词鉴赏、现代文阅读（论述类/实用类/文学类）、语言文字运用、名句默写（课标附录古诗文背诵推荐篇目）、议论文写作
  stage 第一学段 grades=[1, 2] domains=['识字与写字', '阅读与鉴赏', '表达与交流', '梳理与探究', '语言文字积累与梳理（学习任务群·第一学段学习内容）']
  stage 第二学段 grades=[3, 4] domains=['识字与写字', '阅读与鉴赏', '表达与交流', '梳理与探究']
  stage 第三学段 grades=[5, 6] domains=['识字与写字', '阅读与鉴赏', '表达与交流', '梳理与探究']
  stage 第四学段 grades=[7, 9] domains=['识字与写字', '阅读与鉴赏', '表达与交流', '梳理与探究']
  stage 高中必修（通常高一，第10年级） grades=[10, 10] domains=['学习任务群1 整本书阅读与研讨（1学分，贯串三类课程）', '学习任务群2 当代文化参与（0.5学分）', '学习任务群3 跨媒介阅读与交流（0.5学分）', '学习任务群4 语言积累、梳理与探究（1学分）', '学习任务群5 文学阅读与写作（2.5学分）', '学习任务群6 思辨性阅读与表达（1.5学分）', '学习任务群7 实用性阅读与交流（1学分）', '学习任务群8 中华传统文化经典研习（2学分）', '学习任务群9 中国革命传统作品研习（0.5学分）', '学习任务群10 中国现当代作家作品研习（0.5学分）', '学习任务群11 外国作家作品研习（1学分）', '学习任务群12 科学与文化论著研习（1学分）']
  stage 高中选择性必修（通常高二，第11年级） grades=[11, 11] domains=['延续与深化的学习任务群（选择性必修共6学分）']
  stage 高中选修（通常高三，第12年级，含总复习） grades=[12, 12] domains=['选修学习任务群（共12学分，学生自由选择）']
  notes: ["《义务教育语文课程标准（2022年版）》教育部PDF为扫描件，本文件的学段要求、学习任务群与学业质量内容由逐页人工阅读后改写；页码为纸质页（PDF页码约为纸质页+7）。", "义务教育课标按“六三”学制设学段：第一学段1—2年级、第二学段3—4年级、第三学段5—6年级、第四学段7—9年级；“五四”学制另作调整。", "义务教育课标的课程内容以6个学习任务群组织：基础型“语言文字积累与梳理”，发展型“实用性阅读与交流”“文学阅读与创意表达”“思辨性阅读与表达”，拓展型“整本书阅读”“跨学科学习”。stages.domains 主要采用课标“学段要求”的四个语文实践领域（识字与写字、阅读与鉴赏、表达与交流、梳理与探究），第一学段另附一个任务群示例。", "义务教育课标的教学建议与评价建议多为全学段通用；stages 中的 teaching_suggestions 部分来自“语言文字积累与梳理”任务群的分学段学习内容与教学提示，其余为对通用建议的学段化改写。", "高中课标不按年级划分，而分为必修（8学分）、选择性必修（6学分）、选修（12学分）三类课程，共18个学习任务群。本文件按常见教学安排映射：高一（10年级）学必修上/下册，高二（11年级）学选择性必修上/中册，高三（12年级）学选择性必修下册、选修专题并开展高考总复习。各省各校的实际进度可能不同（有的在高二下学期完成全部选择

## configs/curriculum/english.json: subject=英语 grades=[3, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'notes']
  grade 3 basis=textbook n=13: 三上(2024版): Revision Being a good guest；U1 Making friends；U2 Different families；U3 Amazing animals；U4 Plants around us；U5 The colourful world …
  grade 4 basis=textbook n=13: 四上(2024版): U1 Helping at home；U2 My friends；U3 Places we live in；U4 Helping in the community；U5 The weather and us；Revision Let's help! …
  grade 5 basis=textbook n=13: 五上(2024版): U1 Different friends；U2 My feelings；U3 Work and play；U4 Healthy habits；U5 Food we eat；U6 Nature and us …
  grade 6 basis=textbook n=8: 六上(2024版): U1 Amazing places；U2 Getting together；U3 Healthy life；U4 Managing money well；U5 Exploring space；U6 Energy, nature and us …
  grade 7 basis=textbook n=16: 七上(2024版): Starter Units Hello! / Keep Tidy! / Welcome!；U1 You and Me；U2 We're Family!；U3 My School；U4 My Favourite Subject；U5 Fun Clubs …
  grade 8 basis=textbook n=15: 八上(2024版): U1 Happy Holiday；U2 Home Sweet Home；U3 Same or Different?；U4 Amazing Plants and Animals；U5 What a Delicious Meal!；U6 Plan for Yourself …
  grade 9 basis=textbook n=9: 九上(2024版): U1 The Changing World；U2 Inspiring People；U3 Smart Learning；U4 Our Memory；U5 Power of Ideas；U6 Beyond Earth …
  grade 10 basis=textbook n=16: 必修第一册: Welcome Unit；Teenage Life；Travelling Around；Sports and Fitness；Natural Disasters；Languages Around the World …
  grade 11 basis=textbook n=10: 选择性必修第一册: People of Achievement；Looking into the Future；Fascinating Parks；Body Language；Working the Land；选择性必修第二册: Science and Scientists …
  grade 12 basis=textbook n=11: 选择性必修第三册: Art；Healthy Lifestyle；Environmental Protection；Adversity and Courage；Poems；选择性必修第四册: Science Fiction …
  stage 一级（3～4年级） grades=[3, 4] domains=['主题', '语篇', '语言知识', '文化知识', '语言技能', '学习策略']
  stage 二级（5～6年级） grades=[5, 6] domains=['主题', '语篇', '语言知识', '文化知识', '语言技能']
  stage 三级（7～9年级） grades=[7, 9] domains=['主题', '语篇', '语言知识', '文化知识', '语言技能', '学习策略']
  stage 高中必修（学业质量水平一，6学分，英语1-3） grades=[10, 10] domains=['主题语境', '语言知识', '文化知识', '语言技能', '学习策略']
  stage 高中选择性必修（学业质量水平二，8学分，英语4-7） grades=[11, 12] domains=['语言知识', '文化知识', '语言技能']
  stage 高中选修·提高类（学业质量水平三，0～6学分，英语8-10） grades=[12, 12] domains=['语言知识', '文化知识']
  notes: ["起始年级：2022课标建议3～4年级学一级、5～6年级学二级、7～9年级学三级；另设预备级供1～2年级（以视听说为主，课堂视听每周不少于20分钟），故小学英语通常从三年级开始，部分地区从一年级开设。grades按3起算。", "“五四”学制：3～5年级目标参照“六三”学制5～6年级并适当降低；6～9年级内容相应调整（s1第11、13页）。", "2022课标一级未给出词汇量；二级约500词（另可加100～300），三级约1600词（另可加100～300），三级+约1800词。网络二手资料称二级词表“505词”，未在原文核实。", "s1为扫描版PDF，无文本层，本文件内容由逐页查看原图后转述，页码为课标页码。", "高中课标引用的是2017年版全文（s3，非教育部官网托管）；二手资料称2020年修订对英语仅改前言，未逐字核对2020年版。", "高中词汇：课标正文表5写必修累计2000～2100、选必累计3000～3200、提高类累计4000～4200；附录词表说明为必修+500累计2000、选必+1000累计3000，各地可再增200。", "高中年级映射为估计：必修三册标作高一、选必1-2标作高二、选必3-4标作高三（按s6标注），实际各省开课进度不同；选择性必修阶段grades写作[11,12]。", "3～9年级单元标题来自人教社官网数字配套资源（2024年起新版，逐年

## configs/curriculum/geography.json: subject=地理 grades=[7, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'notes']
  grade 7 basis=textbook n=41: 地球；地球的宇宙环境；地球与地球仪；地球的运动；地图；地图的阅读 …
  grade 8 basis=textbook n=42: 从世界看中国；疆域；人口；民族；中国的自然环境；地形 …
  grade 10 basis=textbook n=53: 宇宙中的地球；地球的宇宙环境；太阳对地球的影响；地球的历史；地球的圈层结构；问题研究 火星基地应该是什么样子 …
  grade 11 basis=textbook n=42: 地球的运动；地球的自转和公转；地球运动的地理意义；问题研究 人类是否需要人造月亮；地表形态的塑造；塑造地表形态的力量 …
  grade 12 basis=textbook n=22: 自然环境与人类社会；自然环境的服务功能；自然资源及其利用；环境问题及其危害；问题研究 我们的生态足迹有多大；资源安全与国家安全 …
  stage 7～9年级（义务教育地理） grades=[7, 9] domains=['认识全球·主题一 地球的宇宙环境', '认识全球·主题二 地球的运动', '认识全球·主题三 地球的表层', '认识区域·主题四 认识世界', '认识区域·主题五 认识中国', '地理工具与地理实践', '跨学科主题学习']
  stage 高中必修课程 grades=[10, 10] domains=['地理1（2学分）', '地理2（2学分）']
  stage 高中选择性必修课程 grades=[11, 12] domains=['自然地理基础（选择性必修1）', '区域发展（选择性必修2）', '资源、环境与国家安全（选择性必修3）']
  stage 高中选修课程 grades=[10, 12] domains=['侧重自然领域', '侧重人文领域', '侧重技术与实践领域']
  notes: ["课程方案表1将历史、地理列为7～9年级科目（五四学制可从六年级开设地理）；课标把义务教育地理作为一个学段，要求七、八年级各组织户外实践，人教版教材只编七、八年级四册，九年级通常不设地理新课（多为复习），故 grade_topics 无“9”。", "义务教育课标内容：认识全球（主题一至三）、认识区域（主题四、五），地理工具与地理实践贯穿其中，另设跨学科主题学习（≥10%课时）。", "s1 为教育部官网扫描版PDF（无文字层），经OCR后转述；内容要求为意译并压缩。", "教材目录取自电子课本网（dzkbw.com）转载的人教版目录（七、八年级为2024—2026年新版），未在人教社官网 pep.com.cn 核对；各地还使用湘教版、中图版、商务星球版等，章节编排不同。", "高中年级映射：必修第一、二册→高一；选择性必修1、2→高二；选择性必修3→高三，依电子课本网标注，各地安排不一。", "高中选修9个模块无统一教材，未纳入 grade_topics。", "grade_topics 每个年级依次列出章名与节名（含跨学科主题学习、问题研究）；source 可能含多个来源编号，以逗号分隔。"]

## configs/curriculum/history.json: subject=历史 grades=[7, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'notes']
  grade 7 basis=textbook n=50: 史前时期：原始社会与中华文明的起源；远古时期的人类活动；原始农业与史前社会；中华文明的起源；夏商周时期：奴隶制王朝的更替和向封建社会的过渡；夏商西周王朝的更替 …
  grade 8 basis=textbook n=60: 中国开始沦为半殖民地半封建社会；鸦片战争；第二次鸦片战争；太平天国运动；早期现代化的初步探索和民族危机加剧；洋务运动和边疆危机 …
  grade 9 basis=textbook n=58: 文明的产生和古代亚非文明；从原始社会到奴隶社会；古代两河流域；古代埃及；古代印度；古代欧洲文明 …
  grade 10 basis=textbook n=75: 从中华文明起源到秦汉统一多民族封建国家的建立与巩固；中华文明的起源与早期国家；诸侯纷争与变法运动；秦统一多民族封建国家的建立；西汉与东汉——统一多民族封建国家的巩固；三国两晋南北朝的民族交融与隋唐统一多民族封建国家的发展 …
  grade 11 basis=textbook n=45: 政治制度；中国古代政治制度的形成与发展；西方国家古代和近代政治制度的演变；中国近代至当代政治制度的演变；中国历代变法和改革；官员的选拔与管理 …
  grade 12 basis=textbook n=21: 源远流长的中华文化；中华优秀传统文化的内涵与特点；中华文化的世界意义；丰富多样的世界文化；古代西亚、非洲文化；欧洲文化的形成 …
  stage 7～9年级（义务教育历史） grades=[7, 9] domains=['中国古代史', '中国近代史', '中国现代史', '世界古代史', '世界近代史', '世界现代史', '跨学科主题学习']
  stage 高中必修课程（中外历史纲要） grades=[10, 10] domains=['中国古代史（1.1～1.6）', '中国近现代史（1.7～1.14）', '世界史（1.15～1.24）']
  stage 高中选择性必修课程 grades=[11, 12] domains=['国家制度与社会治理（选择性必修1）', '经济与社会生活（选择性必修2）', '文化交流与传播（选择性必修3）']
  stage 高中选修课程 grades=[10, 12] domains=['史学入门', '史料研读']
  notes: ["课程方案规定历史在初中（7～9年级）开设，课标将7～9年级作为一个学段；高中历史为10～12年级。", "义务教育课标内容分七个板块：中国古代史、中国近代史、中国现代史、世界古代史、世界近代史、世界现代史、跨学科主题学习。", "s1 为教育部官网扫描版PDF（无文字层），经OCR后转述；内容要求为意译并压缩，括注的史事为课标所举示例。", "教材目录取自电子课本网（dzkbw.com）转载的统编版（人教社出版）目录，未在人教社官网 pep.com.cn 核对。", "统编新教材分年度换版：截至2026秋，七、八年级和九年级上册为新版，九年级下册仍为2019年旧版目录，换版后可能调整。", "高中年级映射：《中外历史纲要》（上下）→高一（课标建议必修安排在高一）；选择性必修1、2→高二、选择性必修3→高三，依电子课本网标注，各地安排不一。", "高中选修《史学入门》《史料研读》无统编教材，未纳入 grade_topics。", "grade_topics 每个年级依次列出单元名与课题名；source 可能含多个来源编号（上册、下册），以逗号分隔。"]

## configs/curriculum/information_technology.json: subject=信息科技/信息技术 grades=[3, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'notes']
  grade 3 basis=estimate n=6: 在线学习与生活；感受在线社会与数字化学习；在线协作分步解决问题；在线安全与数字身份；在线学习小能手；自我管理小管家
  grade 4 basis=estimate n=7: 数据与编码；数据来源与可靠性；用编码表示信息；数据的组织与可视化；保护数据安全；用数据讲故事 …
  grade 5 basis=estimate n=7: 身边的算法；算法的描述（自然语言、流程图）；顺序、分支、循环结构；算法效率；编程验证简单算法；游戏博弈中的策略 …
  grade 6 basis=estimate n=7: 过程与控制；输入、计算、输出；系统与模块；反馈与优化；开关量与连续量；小型开关系统 …
  grade 7 basis=estimate n=7: 互联网应用与创新；互联网搜索与协作；网页编辑与发布；互联网协议与数据传输；身份验证与加密；云存储与云计算 …
  grade 8 basis=estimate n=11: 物联网实践与探索；物联网与互联网的异同；搭建简易物联系统；人工智能与智慧社会；人工智能三大基础：数据、算法、算力；搜索、推理、预测与机器学习 …
  grade 10 basis=textbook n=41: 认识数据与大数据；项目：体质数据促健康；数据、信息与知识；数字化与编码；数据科学与大数据；算法与程序实现 …
  grade 11 basis=textbook n=55: 走进数据世界；项目：析说身边数据；深入认识数据；数据的价值；初识数据结构；项目：管理个人书目 …
  grade 12 basis=textbook n=65: 人工智能概述；项目：人工智能在身边；人工智能基础；人工智能发展历程和现状；人工智能研究内容与应用；人工智能技术基本原理 …
  stage 第一学段（相关内容融入其他课程） grades=[1, 2] domains=['信息交流与分享', '信息隐私与安全', '跨学科主题：数字设备体验']
  stage 第二学段 grades=[3, 4] domains=['在线学习与生活', '数据与编码', '跨学科主题：数据编码探秘']
  stage 第三学段 grades=[5, 6] domains=['身边的算法', '过程与控制', '跨学科主题：小型系统模拟']
  stage 第四学段 grades=[7, 9] domains=['互联网应用与创新', '物联网实践与探索', '人工智能与智慧社会', '跨学科主题：互联智能设计']
  stage 高中必修课程（3学分） grades=[10, 10] domains=['数据与计算（必修1）', '信息系统与社会（必修2）']
  stage 高中选择性必修课程 grades=[11, 12] domains=['数据与数据结构（选择性必修1）', '网络基础（选择性必修2）', '数据管理与分析（选择性必修3）', '人工智能初步（选择性必修4）', '三维设计与创意（选择性必修5）', '开源硬件项目设计（选择性必修6）']
  stage 高中选修课程 grades=[10, 12] domains=['算法初步', '移动应用设计']
  notes: ["课程方案规定信息科技在3～8年级独立开设；课标按1～2、3～4、5～6、7～9年级分四个学段设计，1～2年级和9年级的相关内容融入语文、道德与法治、数学、科学、综合实践活动等课程，故 grade_topics 为3～8年级与高中10～12年级。", "高中信息技术课标的学科核心素养同为信息意识、计算思维、数字化学习与创新、信息社会责任四项（s4）。", "课标以数据、算法、网络、信息处理、信息安全、人工智能六条逻辑主线组织内容模块，各学段另设跨学科主题。", "义务教育信息科技没有全国统一的统编教材，各地使用不同出版社版本（2024年起陆续有依据新课标的教材），未能获取可核对的目录，3～8年级 grade_topics 按课标学段模块推测分配到年级（basis 为 estimate）：3年级在线学习与生活、4年级数据与编码、5年级身边的算法、6年级过程与控制、7年级互联网、8年级物联网与人工智能；实际年级安排因教材和地区而异。", "s1 为教育部官网扫描版PDF（无文字层），经OCR后转述；内容要求、学业质量、教学建议均为意译。", "高中教材目录取自电子课本网（dzkbw.com）转载的人教中图版（中国地图出版社）目录；另有教科版、浙教版、粤教版、华东师大版、沪科教版等，章节不同。", "高中年级映射：必修1、2→高一；选择性必修1～3→高二；选择性必修4～6→高三，依电子

## configs/curriculum/math.json: subject=数学 grades=[1, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'prerequisites', 'notes']
  grade 1 basis=textbook n=13: 数学游戏（入学准备）；5以内数的认识和加、减法；6～10的认识和加、减法；认识立体图形；11～20的认识；20以内的进位加法 …
  grade 2 basis=textbook n=13: 分类与整理；1～6的表内乘法；1～6的表内除法；认识东、南、西、北（校园小导游）；厘米和米；身体上的尺子 …
  grade 3 basis=textbook n=16: 观察物体；混合运算；毫米、分米和千米；认识质量单位（曹冲称象的故事）；多位数乘一位数；数字编码 …
  grade 4 basis=textbook n=15: 万以上数的认识；角的度量；多位数乘两位数；加法模型和乘法模型；平行四边形和梯形；条形统计图 …
  grade 5 basis=textbook n=13: 观察简单组合体；小数乘法；小数除法；图形的运动（平移、旋转、轴对称）；用字母表示数和数量关系；多边形的面积 …
  grade 6 basis=textbook n=12: 确定位置；分数乘法；分数除法；负数；圆；体育中的数学 …
  grade 7 basis=textbook n=12: 有理数；有理数的运算；代数式；整式的加减；一元一次方程；几何图形初步 …
  grade 8 basis=textbook n=12: 三角形；全等三角形；轴对称；整式的乘法；因式分解；分式 …
  grade 9 basis=textbook n=10: 一元二次方程；二次函数；反比例函数；旋转；圆（圆的有关性质、弧长和扇形面积）；直线与圆的位置关系 …
  grade 10 basis=textbook n=10: 集合与常用逻辑用语；一元二次函数、方程和不等式；函数的概念与性质；指数函数与对数函数；三角函数；平面向量及其应用 …
  grade 11 basis=textbook n=5: 空间向量与立体几何；直线和圆的方程；圆锥曲线的方程；数列；一元函数的导数及其应用
  grade 12 basis=textbook n=4: 计数原理；随机变量及其分布；成对数据的统计分析；高考总复习
  stage 第一学段 grades=[1, 2] domains=['数与代数', '图形与几何', '统计与概率', '综合与实践']
  stage 第二学段 grades=[3, 4] domains=['数与代数', '图形与几何', '统计与概率', '综合与实践']
  stage 第三学段 grades=[5, 6] domains=['数与代数', '图形与几何', '统计与概率', '综合与实践']
  stage 第四学段 grades=[7, 8, 9] domains=['数与代数', '图形与几何', '统计与概率', '综合与实践']
  stage 高中必修 grades=[10] domains=['预备知识', '函数', '几何与代数', '概率与统计', '数学建模活动与数学探究活动']
  stage 高中选择性必修 grades=[11, 12] domains=['函数', '几何与代数', '概率与统计', '数学建模活动与数学探究活动']
  notes: ["prerequisites 为编辑整理（editorial），依据一般数学知识逻辑与人教版编排顺序给出，非课程标准原文。", "s1 为教育部官网扫描版PDF（无文字层），内容经逐页阅读后转述；学段要求、学业质量、教学建议均为意译而非原文。", "义务教育课标按“六三”学制学段编排；“五四”学制按标准另行对应，本文件仅用六三学制。", "义务教育“数与代数”在小学分“数与运算”“数量关系”两主题，初中分“数与式”“方程与不等式”“函数”三主题；图形与几何、统计与概率亦有子主题，本文件按四大领域归并。", "2022版课标下小学不再要求解方程（新版五上为“用字母表示数和数量关系”），负数在第三学段以综合与实践主题呈现。", "人教社官网 pep.com.cn 访问时返回系统维护页，教材目录取自电子课本网（dzkbw.com）转载的人教版目录，建议后续以人教社官方目录核对。", "人教版新教材（依据2022版课标）分年度换版：截至2026秋，一至三年级、四至六年级上册、七至八年级、九年级上册为新版；四、五、六年级下册和九年级下册目录仍为旧版（预计2027年换新），相关年级的单元归属可能变化。", "新版四年级上册未见“除数是两位数的除法”单元、新版六年级上册未见单独的“比”与“位置与方向”单元，推测已调整至其他册次，待新版下册发布后核实。", "九年级“概率初步”在旧版位于九上，新

## configs/curriculum/morality_politics.json: subject=道德与法治/思想政治 grades=[1, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'notes']
  grade 1 basis=textbook n=40: 我是小学生啦；开开心心上学去；我向国旗敬个礼；这是我们的校园；平平安安回家来；过好校园生活 …
  grade 2 basis=textbook n=40: 过好节假日；假期有收获；教师节快乐；团团圆圆过中秋；欢欢喜喜庆国庆；我爱我们班 …
  grade 3 basis=textbook n=33: 做学习的主人；学习伴我成长；我学习，我快乐；学习有方法；爱科学 学科学；科技力量大 …
  grade 4 basis=textbook n=32: 我们的班集体；热爱班集体；选举班委会；协商决定班级事务；少年在成长；我是独特的 …
  grade 5 basis=textbook n=32: 没有共产党就没有新中国；开天辟地的大事变；探索中国革命道路；抗日战争的中流砥柱；夺取胜利的解放战争；建设社会主义新中国 …
  grade 6 basis=textbook n=29: 生活中的法律；法律是什么；法律作用大；宪法是根本法；公民与国家；我是中国公民 …
  grade 7 basis=textbook n=32: 少年有梦；开启初中生活；正确认识自我；梦想始于当下；成长的时空；幸福和睦的家庭 …
  grade 8 basis=textbook n=35: 走进社会生活；丰富的社会生活；在社会中健康成长；共建网络美好家园；维护社会秩序；遵守社会规则 …
  grade 9 basis=textbook n=24: 坚持党的全面领导；百年大党风华正茂；坚持以人民为中心；党是领导一切的；进入新时代；新的历史方位 …
  grade 10 basis=textbook n=29: 社会主义从空想到科学、从理论到实践的发展；只有社会主义才能救中国；只有中国特色社会主义才能发展中国；只有坚持和发展中国特色社会主义才能实现中华民族伟大复兴；综合探究一 回看走过的路 比较别人的路 远眺前行的路；综合探究二 方向决定道路 道路决定命运 …
  grade 11 basis=textbook n=50: 探索世界与把握规律；时代精神的精华；探究世界的本质；把握世界的规律；综合探究 坚持唯物辩证法 反对形而上学；认识社会与价值选择 …
  grade 12 basis=textbook n=21: 树立科学思维观念；走进思维世界；把握逻辑要义；领会科学思维；综合探究 学会科学思维 提升思维品质；遵循逻辑思维规则 …
  stage 第一学段 grades=[1, 2] domains=['入学教育', '道德教育', '生命安全与健康教育', '法治教育', '中华优秀传统文化与革命传统教育']
  stage 第二学段 grades=[3, 4] domains=['道德教育', '生命安全与健康教育', '法治教育', '中华优秀传统文化与革命传统教育', '国情教育']
  stage 第三学段 grades=[5, 6] domains=['道德教育', '生命安全与健康教育', '法治教育', '中华优秀传统文化与革命传统教育', '国情教育']
  stage 第四学段 grades=[7, 9] domains=['生命安全与健康教育', '法治教育', '中华优秀传统文化教育', '革命传统教育', '国情教育']
  stage 高中必修课程 grades=[10, 11] domains=['中国特色社会主义（必修1，1学分）', '经济与社会（必修2，1学分）', '政治与法治（必修3，2学分）', '哲学与文化（必修4，2学分）']
  stage 高中选择性必修课程 grades=[11, 12] domains=['当代国际政治与经济（选择性必修1）', '法律与生活（选择性必修2）', '逻辑与思维（选择性必修3）']
  stage 高中选修课程 grades=[10, 12] domains=['财经与生活', '法官与律师', '历史上的哲学家']
  notes: ["义务教育阶段科目为“道德与法治”（1～9年级，课程方案表1），高中为“思想政治”（10～12年级）。", "s1 为教育部官网扫描版PDF（无文字层），经OCR后逐页转述；学段要求、学业质量、教学建议均为意译而非原文。", "课标第一学段另设“入学教育”主题（针对一年级第一学期）；第四学段将“中华优秀传统文化教育”与“革命传统教育”分列为两个主题，道德教育融入各主题。", "教材目录取自电子课本网（dzkbw.com）转载的统编版（人教社出版）目录，未能在人教社官网 pep.com.cn 获取完整目录，建议后续核对。", "统编新教材分年度换版：截至2026秋，1～3年级、4～6年级上册、7～8年级、9年级上册为新版；4、5、6年级下册和9年级下册仍为旧版目录，换版后单元归属可能变化。", "高中年级映射依据课标“必修按顺序开设，模块1与2为一学期，模块3、4各一学期”及电子课本网标注：必修1～3→高一，必修4与选择性必修1、2→高二，选择性必修3→高三；各地安排不一。", "高中选修课程（财经与生活、法官与律师、历史上的哲学家）无统编教材，未纳入 grade_topics。", "grade_topics 每个年级依次列出单元名与课题名；source 可能含多个来源编号（上册、下册），以逗号分隔。", "高中部分以《普通高中思想政治课程标准（2017年版2020年修订）》为准

## configs/curriculum/physics.json: subject=物理 grades=[8, 12] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'experiments', 'notes']
  grade 8 basis=textbook n=13: 绪言 开启科学探索之旅（八上）；机械运动；声现象；物态变化；光现象；透镜及其应用 …
  grade 9 basis=textbook n=10: 内能；内能的利用；电流和电路；电压 电阻；欧姆定律；电功率 …
  grade 10 basis=textbook n=8: 运动的描述；匀变速直线运动的研究；相互作用——力；运动和力的关系（必修一）；抛体运动；圆周运动 …
  grade 11 basis=textbook n=14: 静电场及其应用；静电场中的能量；电路及其应用；电能 能量守恒定律；电磁感应与电磁波初步（必修三）；动量守恒定律 …
  grade 12 basis=textbook n=6: 分子动理论；气体、固体和液体；热力学定律；原子结构和波粒二象性；原子核（选必三）；高考/等级性考试总复习
  stage 义务教育阶段（初中物理，标准不再细分年级；人教版八～九年级） grades=[8, 9] domains=['物质', '运动和相互作用', '能量', '实验探究', '跨学科实践']
  stage 高中必修1（机械运动与物理模型；相互作用与运动定律） grades=[10, 10] domains=['机械运动与物理模型', '相互作用与运动定律']
  stage 高中必修2（机械能及其守恒定律；曲线运动与万有引力定律；牛顿力学的局限性与相对论初步） grades=[10, 10] domains=['机械能及其守恒定律', '曲线运动与万有引力定律', '牛顿力学的局限性与相对论初步']
  stage 高中必修3（静电场；电路及其应用；电磁场与电磁波初步；能源与可持续发展） grades=[10, 11] domains=['静电场', '电路及其应用', '电磁场与电磁波初步', '能源与可持续发展']
  stage 高中选择性必修1（动量与动量守恒定律；机械振动与机械波；光及其应用） grades=[11, 11] domains=['动量与动量守恒定律', '机械振动与机械波', '光及其应用']
  stage 高中选择性必修2（磁场；电磁感应及其应用；电磁振荡与电磁波；传感器） grades=[11, 11] domains=['磁场', '电磁感应及其应用', '电磁振荡与电磁波', '传感器']
  stage 高中选择性必修3（固体、液体和气体；热力学定律；原子与原子核；波粒二象性） grades=[11, 12] domains=['固体、液体和气体', '热力学定律', '原子与原子核', '波粒二象性']
  stage 高中选修1-3（选修1物理学与社会发展；选修2物理学与技术应用；选修3近代物理初步） grades=[10, 12] domains=['选修1：物理学与人类认识、社会变革、公民生活', '选修2：物理学与医疗技术、新能源、新材料、信息技术', '选修3：微观世界、高速世界、宇观世界、世界的统一性']
  notes: ["起始年级：国家课程方案只规定7-9年级开设“物理、化学、生物学（或科学）”，未规定物理起始年级；人教版（六三制）物理在八、九年级（s4、s9）。", "地区差异：部分地区（如浙江）初中开设综合“科学”而非分科物理，物理内容并入科学7-9年级学段；“五四”学制地区物理通常在八、九年级（本次未找到官方表述，属估计）。", "义务教育物理标准不按年级细分，只按一级主题（物质、运动和相互作用、能量、实验探究、跨学科实践）给出内容要求；8、9年级topics完全来自人教版目录。", "高中物理标准为2017年版2020年修订，物理学科修订仅涉及前言，正文与2017年版一致（s5）。高中年级对应（高一必修一、二等）为常见安排而非标准规定，各省选课走班与高考方案不同。", "课时：义务教育课程方案要求各科原则上用不少于10%的课时开展跨学科主题学习（s4）；人教版物理新教材跨学科实践约占课时13%（s9，cited）。", "高中学分：必修6学分、选择性必修6学分、选修6学分（每模块2学分）。", "义务教育标准PDF为扫描件，本文件内容经OCR后人工改写概括，个别条目（如2.4.5电磁感应条款）OCR缺失，按上下文补写。", "人教版目录来源为第三方电子课本镜像站（dzkbw.com），非人教社官网；人教社官网新教材介绍（s9）只给出册次与内容范围，未列章名。"]

## configs/curriculum/science.json: subject=科学 grades=[1, 6] keys=['subject', 'grades', 'sources', 'core_competencies', 'stages', 'grade_topics', 'experiments', 'notes']
  grade 1 basis=textbook n=8: 走近科学；我们的感觉器官；家养动物；使用工具（一上）；位置和方向；校园里的植物 …
  grade 2 basis=textbook n=8: 植物的生长；水和空气；常见的力；制作小船（二上）；了解天气；太阳 月亮 四季 …
  grade 3 basis=textbook n=11: 有趣的磁铁；气体 液体 固体；家庭用电；消化与呼吸；小小建筑师（三上）；溶解与分离 …
  grade 4 basis=textbook n=11: 动植物的繁殖；多样的动物；水的变化与分布；声音；制作简易乐器（四上）；天气与气候 …
  grade 5 basis=textbook n=10: 显微镜下的生物世界；物质的变化；烧水中的热传递；光的现象；太阳能热水器（五上）；昼夜与四季 …
  grade 6 basis=textbook n=9: 相互依存的生命世界；能的转化；水和天气；自然资源；建造“植物工厂”（六上）；生物与环境 …
  stage 第一学段（1～2年级） grades=[1, 2] domains=['1.物质的结构与性质', '2.物质的变化与化学反应', '3.物质的运动与相互作用', '5.生命系统的构成层次', '6.生物体的稳态与调节', '9.宇宙中的地球', '10.地球系统', '11.人类活动与环境', '12.技术、工程与社会', '13.工程设计与物化']
  stage 第二学段（3～4年级） grades=[3, 4] domains=['1.物质的结构与性质', '2.物质的变化与化学反应', '3.物质的运动与相互作用', '4.能的转化与能量守恒', '5.生命系统的构成层次', '6.生物体的稳态与调节', '7.生物与环境的相互关系', '8.生命的延续与进化', '9.宇宙中的地球', '10.地球系统', '11.人类活动与环境', '12.技术、工程与社会', '13.工程设计与物化']
  stage 第三学段（5～6年级） grades=[5, 6] domains=['1.物质的结构与性质', '2.物质的变化与化学反应', '3.物质的运动与相互作用', '4.能的转化与能量守恒', '5.生命系统的构成层次', '6.生物体的稳态与调节', '7.生物与环境的相互关系', '8.生命的延续与进化', '9.宇宙中的地球', '10.地球系统', '11.人类活动与环境', '12.技术、工程与社会', '13.工程设计与物化']
  stage 第四学段（7～9年级，仅适用于初中开设综合科学课程的地区） grades=[7, 9] domains=['物质科学（核心概念1-4）', '生命科学（核心概念5-8）', '地球与宇宙科学（核心概念9-11）', '技术与工程（核心概念12-13）']
  notes: ["起始年级：课程方案规定科学在一至九年级开设（初中阶段可选择分科开设物理、化学、生物学），课程设置表按“六三”学制列科学为一至六年级（s3）。", "地区差异：初中阶段若开设科学（如浙江等地使用综合科学），需统筹科学与自然地理；“五四”学制第三学段为6～7年级（s1），小学为1～5年级。", "小学科学教材有多个版本（如教科版、人教鄂教版、苏教版等；各版本使用范围本次未核实）。本文件grade_topics按人教鄂教版（人教社与湖北教育出版社合编），因“人教版”小学科学即此版本。", "四、五、六年级下册目录来自镜像站标注“新版”的页面，未注明是否为2024年后的新教材，可能与后续新修订版不一致。", "标准含7～9年级学段内容，仅对开设综合科学的地区适用；本文件grades仍按1～6年级，7～9年级只作概要。", "标准PDF为扫描件，内容经OCR后改写概括；人教鄂教版目录来源为第三方电子课本镜像站（dzkbw.com）。"]
