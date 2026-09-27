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
{{"board": {{"title": 小节标题, "items": [板书要点]}}, "lines": [{{"text": 老师说的一句话, "item": 这句话在讲第几条板书要点（从 0 开始）}}]}}
板书要求：3-{max_items} 条要点，每条不超过 {item_chars} 个字，简洁像真正的板书；公式用 LaTeX 写在 $...$ 里（如 $x^2+y^2=r^2$）。
讲稿要求：
1. 按板书顺序讲，每条要点讲 2-4 句：先说要点，再解释原因，再举生活中的例子或算一个小例题。
2. 每句不超过 {chars} 个汉字，口语化；公式和符号全部用中文读出来（如「a 加 b 的和的平方」「x 的平方」），讲稿里不要出现 $、LaTeX、括号、加减乘除号或等号。
3. 直接从这一节的内容讲起，不要打招呼，不要重复开场白或前面讲过的话。
4. 最后一句简短小结这一节{outro}。
5. 总共 10-18 句。"""


@dataclass
class Board:
    key: str  # changes when the board is rewritten (a new section / answer)
    title: str
    items: list[str] = field(default_factory=list)  # raw text with $...$ LaTeX

    def view(self, reveal: int | None) -> dict[str, Any]:
        """What the page shows: items up to ``reveal`` (all when None), the ``reveal``-th highlighted."""
        return {"key": self.key, "title": html.escape(self.title), "items": [render_item(x) for x in self.items],
                "reveal": reveal}


@dataclass
class LessonLine:
    text: str
    board: Board | None  # None: a plain line (keeps whatever the board shows)
    item: int | None  # board point this line explains (None: whole board, e.g. an intro line)
    gesture: bool = False  # first line of a point: present the board


@dataclass
class Outline:
    title: str
    sections: list[dict]
    intro: list[str]


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
        items = [str(x)[:ITEM_CHARS] for x in (b.get("items") or []) if str(x).strip()][:MAX_ITEMS]
        board = Board(key=f"s{i}", title=str(b.get("title") or sec["title"])[:24], items=items)
        lines: list[LessonLine] = []
        seen: set[int] = set()
        for ln in d.get("lines") or []:
            if not isinstance(ln, dict):
                continue
            item = ln.get("item")
            item = item if isinstance(item, int) and 0 <= item < len(items) else None
            for piece in spoken(str(ln.get("text", "")), self.chars):
                first = item is not None and item not in seen
                if item is not None:
                    seen.add(item)
                lines.append(LessonLine(piece, board, item, gesture=first))
        if not lines:
            raise ValueError(f"lesson section {i} without lines")
        return lines

    def intro_lines(self, outline: Outline) -> list[LessonLine]:
        board = Board(key="outline", title=outline.title, items=[s["title"] for s in outline.sections])
        return [LessonLine(x, board, None) for x in outline.intro] or \
            [LessonLine(f"今天我们来学{outline.title}。"[: self.chars], board, None)]


__all__ = ["Board", "LessonLine", "LessonPlanner", "Outline", "render_item", "spoken"]
