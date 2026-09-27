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

OUTLINE_PROMPT = """你是中学老师「{name}」，要给学生上一节关于「{topic}」的课。人设：{bio}
请设计课程大纲，只输出 JSON：
{{"title": 课程标题（不超过 16 字）, "sections": [{{"title": 小节标题（不超过 14 字）, "goal": 这一节要讲清楚什么（一句话）}}], "intro": [开场白，2-3 句]}}
要求：3-5 个小节，由浅入深；开场白先说今天学什么，再说分几部分讲；每句开场白不超过 {chars} 个汉字。
学生之前的对话（只作参考）：{context}"""

SECTION_PROMPT = """你是中学老师「{name}」，正在上「{title}」这节课。人设：{bio}
现在讲第 {i}/{n} 节「{section}」，目标：{goal}。
前面已经讲过：{covered}
请写这一节的板书和讲稿，只输出 JSON：
{{"board": {{"title": 小节标题, "figure": 配图（见下）或 null}},
 "points": [{{"text": 一条板书要点, "lines": [讲这条要点时老师说的话，按顺序]}}],
 "summary": [这一节的小结句]}}
板书要求：3-{max_items} 条要点，每条不超过 {item_chars} 个字，简洁像真正的板书；公式用 LaTeX 写在 $...$ 里（如 $x^2+y^2=r^2$）。
对齐要求：每句讲稿都放在它正在讲的那条要点下面；讲完一条再讲下一条；只属于整节的小结放在 summary 里。
配图：每一节尽量配一张图（这一节确实用不上图时才写 null）；讲稿里只要说到「看这个图」「这个正方形」「这条曲线」等画面，就必须给出对应的 figure，
并且图里画的就是讲稿说的东西。两种：
- 函数图像、坐标系里的点：{{"plot": {{"functions": ["x**2-2*x-3"], "x": [-3, 5], "points": [{{"x": -1, "y": 0, "label": "x₁"}}], "title": 图标题}}, "caption": 图注}}
  （functions 用 Python 写法：x**2、2*x、sqrt(x)、sin(x)；图会被精确画出）
- 几何图形（三角形、正方形、多边形，按比例精确画在方格上）：{{"plot": {{"polygons": [{{"points": [[0,0],[4,0],[0,3]], "label": "直角三角形", "sides": ["4", "5", "3"]}}], "grid": true}}, "caption": 图注}}
  （points 是顶点坐标，sides 依次标注每条边：第 i 条边从第 i 个顶点到下一个顶点）
- 插图、结构、流程、实验装置示意：{{"prompt": 配图描述, "caption": 图注}}；prompt 具体写清画什么、怎么摆放，要标注的文字都放在「」里
  （如：一片绿叶，太阳的箭头标注「阳光」，根部箭头标注「水」）；这类图由图像模型画，画不准数学关系，几何图形和函数图像一律用 plot。
caption 不超过 16 个字。
讲稿要求：
1. 每条要点讲 2-4 句：先说要点，再解释原因，再举生活中的例子或算一个小例题。
2. 每句不超过 {chars} 个汉字，口语化；公式和符号全部用中文读出来（如「a 加 b 的和的平方」「x 的平方」），讲稿里不要出现 $、LaTeX、括号、加减乘除号或等号。
3. 直接从这一节的内容讲起，不要打招呼，不要重复开场白或前面讲过的话。
4. summary 写 1-2 句，简短小结这一节{outro}。
5. 讲稿总共 10-18 句。"""


@dataclass
class Board:
    key: str  # changes when the board is rewritten (a new section / answer)
    title: str
    items: list[str] = field(default_factory=list)  # raw text with $...$ LaTeX
    figure_prompt: str = ""  # an explanatory image is wanted (generated in the background)
    figure_plot: dict | None = None  # an exact graph instead (board_plot spec: functions, x range, points)
    figure_caption: str = ""
    figure_url: str = ""  # set once the image exists; boards locked after that show it

    def view(self, reveal: int | None, progress: tuple[int, int] | None = None) -> dict[str, Any]:
        """What the page shows: items up to ``reveal`` (all when None), the ``reveal``-th highlighted, with the
        spoken line's position within that point (``progress``)."""
        v = {"key": self.key, "title": html.escape(self.title), "items": [render_item(x) for x in self.items],
             "reveal": reveal}
        if progress is not None and reveal is not None:
            v["progress"] = list(progress)
        if self.figure_url:
            v["figure"] = {"url": self.figure_url, "caption": html.escape(self.figure_caption)}
        return v


@dataclass
class LessonLine:
    text: str
    board: Board | None  # None: a plain line (keeps whatever the board shows)
    item: int | None  # board point this line explains (None: whole board, e.g. an intro line or a summary)
    gesture: bool = False  # first line of a point: present the board
    progress: tuple[int, int] | None = None  # (this line, lines about the point), 1-based: shown on the board


@dataclass
class Outline:
    title: str
    sections: list[dict]
    intro: list[str]


def set_figure(board: Board, fig) -> bool:
    """Attach a figure request (an exact plot spec or an illustration prompt) to ``board``; True if one was set."""
    if not isinstance(fig, dict):
        return False
    plot = fig.get("plot")
    if isinstance(plot, dict) and (plot.get("functions") or plot.get("points") or plot.get("polygons")):
        board.figure_plot = fig["plot"]
    elif str(fig.get("prompt") or "").strip():
        board.figure_prompt = str(fig["prompt"]).strip()[:400]
    else:
        return False
    board.figure_caption = str(fig.get("caption") or "")[:20]
    return True


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


_SAY = [(r"\(([^()]*[+＋][^()]*)\)\s*(的)?(平方|²)", r"\1的和的平方"),
        (r"\(([^()]*[-−－][^()]*)\)\s*(的)?(平方|²)", r"\1的差的平方"),
        (r"\^\s*2|²", "的平方"), (r"\^\s*3|³", "的立方"), (r"√\s*", "根号"),
        (r"\s*[+＋]\s*", "加"), (r"(?<=[0-9a-zA-Z])\s*[-−－]\s*(?=[0-9a-zA-Z])", "减"),
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

    async def outline(self, topic: str, context: str = "") -> Outline:
        raw = await self.llm.chat([{"role": "user", "content": OUTLINE_PROMPT.format(
            name=self.name, topic=topic, bio=self.bio, chars=self.chars, context=context or "无")}],
            max_tokens=600, temperature=0.4, json_mode=True)
        d = parse_json(raw)
        sections = [s for s in d.get("sections") or [] if isinstance(s, dict) and s.get("title")][:6]
        if not sections:
            raise ValueError("lesson outline without sections")
        intro = [p for x in d.get("intro") or [] for p in spoken(str(x), self.chars)][:4]
        return Outline(title=str(d.get("title") or topic)[:24], sections=sections, intro=intro)

    async def section(self, outline: Outline, i: int, covered: list[str]) -> list[LessonLine]:
        sec = outline.sections[i]
        last = i == len(outline.sections) - 1
        raw = await self.llm.chat([{"role": "user", "content": SECTION_PROMPT.format(
            name=self.name, bio=self.bio, title=outline.title, i=i + 1, n=len(outline.sections),
            section=sec["title"], goal=sec.get("goal", ""), covered="；".join(covered) or "（这是第一节）",
            max_items=MAX_ITEMS, item_chars=ITEM_CHARS, chars=self.chars,
            outro="，并告诉学生这节课就讲到这里、有问题随时问" if last else "，并引出下一节")}],
            max_tokens=1500, temperature=0.4, json_mode=True)
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
        return lines

    def intro_lines(self, outline: Outline) -> list[LessonLine]:
        board = Board(key="outline", title=outline.title, items=[s["title"] for s in outline.sections])
        return [LessonLine(x, board, None) for x in outline.intro] or \
            [LessonLine(f"今天我们来学{outline.title}。"[: self.chars], board, None)]


__all__ = ["Board", "LessonLine", "LessonPlanner", "Outline", "render_item", "spoken"]
