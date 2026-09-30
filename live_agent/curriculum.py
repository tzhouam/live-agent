"""Course knowledge base: the national curriculum (grades 1-12) and a teaching profile per grade.

Data lives in ``configs/curriculum/*.json`` (one file per subject, plus ``pedagogy.json`` and
``teaching_craft.json``), researched from the 2022 compulsory-education standards and the 2017/2020 senior-high
standards, with per-grade topics from the textbook tables of contents; every file lists its sources and which parts
are estimates. This module finds where a lesson topic sits in the curriculum (subject, grade, the standard's
requirements, prerequisites), how a teacher should teach a given grade (methods, amount of content, tone) and how
a lesson is built and judged (the teaching craft: lesson stages, teacher moves, board rules, master teachers'
methods, a lesson-quality checklist), and renders all of it as prompt context.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def parse_grade(text: str | int | None) -> int | None:
    """"初二" / "初中二年级" -> 8, "高一" / "高中一年级" -> 10, "小学三年级" / "三年级" -> 3, "8年级" / "grade 8" -> 8;
    None if unknown. Meant for a profile's grade field (the API stores the normalised name), not for free text."""
    if isinstance(text, int):
        return text if 1 <= text <= 12 else None
    s = str(text or "").strip().lower()
    if not s:
        return None
    m = re.search(r"(初|高)中?([一二三123])", s)  # the stage first: "初中二年级" is grade 8, not 2
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


_CITE = re.compile(r"[（(]\s*[a-z]{1,2}\d+(?:[、,，\s]*[a-z]{0,2}\d+)*(?:第\S{1,6}页)?\s*[）)]")


def clean(text: Any) -> str:
    """Prompt text without the data's source tags ("（s2、s7）", "（c12）"): those are for audit, not for the teacher
    to say. Control characters go and one entry is at most 200 characters (the data is reference material)."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", _CITE.sub("", str(text))).strip()[:200]


def _prefix(a: str, b: str) -> str:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n]


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def clean_topic(topic: Any) -> str:
    """A lesson topic as prompt data: first line only, no control characters, at most 40 characters."""
    first = str(topic or "").strip().splitlines()[0] if str(topic or "").strip() else ""
    return re.sub(r"[\x00-\x1f\x7f「」]", "", first).strip()[:40]


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
    located: bool = False  # picked by the model from the chapter index: a candidate, relevance not verified


class Curriculum:
    def __init__(self, subjects: list[dict], pedagogy: dict | None = None, craft: dict | None = None):
        self.subjects = subjects
        self.pedagogy = pedagogy or {}
        self.craft = craft or {}  # teaching_craft.json: lesson stages, moves, bands, masters, board, checklist

    @classmethod
    def load(cls, directory: str | Path) -> Curriculum:
        d = Path(directory)
        subjects, pedagogy, craft = [], {}, {}
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                if f.stem == "pedagogy":
                    pedagogy = data
                elif f.stem == "teaching_craft":
                    craft = data
                elif isinstance(data, dict) and data.get("subject"):
                    subjects.append(data)
        return cls(subjects, pedagogy, craft)

    def __bool__(self) -> bool:
        return bool(self.subjects or self.pedagogy or self.craft)

    def subject_names(self) -> list[str]:
        return [str(s.get("subject")) for s in self.subjects if s.get("subject")]

    def subject_of(self, topic: str, grade: int | None = None) -> str:
        """The subject the curriculum files place ``topic`` in (a strong lexical match, else a cached locator pick),
        "" when unknown. No model call: ``locate`` must have run first for chapter-named topics."""
        topic = clean_topic(topic)
        ms = self.lookup(topic, grade, limit=1)
        if ms and ms[0].sim >= 0.8:  # (a close form of) the curriculum's own wording; a weak hit decides nothing
            return ms[0].subject
        picks = (self.__dict__.get("_located") or {}).get(_norm(topic))
        for p in picks if isinstance(picks, list) else []:
            m = self._entry(str(p.get("subject") or ""), p.get("grade"), str(p.get("topic") or ""), topic)
            if m is not None:
                return m.subject
        return ""

    # ------------------------------------------------------------ where does a topic sit
    def lookup(self, topic: str, grade: int | None = None, limit: int = 3) -> list[Match]:
        """Curriculum entries for ``topic``: textbook topics by character-pair similarity (so "函数的单调性" finds
        the senior-high function unit rather than grade 8's "函数"), then the standard's requirements that name it;
        nearest to the student's grade first."""
        topic = clean_topic(topic)
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
                        whole = re.search(rf"\b{re.escape(str(topic).lower().strip())}\b", str(t).lower())
                        sim = 1.0 if nt == q else 0.9 if whole else 0.6 if any(len(_prefix(w, x)) >= min(5, len(x))
                                                                                  for w in words for x in qwords) else 0.0
                    else:
                        sim = 1.0 if nt == q else len(qb & _bigrams(nt)) / max(len(qb), 1)
                    if latin:
                        pass  # whole words only (above): "art" is not in "Smart Learning"
                    elif q in nt and len(q) >= 2:
                        sim = max(sim, 0.9)
                    elif nt and nt in q:
                        sim = max(sim, 0.6)  # the unit named inside the question ("圆" in "圆的面积")
                    if sim < 0.5:
                        continue
                    stage, domain, reqs = self._requirements(subj, g_int, q, t if sim >= 0.9 else "")
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
        if best[0] >= 0.6:  # half the topic's character pairs was too loose ("三角形面积" got the triangle-types one)
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
        topic = clean_topic(topic)
        lexical = self.lookup(topic, grade)
        if any(m.sim >= 0.9 for m in lexical) or llm is None or not self.subjects or len(_norm(topic)) < 2:
            return lexical
        cache = self.__dict__.setdefault("_located", {})
        key = _norm(topic)
        if not isinstance(cache.get(key), list):  # not known yet, or being asked by a concurrent lesson start
            task = cache.get(key)
            if task is None:
                task = cache[key] = asyncio.ensure_future(self._ask_locator(llm, topic))
            try:
                cache[key] = await asyncio.shield(task)
            except Exception:
                cache.pop(key, None)
                raise
        out = []
        for p in cache[key]:
            m = self._entry(str(p.get("subject") or ""), p.get("grade"), str(p.get("topic") or ""), topic)
            if m is not None:
                out.append(m)
        if grade is not None:
            out.sort(key=lambda m: abs((m.grade or grade) - grade))
        return out or lexical

    async def _ask_locator(self, llm, topic: str) -> list[dict]:
        from live_agent.llm import parse_json

        raw = await llm.chat([{"role": "user", "content": LOCATE_PROMPT.format(
            topic=topic, index=self.index_text())}], max_tokens=300, temperature=0.0, json_mode=True)
        try:
            d = parse_json(raw)
        except ValueError:
            return []
        picks = d.get("matches") if isinstance(d, dict) else None
        return [p for p in picks if isinstance(p, dict)][:3] if isinstance(picks, list) else []

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
                long_enough = len(nc) >= max(3, len(nt) // 2)  # "二次" alone does not name "二次根式"
                close = nc and (nc == nt or (long_enough and (nt.startswith(nc) or nc in nt))
                                or (len(nc) >= 6 and nt in nc)
                                or len(_bigrams(nc) & _bigrams(nt)) / max(len(_bigrams(nc)), 1) >= 0.8)
                if close:  # the model copied (a close form of) a real chapter; anything else is dropped
                    # a real chapter is not necessarily the right one: it stays a candidate (no requirement from the
                    # chapter name, no grade warning from it)
                    stage, domain, reqs = self._requirements(subj, g, _norm(topic))
                    prereq = {(_norm(k)): v for k, v in (subj.get("prerequisites") or {}).items()}
                    return Match(subject, g, t, stage, domain, reqs, prereq.get(_norm(t)) or [], e.get("basis", ""),
                                 score=2.0, sim=0.7, located=True)
        return None

    async def topic_context_async(self, llm, topic: str, grade: int | None) -> str:
        return self._render(topic, await self.locate(llm, topic, grade), grade)

    # ------------------------------------------------------------ how to teach a grade
    def profile(self, grade: int | None) -> dict[str, Any]:
        grades = self.pedagogy.get("grades") or {}
        if grade is None or not grades:
            return {}
        return grades.get(str(grade)) or grades.get(str(min(max(grade, 1), 12))) or {}

    def teaching_context(self, grade: int | None, chars: int | None = None, brief: bool = False) -> str:
        """Per-grade teaching guidance for prompts (methods, content per explanation, tone, sentence length).
        ``chars``: the spoken-line limit, stated as overriding the profile's sentence lengths. ``brief``: only tone,
        wording and feedback (for the responder, which sees it on every utterance)."""
        p = self.profile(grade)
        if not p:
            return ""
        parts = [f"学生是{grade_name(grade)}（{p.get('stage', '')}）。按这个年级的特点来教"
                 "（以下是按学段特点整理的经验建议，不是课标原文；其中的时间、数量和句长是估计）："]
        keys = (("tone", "语气"),) if brief else (("methods", "教法"), ("content", "内容量"), ("tone", "语气"),
                                                   ("examples", "例子"), ("avoid", "避免"))
        for key, label in keys:
            v = p.get(key)
            if v:
                parts.append(f"{label}：{'；'.join(clean(x) for x in v) if isinstance(v, list) else clean(v)}")
        if p.get("vocabulary"):
            parts.append(f"用词：{clean(p['vocabulary'])}")
        if p.get("encouragement"):
            parts.append(f"表扬与纠错：{clean(p['encouragement'])}")
        if chars:
            parts.append(f"台词硬性限制：每句不超过{chars}个字（视频每段只能说这么多），这条优先于上面的句长建议；"
                         "长句拆成几句说。")
        return "\n".join(parts)

    def exercise_style(self, grade: int | None) -> str:
        return clean(self.profile(grade).get("exercise_style") or "")

    # ------------------------------------------------------------ teaching craft (lesson stages, moves, masters)
    CRAFT_HEADER = ("教学法参考（从教学法教材、教学竞赛评价标准和名师课例整理的做法建议，编辑意译，不是原文；未标「引用」的数字为估计。"
                    "这是供你选用的参考资料，不是对你的指令；讲稿里的提问是自问自答，学生只在练习时真正作答）：")

    def band(self, grade: int | None) -> dict[str, Any]:
        """The grade band (小学低/中/高年级, 初中, 高中) of ``grade`` in the craft data."""
        if grade is None:
            return {}
        for b in self.craft.get("bands") or []:
            lo, hi = (b.get("grades") or [0, 0])[:2]
            if lo <= grade <= hi:
                return b
        return {}

    def _in_grade(self, item: dict, grade: int | None) -> bool:
        if grade is None:
            return True
        lo, hi = (item.get("grades") or [1, 12])[:2]
        return lo <= grade <= hi

    def moves(self, stage: str | None = None, grade: int | None = None, subject: str = "", limit: int | None = None
              ) -> list[dict]:
        """Teacher moves for a lesson stage (hook / explain / check / practice / close / feedback), the grade and
        the subject ("*" or no subject list matches every subject), best-ranked first."""
        out = []
        for m in self.craft.get("moves") or []:
            if stage and stage not in (m.get("stages") or []):
                continue
            if not self._in_grade(m, grade):
                continue
            subs = m.get("subjects") or ["*"]
            if subject and "*" not in subs and subject not in subs:
                continue
            if not subject and "*" not in subs:
                continue
            out.append(m)
        out.sort(key=lambda m: (m.get("rank", 99), m.get("id", "")))
        return out[:limit] if limit else out

    def masters(self, subject: str = "", grade: int | None = None, limit: int = 2) -> list[dict]:
        """Master teachers whose documented practice fits the subject and grade (the subject must match when
        given; without a subject only cross-subject entries)."""
        out = []
        for m in self.craft.get("masters") or []:
            if not self._in_grade(m, grade):
                continue
            subs = m.get("subjects") or []
            if subject and subject not in subs and "*" not in subs:
                continue
            if not subject and "*" not in subs:
                continue
            out.append(m)
        out.sort(key=lambda m: (m.get("rank", 99), m.get("id", "")))
        return out[:limit]

    def stage(self, stage_id: str) -> dict[str, Any]:
        for st in (self.craft.get("lesson_model") or {}).get("stages") or []:
            if st.get("id") == stage_id:
                return st
        return {}

    def _stage_rules(self, stage_id: str, grade: int | None, n: int) -> list[str]:
        st = self.stage(stage_id)
        rules = [clean(r) for r in (st.get("rules") or [])][:n]
        band = self.band(grade)
        extra = (band.get("stage_notes") or {}).get(stage_id) if band else None
        if extra:
            rules.append(clean(extra))
        return rules

    def _move_lines(self, stage_id: str, grade: int | None, subject: str, n: int) -> list[str]:
        lines = []
        for m in self.moves(stage_id, grade, subject, limit=n):
            ex = clean(m.get("example") or "")
            lines.append(f"{clean(m.get('name'))}：{clean(m.get('what'))}" + (f"（如「{ex}」）" if ex else ""))
        return lines

    def _master_lines(self, subject: str, grade: int | None, n: int = 2, moves_each: int = 3) -> list[str]:
        lines = []
        for m in self.masters(subject, grade, limit=n):
            mv = "；".join(clean(x) for x in (m.get("moves") or [])[:moves_each])
            who = clean(m.get("name")) + ("老师" if (m.get("kind") or "teacher") == "teacher" else "")
            lines.append(f"借鉴{who}（{clean(m.get('method') or '')}）的做法：{mv}")
        return lines

    def plan_craft(self, grade: int | None, subject: str = "") -> str:
        """For the outline prompt: how a lesson is built (stages, one rule each), the band's opening and pacing,
        the masters whose lesson design fits."""
        if not self.craft:
            return ""
        parts = [self.CRAFT_HEADER]
        stages = (self.craft.get("lesson_model") or {}).get("stages") or []
        if stages:
            parts.append("一节课的环节：" + "；".join(
                f"{clean(st.get('name'))}（{clean((st.get('rules') or [''])[0])}）" for st in stages))
        band = self.band(grade)
        if band:
            parts.append(f"{clean(band.get('name'))}的课：" + "；".join(clean(x) for x in (band.get("plan") or [])[:4]))
        hooks = self._move_lines("hook", grade, subject, 3)
        if hooks:
            parts.append("导入的做法：" + "；".join(hooks))
        parts += self._master_lines(subject, grade, n=2, moves_each=2)
        return "\n".join(parts)

    def section_craft(self, grade: int | None, subject: str = "", last: bool = False) -> str:
        """For a section prompt: explanation, questioning, practice (and closing on the last section) moves for
        the grade and subject, the band's notes, the masters' moves, the board rules."""
        if not self.craft:
            return ""
        parts = [self.CRAFT_HEADER]
        for sid, label in (("explain", "讲解"), ("check", "提问与检查理解"), ("practice", "练习"),
                           ("feedback", "反馈")) + ((("close", "结课"),) if last else ()):
            rules = self._stage_rules(sid, grade, 2) + self._move_lines(sid, grade, subject, 3)
            if rules:
                parts.append(f"{label}：" + "；".join(rules))
        band = self.band(grade)
        if band and band.get("section"):
            parts.append(f"{clean(band.get('name'))}：" + "；".join(clean(x) for x in band["section"][:4]))
        parts += self._master_lines(subject, grade, n=2, moves_each=3)
        board = self.board_rules(4)
        if board:
            parts.append("板书：" + "；".join(board))
        return "\n".join(parts)

    def practice_craft(self, grade: int | None, subject: str = "") -> str:
        """For the exercise prompt: how to design a practice question for the grade (rules and moves)."""
        if not self.craft:
            return ""
        rules = self._stage_rules("practice", grade, 3) + self._move_lines("practice", grade, subject, 3)
        return (self.CRAFT_HEADER + "\n练习：" + "；".join(rules)) if rules else ""

    def board_rules(self, n: int | None = None) -> list[str]:
        rules = [clean(r) for r in (self.craft.get("board") or {}).get("rules") or []]
        return rules[:n] if n else rules

    def checklist(self, grade: int | None = None, scope: str = "section") -> list[str]:
        """Lesson-quality checklist items (from competition rubrics and the textbooks) for the grade and ``scope``:
        "section" (a generated section: board + script, the default) or "feedback" (grading feedback)."""
        out = []
        for c in self.craft.get("checklist") or []:
            if self._in_grade(c, grade) and (c.get("scope") or "section") == scope:
                out.append(clean(c.get("item")))
        return out

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
                s += f"，{grade_name(m.grade)}"
                if m.located:
                    s += "（模型从教材目录里挑的候选章节，未核实是否对应本课）"
                elif m.basis == "estimate" or m.grade >= 11:
                    s += "（年级为估计，各校安排不一）"
                elif m.basis == "textbook":
                    s += "（教材）"
            elif m.grades and m.grades[0]:
                if m.grades[0] >= 10:  # 必修 / 选择性必修 are course categories, not fixed school years
                    s += "，课标高中阶段（具体年级各校安排不一）"
                else:
                    s += f"，课标{grade_name(m.grades[0])}" + (f"至{grade_name(m.grades[1])}" if m.grades[1] != m.grades[0] else "")
            if m.stage or m.domain:
                s += f"，{m.stage}{('·' + m.domain) if m.domain else ''}"
            if m.requirements:
                s += f"；课标要求（意译）：{'；'.join(clean(r) for r in m.requirements)}"
            if m.prerequisites:
                s += f"；前置知识：{'、'.join(m.prerequisites)}"
            lines.append(s)
        note = self._grade_note(topic, grade)
        if note:
            lines.append(note)
        return "课程标准参考（系统检索到的相关条目，只采用和本课真正相关的）：\n" + "\n".join(lines)

    def _grade_note(self, topic: str, grade: int | None) -> str:
        """Above / below the student's grade only when every textbook grade that teaches the topic (same wording or
        containing it) says so: a concept taught in several grades ("三角形" in grades 4 and 8) is never flagged, and
        neither are senior-high grades for a senior-high student (the order of 选择性必修 varies by school)."""
        if grade is None:
            return ""
        taught = sorted({m.grade for m in self.lookup(topic, None, limit=200)
                         if m.grade is not None and m.sim >= 0.9 and m.basis != "estimate"})
        if not taught:
            return ""
        if taught[0] > grade and not (grade >= 10 and taught[0] >= 10):
            where = "高中" if taught[0] >= 10 else grade_name(taught[0])
            return (f"注意：这个内容一般在{where}学，学生现在{grade_name(grade)}，"
                    f"要从学生已有的知识讲起，降低难度，必要时先补前置知识。")
        if taught[-1] < grade - 2:
            return f"注意：这是{grade_name(taught[-1])}的内容，学生已经{grade_name(grade)}，以复习和提高为主。"
        return ""

    def summary(self) -> dict[str, Any]:
        return {"subjects": [{"subject": s.get("subject"), "grades": s.get("grades"),
                              "sources": len(s.get("sources") or []),
                              "topics": sum(len((e or {}).get("topics") or []) for e in (s.get("grade_topics") or {}).values())}
                             for s in self.subjects],
                "pedagogy_grades": sorted(int(g) for g in (self.pedagogy.get("grades") or {}) if str(g).isdigit()),
                "craft": {k: len(self.craft.get(k) or []) for k in ("moves", "masters", "bands", "checklist")}
                if self.craft else {}}


LOCATE_PROMPT = """下面是中国中小学课程目录（每行：学科|年级|这个年级的教材章节，章节之间用；分隔）。
请找出讲「{topic}」这个内容的章节，最多 3 个，最主要的放第一个；同一内容在不同学段都讲的（如初中和高中），各列一个。
topic 必须从目录里原样复制章节名，不要自己编；目录里没有相关章节就返回空列表。
只输出 JSON：{{"matches": [{{"subject": 学科（原样）, "grade": 年级数字, "topic": 章节名（原样）}}]}}
目录：
{index}"""


__all__ = ["Curriculum", "LOCATE_PROMPT", "Match", "clean_topic", "grade_name", "parse_grade"]
