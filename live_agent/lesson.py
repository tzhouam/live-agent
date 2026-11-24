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
from live_agent.types import new_id

MAX_ITEMS = 6
ITEM_CHARS = 60
# section depth chosen by the outline from the student's profile: (spoken lines, instruction)
DEPTH_NAMES = {"review": "复习（学生已掌握，按计划只讲 1-2 条要点、快速带过、不举新例子，不按重点课的标准要求）",
               "core": "重点（学生薄弱或考试失分，要放慢、每条要点有例子或例题、指出常见错误）",
               "new": "新内容（正常讲解）"}
DEPTHS = {
    "review": ("4-6", "这一节是复习，学生已经掌握：只讲 1-2 条要点，每条一两句，快速带过，不举新例子。"),
    "core": ("14-20", "这一节是重点，学生这里薄弱或考试失分：放慢，每条要点先讲直观理解，再举一个具体的例子或算一道例题，指出常见错误。"),
    "new": ("10-18", "这一节是新内容，正常讲解。"),
}
MIN_ITEMS = {"review": 1, "core": 3, "new": 3}  # board points: a review section is brief by design
MAX_EXERCISES = 3  # per lesson (the outline prompt asks for 1-3)

OUTLINE_PROMPT = """你是{role}「{name}」，要给学生上一节关于「{topic}」的课。人设：{bio}
学生档案（年级、考试成绩、各概念的掌握情况）：
{profile}
{curriculum}{craft}请按这个学生的情况因材施教，设计课程大纲，只输出 JSON：
{{"title": 课程标题（不超过 16 字）, "subject": 学科（{subjects}之一，原样写）,
 "plan_note": 一句话说明你根据档案怎么安排的（给老师自己看，不念出来）,
 "objectives": [学习目标 1-3 条，写成学生学完能做什么（「能……」），每条不超过 20 字],
 "key_point": 本课重点（不超过 20 字）, "difficulty": 本课难点（学生最容易卡住的地方，不超过 20 字）,
 "hook_type": 导入方式（情境、问题、复习、故事、实验、直接之一，按年级和内容选）,
 "sections": [{{"title": 小节标题（不超过 14 字）, "goal": 这一节要讲清楚什么（一句话）,
   "concepts": [这一节讲的概念，档案里已有的概念用完全相同的名字，每个不超过 8 字],
   "role": "main"（「{topic}」本身的内容）或 "prerequisite"（不先会就学不了「{topic}」的前置知识）,
   "depth": "review"（已掌握，一两句带过）或 "core"（薄弱或考试失分，重点讲、放慢、多举例）或 "new"（新内容，正常讲）,
   "exercise": true 或 false（讲完这一节出一道练习）}}],
 "intro": [导入和开场，3-5 句]}}
要求：3-5 个小节，由浅入深、小步子推进，全部围绕「{topic}」；讲解深度、用词和例子符合学生的年级；重点和难点各落在某个 core 或 new 小节里。
因材施教只改变「怎么讲」，不改变「讲什么」：
- 不要加入和「{topic}」无关的内容，档案里其他薄弱的知识点（哪怕考试丢过分）不要为了补弱点塞进这节课；
- 前置知识最多 1 节、放在最前面，只有学生这个前置知识薄弱时才讲，否则不单独成节；
- 学生对「{topic}」本身薄弱或考试失分：放慢、多举例（core）；已经掌握：讲得更快、例题更有挑战，但仍然讲「{topic}」，不要换话题。
整节课 1-3 道练习，都考「{topic}」本身，放在重点小节后面；没有档案时按{default_grade}的一般水平讲。
intro 是导入和开场：先按 hook_type 导入（一个学生熟悉的情境、一个悬念问题、一句复习旧知或一个小故事，1-2 句），再说学完能做什么（对应 objectives），最后说分几部分讲；知道学生情况时可以自然地提一句（如「上次考试这里丢了分，今天重点讲」）；每句不超过 {chars} 个汉字。
学生之前的对话（只作参考）：{context}"""

SECTION_PROMPT = """你是{role}「{name}」，正在上「{title}」这节课。人设：{bio}
现在讲第 {i}/{n} 节「{section}」，目标：{goal}。{focus}
前面已经讲过：{covered}
请写这一节的板书和讲稿，只输出 JSON：
{{"board": {{"title": 小节标题}},
 "points": [{{"text": 一条板书要点, "lines": [讲这条要点时老师说的话，按顺序]}}],
 "summary": [这一节的小结句]}}
板书要求：{min_items}-{max_items} 条要点，每条不超过 {item_chars} 个字，简洁像真正的板书；公式用 LaTeX 写在 $...$ 里（如 $x^2+y^2=r^2$）。
对齐要求：每句讲稿都放在它正在讲的那条要点下面；讲完一条再讲下一条；只属于整节的小结放在 summary 里。
讲稿要求：
1. 每条要点讲 2-4 句：先说要点，再解释原因，再举生活中的例子或算一个小例题；重点、难点所在的要点多加一句常见错误或换一个变式。
2. 每句不超过 {chars} 个汉字，口语化；公式和符号全部用中文读出来（如「a 加 b 的和的平方」「x 的平方」），讲稿里不要出现 $、LaTeX、括号、加减乘除号或等号。
3. 直接从这一节的内容讲起，不要打招呼，不要重复开场白或前面讲过的话。
   配图由系统按要点另外判断和绘制；讲图形、图像或结构时可以说「看黑板上的图」，但不要描述图里没有的细节。
4. 在需要引导思考时自然地提出一个具体问题，再解释思路；不必每节都设问。学生没有作答时，不要说「对」「答得真好」或假装收到了回答。避免反复使用「你猜猜」「明白了吗」和夸张语气。
5. summary 写 1-2 句，简短小结这一节{outro}。
6. 讲稿总共 {n_lines} 句。{craft}
7. 每条新概念要点都走完「直观情境 → 为什么/条件 → 展开的例子 → 回扣结论」。例题写清中间推理，不只念答案。
   不要把所有句子写成同一句结论的改写；要点之间有因果或递进。重点内容用一个常见错误与正确方法对照。
   检查理解的问题要能暴露具体误解，不能只问懂了吗；若本节另有练习，不要提前透露那道练习的答案。
因材施教：{adapt}{exercise_req}"""


CHECK_PROMPT = """你是中小学教学竞赛的评委。下面是{role}「{name}」给{grade}学生上「{title}」这节课的第 {i}/{n} 节「{section}」的板书和讲稿（一对一视频课，台词可以短，但要按完整意思和自然停顿组织，不能把无意义的碎片句当成正常讲解）。
本课目标：{objectives}；重点：{key_point}；难点：{difficulty}。
这一节的定位：{depth}。练习题由系统在小结后另外提出（讲稿末尾的 [练习] 行），没有 [练习] 行的小节本来就不出题，不算缺练习。
请按下面的标准逐条打分，只输出 JSON：
{{"scores": {{"1": 0-2, "2": 0-2, ...}}（0 不符合，1 部分符合，2 符合；一条标准对这一节不适用时记 2，不列为问题）,
 "problems": [最多 3 条最严重的问题，每条一句，指出具体是哪条要点或哪句话],
 "pass": true 或 false（有标准得 0 分，或有三条以上只得 1 分，就 false）,
 "fix": 一句话说明重写这一节时最需要改什么}}
评价标准：
{checklist}
板书「{board_title}」：
{board}
讲稿：
{lines}"""


FIGURE_JUDGE_PROMPT = """你是教学设计专家。下面是「{title}」这一节的板书要点，以及老师讲每条要点时说的话。
采用先看懂、再讲清的教学方式：逐条为实质性知识点安排有帮助的图，目标是多数要点都有视觉支持，而不只给最难的要点画图。
具体概念、定义和简单事实可以用例子、结构或分类图说明；简单例题、数量关系、变化过程、循环、对比、实验步骤也优先配图。
复杂程度不是是否配图的门槛；即使 complexity 为 1，只要图能帮助理解或展示具体例子，need 就应为 true。
几何图形和空间关系、函数图像、细胞等结构、多个量的对比都适合配图。不同要点围绕各自的概念或例子画图，避免重复同一张泛泛的全课图。
讲解里说到「看黑板上的图」「这个形状」「这条曲线」的，必须配图。
只跳过纯问候、鼓励、过渡、没有知识内容的提问以及没有新内容的空泛小结；有具体比较或例子的总结仍可配图。
每个要点最多一张，最多给 {max_figs} 个要点配图，优先覆盖不同的知识点。已有配图可保留，不重复提出同一要点。
只输出 JSON：{{"points": [{{"i": 要点序号, "complexity": 1-3（1 简单，2 一般，3 抽象或空间关系复杂）, "need": true 或 false, "why": 一句理由, "figure": 需要时写配图，否则 null}}]}}
配图写法：
- 函数图像、坐标系里的点：{{"plot": {{"functions": ["x**2-2*x-3"], "x": [-3, 5], "points": [{{"x": -1, "y": 0, "label": "x₁"}}], "title": 图标题}}, "caption": 图注}}
  （functions 用 Python 写法：x**2、2*x、sqrt(x)、sin(x)；图会被精确画出）
- 几何图形（三角形、正方形、多边形，按比例精确画在方格上）：{{"plot": {{"polygons": [{{"points": [[0,0],[4,0],[0,3]], "label": "直角三角形", "sides": ["4", "5", "3"]}}], "grid": true}}, "caption": 图注}}
  （points 是顶点坐标，sides 依次标注每条边：第 i 条边从第 i 个顶点到下一个顶点）
- 插图、结构、流程、实验装置示意：{{"prompt": 配图描述, "caption": 图注}}；prompt 具体写清画什么、怎么摆放，要标注的文字都放在「」里
  （如：一片绿叶，太阳的箭头标注「阳光」，根部箭头标注「水」）；这类图表达结构和概念关系，几何图形和函数图像一律用 plot。
caption 不超过 16 个字。
整段回答或总结的上下文（不属于任何一个特定要点，不要按句子序号映射到要点）：
{context}
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
    strip_numbering: bool = True  # explanatory points number themselves; exercise text must stay exact

    def view(self, reveal: int | None, progress: tuple[int, int] | None = None) -> dict[str, Any]:
        """What the page shows: items up to ``reveal`` (all when None), the ``reveal``-th highlighted, with the
        spoken line's position within that point (``progress``)."""
        v = {"key": self.key, "title": html.escape(self.title),
             "items": [render_item(x, strip_numbering=self.strip_numbering) for x in self.items],
             "reveal": reveal}
        if progress is not None and reveal is not None:
            v["progress"] = list(progress)
        v["figures"] = [{"url": f.url, "caption": html.escape(f.caption), "point": f.point}
                        for f in self._ready_figures()]
        fig = self.figure_for(reveal)
        if fig is not None:
            v["figure"] = {"url": fig.url, "caption": html.escape(fig.caption)}
        return v

    def figure_for(self, reveal: int | None) -> Figure | None:
        """The figure of the point being explained, else the board's own figure; never another point's figure
        (it would illustrate something she is not talking about)."""
        ready = self._ready_figures()
        exact = [f for f in ready if reveal is not None and f.point == reveal]
        whole = [f for f in ready if f.point is None]
        return (exact or whole or [None])[0]

    def _ready_figures(self) -> list[Figure]:
        """One authoritative figure per valid point, including future points for manual gallery viewing."""
        points, ready = set(), []
        for fig in self.figures:
            if fig.point is not None and (type(fig.point) is not int or not 0 <= fig.point < len(self.items)):
                continue
            if fig.point in points:
                continue
            points.add(fig.point)
            if fig.url:
                ready.append(fig)
        return ready


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
    subject: str = ""  # the school subject (from the model, checked against the curriculum's subject names)
    objectives: list[str] = field(default_factory=list)  # what the student can do afterwards ("能…")
    key_point: str = ""  # 重点
    difficulty: str = ""  # 难点
    hook_type: str = ""  # how the intro opens (情境 / 问题 / 复习 / 故事 / 实验 / 直接)
    board_key: str = field(default_factory=lambda: new_id("lesson"))  # isolates late figures across lessons

    def focus(self) -> str:
        """The lesson's objectives, key point and difficulty for a section prompt ("" when the outline has none)."""
        parts = []
        if self.objectives:
            parts.append("本课目标：" + "；".join(self.objectives))
        if self.key_point:
            parts.append("重点：" + self.key_point)
        if self.difficulty:
            parts.append("难点：" + self.difficulty)
        return ("\n" + "；".join(parts) + "。") if parts else ""


def _figure_request(fig) -> tuple[dict | None, str] | None:
    if not isinstance(fig, dict):
        return None
    plot = fig.get("plot")
    if isinstance(plot, dict) and (plot.get("functions") or plot.get("points") or plot.get("polygons")):
        # Model records need the renderer's containers, otherwise a malformed first
        # record can consume a point and prevent its corrected duplicate being used.
        functions, points, polygons = (plot.get(k) or [] for k in ("functions", "points", "polygons"))
        if not all(isinstance(value, list) for value in (functions, points, polygons)):
            return None
        if any(not isinstance(f, str) or not f.strip() for f in functions):
            return None
        if any(not isinstance(p, dict) or "x" not in p or "y" not in p for p in points):
            return None
        for polygon in polygons:
            if not isinstance(polygon, dict):
                return None
            vertices = polygon.get("points")
            if not isinstance(vertices, list) or len(vertices) < 2:
                return None
            if any(not isinstance(v, list) or len(v) != 2 for v in vertices):
                return None
            if polygon.get("sides") is not None and not isinstance(polygon["sides"], list):
                return None
        if any(plot.get(axis) is not None and
               (not isinstance(plot[axis], list) or len(plot[axis]) != 2) for axis in ("x", "y")):
            return None
        return plot, ""
    prompt = fig.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return None, prompt.strip()[:400]
    return None


def set_figure(board: Board, fig, point: int | None = None, why: str = "") -> Figure | None:
    """Attach at most one figure per valid point, preserving an existing queued or ready figure."""
    if point is not None and (type(point) is not int or not 0 <= point < len(board.items)):
        return None
    request = _figure_request(fig)
    if request is None:
        return None
    existing = next((f for f in board.figures if (f.point is None if point is None
                     else type(f.point) is int and f.point == point)), None)
    if existing is not None:
        return existing
    f = Figure(point=point, caption=str(fig.get("caption") or "")[:20], why=str(why)[:60], board_key=board.key)
    f.plot, f.prompt = request
    board.figures.append(f)
    return f


_CTRL = {"\n": "\\n", "\t": "\\t", "\x0c": "\\f", "\x08": "\\b", "\r": "\\r"}


def repair_latex(text: str) -> str:
    """LaTeX whose backslash a JSON reply did not double: "\\neq" arrives as a newline + "eq" (seen live on the board as
    "(a+b)² eq a²+b²"), likewise \\times / \\theta (tab), \\frac (form feed), \\beta (backspace), \\right (CR).
    Inside $...$ a control character followed by a letter is put back as the command."""
    def fix(m):
        return re.sub(r"[\n\t\x0c\x08\r](?=[a-zA-Z])", lambda c: _CTRL[c.group(0)], m.group(0))
    return re.sub(r"\$[^$]*\$", fix, text or "")


# LaTeX commands read out (the rest are dropped): the meaning of ≠, ×, a fraction or a root must survive speech
_TEX_SAY = [(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\2分之\1"), (r"\\sqrt\s*\{([^{}]*)\}", r"根号\1"),
            (r"\\(neq|ne)(?![a-zA-Z])", "不等于"), (r"\\(times|cdot)(?![a-zA-Z])", "乘"), (r"\\div(?![a-zA-Z])", "除以"),
            (r"\\(leq|le)(?![a-zA-Z])", "小于等于"), (r"\\(geq|ge)(?![a-zA-Z])", "大于等于"), (r"\\pm(?![a-zA-Z])", "加减"),
            (r"\\approx(?![a-zA-Z])", "约等于"), (r"\\pi(?![a-zA-Z])", "派"), (r"\\(to|rightarrow)(?![a-zA-Z])", "变成"),
            (r"<", "小于"), (r">", "大于")]


def _tex_say(tex: str) -> str:
    for pat, rep in _TEX_SAY:
        tex = re.sub(pat, rep, tex)
    return re.sub(r"\\[a-zA-Z]+|[{}]", "", tex)


def render_item(text: str, *, strip_numbering: bool = True) -> str:
    """Board text -> safe HTML: plain text escaped, **bold**, $...$ LaTeX as MathML (text fallback)."""
    text = repair_latex(text)
    if strip_numbering:
        text = re.sub(r"^\s*(?:\d{1,2}|[一二三四五六七八九十])\s*[.、．)）]\s*", "", text)  # the board numbers points itself
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
    text = re.sub(r"\$([^$]*)\$", lambda m: _tex_say(m.group(1)), repair_latex(text))
    text = text.replace("\\", "").strip()
    text = _say(text).replace("*", "").strip()
    if not text:
        return []
    pieces, cur = [], ""
    # a closing quote or bracket after the punctuation stays with its sentence (seen live: '“鲸很大……重得多。' then
    # '”用了什么方法？' as two lines)
    for tok in re.split(r"(?<=[，。！？；：,.!?;])(?![”」』）\)\]])", text):
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
    def __init__(self, llm: ChatLLM, *, name: str, bio: str, chars: int = 22, curriculum=None):
        self.llm, self.name, self.bio, self.chars = llm, name, bio, chars
        self.curriculum = curriculum  # curriculum.Curriculum: where the topic sits, how to teach the grade
        self.last_curriculum = ""  # the curriculum block of the last outline (for the log)

    def _grade(self, profile) -> int | None:
        from live_agent.curriculum import parse_grade

        return parse_grade(profile.grade) if profile is not None else None

    def _role(self, profile) -> str:
        g = self._grade(profile)
        return "小学老师" if g is not None and g <= 6 else "高中老师" if g is not None and g >= 10 else "中学老师"

    async def _curriculum_block(self, topic: str, profile) -> str:
        if not self.curriculum:
            return ""
        g = self._grade(profile)
        try:
            where = await self.curriculum.topic_context_async(self.llm, topic, g)
        except Exception:  # noqa: BLE001 - the locator failed: plan without the curriculum reference
            where = self.curriculum.topic_context(topic, g)
        parts = [where, self.curriculum.teaching_context(g, self.chars)]
        text = "\n".join(x for x in parts if x)
        return (text + "\n") if text else ""

    def _craft(self, kind: str, grade: int | None, subject: str = "", last: bool = False) -> str:
        """The teaching-craft block ("" without craft data): lesson stages and opening moves for the outline
        ("plan"), explanation / questioning / practice / board moves for a section ("section")."""
        if not self.curriculum or not getattr(self.curriculum, "craft", None):
            return ""
        text = self.curriculum.plan_craft(grade, subject) if kind == "plan" else \
            self.curriculum.section_craft(grade, subject, last=last)
        return text

    async def outline(self, topic: str, context: str = "", profile=None, feedback: str = "") -> Outline:
        """``profile``: a student.StudentProfile (None: no saved profile, an average student of ``default_grade``)."""
        curriculum = await self._curriculum_block(topic, profile)
        self.last_curriculum = curriculum  # for the log
        g = self._grade(profile)
        known = self.curriculum.subject_names() if self.curriculum else []
        placed = self.curriculum.subject_of(topic, g) if self.curriculum else ""  # the curriculum's own placement
        craft = self._craft("plan", g, placed)
        raw = await self.llm.chat([{"role": "user", "content": OUTLINE_PROMPT.format(
            name=self.name, topic=topic, bio=self.bio, chars=self.chars, context=context or "无", role=self._role(profile),
            profile=profile.summary() if profile is not None else "无（新学生，没有档案）",
            subjects="、".join(known) or "语文、数学、英语、物理、化学、生物学、历史、地理、道德与法治、科学、信息科技",
            curriculum=curriculum, craft=(craft + "\n") if craft else "",
            default_grade=(profile.grade if profile is not None and profile.grade else "初中"))
            + ("\n上一版备课大纲的评审意见：" + feedback + "。修正具体问题，保持原主题和学生程度。" if feedback else "")}],
            max_tokens=1100, temperature=0.4, json_mode=True)
        d = parse_json(raw)
        sections, prereq = [], 0
        for s in d.get("sections") or []:
            if isinstance(s, dict) and s.get("title"):
                # the profile adapts how the topic is taught, never what: off-topic sections are dropped (seen live:
                # a 勾股定理 lesson got a "core" section on 完全平方公式 because the profile listed it as weak), and at
                # most one prerequisite section is kept
                role = s.get("role") if s.get("role") in ("main", "prerequisite") else "main"
                if role == "prerequisite":
                    prereq += 1
                    if prereq > 1 or sections:
                        continue
                s["role"] = role
                s["concepts"] = [str(c).strip()[:12] for c in (s.get("concepts") or []) if str(c).strip()][:4]
                s["depth"] = s.get("depth") if s.get("depth") in DEPTHS else "new"
                s["exercise"] = bool(s.get("exercise"))
                sections.append(s)
        sections = sections[:6]
        if not sections:
            raise ValueError("lesson outline without sections")
        n_ex = 0
        for sec in sections:  # the prompt asks for 1-3 exercises; the plan is capped, not trusted
            if sec["exercise"]:
                n_ex += 1
                if n_ex > MAX_EXERCISES:
                    sec["exercise"] = False
        intro = [p for x in d.get("intro") or [] for p in spoken(str(x), self.chars)][:6]
        # the subject: the curriculum's placement of the topic when it has one (a strong lexical match or a locator
        # pick), else the model's word if the curriculum knows that subject (a model label never overrides a placement)
        said = str(d.get("subject") or "").strip()
        model_subject = said if said in known else next((k for k in known if said and (said in k or k in said)), "")
        subject = placed or model_subject
        self.last_subject = {"placed": placed, "model": model_subject}  # for the log (a disagreement is visible)
        objectives = [str(x).strip()[:24] for x in (d.get("objectives") or []) if str(x).strip()][:3]
        return Outline(title=str(d.get("title") or topic)[:24], sections=sections, intro=intro,
                       note=str(d.get("plan_note") or "")[:120], subject=subject, objectives=objectives,
                       key_point=str(d.get("key_point") or "").strip()[:24],
                       difficulty=str(d.get("difficulty") or "").strip()[:24],
            hook_type=str(d.get("hook_type") or "").strip()[:6])

    async def review_outline(self, outline: Outline, topic: str, profile=None) -> dict:
        from live_agent.teaching_quality import review_material
        material = {"outline": {"title": outline.title, "objectives": outline.objectives,
                    "key_point": outline.key_point, "difficulty": outline.difficulty,
                    "sections": outline.sections, "intro": outline.intro}}
        return await review_material(self.llm, material, goal=f"为「{topic}」准备符合学生程度的课程大纲",
            profile=profile.summary() if profile is not None else "",
            guidance="这是课程大纲，不是讲稿。example检查不适用记2，不要求大纲写展开算例。"
            "reasoning检查小节目标与前置关系和递进顺序；alignment检查是否围绕原主题、目标有对应小节。"
            "correctness检查目标、重点、难点和导入是否有错误概念；不能人为对立本来相同的概念。"
            "练习尚未生成，不要求大纲展示题目或答案。不要要求复习小节提前讲完核心小节。")

    async def section(self, outline: Outline, i: int, covered: list[str], profile=None,
                      mistakes: list[str] | None = None, feedback: str = "") -> list[LessonLine]:
        """One section; with a profile its depth, examples and exercise follow the student's understanding of
        the section's concepts, and ``mistakes`` (this lesson's wrong answers so far) are addressed first.
        ``feedback``: the self-check's problems with a previous version of this section, to be corrected."""
        from live_agent.exercise import EXERCISE_SPEC, Exercise

        sec = outline.sections[i]
        last = i == len(outline.sections) - 1
        depth = sec.get("depth") if sec.get("depth") in DEPTHS else "new"
        adapt = [DEPTHS[depth][1]]
        want_ex = bool(sec.get("exercise"))
        if profile is not None:
            if profile.grade:
                adapt.append(f"学生是{profile.grade}，用这个年级听得懂的说法和例子。")
            adapt.append(f"学生对本节概念的掌握：{profile.concept_notes(sec.get('concepts') or [])}。")
            adapt.append(f"只讲本节和「{outline.title}」的内容；学生其他薄弱的知识点不要展开，需要用到时一句话带过。")
        if self.curriculum and profile is not None:
            teach = self.curriculum.teaching_context(self._grade(profile), self.chars)
            if teach:
                adapt.append("\n" + teach + "\n")
            ex_style = self.curriculum.exercise_style(self._grade(profile))
            if want_ex and ex_style:
                adapt.append(f"练习题的形式：{ex_style}。")
        if mistakes:
            adapt.append(f"学生刚才的练习做错了：{'；'.join(mistakes[-2:])}。本节第一条要点先用一两句换个说法把这个错误纠正过来。")
        if feedback:
            adapt.append(f"\n上一版讲稿的评审问题：{feedback}。这一版必须改正这些问题，其他保持。")
        ex_req = ("\n7. 讲完出一道练习，考查本节最重要的概念，难度按学生的掌握度定（薄弱出基础题，已掌握出稍有变化的题）；"
                  "在 JSON 里加字段 \"exercise\"。" + EXERCISE_SPEC.format(chars=self.chars, q_chars=60)) if want_ex else ""
        craft = self._craft("section", self._grade(profile), outline.subject, last=last)
        raw = await self.llm.chat([{"role": "user", "content": SECTION_PROMPT.format(
            name=self.name, bio=self.bio, title=outline.title, i=i + 1, n=len(outline.sections), role=self._role(profile),
            section=sec["title"], goal=sec.get("goal", ""), covered="；".join(covered) or "（这是第一节）",
            focus=outline.focus(), min_items=MIN_ITEMS[depth], max_items=MAX_ITEMS, item_chars=ITEM_CHARS, chars=self.chars,
            n_lines=DEPTHS[depth][0], adapt="".join(adapt), exercise_req=ex_req, craft=("\n" + craft) if craft else "",
            outro=("，回到本课目标和重点，用一句话让学生记住最关键的一点，再留一个小延伸或悬念，并告诉学生这节课就讲到这里、有问题随时问"
                   if last else "，并引出下一节"))}],
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
        board = Board(key=f"{outline.board_key}:s{i}", title=str(b.get("title") or sec["title"])[:24], items=[g[0] for g in groups])
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

    async def review_section(self, outline: Outline, i: int, lines: list[LessonLine], profile=None) -> dict:
        """Pre-presentation review includes reasoning, worked examples and exercise answers."""
        from live_agent.teaching_quality import review_material
        board = next((line.board for line in lines if line.board is not None), None)
        exercise = next((line.exercise for line in lines if line.exercise is not None), None)
        material = {"board": {"title": board.title, "items": board.items} if board else None,
                    "lines": [{"point": line.item, "text": line.text} for line in lines if line.exercise is None],
                    "exercise": {"question": exercise.question, "answer": exercise.answer,
                                 "options": exercise.options} if exercise else None}
        checklist = self.curriculum.checklist(self._grade(profile)) if self.curriculum and self.curriculum.craft else []
        sec = outline.sections[i]
        return await review_material(self.llm, material, goal=f"本节「{sec['title']}」：{sec.get('goal', '')}",
            profile=profile.summary() if profile is not None else "",
            context=f"全课「{outline.title}」背景（不是要求本节覆盖的全部内容）：" + outline.focus(),
            guidance=DEPTH_NAMES.get(sec.get("depth"), DEPTH_NAMES["new"])
            + "；只按本节目标检查，不要求前置/复习小节讲完后续主课内容或提前解后面的题。"
            + "；教学参考：" + "；".join(checklist))

    async def check_section(self, outline: Outline, i: int, lines: list[LessonLine], profile=None) -> dict:
        """Self-check of a generated section against the lesson-quality checklist (competition rubrics and the
        textbooks): {"pass", "scores", "problems", "fix"}; {} without craft data. A judgement, not a measurement:
        the checklist is editorial and the judge is the same model family as the writer."""
        items = self.curriculum.checklist(self._grade(profile)) if self.curriculum and self.curriculum.craft else []
        board = next((ln.board for ln in lines if ln.board is not None), None)
        if not items or board is None:
            return {}
        from live_agent.curriculum import grade_name

        g = self._grade(profile)
        said = "\n".join(f"[要点{ln.item + 1 if ln.item is not None else '-'}] {ln.text}" for ln in lines
                         if ln.exercise is None)
        ex = next((ln.exercise for ln in lines if ln.exercise is not None), None)
        if ex is not None:
            said += f"\n[练习] {ex.question}" + (f"（{' '.join(ex.options)}）" if getattr(ex, "options", None) else "")
        depth = outline.sections[i].get("depth") if outline.sections[i].get("depth") in DEPTHS else "new"
        raw = await self.llm.chat([{"role": "user", "content": CHECK_PROMPT.format(
            role=self._role(profile), name=self.name, grade=grade_name(g) if g else "中学", title=outline.title,
            i=i + 1, n=len(outline.sections), section=outline.sections[i]["title"], depth=DEPTH_NAMES[depth],
            objectives="；".join(outline.objectives) or "（未给出）", key_point=outline.key_point or "（未给出）",
            difficulty=outline.difficulty or "（未给出）",
            checklist="\n".join(f"{k + 1}. {x}" for k, x in enumerate(items)),
            board_title=board.title, board="\n".join(f"- {x}" for x in board.items), lines=said)}],
            max_tokens=700, temperature=0.1, json_mode=True)
        d = parse_json(raw)
        raw_scores = d.get("scores") if isinstance(d.get("scores"), dict) else {}
        scores = {}
        for k in range(1, len(items) + 1):  # one integer 0-2 per checklist item, nothing else: else no verdict
            v = raw_scores.get(str(k))
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v not in (0, 1, 2):
                raise ValueError(f"incomplete self-check verdict: item {k} scored {v!r}")
            scores[str(k)] = int(v)
        problems = [str(x).strip()[:80] for x in (d.get("problems") or []) if str(x).strip()][:3]
        # the pass rule is applied here, whatever the judge wrote in "pass"
        ok = not any(v == 0 for v in scores.values()) and sum(v == 1 for v in scores.values()) <= 3
        return {"pass": ok, "scores": scores, "problems": problems, "fix": str(d.get("fix") or "").strip()[:120],
                "items": len(items)}


    async def judge_figures(self, lines: list[LessonLine], max_figs: int = MAX_ITEMS) -> list[dict]:
        """Plan visual support for substantive points, bounded by a per-point budget.

        Existing figures remain authoritative; duplicated model records cannot replace
        queued/drawn images. Unassigned speech supplies global context, never a guessed point.
        """
        board = next((ln.board for ln in lines if ln.board is not None), None)
        if board is None or not board.items:
            return []
        if type(max_figs) is not int or max_figs < 0:
            raise ValueError("figure budget must be a nonnegative integer")
        budget = min(max_figs, MAX_ITEMS, len(board.items))
        if not budget:
            return []
        said = {j: [] for j in range(len(board.items))}
        context = []
        for ln in lines:
            if ln.board is not None and ln.board is not board:
                continue
            if ln.item is None:
                context.append(ln.text)
            elif type(ln.item) is int and ln.item in said:
                said[ln.item].append(ln.text)
        points = "\n".join(f"{j}. {board.items[j]}：{''.join(said[j])}" for j in range(len(board.items)))
        raw = await self.llm.chat([{"role": "user", "content": FIGURE_JUDGE_PROMPT.format(
            title=board.title, max_figs=budget, points=points, context="\n".join(context) or "无额外上下文")}],
            max_tokens=max(1200, 300 * budget + 400), temperature=0.2, json_mode=True)
        verdicts = {}
        for d in parse_json(raw).get("points") or []:
            if not isinstance(d, dict) or type(d.get("i")) is not int or not 0 <= d["i"] < len(board.items):
                continue
            previous = verdicts.get(d["i"])
            usable = d.get("need") is True and _figure_request(d.get("figure")) is not None
            earlier_usable = previous is not None and previous.get("need") is True and _figure_request(previous.get("figure")) is not None
            if previous is None or (usable and not earlier_usable):
                verdicts[d["i"]] = d
        existing = {}
        for fig in board.figures:
            if type(fig.point) is int and 0 <= fig.point < len(board.items):
                existing.setdefault(fig.point, fig)
        out = []
        for i, d in verdicts.items():
            fig = existing.get(i)
            if fig is None and d.get("need") is True and len(existing) < budget:
                fig = set_figure(board, d.get("figure"), point=i, why=str(d.get("why") or ""))
                if fig is not None:
                    existing[i] = fig
            out.append({"point": d["i"], "complexity": d.get("complexity"), "need": fig is not None,
                        "why": str(d.get("why") or "")[:60],
                        "kind": ("plot" if fig and fig.plot else "illustration" if fig else None)})
        return out

    def intro_lines(self, outline: Outline) -> list[LessonLine]:
        board = Board(key=f"{outline.board_key}:outline", title=outline.title, items=[s["title"] for s in outline.sections])
        return [LessonLine(x, board, None) for x in outline.intro] or \
            [LessonLine(f"今天我们来学{outline.title}。"[: self.chars], board, None)]


def rewrite_keeps(original: list[LessonLine], new: list[LessonLine], mistakes: list[str] | None = None) -> str:
    """Why a rewritten section must NOT replace the original ("" when it may): it lost the planned exercise, or it
    lost the opening correction of the student's last mistake (its concept named in the first point's lines)."""
    had_ex = any(ln.exercise is not None for ln in original)
    if had_ex and not any(ln.exercise is not None for ln in new):
        return "the rewrite lost the planned exercise"
    if mistakes:
        term = mistakes[-1].split("（")[0].strip()

        def first_point_mentions(lines):
            first = [ln.text for ln in lines if ln.item == 0]
            return bool(term) and any(term in t for t in first)

        if first_point_mentions(original) and not first_point_mentions(new):
            return f"the rewrite no longer corrects「{term}」in its first point"
    return ""


__all__ = ["Board", "LessonLine", "LessonPlanner", "Outline", "render_item", "rewrite_keeps", "spoken"]
