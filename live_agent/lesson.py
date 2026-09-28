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
