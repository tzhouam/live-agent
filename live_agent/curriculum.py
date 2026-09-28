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
