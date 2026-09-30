# Codex review round `craft1`: teaching-craft knowledge base and the enriched lesson workflow

You are GPT-6 Sol reviewing a change to `live_agent/` (a real-time AI teacher persona that teaches one Chinese K-12
student at a time by live generated video with a text board rendered beside it). Reply in English. Rank findings by
severity (blocking / high / medium / low), each with file:line or symbol, the failure scenario, and the smallest fix.
Say explicitly which claims in the decision-log entry you could verify from the inlined material and which you could not.

## What changed (owner request: "enrich the teaching for the agent, including workflow, knowledge base, skill:
1. search for the textbooks teaching teachers how to teach; 2. search for outstanding teachers in top schools or
teaching-competition winners in each grade and analyse their teaching skills")

1. **Knowledge base** `configs/curriculum/teaching_craft.json` (inlined in full): 7 lesson stages with rules, 55 teacher
   moves (stage, grade range, subjects, rank, example line), 5 grade bands (plan / delivery notes), 34 master teachers
   with verified honours and imitable moves, 13 board rules, an 18-item lesson-quality checklist with rubric weights,
   116 sources. Built from five research notes (not inlined; ~430 KB; the synthesis report's structure is described
   in the decision-log entry). Every entry cites sources; unverified items are excluded and listed in `notes`.
2. **Rendering** (`live_agent/curriculum.py`, inlined): `plan_craft` (outline prompt), `section_craft` (section
   prompt), `practice_craft` (exercise prompt), `checklist` (self-check), `masters` / `moves` filtered by stage, grade
   and subject, `subject_of`. Source tags "（cN）" are stripped by `clean()`.
3. **Workflow** (`live_agent/lesson.py`, inlined): the outline returns subject, objectives, key point, difficulty and a
   hook type; the intro is a hook + objectives + parts; the section prompt gets the craft block, a focus line
   (objectives / 重点 / 难点), requires one guided question per section (ask, then answer on the next line) and a
   closing on the last section; `check_section` judges a section against the checklist (scores 0-2, problems, fix,
   pass); `section(..., feedback=...)` rewrites with the judge's problems.
4. **Orchestrator** (diff inlined): `lesson_self_check` = off / log (background, logged) / revise (sections after the
   first are judged before they play and rewritten once on a fail; lookahead doubled in that mode); server flag
   `--lesson-self-check`; requested exercises get the practice rules.
5. `tools/check_curriculum.py` validates the craft file; tests in `tests/test_curriculum.py` (inlined).

## Evidence (measured locally, hosted qwen3.8-flash, one run each, 2026-10-01; excerpts inlined)
Sample runs (grade 1 数学 20以内的进位加法, grade 5 语文 说明文的说明方法, grade 8 数学 勾股定理, grade 10 数学 函数的单调性):
outline 10.6-16.5 s, review section 4.5-5.6 s, core/new section 7.5-13.3 s, self-check 4.5-9.6 s per section. Before the
judge was told the section's planned depth and the not-applicable rule, it failed 7 of 8 sections, mostly on items that
a monologue section cannot show (praise after an answer, an exercise on a section not marked for one); those items are
now scoped out or marked not applicable. The runs after that change are inlined as `craft1_runs.txt`.

## Questions to answer
- Correctness of the rendering and filtering (grade bands, subject "*" semantics, rank ordering, `subject_of` fallbacks,
  `clean()` on the new tags, the checklist scope), and of the outline parsing (subject cross-check, objective limits).
- The self-check: is the pass rule sound; can the revise mode stall the lesson (lookahead, the first section, failures);
  does a rewrite ever lose the exercise or the mistakes-first correction; is a judge from the same model family as
  the writer worth anything (say what would make it a measurement rather than a judgement).
- Prompt-injection and data-quality risks from the knowledge base reaching prompts (names, quotes, "（估计）" labels,
  the claim that numbers are estimates), and whether the provenance claims in the decision log are supported.
- Anything in the decision-log entry that overclaims (e.g. that lessons "follow" master teachers, or that the
  self-check improves quality), and what the smallest experiment would be.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

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
DEPTH_NAMES = {"review": "复习（学生已掌握，按计划只讲 1-2 条要点、快速带过、不举新例子，不按重点课的标准要求）",
               "core": "重点（学生薄弱或考试失分，要放慢、每条要点有例子或例题、指出常见错误）",
               "new": "新内容（正常讲解）"}
DEPTHS = {
    "review": ("4-6", "这一节是复习，学生已经掌握：只讲 1-2 条要点，每条一两句，快速带过，不举新例子。"),
    "core": ("14-20", "这一节是重点，学生这里薄弱或考试失分：放慢，每条要点先讲直观理解，再举一个具体的例子或算一道例题，指出常见错误。"),
    "new": ("10-18", "这一节是新内容，正常讲解。"),
}

OUTLINE_PROMPT = """你是{role}「{name}」，要给学生上一节关于「{topic}」的课。人设：{bio}
学生档案（年级、考试成绩、各概念的掌握情况）：
{profile}
{curriculum}{craft}请按这个学生的情况因材施教，设计课程大纲，只输出 JSON：
{{"title": 课程标题（不超过 16 字）, "subject": 学科（语文、数学、英语、物理、化学、生物学、历史、地理、道德与法治、科学、信息科技之一）,
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
板书要求：3-{max_items} 条要点，每条不超过 {item_chars} 个字，简洁像真正的板书；公式用 LaTeX 写在 $...$ 里（如 $x^2+y^2=r^2$）。
对齐要求：每句讲稿都放在它正在讲的那条要点下面；讲完一条再讲下一条；只属于整节的小结放在 summary 里。
讲稿要求：
1. 每条要点讲 2-4 句：先说要点，再解释原因，再举生活中的例子或算一个小例题；重点、难点所在的要点多加一句常见错误或换一个变式。
2. 每句不超过 {chars} 个汉字，口语化；公式和符号全部用中文读出来（如「a 加 b 的和的平方」「x 的平方」），讲稿里不要出现 $、LaTeX、括号、加减乘除号或等号。
3. 直接从这一节的内容讲起，不要打招呼，不要重复开场白或前面讲过的话。
   配图由系统按要点另外判断和绘制；讲图形、图像或结构时可以说「看黑板上的图」，但不要描述图里没有的细节。
4. 每节至少一处启发式提问：先提一个学生能想一想的问题，下一句再给答案（如「你猜猜看，是哪个？」「对，是……」），不要连着问几个问题。
5. summary 写 1-2 句，简短小结这一节{outro}。
6. 讲稿总共 {n_lines} 句。{craft}
因材施教：{adapt}{exercise_req}"""


CHECK_PROMPT = """你是中小学教学竞赛的评委。下面是{role}「{name}」给{grade}学生上「{title}」这节课的第 {i}/{n} 节「{section}」的板书和讲稿（一对一视频课，每句台词很短是系统要求，不算问题）。
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
    subject: str = ""  # the school subject (from the model, checked against the curriculum's subject names)
    objectives: list[str] = field(default_factory=list)  # what the student can do afterwards ("能…")
    key_point: str = ""  # 重点
    difficulty: str = ""  # 难点
    hook_type: str = ""  # how the intro opens (情境 / 问题 / 复习 / 故事 / 实验 / 直接)

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


def render_item(text: str) -> str:
    """Board text -> safe HTML: plain text escaped, **bold**, $...$ LaTeX as MathML (text fallback)."""
    text = repair_latex(text)
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

    async def outline(self, topic: str, context: str = "", profile=None) -> Outline:
        """``profile``: a student.StudentProfile (None: no saved profile, an average student of ``default_grade``)."""
        curriculum = await self._curriculum_block(topic, profile)
        self.last_curriculum = curriculum  # for the log
        g = self._grade(profile)
        subject = self.curriculum.subject_of(topic, g) if self.curriculum else ""
        craft = self._craft("plan", g, subject)
        raw = await self.llm.chat([{"role": "user", "content": OUTLINE_PROMPT.format(
            name=self.name, topic=topic, bio=self.bio, chars=self.chars, context=context or "无", role=self._role(profile),
            profile=profile.summary() if profile is not None else "无（新学生，没有档案）",
            curriculum=curriculum, craft=(craft + "\n") if craft else "",
            default_grade=(profile.grade if profile is not None and profile.grade else "初中"))}],
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
        intro = [p for x in d.get("intro") or [] for p in spoken(str(x), self.chars)][:6]
        # the model's subject only when the curriculum knows it (else the curriculum's own placement, or none)
        said = str(d.get("subject") or "").strip()
        known = self.curriculum.subject_names() if self.curriculum else []
        subject = said if said in known else next((k for k in known if said and (said in k or k in said)), subject)
        objectives = [str(x).strip()[:24] for x in (d.get("objectives") or []) if str(x).strip()][:3]
        return Outline(title=str(d.get("title") or topic)[:24], sections=sections, intro=intro,
                       note=str(d.get("plan_note") or "")[:120], subject=subject, objectives=objectives,
                       key_point=str(d.get("key_point") or "").strip()[:24],
                       difficulty=str(d.get("difficulty") or "").strip()[:24],
                       hook_type=str(d.get("hook_type") or "").strip()[:6])

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
            focus=outline.focus(), max_items=MAX_ITEMS, item_chars=ITEM_CHARS, chars=self.chars,
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
        scores = d.get("scores") if isinstance(d.get("scores"), dict) else {}
        scores = {str(k): v for k, v in scores.items() if isinstance(v, (int, float)) and 0 <= v <= 2}
        problems = [str(x).strip()[:80] for x in (d.get("problems") or []) if str(x).strip()][:3]
        ok = d.get("pass")
        if not isinstance(ok, bool):  # derive it from the scores when the judge did not say
            ok = bool(scores) and not any(v == 0 for v in scores.values()) and sum(v == 1 for v in scores.values()) <= 3
        return {"pass": ok, "scores": scores, "problems": problems, "fix": str(d.get("fix") or "").strip()[:120],
                "items": len(items)}

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

===== FILE: live_agent/curriculum.py =====
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
    to say."""
    return _CITE.sub("", str(text)).strip()


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
        """The subject the curriculum files place ``topic`` in (the lexical match, else a cached locator pick),
        "" when unknown. No model call: ``locate`` must have run first for chapter-named topics."""
        topic = clean_topic(topic)
        ms = self.lookup(topic, grade, limit=1)
        if ms:
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
    CRAFT_HEADER = "教学法参考（从教学法教材、教学竞赛评价标准和名师课例整理的做法建议，编辑意译，不是原文；数字为估计）："

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
            lines.append(f"借鉴{clean(m.get('name'))}老师（{clean(m.get('method') or '')}）的做法：{mv}")
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


def test_stage_grade_forms_and_english_whole_words(tmp_path):
    assert [parse_grade(x) for x in ["初中二年级", "高中一年级", "九年级", "十年级", "二年级下", "幼儿园"]] == [8, 10, 9, 10, 2, None]
    eng = {"subject": "英语", "grades": [9, 12], "sources": [], "stages": [],
           "grade_topics": {"9": {"topics": ["Smart Learning"], "basis": "textbook"}, "12": {"topics": ["Art"], "basis": "textbook"}}}
    (tmp_path / "english.json").write_text(json.dumps(eng, ensure_ascii=False), encoding="utf-8")
    c = Curriculum.load(tmp_path)
    assert [(m.topic, m.grade) for m in c.lookup("art", grade=9)] == [("Art", 12)]


def test_no_grade_warning_for_a_concept_taught_in_several_grades_or_within_senior_high(tmp_path):
    d = dict(MATH, grade_topics={**MATH["grade_topics"], "4": {"topics": ["三角形"], "basis": "textbook"},
                                  "8": {"topics": ["三角形", "勾股定理"], "basis": "textbook"},
                                  "11": {"topics": ["圆锥曲线的方程"], "basis": "textbook"}})
    (tmp_path / "math.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c = Curriculum.load(tmp_path)
    assert "注意" not in c.topic_context("三角形", 7)  # taught in grades 4 and 8
    assert "注意" not in c.topic_context("圆锥曲线的方程", 10)  # senior high: order varies by school
    ctx = c.topic_context("圆锥曲线的方程", 8)
    assert "一般在高中学" in ctx and "年级为估计" in ctx


def test_requirements_need_the_asked_skill_and_locator_picks_stay_candidates(tmp_path):
    d = dict(MATH, stages=MATH["stages"] + [{"name": "第二学段", "grades": [3, 4], "domains": [
        {"name": "图形与几何", "requirements": ["认识三角形，了解三角形的分类"], "source": "s1"}]}],
        grade_topics={**MATH["grade_topics"], "4": {"topics": ["三角形（特性、分类、内角和）"], "basis": "textbook"}})
    (tmp_path / "math.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c = Curriculum.load(tmp_path)
    assert all(not m.requirements for m in c.lookup("三角形面积", 4))  # area is not "types of triangles"
    replies = iter([json.dumps({"matches": [{"subject": "数学", "grade": 8, "topic": "勾股定理"}]}, ensure_ascii=False),
                    json.dumps(["not", "an", "object"])])
    llm = ScriptedLLM(lambda m: next(replies))
    ctx = asyncio.run(c.topic_context_async(llm, "根号的化简", 5))
    assert "候选章节" in ctx and "注意" not in ctx  # a real but unverified chapter: no grade warning from it
    assert asyncio.run(c.locate(llm, "别的话题", 5)) == []  # a JSON list instead of an object is handled


def test_the_spoken_line_limit_overrides_the_profile_sentence_length(tmp_path):
    c = kb(tmp_path)
    t = c.teaching_context(8, chars=22)
    assert "每句不超过22个字" in t and "估计" in t
    assert "教法" not in c.teaching_context(8, chars=22, brief=True)


CRAFT = {
    "sources": [{"id": "c1", "title": "教学法教材", "url": "https://example.org/c1", "kind": "textbook", "accessed": "2026-09-30"}],
    "lesson_model": {"stages": [
        {"id": "hook", "name": "导入", "rules": ["2-5 分钟，联系旧知或生活情境（c1）"], "sources": ["c1"]},
        {"id": "explain", "name": "新授", "rules": ["小步子，一次一个要点", "先具体后抽象"], "sources": ["c1"]},
        {"id": "check", "name": "检查理解", "rules": ["多提问，问后等一等"], "sources": ["c1"]},
        {"id": "practice", "name": "练习", "rules": ["变式练习，成功率高"], "sources": ["c1"]},
        {"id": "feedback", "name": "反馈", "rules": ["先肯定再指出错误类型"], "sources": ["c1"]},
        {"id": "close", "name": "结课", "rules": ["回到目标，学生复述"], "sources": ["c1"]}]},
    "bands": [
        {"id": "p_low", "name": "小学低年级", "grades": [1, 2], "plan": ["一课一得"], "section": ["儿歌口诀"],
         "stage_notes": {"hook": "用游戏或儿歌导入"}, "sources": ["c1"]},
        {"id": "p_mid", "name": "小学中高年级", "grades": [3, 6], "plan": ["大问题引领"], "sources": ["c1"]},
        {"id": "junior", "name": "初中", "grades": [7, 9], "plan": ["结构化板书"], "section": ["错误资源化"], "sources": ["c1"]},
        {"id": "senior", "name": "高中", "grades": [10, 12], "plan": ["一题多解"], "sources": ["c1"]}],
    "moves": [
        {"id": "wait", "name": "候答等待", "stages": ["check"], "what": "提问后停三秒再叫答", "example": "想一想再说。",
         "rank": 1, "sources": ["c1"]},
        {"id": "variation", "name": "变式", "stages": ["practice", "explain"], "what": "换非本质特征再练一遍",
         "grades": [3, 12], "subjects": ["数学", "物理"], "sources": ["c1"]},
        {"id": "song", "name": "儿歌", "stages": ["hook", "explain"], "what": "把规则编成口诀", "grades": [1, 3],
         "sources": ["c1"]}],
    "masters": [
        {"id": "hua", "name": "华应龙", "subjects": ["数学"], "grades": [1, 6], "school": "北京第二实验小学",
         "honours": ["特级教师"], "method": "化错教学", "moves": ["把错误当资源", "让学生先试", "追问为什么"], "sources": ["c1"]},
        {"id": "sun", "name": "孙维刚", "subjects": ["数学"], "grades": [7, 12], "honours": ["特级教师"], "method": "结构教学",
         "moves": ["一题多解", "知识结构图"], "sources": ["c1"]},
        {"id": "yu", "name": "于漪", "subjects": ["语文"], "grades": [7, 12], "honours": ["人民教育家"], "method": "情感教学",
         "moves": ["朗读体味"], "sources": ["c1"]}],
    "board": {"rules": ["提纲式，关键词不写整句", "主板书留在黑板上不擦"], "sources": ["c1"]},
    "checklist": [{"id": "goal", "item": "目标明确，讲解围绕目标", "sources": ["c1"]},
                  {"id": "kid", "item": "低年级有游戏或儿歌", "grades": [1, 2], "sources": ["c1"]},
                  {"id": "praise", "item": "表扬具体", "scope": "feedback", "sources": ["c1"]}]}


def kb_craft(tmp_path):
    (tmp_path / "teaching_craft.json").write_text(json.dumps(CRAFT, ensure_ascii=False), encoding="utf-8")
    return kb(tmp_path)


def test_craft_moves_and_masters_follow_stage_grade_and_subject(tmp_path):
    c = kb_craft(tmp_path)
    assert [m["id"] for m in c.moves("check", 8)] == ["wait"]
    assert [m["id"] for m in c.moves("practice", 8, "数学")] == ["variation"]
    assert c.moves("practice", 2, "数学") == [] and c.moves("explain", 8, "语文") == []  # grade / subject filters
    assert [m["id"] for m in c.moves("explain", 2)] == ["song"]  # no subject: only cross-subject moves
    assert [m["name"] for m in c.masters("数学", 5)] == ["华应龙"] and [m["name"] for m in c.masters("数学", 11)] == ["孙维刚"]
    assert c.masters("", 11) == [] and c.band(4)["id"] == "p_mid" and c.band(None) == {}
    assert c.checklist(8) == ["目标明确，讲解围绕目标"] and len(c.checklist(1)) == 2  # feedback items are not section items
    assert c.checklist(8, scope="feedback") == ["表扬具体"]
    assert c.subject_of("勾股定理", 8) == "数学" and c.subject_of("量子力学") == ""


def test_craft_blocks_render_for_the_outline_the_section_and_the_exercise(tmp_path):
    c = kb_craft(tmp_path)
    plan = c.plan_craft(2, "数学")
    assert plan.startswith("教学法参考") and "编辑意译" in plan and "一节课的环节：导入（2-5 分钟" in plan
    assert "(c1)" not in plan and "（c1）" not in plan  # source tags are for audit, not the teacher
    assert "小学低年级的课：一课一得" in plan and "儿歌：把规则编成口诀" in plan and "借鉴华应龙老师（化错教学）" in plan
    sec = c.section_craft(1, "数学")
    assert "提问与检查理解：多提问，问后等一等；用游戏或儿歌导入" not in sec  # a band note applies to its own stage only
    assert "候答等待：提问后停三秒再叫答（如「想一想再说。」）" in sec and "板书：提纲式" in sec
    assert "小学低年级：儿歌口诀" in sec and "结课" not in sec and "结课：回到目标" in c.section_craft(1, "数学", last=True)
    assert "换非本质特征" in c.section_craft(8, "物理") and "换非本质特征" not in c.section_craft(8, "语文")
    assert "练习：变式练习，成功率高" in c.practice_craft(8, "数学") and c.practice_craft(8, "语文").endswith("成功率高")
    assert Curriculum([], {}, {}).plan_craft(8) == "" and Curriculum([], {}, {}).section_craft(8) == ""


def test_the_planner_carries_objectives_focus_and_the_craft_into_every_prompt(tmp_path):
    c = kb_craft(tmp_path)
    out = {"title": "勾股定理", "subject": "数学", "objectives": ["能说出勾股定理", "能求斜边"], "key_point": "a²+b²=c²",
           "difficulty": "分清直角边和斜边", "hook_type": "情境",
           "sections": [{"title": "定理", "role": "main", "depth": "new"}, {"title": "应用", "role": "main", "exercise": True}],
           "intro": ["工人量墙角用的什么办法？", "学完你能自己求斜边。", "分两部分讲。"]}
    sec = {"board": {"title": "定理"}, "points": [{"text": "$a^2+b^2=c^2$", "lines": ["你猜猜看，哪条边最长？", "对，是斜边。"]}],
           "summary": ["这一节就到这里。"]}
    check = {"scores": {"1": 2, "2": 1}, "problems": ["第一条要点没有例子"], "pass": False, "fix": "加一个例子"}

    def llm(messages):
        t = messages[-1]["content"]
        return json.dumps(out if "课程大纲" in t else check if "评委" in t else sec, ensure_ascii=False)

    p = StudentProfile(student_id="x", grade="初二")
    planner = LessonPlanner(ScriptedLLM(llm), name="林老师", bio="", curriculum=c)
    outline = asyncio.run(planner.outline("勾股定理", profile=p))
    assert (outline.subject, outline.objectives, outline.key_point, outline.hook_type) == \
        ("数学", ["能说出勾股定理", "能求斜边"], "a²+b²=c²", "情境")
    plan_prompt = planner.llm.calls[0][-1]["content"]
    assert "教学法参考" in plan_prompt and "初中的课：结构化板书" in plan_prompt and "借鉴孙维刚老师" in plan_prompt
    assert '"objectives"' in plan_prompt and "hook_type" in plan_prompt
    lines = asyncio.run(planner.section(outline, 1, ["定理"], profile=p))
    sec_prompt = planner.llm.calls[1][-1]["content"]
    assert "本课目标：能说出勾股定理；能求斜边；重点：a²+b²=c²；难点：分清直角边和斜边。" in sec_prompt
    assert "结课：回到目标" in sec_prompt and "借鉴孙维刚老师（结构教学）的做法：一题多解；知识结构图" in sec_prompt
    assert "启发式提问" in sec_prompt and "回到本课目标和重点" in sec_prompt  # the last section closes the lesson
    v = asyncio.run(planner.check_section(outline, 1, lines, profile=p))
    assert v == {"pass": False, "scores": {"1": 2, "2": 1}, "problems": ["第一条要点没有例子"], "fix": "加一个例子", "items": 1}
    check_prompt = planner.llm.calls[2][-1]["content"]
    assert "1. 目标明确，讲解围绕目标" in check_prompt and "[要点1] 你猜猜看，哪条边最长？" in check_prompt
    lines2 = asyncio.run(planner.section(outline, 1, ["定理"], profile=p, feedback="第一条要点没有例子"))
    assert "上一版讲稿的评审问题：第一条要点没有例子" in planner.llm.calls[3][-1]["content"] and len(lines2) == len(lines)
    assert asyncio.run(LessonPlanner(ScriptedLLM(llm), name="林老师", bio="").check_section(outline, 1, lines)) == {}


def test_a_subject_the_curriculum_does_not_know_falls_back_to_its_own_placement(tmp_path):
    c = kb_craft(tmp_path)
    out = {"title": "勾股定理", "subject": "算术", "sections": [{"title": "定理"}], "intro": ["开始。"]}
    planner = LessonPlanner(ScriptedLLM(lambda m: json.dumps(out, ensure_ascii=False)), name="林老师", bio="", curriculum=c)
    assert asyncio.run(planner.outline("勾股定理")).subject == "数学"  # the lexical match, not the model's word
    out["subject"] = "生物"
    assert asyncio.run(planner.outline("量子力学")).subject == ""  # unknown to the curriculum: no master hints

===== FILE: docs/reviews/craft1_diff.patch =====
diff --git a/docs/implementation.md b/docs/implementation.md
index 381341e..ba111b8 100644
--- a/docs/implementation.md
+++ b/docs/implementation.md
@@ -24,6 +24,10 @@ verified. Every number is labelled *measured locally*, *cited*, *estimate* or *t
 | `live_agent/asr.py` | — | Qwen3-ASR client (vLLM transcription API) and audio decoding |
 | `live_agent/eval/` | §7, §14, §15 | Evaluation: SCHEMA.md log format, scoring (intent chains, D table, outcome rules), stats (Wilson, Clopper–Pearson, KM, clustered bootstrap, Holm, κ, power), 30-task suite, simulated user, runner, report |
 | `configs/persona_hanfu/` | §3 | Persona canon and capability manifest (24 actions covering the E2 suite; `documented` until E1 executes them) |
+| `configs/persona_teacher/` | demo | Teacher persona (林老师): canon, responder rules for answers with a board, lessons, exercises and profile updates |
+| `live_agent/lesson.py` | D-038, D-043 | Lesson planner: outline (subject, objectives, key point, difficulty, hook type, sections with depth and exercises), one section at a time (board points with the spoken lines under each, a guided question per section, a closing that returns to the objectives), figure judgement, and the rubric self-check of a section (`check_section`, rewrite with `feedback`) |
+| `live_agent/exercise.py`, `live_agent/student.py` | D-038, D-039 | Exercises (choice / short answer, rule or LLM grading, practice-design rules from the craft data) and the student profile store |
+| `live_agent/curriculum.py`, `configs/curriculum/` | D-040, D-043 | Course knowledge base: the national curriculum per subject and grade, the per-grade teaching profile (`pedagogy.json`) and the teaching craft (`teaching_craft.json`: lesson stages, teacher moves, grade bands, master teachers, board rules, quality checklist), rendered into the planner, section, exercise and self-check prompts by grade and subject; `tools/check_curriculum.py` validates the files |
 | `live_agent/generator/base.py` `SessionView` | — | One live session on a long-lived shared generator: reset per session, local request numbering, stale chunks dropped (D-022) |
 | `live_agent/sim.py` `Recorder` | — | MP4 of the *presented* stream (background-thread encoding), used for adjudication and E1 clips |
 | `live_agent/eval/adjudicate.py` | §14, D-014 | Blinded human adjudication: shuffled items, random ids and media names, key kept apart; labels merged back as `source: adjudicated` verdicts with video→session time mapping (D-024) |
diff --git a/live_agent/exercise.py b/live_agent/exercise.py
index 4d3ca86..439ef1d 100644
--- a/live_agent/exercise.py
+++ b/live_agent/exercise.py
@@ -23,7 +23,7 @@ EXERCISE_PROMPT = """你是中学老师「{name}」。请给学生出一道关
 学生档案：
 {profile}
 难度按学生情况定：这个知识点薄弱就出基础题（直接用定义或公式一步能做），基本理解出中等题，已掌握出稍有变化的题；按学生年级出题。
-{exercise_spec}"""
+{craft}{exercise_spec}"""
 
 EXERCISE_SPEC = """练习题格式（只输出 JSON）：
 {{"exercise": {{"concept": 考查的概念（用档案里已有的概念名，没有就写一个不超过 8 字的名称）, "subject": 学科,
@@ -176,9 +176,11 @@ def feedback_lines(ex: Exercise, r: dict, chars: int, llm_lines: list[str] | Non
 
 
 async def make_exercise(llm: ChatLLM, *, name: str, topic: str, profile: str, key: str, chars: int = 22,
-                        source: str = "asked") -> Exercise:
+                        source: str = "asked", craft: str = "") -> Exercise:
+    """``craft``: the curriculum's practice-design rules for the student's grade ("" without craft data)."""
     raw = await llm.chat([{"role": "user", "content": EXERCISE_PROMPT.format(
-        name=name, topic=topic, profile=profile, exercise_spec=EXERCISE_SPEC.format(chars=chars, q_chars=60))}],
+        name=name, topic=topic, profile=profile, craft=(craft + "\n") if craft else "",
+        exercise_spec=EXERCISE_SPEC.format(chars=chars, q_chars=60))}],
         max_tokens=600, temperature=0.5, json_mode=True)
     d = parse_json(raw)
     ex = Exercise.from_dict(d.get("exercise", d), key=key, source=source)
diff --git a/live_agent/orchestrator.py b/live_agent/orchestrator.py
index a957579..4aacfd0 100644
--- a/live_agent/orchestrator.py
+++ b/live_agent/orchestrator.py
@@ -93,6 +93,11 @@ class OrchestratorConfig:
     # player switches to the reply at the moment the reply's first chunk is ready (erasure still cuts at once)
     soft_switch: bool = True
     lesson_lookahead: int = 6  # generate the next lesson section once fewer lines than this are waiting (~30 s)
+    # self-check of every generated section against the lesson-quality checklist (configs/curriculum/teaching_craft
+    # .json): "off"; "log" (judged in the background, logged only); "revise" (sections after the first are judged
+    # before they play and rewritten once with the judge's problems when they fail; the first section is logged
+    # only, so the lesson still starts as soon as its outline is ready)
+    lesson_self_check: str = "log"
     # student attention (opt-in camera): nudge during a lesson after this many consecutive distracted/absent checks
     attention_nudge_after: int = 2
     attention_cooldown_s: float = 45.0
@@ -1090,8 +1095,10 @@ class Orchestrator:
             if self.curriculum.exercise_style(g):
                 profile += f"\n这个年级的练习形式：{self.curriculum.exercise_style(g)}"
         try:
+            craft = self.curriculum.practice_craft(g, self.curriculum.subject_of(topic, g)) \
+                if self.curriculum and self.student is not None else ""
             ex = await make_exercise(d.llm, name=d.persona_name, topic=topic, profile=profile,
-                                     key=f"q{self._exercises}")
+                                     key=f"q{self._exercises}", craft=craft)
         except Exception as e:  # noqa: BLE001
             self.log.emit(EventType.LESSON, now(), stage="exercise_failed", topic=topic, error=str(e)[:160])
             d.say_verified("抱歉，这道题我没出好，你可以换个问法。")
@@ -1229,8 +1236,10 @@ class Orchestrator:
         covered: list[str] = []
         waiting_for = None  # the previous section's exercise: its result shapes the next section
         for i in range(len(outline.sections)):
+            # a judged-and-rewritten section takes about twice as long to produce: start it earlier
+            lookahead = self.cfg.lesson_lookahead * (2 if self.cfg.lesson_self_check == "revise" and i > 0 else 1)
             while not self._stop.is_set() and (
-                    len(d.lesson_backlog) >= self.cfg.lesson_lookahead
+                    len(d.lesson_backlog) >= lookahead
                     or (waiting_for is not None and (d.exercise is waiting_for
                                                      or any(x.exercise is waiting_for for x in d.lesson_backlog)))
                     or (self.student is not None and d.exercise is not None)):
@@ -1245,7 +1254,11 @@ class Orchestrator:
                 except Exception as e:  # noqa: BLE001 - retry once, then skip the section
                     self.log.emit(EventType.LESSON, now(), stage="section_failed", section=i, attempt=attempt,
                                   error=str(e)[:160])
+            if lines and self.cfg.lesson_self_check == "revise" and i > 0:
+                lines = await self._revise_section(planner, outline, i, covered, lines)
             if lines:
+                if self.cfg.lesson_self_check == "log" or (self.cfg.lesson_self_check == "revise" and i == 0):
+                    self._spawn(self._check_section(planner, outline, i, lines), "lesson_check")
                 self._lesson_mistakes.clear()  # addressed by this section
                 d.add_lesson_lines(lines)
                 if self.student is not None and outline.sections[i].get("concepts"):
@@ -1262,6 +1275,35 @@ class Orchestrator:
             covered.append(outline.sections[i]["title"])
         self.log.emit(EventType.LESSON, now(), stage="planned", title=outline.title)
 
+    async def _check_section(self, planner, outline, i: int, lines, *, revised: bool = False) -> dict:
+        """Judge a section against the lesson-quality checklist and log the verdict (never raises)."""
+        try:
+            v = await planner.check_section(outline, i, lines, profile=self.student)
+        except Exception as e:  # noqa: BLE001 - the check is advisory
+            self.log.emit(EventType.LESSON, now(), stage="check_failed", section=i, error=str(e)[:160])
+            return {}
+        if v:
+            self.log.emit(EventType.LESSON, now(), stage="check", section=i, title=outline.sections[i]["title"],
+                          passed=v["pass"], scores=v["scores"], problems=v["problems"], fix=v["fix"], revised=revised)
+        return v
+
+    async def _revise_section(self, planner, outline, i: int, covered: list[str], lines):
+        """Self-check before the section plays; on a fail, one rewrite with the judge's problems (kept even if the
+        judge would still object: a second opinion is logged, not enforced)."""
+        v = await self._check_section(planner, outline, i, lines)
+        if not v or v["pass"]:
+            return lines
+        feedback = "；".join(v["problems"]) + (f"；改法：{v['fix']}" if v["fix"] else "")
+        try:
+            new = await planner.section(outline, i, covered, profile=self.student,
+                                        mistakes=list(self._lesson_mistakes), feedback=feedback)
+        except Exception as e:  # noqa: BLE001 - keep the first version
+            self.log.emit(EventType.LESSON, now(), stage="revise_failed", section=i, error=str(e)[:160])
+            return lines
+        self.log.emit(EventType.LESSON, now(), stage="revised", section=i, feedback=feedback[:200], lines=len(new))
+        self._spawn(self._check_section(planner, outline, i, new, revised=True), "lesson_check")
+        return new
+
     async def _switch_to(self, target: int) -> None:
         """The reply's first chunk is ready: drop what was generated before it and not yet fully shown, stop
         the player (it cuts at the current frame) and let the reply play next."""
diff --git a/live_agent/server/app.py b/live_agent/server/app.py
index 9b57149..642acd7 100644
--- a/live_agent/server/app.py
+++ b/live_agent/server/app.py
@@ -493,7 +493,8 @@ def build_app(args: argparse.Namespace) -> FastAPI:
                                 cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                        correction_mode=CorrectionMode(args.correction_mode),
                                                        # the demo's vLLM-Omni configs hold for every prompt
-                                                       generator_holds=args.generator == "vllm_omni_h3"))
+                                                       generator_holds=args.generator == "vllm_omni_h3",
+                                                       lesson_self_check=args.lesson_self_check))
             transport.orchestrator = orch
             if args.image_url:
                 from live_agent.board_images import ImageMaker
@@ -720,6 +721,9 @@ def main() -> None:
     p.add_argument("--student", default="demo", help="student profile id for private sessions (the page may pick one)")
     p.add_argument("--students", default="", help="comma-separated profile ids the page may pick (default: only --student)")
     p.add_argument("--student-store", default=str(BOARD_IMAGES.parent / "students"), help="saved student profiles (personal data)")
+    p.add_argument("--lesson-self-check", default="log", choices=["off", "log", "revise"],
+                   help="judge every lesson section against the lesson-quality checklist: log only, or rewrite "
+                        "a failing section once before it plays (sections after the first)")
     p.add_argument("--host", default="127.0.0.1")
     p.add_argument("--port", type=int, default=8200)
     # Generator options (--taomate-*, --omni-*) are parsed by the adapters (taomate_h3.py, vllm_omni_h3.py).
diff --git a/tools/check_curriculum.py b/tools/check_curriculum.py
index 6a40275..5c4baa0 100644
--- a/tools/check_curriculum.py
+++ b/tools/check_curriculum.py
@@ -57,6 +57,79 @@ def check_subject(d: dict, name: str) -> tuple[list[str], list[str]]:
     return errors, warnings
 
 
+def check_craft(d: dict) -> tuple[list[str], list[str]]:
+    """teaching_craft.json: sources with URLs; every citation resolves; bands cover grades 1-12 without overlap;
+    moves name known stages; masters and moves have grades within 1-12 and at least one source."""
+    errors, warnings = [], []
+    ids = {s.get("id") for s in d.get("sources") or []}
+    for s in d.get("sources") or []:
+        if not str(s.get("url") or "").startswith("http"):
+            errors.append(f"teaching_craft: source {s.get('id')} has no URL")
+        if not s.get("accessed"):
+            warnings.append(f"teaching_craft: source {s.get('id')} has no access date")
+
+    def cites(item: dict, what: str, required: bool = True) -> None:
+        srcs = item.get("sources") or []
+        if required and not srcs:
+            errors.append(f"teaching_craft: {what} has no sources")
+        for x in srcs:
+            if x not in ids:
+                errors.append(f"teaching_craft: {what} cites unknown source {x}")
+
+    def grades_ok(item: dict, what: str) -> None:
+        gs = item.get("grades")
+        if gs is not None and (len(gs) != 2 or not all(isinstance(g, int) and 1 <= g <= 12 for g in gs) or gs[0] > gs[1]):
+            errors.append(f"teaching_craft: {what} has grades {gs}")
+
+    stages = [st.get("id") for st in (d.get("lesson_model") or {}).get("stages") or []]
+    if not stages:
+        errors.append("teaching_craft: lesson_model has no stages")
+    for st in (d.get("lesson_model") or {}).get("stages") or []:
+        if not st.get("rules"):
+            errors.append(f"teaching_craft: stage {st.get('id')} has no rules")
+        cites(st, f"stage {st.get('id')}")
+    covered = Counter()
+    for b in d.get("bands") or []:
+        grades_ok(b, f"band {b.get('id')}")
+        cites(b, f"band {b.get('id')}")
+        lo, hi = (b.get("grades") or [0, -1])[:2]
+        for g in range(lo, hi + 1) if isinstance(lo, int) and isinstance(hi, int) else []:
+            covered[g] += 1
+        for sid in (b.get("stage_notes") or {}):
+            if sid not in stages:
+                errors.append(f"teaching_craft: band {b.get('id')} notes unknown stage {sid}")
+    for g in range(1, 13):
+        if covered[g] != 1:
+            errors.append(f"teaching_craft: grade {g} is in {covered[g]} bands (must be exactly one)")
+    for m in d.get("moves") or []:
+        for sid in m.get("stages") or []:
+            if sid not in stages:
+                errors.append(f"teaching_craft: move {m.get('id')} names unknown stage {sid}")
+        if not m.get("stages"):
+            errors.append(f"teaching_craft: move {m.get('id')} has no stages")
+        if not m.get("what"):
+            errors.append(f"teaching_craft: move {m.get('id')} has no 'what'")
+        grades_ok(m, f"move {m.get('id')}")
+        cites(m, f"move {m.get('id')}")
+    for m in d.get("masters") or []:
+        for key in ("name", "subjects", "method", "moves"):
+            if not m.get(key):
+                errors.append(f"teaching_craft: master {m.get('id')} has no '{key}'")
+        grades_ok(m, f"master {m.get('id')}")
+        cites(m, f"master {m.get('id')}")
+        if not m.get("honours"):
+            warnings.append(f"teaching_craft: master {m.get('id')} lists no honours (why outstanding?)")
+    cites(d.get("board") or {}, "board", required=bool((d.get("board") or {}).get("rules")))
+    for c in d.get("checklist") or []:
+        if not c.get("item"):
+            errors.append(f"teaching_craft: checklist entry {c.get('id')} has no item")
+        if c.get("scope") not in (None, "section", "feedback"):
+            errors.append(f"teaching_craft: checklist entry {c.get('id')} has scope {c.get('scope')!r}")
+        grades_ok(c, f"checklist {c.get('id')}")
+        cites(c, f"checklist {c.get('id')}")
+    return errors, warnings
+
+
 def main(directory: str = "configs/curriculum") -> int:
     d = Path(directory)
     errors, warnings = [], []
@@ -66,6 +139,15 @@ def main(directory: str = "configs/curriculum") -> int:
         except ValueError as e:
             errors.append(f"{f.name}: invalid JSON ({e})")
             continue
+        if f.stem == "teaching_craft":
+            e, w = check_craft(data)
+            errors += e
+            warnings += w
+            print(f"teaching_craft: stages {len((data.get('lesson_model') or {}).get('stages') or [])}, "
+                  f"moves {len(data.get('moves') or [])}, masters {len(data.get('masters') or [])}, "
+                  f"bands {len(data.get('bands') or [])}, board rules {len((data.get('board') or {}).get('rules') or [])}, "
+                  f"checklist {len(data.get('checklist') or [])}, sources {len(data.get('sources') or [])}")
+            continue
         if f.stem == "pedagogy":
             ids = {s.get("id") for s in data.get("sources") or []}
             grades = data.get("grades") or {}

===== FILE: docs/reviews/craft1_decision.md =====
Decision-log entry D-043 (docs/decision_log.md):

| D-043 | 2026-10-01 | **Teaching-craft knowledge base and an enriched lesson workflow (owner: "enrich the teaching for the agent, including workflow, knowledge base, skill: 1. search for the textbooks teaching teachers how to teach; 2. search for outstanding teachers in top schools or teaching-competition winners in each grade and analyse their teaching skills").** Research: five parallel web-research agents wrote `docs/notes/research_notes/Teaching craft for the teacher agent/` (zh_textbooks: 王道俊/郭文安《教育学》, 陈琦/刘儒德《教育心理学》, 崔允漷《有效教学》, 微格教学技能, the 2011 教师资格考试标准, 《学记》, 邱学华/洋思/卢仲衡/顾泠沅/李吉林; intl_textbooks: Rosenshine, Lemov, Hunter, Gagné, UbD, Bloom, Black & Wiliam, Hattie & Timperley, cognitive load, Willingham, Make It Stick, Mayer, Marzano, Sutton Trust, Berliner; zh_master_teachers: 特级教师 / 教书育人楷模 / 教学成果奖 / 青教赛 winners per band and subject, top-school models; intl_master_teachers: Global Teacher Prize, US NTOY, Japanese lesson study and 板書, Shanghai/NCETM mastery, Engelmann DI; zh_rubrics_templates: competition and 优质课 scoring tables with weights, 教案/板书/说课 conventions, NTCE 面试 criteria), every source with URL and access date and every claim labelled cited / secondary / inference / not verified; a report writer synthesised `docs/notes/reports/Teaching craft for the teacher agent.md` (~8,800 words, 206 links). Findings: both traditions prescribe one loop (定向 → 尝试 → 后教 → 检查 → 练习 → 自结); the masters converge on nine moves (conflict-laden 情境导入, pupil-first attempt, one big question per block, 化错, 变式/一题多解, structured board, 朗读/复述, specific praise, in-lesson check); grade band changes tone, pace and abstraction, not the loop; award citations abroad document access rather than mechanics, so the mechanics come from Shanghai, Japan and DI. **Knowledge base** `configs/curriculum/teaching_craft.json` (built by an agent from the notes, validated by `tools/check_curriculum.py`): 7 lesson stages with rules, 55 teacher moves (stage, grade range, subjects, rank, example line), 5 grade bands (design and delivery notes), 34 master teachers with verified honours and 3-5 imitable moves, 13 board rules, an 18-item lesson-quality checklist with rubric weights where a rubric gives one, 116 sources; wording is editorial paraphrase, numbers not cited are marked （估计）, unverified honours and method details are excluded and listed in the file's `notes` (e.g. 王崧舟 六字诀, 吴正宪 八种课型, national 青教赛 weights, NTCE 小学/中学 weights). No master for 化学, 生物学, 地理, 科学, 信息科技, 初中历史, 高中英语/物理: nobody with technique-level documentation plus a verifiable honour in the notes. **Workflow** (`live_agent/curriculum.py`, `lesson.py`, `exercise.py`, `orchestrator.py`): the outline returns the subject (cross-checked against the curriculum), 1-3 objectives, 重点, 难点 and a hook type, and its intro is hook → objectives → parts; every section prompt gets the craft block for the grade and subject (stage rules, ranked moves, band notes, two masters' moves, four board rules; 470-1070 characters), a focus line, one guided question (ask, then answer on the next line) and, on the last section, a closing that returns to the objectives with a 延伸; exercises get the practice rules; a rubric **self-check** (`check_section`: scores 0-2 per item, problems, fix, pass) runs in `log` mode by default, `revise` rewrites a failing section once before it plays (sections after the first; lookahead doubled), `off` disables it (server flag `--lesson-self-check`). The judge is told the section's planned depth (a review section is brief by design) and that inapplicable items score 2. Skill port: the same modules, the data file, `--self-check` on the skill's lesson server and a `craft` lookup command in `/data/zhoutaichang/taomate-live-skill`. **Evidence** (*measured locally*, hosted qwen3.8-flash, one run each, `docs/reviews/craft1_runs.txt`): outline 8.5-16.5 s (24.5 s once), review section 4.0-7.4 s, core/new section 7.5-13.3 s, self-check 3.0-9.6 s. Lessons follow the grade: grade 1 opens with a 猴子分桃 story and 凑十歌, grade 8 with 梯子靠墙, grade 10 with a temperature curve; every section had a guided question and the last a 延伸. Before the judge calibration it failed 7 of 8 sections, mostly on items a monologue section cannot show (praise after an answer, an exercise on a section not marked for one); after it, 4 of 6 passed and the two fails were substantive (说明方法 defined as "说话的技巧"; only the 3-4-5 special case shown). One defect found in the runs and fixed with a test: a closing quote after 。 opened the next spoken line. **Not validated**: whether the enriched lessons teach better (needs a blinded comparison of old vs new prompts with human ratings); the self-check is a judgement by the same model family as the writer, not a measurement (a human-rated sample of its verdicts would calibrate it); `revise` was not run live (latency: check + rewrite ≈ 15-25 s per section); the skill port has CPU tests only. Why: the brief asks for a teacher that teaches like a good teacher; explicit, sourced craft in the prompts is auditable and editable, unlike tuning by example. | accepted, Codex round craft1 pending |

===== FILE: docs/reviews/craft1_runs.txt =====
# Measured runs of the enriched planner (hosted qwen3.8-flash, 2026-10-01, one run each). Script: scratchpad craft_run.py <grade> <topic> check

## After the judge calibration (depth stated, not-applicable rule, praise item scoped to feedback)

### run2_g8
outline 8.5s | subject=数学 hook=情境
  objectives: ['能说出直角三角形三边关系', '能用勾股定理求未知边长', '能解决简单的实际距离问题'] | key: 理解并掌握a²+b²=c² | difficulty: 区分斜边与直角边
  sections: [('回顾前置知识', 'review', False), ('发现数量关系', 'core', True), ('归纳勾股定理', 'new', False), ('应用定理求解', 'core', True)]
  intro: ['同学们好，我是林老师。', '大家见过梯子靠墙吗？', '如果梯子底端滑动，顶端会怎样？', '今天我们要解开这个几何秘密。', '学完后你能算出直角三角形的边长。', '我们将分四步来探索这个定理。']
section 1 4.0s | board: 回顾前置知识 | ['正方形面积 $S=a^2$，边长 $a=\\sqrt{S}$', '直角三角形两直角边为 $a,b$，斜边 $c$']
    [0] 正方形面积是边长的平方。
    [0] 已知面积求边长用开方。
    [0] 比如面积九，边长就是三。
    [1] 直角对着最长边叫斜边。
    [1] 夹直角的两边叫直角边。
    [1] 你猜猜看，哪个最长？
    [1] 对，斜边永远比直角边长。
    [-] 面积和根式是勾股定理的基础。
    [-] 接下来我们探索三边的数量关系。
  check 5.0s | {"pass": true, "scores": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 2, "10": 2, "11": 1, "12": 2, "13": 2, "14": 2, "15": 2, "16": 2}, "problems": ["标准3：要点2（直角三角形边名）缺乏具体例子或小例题，仅靠口头定义和提问，不符合‘每条要点有解释原因和一个例子’的要求。", "标准11：学生在本节参与度低，除了回答一个简单的是非/选择题外，没有复述、试做或书写练习的机会，作为复习课略显单薄。"], "fix": "在讲解直角三角形边名时，增加一个简单的图形标注示例或让学生快速指认图中的斜边与直角边，以增强互动性和实例支撑。", "items": 16}
section 4 10.3s | board: 应用定理求解 | ['步骤一：判断斜边，确定未知量', '步骤二：列式 $a^2+b^2=c^2$ 代入', '步骤三：开方求值，取正数']
    [0] 已知两边求第三边。
    [0] 先找直角和斜边。
    [0] 斜边对着直角。
    [0] 你猜猜看，哪个是斜边？
    [0] 对，是最长的那条。
    [1] 把数字代进公式。
    [1] 注意平方运算顺序。
    [1] 比如三和四求五。
    [1] 九加十六等于二十五。
    [1] 别漏掉平方这一步。
    [2] 算出平方后的结果。
    [2] 最后一步要开方。
    [2] 长度不能是负数。
    [2] 二十五开方是几？
    [2] 对，答案是五。
    [-] 记住先定斜边再计算。
    [-] 下节课我们看实际距离问题。
    [-] 我们来做一道练习。
    [-] 直角三角形两直角边为6和8，斜边长为？
    [-] 选项在黑板上，选好了告诉我。
  check 5.6s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 2, "6": 2, "7": 1, "8": 2, "9": 2, "10": 2, "11": 1, "12": 2, "13": 2, "14": 2, "15": 2, "16": 1}, "problems": ["要点2中仅演示了已知两直角边求斜边的特例（3,4,5），未展示已知斜边和一直角边求另一直角边的逆向运算，导致‘应用定理求解’的覆盖面不全。", "学生互动不足，虽有提问但多为封闭式确认（如‘对，答案是五’），缺乏让学生独立书写解题过程或进行变式试做的环节。", "重点难点处缺少针对‘区分斜边与直角边’的典型错误案例（如误将最长边当直角边代入公式）的深度剖析，仅靠口头提醒力度不够。"], "fix": "补充已知斜边求直角边的例题及常见错误辨析，并增加让学生动手计算不同情境下未知边长的互动环节。", "items": 16}


### run2_g5
outline 24.5s | subject=语文 hook=情境
  objectives: ['能识别常见的说明方法', '能说出说明方法的作用', '能尝试运用一种方法'] | key: 掌握列数字、作比较、打比方的作用 | difficulty: 区分打比方和比喻的异同
  sections: [('认识说明方法', 'new', False), ('数字与比较', 'core', True), ('生动的比喻', 'core', True), ('综合练习', 'review', True)]
  intro: ['同学们，介绍太阳时怎么说才清楚？', '今天我们要学会几种神奇的说明方法。', '学完后你能认出它们，还能试着用一用。', '我们分三步来探索这些方法的奥秘吧。']
section 1 7.4s | board: 认识说明方法 | ['定义：用技巧把事物说清楚', '列数字：用数据让事实更准确', '作比较：拿熟悉事物来对照', '打比方：像比喻但重在说明']
    [0] 同学们，什么是说明方法呢？
    [0] 简单说，就是说话的技巧。
    [0] 目的是让别人听懂你的意思。
    [0] 就像做菜要有菜谱一样。
    [1] 第一种叫列数字。
    [1] 比如这座塔高一百米。
    [1] 数字比形容词更靠谱。
    [1] 你猜猜看，哪个更准？
    [1] 对，是带数字的那个。
    [2] 第二种叫作比较。
    [2] 大象比小狗重得多。
    [2] 用熟悉的帮理解陌生的。
    [2] 注意别把两者搞混了。
    [3] 第三种叫打比方。
    [3] 地球像个大篮球。
    [3] 它和比喻很像对吧？
    [3] 区别在于目的不同。
    [3] 比喻为了生动形象。
    [3] 打比方为了讲清楚。
    [-] 今天我们认识了三种方法。
    [-] 下节课我们深入学作用。
  check 4.1s | {"pass": false, "scores": {"1": 2, "2": 0, "3": 1, "4": 2, "5": 2, "6": 1, "7": 1, "8": 2, "9": 2, "10": 1, "11": 1, "12": 2, "13": 2, "14": 2, "15": 1}, "problems": ["标准2：讲稿中定义说明方法为“说话的技巧”不准确，说明方法是写作手法而非口语技巧。", "标准3：要点2（列数字）和要点3（作比较）缺乏对“作用/原因”的深入解释，仅停留在举例层面。", "标准7：难点处（打比方与比喻的区别）讲解过于简略，未通过具体对比案例或常见错误提醒来强化区分。"], "fix": "修正说明方法的定义表述，补充列数字和作比较的具体作用分析，并增加打比方与比喻的对比辨析案例以突破难点。", "items": 15}
section 4 9.5s | board: 综合练习：火眼金睛辨方法 | ['列数字：准确具体，体现科学性', '作比较：突出特征，强调差异', '打比方：生动形象，化难为易', '难点辨析：比喻修辞与说明方法']
    [0] 看到具体数据，就是列数字。
    [0] 它让说明更准确，更有说服力。
    [0] 比如桥长五百米，比说很长清楚。
    [1] 拿两个事物对比，就是作比较。
    [1] 目的是突出其中一个的特点。
    [1] 比如大象比猫重，强调大象大。
    [2] 把事物比作另一物，是打比方。
    [2] 让枯燥知识变得有趣好懂。
    [2] 石拱桥像彩虹，画面感就来了。
    [3] 打比方和比喻很像，怎么区分？
    [3] 看目的：为了说明还是抒情？
    [3] 说明文里用，通常叫打比方。
    [-] 记住：数字求准，比较求显，比方求生。
    [-] 下节课我们试试自己写一段说明文。
    [-] 有问题随时问林老师哦。
    [-] 我们来做一道练习。
    [-] “地球是一个蓝色的水球”用了什么说明方法？
    [-] 选项在黑板上，选好了告诉我。
  check 4.2s | {"pass": true, "scores": {"1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 1, "7": 2, "8": 2, "9": 2, "10": 2, "11": 1, "12": 2, "13": 2, "14": 2, "15": 2}, "problems": ["第6条标准：讲稿中虽有提问“怎么区分？”，但紧接着直接给出答案，缺乏引导学生思考的互动过程或等待时间提示。", "第11条标准：作为综合练习课，学生在本节主要处于被动听讲状态，缺少明确的复述、判断或试做环节来体现‘有事可做’。"], "fix": "在讲解难点辨析时增加引导性停顿或反问，并在小结前安排一个快速的学生口头判断或填空环节以增强参与度。", "items": 15}


### run2_g9
outline 14.0s | subject=化学 hook=问题
  objectives: ['能运用最小公倍数法配平常见方程式', '能识别并修正配平中的系数错误', '能规范书写配平后的化学方程式'] | key: 最小公倍数法的步骤与原理 | difficulty: 奇数配偶法的应用时机
  sections: [('回顾质量守恒定律', 'review', False), ('掌握最小公倍数法', 'core', True), ('尝试奇数配偶法', 'new', False), ('综合练习与纠错', 'core', True)]
  intro: ['同学们好，我是林老师。', '大家还记得铁生锈吗？', '反应前后原子去哪了？', '今天我们要解决这个疑问。', '目标是学会配平化学方程式。', '我们将分四步来攻克它。']
section 1 4.3s | board: 回顾质量守恒定律 | ['核心：反应前后原子种类、数目不变', '依据：质量守恒定律的微观解释']
    [0] 同学们，配平的本质是什么？
    [0] 对，就是让两边原子个数相等。
    [0] 就像天平两端必须一样重。
    [1] 为什么原子数目不能变呢？
    [1] 因为化学反应只是原子的重组。
    [1] 没有创造也没有消灭任何原子。
    [-] 记住原子守恒是配平的根基。
    [-] 接下来我们学习具体的配平方法。
  check 3.0s | {"pass": true, "scores": {"1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 2, "10": 2, "11": 2, "12": 2, "13": 2, "14": 2, "15": 2, "16": 2}, "problems": [], "fix": "无需修改，符合复习课快速带过、不举新例的要求。", "items": 16}
section 4 10.5s | board: 综合练习与纠错 | ['易错点一：漏写反应条件或气体符号', '易错点二：奇数配偶法使用不当', '易错点三：系数未约分或写成分数']
    [0] 同学们，配平对了不代表满分。
    [0] 看这道题，加热高锰酸钾制氧气。
    [0] 很多同学忘了写加热符号和箭头。
    [0] 就像做菜没开火，步骤是不完整的。
    [0] 记住，条件和状态符号不能少。
    [1] 再看这个难点，氧化铁加一氧化碳。
    [1] 氧原子总数是奇数，怎么办？
    [1] 你猜猜看，先给谁配系数？
    [1] 对，先给氧化铁配二，变偶数。
    [1] 这样最小公倍数才好找。
    [2] 最后检查系数，必须是整数。
    [2] 比如氢气燃烧，别写成一点五。
    [2] 如果有公约数，记得要约分。
    [2] 像四和二，化简成二和一。
    [2] 最简整数比才是标准答案。
    [-] 我们复习了条件、奇偶法和约分。
    [-] 最关键的是：配平后必查这三点。
    [-] 这节课就到这里，有问题随时问。
    [-] 我们来做一道练习。
    [-] 下列方程式配平及标注正确的是？
    [-] 选项在黑板上，选好了告诉我。
  check 8.0s | {"pass": true, "scores": {"1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 2, "10": 2, "11": 1, "12": 2, "13": 2, "14": 2, "15": 2, "16": 1}, "problems": ["要点2中‘氧原子总数是奇数’表述不严谨，应明确指反应物或生成物中某元素原子个数为奇数时采用奇数配偶法，避免学生误解为整个方程式所有氧原子总和。", "学生互动不足，仅在要点2有一次简单提问，缺乏让学生独立尝试配平或纠错的具体活动（如板演、口述步骤），不符合‘学生有事可做’的高标准要求。", "板书与讲稿对应性稍弱，板书列出三个易错点，但讲稿中要点3的‘约分’例子（4和2化简）未体现具体化学方程式背景，略显抽象，建议结合具体方程式展示错误写法再修正。"], "fix": "增加学生动手环节，例如给出一个典型错误方程式让学生现场修改并说明理由；同时优化要点2的术语表述，明确‘奇数配偶法’针对的是特定物质中原子个数为奇数的情况。", "items": 16}


## Before the calibration (same prompts otherwise)

### run_g1
outline 11.6s | subject=数学 hook=故事
  objectives: ['能说出9加几的凑十方法', '能正确计算20以内进位加法', '能用小棒演示凑十过程'] | key: 掌握“拆小数、凑大数”的方法 | difficulty: 理解为什么要先凑成10
  sections: [('复习10的组成', 'review', False), ('猴子分桃情境', 'new', False), ('动手摆小棒', 'core', True), ('儿歌记忆口诀', 'core', True)]
  intro: ['小朋友们好，我是林老师！', '今天森林里开派对啦！', '猴子哥哥有9个桃子。', '弟弟又送来4个桃子。', '一共有多少个呢？', '咱们一起学“凑十法”。']
section 1 4.5s | board: 复习10的组成 | ['10可以分成几和几']
  check 6.5s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 0, "4": 1, "5": 2, "6": 1, "7": 0, "8": 1, "9": 1, "10": 2, "11": 1, "12": 1, "13": 0, "14": 1, "15": 2, "16": 2, "17": 2}, "problems": ["标准3：仅展示了5+5=10这一种情况，未解释其他组合（如1和9、2和8等）的原因及举例，内容单薄。", "标准7：作为复习课，未针对一年级学生易错的‘凑十’概念进行常见错误提醒或变式练习，缺乏深度。", "标准13：没有安排任何紧扣本节要点的练习题或互动环节，学生处于被动听讲状态，不符合‘有事可做’的要求。"], "fix": "需补充10的其他组成形式（如1和9、2和8等）并配合具体实物演示，增加快速口算练习以巩固记忆，确保板书与讲稿涵盖完整的10的分解知识体系。", "items": 17}
section 4 13.0s | board: 儿歌记忆口诀 | ['凑十歌：一九一九好朋友', '二八二八手拉手', '三七三七真亲密', '四六四六一起走', '五五凑成一双手']
  check 9.6s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 2, "6": 1, "7": 0, "8": 2, "9": 2, "10": 2, "11": 1, "12": 1, "13": 1, "14": 1, "15": 2, "16": 1, "17": 2}, "problems": ["标准7缺失：重点难点处（如‘拆小数凑大数’的具体应用或常见错误）没有例题、变式或针对性提醒，仅停留在背诵口诀层面。", "标准3不足：部分要点缺乏具体的计算小例题演示如何运用口诀解决实际问题（如9+4具体怎么拆），导致‘能用小棒演示/正确计算’的目标落实不够。", "标准12薄弱：学生在本节主要是听和读，缺乏动手操作（如摆小棒验证口诀）或完整的试做练习环节，互动深度不足。"], "fix": "在讲解每句口诀后，增加一个具体的进位加法算式（如9+4）作为例子，演示如何利用口诀进行‘拆小数、凑大数’的计算过程，并设计让学生动手摆小棒验证的环节。", "items": 17}

### run_g8
outline 10.6s | subject=数学 hook=情境
  objectives: ['能叙述勾股定理的内容', '能用勾股定理求直角边长', '能解决简单的实际问题'] | key: 勾股定理的内容及公式应用 | difficulty: 灵活选择已知边求未知边
  sections: [('回顾直角三角形', 'review', False), ('发现数量关系', 'core', True), ('定理简单应用', 'new', True), ('生活问题解决', 'new', False)]
  intro: ['同学们好，我是林老师。', '大家见过梯子靠墙吗？', '梯脚到墙根的距离怎么算？', '今天我们要学一个神奇工具。', '它能帮我们求出直角三角形的边长。', '课程分为四个部分进行讲解。']
section 1 4.7s | board: 回顾直角三角形 | ['直角三角形：有一个角是 $90^\\circ$ 的三角形', '边：两条直角边和一条斜边（最长）']
  check 5.0s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 2, "6": 2, "7": 0, "8": 2, "9": 2, "10": 2, "11": 0, "12": 1, "13": 0, "14": 2, "15": 2, "16": 2, "17": 1}, "problems": ["标准7缺失：作为回顾课，未针对初二学生易混淆的‘斜边定义’或‘直角边与斜边的位置关系’设置常见错误提醒或辨析例题。", "标准11缺失：讲稿中无具体的表扬反馈机制，也未体现‘先肯定再纠错’的教学互动策略。", "标准13缺失：本节无练习题设计，仅靠口头问答无法落实‘紧扣本节要点’的练习要求。"], "fix": "增加一道关于识别直角三角形各边名称的辨析题（含常见错误选项），并在讲稿中补充具体的评价语和互动环节。", "items": 17}
section 4 8.8s | board: 生活问题解决 | ['建模：实际问题 $\\rightarrow$ 直角三角形', '找直角：确定哪条是斜边', '公式：$a^2+b^2=c^2$ 求未知', '检验：结果是否符合实际']
  check 6.3s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 2, "6": 1, "7": 2, "8": 2, "9": 2, "10": 2, "11": 0, "12": 1, "13": 1, "14": 2, "15": 2, "16": 2, "17": 1}, "problems": ["标准11不符合：讲稿中完全没有出现表扬学生具体做法或先肯定再指出错误的互动环节，缺乏对‘错误’的具体反馈机制。", "标准3部分符合：要点3仅给出数字例子（3-4-5），未展示具体的解题步骤或完整的小例题演算过程，解释不够充分。", "标准12/13部分符合：结尾布置的‘电视对角线’任务过于简略，且前文缺乏对应的练习变式，学生在本节中实际动手操作的机会较少。"], "fix": "增加师生互动环节，模拟学生回答后给予具体表扬或纠错反馈；在讲解公式应用时补充一个完整的解题步骤示例，并设计一道紧扣本节要点的即时练习题供学生试做。", "items": 17}

### run_g10
outline 16.5s | subject=数学 hook=情境
  objectives: ['能准确表述函数单调性的严格定义', '能用定义法证明简单函数的单调性', '能结合图像直观判断函数的单调区间'] | key: 函数单调性的严格定义及证明步骤 | difficulty: 从图形直观到代数定义的思维转化
  sections: [('温故知新：图像观察', 'review', False), ('概念建构：严格定义', 'core', True), ('方法演练：定义证明', 'new', True), ('应用拓展：复合视角', 'new', False)]
  intro: ['同学们好，我是林老师。', '大家见过气温随时间变化的曲线吗？', '有的段上升，有的段下降。', '数学里如何严谨描述这种变化？', '今天我们要攻克函数的单调性。', '目标是学会用定义证明单调性。']
section 1 4.5s | board: 温故知新：图像观察 | ['一次函数 $y=kx+b$：$k>0$ 时上升，$k<0$ 时下降', '二次函数 $y=x^2$：对称轴左侧降，右侧升']
  check 5.4s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 0, "4": 2, "5": 2, "6": 1, "7": 0, "8": 2, "9": 2, "10": 2, "11": 0, "12": 1, "13": 0, "14": 2, "15": 2, "16": 2, "17": 0}, "problems": ["标准3：要点讲解缺乏具体例子或小例题支撑，仅停留在描述图像特征。", "标准7：作为难点转化的起始节，未针对‘直观到定义’的常见认知误区进行提醒或变式训练。", "标准12：学生互动极少，仅有两次简单猜测，缺乏实质性的复述、试做或练习环节。"], "fix": "增加具体的函数实例（如给出具体解析式让学生判断）和针对性的易错点辨析，并设计一个让学生尝试用自然语言描述‘上升’的小练习以衔接下节课的定义。", "items": 17}
section 4 13.3s | board: 应用拓展：复合视角 | ['单调性是局部性质，非整体特征', '反例：$y=\\frac{1}{x}$ 在 $(-\\infty,0)$ 和 $(0,+\\infty)$ 分别递减', '易错点：跨区间比较需满足定义域连续性', '规范表述：单调区间必须用逗号或“和”连接', '总结：严格区分“在区间上”与“在定义域上”']
  check 6.3s | {"pass": true, "scores": {"1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 2, "10": 2, "11": 1, "12": 1, "13": 1, "14": 2, "15": 2, "16": 2, "17": 1}, "problems": ["第11条：讲稿中缺乏具体的表扬或纠错反馈机制，仅用‘对’简单回应，未体现先肯定后指出错误类型的规范。", "第12条：学生互动不足，除了猜测大小外，缺少让学生动手书写正确区间表述或复述定义的环节。", "第13条：结尾提出的二次函数问题虽好，但未给出变式练习或让学生尝试解答，导致本节以提问结束而非巩固结束。"], "fix": "增加学生动手写单调区间的环节，并在点评时具体化表扬与纠错话术，确保最后有一个简短的变式练习闭环。", "items": 17}

### run_g5
outline 13.9s | subject=语文 hook=情境
  objectives: ['能识别文中常用的三种说明方法', '能说出每种方法的作用和好处', '能尝试用一种方法介绍身边事物'] | key: 掌握列数字、作比较、举例子 | difficulty: 区分不同方法的表达效果
  sections: [('认识说明方法', 'new', False), ('列数字与作比较', 'core', True), ('举例子的妙处', 'core', True), ('综合运用练习', 'review', True)]
  intro: ['同学们好！我是林老师。', '看这张照片，大象真大呀！', '怎么让别人知道它多大？', '今天学几种说明方法。', '学会后你能把事物讲清楚。']
section 1 5.6s | board: 认识说明方法 | ['对比句子：大象重六吨 vs 大象很重', '列数字：用具体数据让说明更准确', '作比较：通过对比突出事物特征', '举例子：用具体事例让抽象变直观']
  check 4.5s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2, "7": 1, "8": 2, "9": 2, "10": 2, "11": 0, "12": 1, "13": 0, "14": 2, "15": 2, "16": 2}, "problems": ["标准11：讲稿中缺乏对学生回答的具体表扬或错误纠正环节，未体现‘先肯定再指出错误’的反馈机制。", "标准13：本节无练习题（符合定位），但作为新授课，缺少即时的小练习或变式训练来巩固识别能力，仅靠讲解略显单薄。", "标准7：重点难点处虽有例子，但缺乏针对‘区分不同方法表达效果’这一难点的对比辨析或常见错误提醒（如混淆列数字与举例子）。"], "fix": "增加师生互动中的具体反馈环节（表扬/纠错），并在讲解每种方法后插入一个微型判断练习以突破难点。", "items": 16}
section 4 7.5s | board: 综合运用练习 | ['混合使用：数字+比较+例子', '辨析难点：看标志词判断方法']
  check 5.9s | {"pass": false, "scores": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 2, "6": 1, "7": 2, "8": 2, "9": 2, "10": 2, "11": 0, "12": 1, "13": 2, "14": 2, "15": 2, "16": 2}, "problems": ["标准11不符合：讲稿中完全没有体现‘表扬具体到做法’或‘指出错误先肯定再说错误类型’的教学互动环节，缺乏对预设学生反馈的处理。", "标准3部分符合：要点2讲解标志词时，仅列举了关键词，未提供具体的句子示例来演示如何应用这些标志词进行判断，解释略显单薄。", "标准6部分符合：虽有提问‘怎么区分’，但直接给出答案，缺乏引导学生思考的中间步骤（如先让学生猜再揭示），启发性稍弱。"], "fix": "增加师生互动环节，模拟对学生回答的具体表扬或对常见错误的纠正话术，以符合教学评价标准11。", "items": 16}

===== FILE: configs/curriculum/teaching_craft.json =====
{
 "sources": [
  {
   "id": "c1",
   "title": "233网校《2019下半年教师资格笔试科目二 教育教学知识与能力（小学）》考点（教学原则、导入、提问、板书、课堂总结）",
   "url": "https://img3.233.com/2019-07/26/156412076595801.pdf",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c2",
   "title": "教育部师范教育司、教育部考试中心《中小学和幼儿园教师资格考试标准（试行）》2011",
   "url": "https://www.wic.edu.cn/upload/20260521/9d99b67b3edce71df4045951441c7d30.pdf",
   "kind": "standard",
   "accessed": "2026-09-30"
  },
  {
   "id": "c3",
   "title": "华立学院教师发展中心《备课、说课、上课、评课、听课诀窍大全》",
   "url": "https://www.hualixy.edu.cn/jsfzzx/xxzy/content_66135",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c4",
   "title": "黑龙江职业学院课程思政教学研究中心《教学设计｜十种导入法》",
   "url": "https://www.hljp.edu.cn/kcszjxyj/info/1041/1574.htm",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c5",
   "title": "上海师范大学心理学院《教师课堂教学行为规范》",
   "url": "https://psy.shnu.edu.cn/46/54/c30437a804436/page.htm",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c6",
   "title": "《礼记·学记》全文（维基文库）",
   "url": "https://zh.wikisource.org/wiki/%E7%A6%AE%E8%A8%98/%E5%AD%B8%E8%A8%98",
   "kind": "book",
   "accessed": "2026-09-30"
  },
  {
   "id": "c7",
   "title": "邱学华《上好一堂课的十二个诀窍》（西北农林科技大学附中转载）",
   "url": "https://fuzhong.nwafu.edu.cn/tzgg/292524.htm",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c8",
   "title": "《尝试教学的理论探索与实践创新——专访尝试教学法创始人邱学华》教师教育学报 2023",
   "url": "https://xbgjxt.swu.edu.cn/article/doi/10.13718/j.cnki.jsjy.2023.04.001?viewType=HTML",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c9",
   "title": "邱学华《尝试教学法ABC》黑龙江教育 1998(5)",
   "url": "https://hllj.cbpt.cnki.net/portal/journal/portal/client/paper/6c2d0b09ea389899269149743a14d63d",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c10",
   "title": "《有效教学应该从洋思中学学什么》中国教育和科研计算机网 2006-03-23",
   "url": "https://www.cernet.edu.cn/xxh/fei/xin_xi_zi_xun/importantnews/200603/t20060323_158424.shtml",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c11",
   "title": "曹伟林（洋思中学校长）《洋思模式如何保持定力与创新》中国教育报 2022-02-09",
   "url": "http://www.jyb.cn/rmtzgjyb/202202/t20220209_678534.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c12",
   "title": "顾泠沅《学科教学的水平演变与教师学习》WALS 2007 会议报告（青浦实验 1982/2007 观课标准、变式、错误资源）",
   "url": "https://eduhk.hk/wals/conference07/resources/wals07/2_29112007_gu.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c13",
   "title": "卢仲衡《三十三年自学辅导教学研究的回顾与展望》教育研究 1998(10)",
   "url": "https://ir.psych.ac.cn/bitstream/311026/9615/2/%E4%B8%89%E5%8D%81%E4%B8%89%E5%B9%B4%E8%87%AA%E5%AD%A6%E8%BE%85%E5%AF%BC%E6%95%99%E5%AD%A6%E7%A0%94%E7%A9%B6%E7%9A%84%E5%9B%9E%E9%A1%BE%E4%B8%8E%E5%B1%95%E6%9C%9B.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c14",
   "title": "李吉林《谈情境教育的课堂操作要义》教育研究 2002(3)（爱思想转载）",
   "url": "https://www.aisixiang.com/data/100090.html",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c15",
   "title": "《课堂提问教学解读与评价》教师培训文档（信阳农林学院）：问题设计、候答3-5秒、助答五法、追问、理答",
   "url": "https://www.xyafu.edu.cn/__local/A/F4/5A/542638649C0D5860018A98BAA9E_788EA74A_338CA5.pdf",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c16",
   "title": "教育部办公厅《关于加强义务教育学校作业管理的通知》教基厅函〔2021〕13号",
   "url": "http://www.moe.gov.cn/srcsite/A06/s3321/202104/t20210425_528077.html",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c17",
   "title": "清华大学出版社《教育心理学（第2版）》第二章 心理发展与教育（样章：年龄阶段与思维类型）",
   "url": "http://www.tup.tsinghua.edu.cn/upload/books/yz/071572-01.pdf",
   "kind": "textbook",
   "accessed": "2026-09-30"
  },
  {
   "id": "c18",
   "title": "华图教师网《中小学学生心理发展的一般特征与阶段特征》",
   "url": "https://ah.huatu.com/2022/0930/2430122.html",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c19",
   "title": "《课堂上“导与学”的迭代》中国教师报 2020-06-02（导学案三节点、低起点小跨度上台阶）",
   "url": "http://www.jyb.cn/rmtzgjsb/202006/t20200602_333838.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c20",
   "title": "《魏书生 教育更像是一场长跑》中国教师报 2023-07-11",
   "url": "http://www.jyb.cn/rmtzgjsb/202307/t20230711_2111068301.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c21",
   "title": "Rosenshine, B. (2012). Principles of Instruction. American Educator 36(1)",
   "url": "https://www.aft.org/sites/default/files/Rosenshine.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c22",
   "title": "Lemov, D. Teach Like a Champion Field Guide, sample chapter: Technique 1 No Opt Out",
   "url": "https://teachlikeachampion.org/wp-content/uploads/Field-Guide-sample-chapter.pdf",
   "kind": "book",
   "accessed": "2026-09-30"
  },
  {
   "id": "c23",
   "title": "Teach Like a Champion blog: TLaC 2.0 Adding Stretch It to No Opt Out",
   "url": "https://teachlikeachampion.org/blog/tlac-2-0-adding-stretch-it-to-no-opt-out/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c24",
   "title": "Teach Like a Champion: Precise Praise (official tag page)",
   "url": "https://teachlikeachampion.org/tag/precise-praise/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c25",
   "title": "Teach Like a Champion blog: Katie McNickle's Show Call",
   "url": "https://teachlikeachampion.org/blog/katie-mcnickles-show-call/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c26",
   "title": "Teach Like a Champion: Free Resources / Grab and Go (Cold Call, Wait Time, Exit Ticket, Do Now)",
   "url": "https://teachlikeachampion.org/resources/grab-and-go/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c27",
   "title": "Teach Like a Champion: Retrieval Practice (official tag page)",
   "url": "https://teachlikeachampion.org/tag/retrieval-practice/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c28",
   "title": "Teach Like a Champion: Everybody Writes (official tag page)",
   "url": "https://teachlikeachampion.org/tag/everybody-writes/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c29",
   "title": "CSUN: Elements of Lesson Design (Madeline Hunter)",
   "url": "https://csun.edu/science/ref/plans/lesson_design_hunter.html",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c30",
   "title": "Northern Illinois University CITL: Gagné's Nine Events of Instruction",
   "url": "https://www.niu.edu/citl/resources/guides/instructional-guide/gagnes-nine-events-of-instruction.shtml",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c31",
   "title": "McTighe, J. & Wiggins, G. (2012). Understanding by Design Framework (ASCD white paper)",
   "url": "https://files.ascd.org/staticfiles/ascd/pdf/siteASCD/publications/UbD_WhitePaper0312.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c32",
   "title": "Black, P. & Wiliam, D. (1998). Inside the Black Box. Phi Delta Kappan 80(2)",
   "url": "https://kappanonline.org/inside-the-black-box-raising-standards-through-classroom-assessment/",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c33",
   "title": "Wiliam, D. (2015). Designing Great Hinge Questions. Educational Leadership 73(1)",
   "url": "https://www.ascd.org/el/articles/designing-great-hinge-questions",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c34",
   "title": "Wiliam, D. Assessment for Learning: why, what and how? (Cambridge AfL keynote)",
   "url": "https://www.dylanwiliam.org/Dylan_Wiliams_website/Papers_files/Cambridge%20AfL%20keynote.doc",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c35",
   "title": "Wiliam, D. (2004). Keeping learning on track: integrating assessment with instruction (IAEA)",
   "url": "https://www.dylanwiliam.org/Dylan_Wiliams_website/Papers_files/IAEA%2004%20paper.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c36",
   "title": "Hattie, J. & Timperley, H. (2007). The Power of Feedback. Review of Educational Research 77(1)",
   "url": "https://www.uky.edu/~gmswan3/575/Hattie_Timperly_2007.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c37",
   "title": "Coe, R., Aloisi, C., Higgins, S. & Major, L. E. (2014). What makes great teaching? Sutton Trust",
   "url": "https://www.suttontrust.com/wp-content/uploads/2014/10/What-Makes-Great-Teaching-REPORT.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c38",
   "title": "Young-Jones, A. (2013). Review of Willingham, Why Don't Students Like School? Education Research and Perspectives 40",
   "url": "https://www.erpjournal.net/wp-content/uploads/2020/01/ERPV40_Young-Jones_2013_Willingham_Book_Review.pdf",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c39",
   "title": "APA Blog (2020). Takeaways from Make It Stick: The Science of Successful Learning",
   "url": "https://blog.apaonline.org/2020/02/19/takeaways-from-make-it-stick-the-science-of-successful-learning/",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c40",
   "title": "Russell, D. (2019). Cognitive load theory: teaching strategies (interview with John Sweller), Teacher magazine",
   "url": "https://www.teachermagazine.com/au_en/articles/cognitive-load-theory-teaching-strategies",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c41",
   "title": "educationaltechnology.net: Mayer's principles of multimedia learning (Mayer 2009)",
   "url": "https://educationaltechnology.net/?p=1878",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c42",
   "title": "Structural Learning research briefing: Wait time — three seconds (Rowe 1986)",
   "url": "https://www.structural-learning.com/research-briefings/wait-time-three-seconds",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c43",
   "title": "教育部关于批准2014年国家级教学成果奖获奖项目的决定 教师〔2014〕8号",
   "url": "http://www.moe.gov.cn/jyb_xxgk/xxgk/neirong/fenlei/sxml_jsgz/jsgz_sdjs/sdjs_yxjs/201409/t20140905_174749.html",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c44",
   "title": "澎湃新闻（转教育部）2018年国家级教学成果奖获奖项目揭晓（上海市教委教研室 数学 特等奖）",
   "url": "https://www.thepaper.cn/newsDetail_forward_2808246",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c45",
   "title": "教育部（转光明日报）“全国教书育人楷模”于漪：教师是教育的希望 2010-10-20",
   "url": "http://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/s3582/s4672/s4728/s4729/201010/t20101028_110449.html",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c46",
   "title": "教育部 人民教育家先进事迹——于漪 2021-05-11",
   "url": "http://www.moe.gov.cn/jyb_xwfb/moe_2082/2021/2021_zl37/shideshiji/202105/t20210511_530839.html",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c47",
   "title": "光明日报 全国教书育人楷模候选人简介 2010-08-08（吴正宪）",
   "url": "https://epaper.gmw.cn/gmrb/html/2010-08/08/nw.D110000gmrb_20100808_1-06.htm",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c48",
   "title": "新华网 2024年度全国教书育人楷模名单公布 2024-09-06（俞正强）",
   "url": "https://www.news.cn/edu/20240906/ff95f1b23d804466983309609ecf0b47/c.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c49",
   "title": "光明日报 2015年度全国教书育人楷模候选人简介 2015-07-28（李庾南）",
   "url": "http://epaper.gmw.cn/gmrb/html/2015-07/28/nw.D110000gmrb_20150728_1-15.htm",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c50",
   "title": "澎湃新闻 中国名校访谈④｜清华附小校长窦桂梅：让教师退居后台还课堂给学生 2016-04-14",
   "url": "https://m.thepaper.cn/newsDetail_forward_1456211",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c51",
   "title": "清华大学新闻 超越·主题·整合——窦桂梅教育教学实践研讨会 2013-10-18",
   "url": "https://www.tsinghua.edu.cn/info/1181/53722.htm",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c52",
   "title": "澎湃新闻 “最美奋斗者”斯霞老师事迹报告会在南京举行 2019-11-15",
   "url": "https://www.thepaper.cn/newsDetail_forward_4959458",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c53",
   "title": "澎湃号·政务 于永正：做一个学生喜欢的老师",
   "url": "https://www.thepaper.cn/newsDetail_forward_28485552",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c54",
   "title": "李虹霞 于永正：不要忘记自己曾经也是孩子 中国教师报 2024-04-17",
   "url": "http://www.jyb.cn/rmtzgjsb/202404/t20240416_2111181994.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c55",
   "title": "浙江在线 他曾是杭州小学语文教育的标杆 特级教师王崧舟重出江湖 2017-07-31",
   "url": "https://zjnews.zjol.com.cn/zjnews/hznews/201707/t20170731_4682424.shtml",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c56",
   "title": "王崧舟 诗意语文，境界为上 当代教育家 2025-06（网易转载）",
   "url": "https://m.163.com/dy/article/K2DJ2PO00516DKF5.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c57",
   "title": "薛法根 从“教课文”到“学语文”——小学阅读教学内容的组块策略 福建教育 2015(1/2)",
   "url": "https://www.aisixiang.com/data/91299.html",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c58",
   "title": "扬子晚报 星光好老师②金陵中学附属小学孙双金 2025-09-30",
   "url": "https://www.yzwb.net/news/yysp/202509/t20250930_271296.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c59",
   "title": "华应龙 有“化错”，才有真正的学习 光明日报 2015-01-13",
   "url": "https://epaper.gmw.cn/gmrb/html/2015-01/13/nw.D110000gmrb_20150113_1-15.htm",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c60",
   "title": "人民日报 “错不起的学生，对不了”（在一线）2019-07-21（华应龙课例）",
   "url": "http://society.people.com.cn/n1/2019/0721/c1008-31246394.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c61",
   "title": "孙敬彬 华应龙老师的“求化” 中国教师报 2024-06-19",
   "url": "http://www.jyb.cn/rmtzgjsb/202406/t20240618_2111211310.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c62",
   "title": "禹跃昆 华应龙：把立德树人写到数学课中 中国教育报 2025-04-08",
   "url": "http://paper.jyb.cn/zgjyb/h5/html5/2025-04/08/content_144742_18418009.htm",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c63",
   "title": "张兴华口述 穷尽一生探寻贝壳里的世界 中国教师报 2020-12-16",
   "url": "http://www.jyb.cn/rmtzgjsb/202012/t20201215_382756.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c64",
   "title": "澎湃新闻 “上好课、教好书、管好学校、带好学生”，俞正强老师这样说 2024-09-21",
   "url": "https://m.thepaper.cn/newsDetail_forward_28814093",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c65",
   "title": "中国教育新闻网 2024年度全国教书育人楷模俞正强：为师生寻找幸福 2024-09-06",
   "url": "http://www.jyb.cn/rmtzcg/xwy/wzxw/202409/t20240906_2111242258.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c66",
   "title": "双流县实验小学 校本培训简讯 2016（黄爱华《倒数的认识》大问题课例，摘要）",
   "url": "https://slypzx.com/uploadFolder/mystudio/2016/12/19/校本培训简讯_57002.doc",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c67",
   "title": "小花生网（澎湃号）专访全国特级教师刘善娜：一二年级娃这么“搞”数学，后劲才足 2024-02-27",
   "url": "https://m.thepaper.cn/newsDetail_forward_26476895",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c68",
   "title": "王咏梅 在教学四“变”中走向新我 中国教育报 2022-06-07",
   "url": "http://www.jyb.cn/rmtzgjyb/202206/t20220607_696175.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c69",
   "title": "光明网·教育家 魏书生：为“教书”而生 2019-07-04",
   "url": "https://jyj.gmw.cn/2019-07/04/content_32973748.htm",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c70",
   "title": "林志芳 寻找幸福教育的符码 中国教育报 2022-03-23（魏书生六步教学法）",
   "url": "http://www.jyb.cn/rmtzgjyb/202203/t20220323_685920.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c71",
   "title": "陈文 寻找语文教育的“魂”——读钱梦龙《教师的价值》中国教育报 2024-06-05",
   "url": "http://www.jyb.cn/rmtzgjyb/202406/t20240605_2111205162.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c72",
   "title": "胡立根 钱梦龙专业成长的三点启示 中国教师报 2024-05-29",
   "url": "http://www.jyb.cn/rmtzgjsb/202405/t20240528_2111201569.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c73",
   "title": "澎湃新闻 悲痛，钱梦龙老师去世 2024-05",
   "url": "https://m.thepaper.cn/newsDetail_forward_27485079",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c74",
   "title": "搜狐 教学流派｜余映潮：我与“板块式”教学思路的创立（摘要）",
   "url": "https://www.sohu.com/a/128642576_549584",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c75",
   "title": "褚清源 李庾南：教学实践的三重境界 中国教师报 2023-03-14",
   "url": "http://www.jyb.cn/rmtzgjsb/202303/t20230314_2111014383.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c76",
   "title": "李庾南 弘扬教育家精神 长出精神和本领来 人民教育（中国教育新闻网）2024-09-13",
   "url": "http://www.jyb.cn/rmtzcg/xwy/wzxw/202409/t20240913_2111245227.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c77",
   "title": "人民网 躬耕三尺讲台58载——记江苏省南通市启秀中学教师李庾南 2015-09-12",
   "url": "http://edu.people.com.cn/n/2015/0912/c1053-27575628.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c78",
   "title": "温丹丹 如何训练发达的大脑 中国教育报（人民网转载）2015-08-13（孙维刚）",
   "url": "http://edu.people.com.cn/n/2015/0813/c1053-27455474.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c79",
   "title": "顾泠沅 45年：一项数学教改实验 华东师范大学学报（教育科学版）2022,40(4)",
   "url": "https://xbjk.ecnu.edu.cn/CN/Y2022/V40/I4/103",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c80",
   "title": "新民晚报 2021-07-14 青浦实验报道（1992年国家教委定为基础教育改革重大成果，摘要）",
   "url": "https://img1.xinmin.cn/xmwb/2021-07-14/50714.pdf",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c81",
   "title": "程翔 教者与编者 中华读书报 2020-09-23（中国教育新闻网转载）",
   "url": "http://www.jyb.cn/rmtzcg/xwy/wzxw/202011/t20201116_373898.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c82",
   "title": "北京师范大学数学科学学院 章建跃讲座：核心素养统领下的高中数学教育变革 2017-06-02",
   "url": "https://math.bnu.edu.cn/xzbg/jcxylt/218849.htm",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c83",
   "title": "中国教育新闻网 任勇：努力用“数学砖瓦”筑起思维“游乐场” 2025-04-30",
   "url": "http://www.jyb.cn/rmtzcg/xwy/wzxw/202504/t20250430_2111339397.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c84",
   "title": "李惠军 灵魂的追问（8）——谨防“泛方法论” 历史教学 2015(10)（搜狐转载）",
   "url": "https://m.sohu.com/a/128183340_629818",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c85",
   "title": "解放网（人民网上海）国家级基础教育教学成果奖揭晓 2024-01-24（顾雨薇 画兔点睛 课例）",
   "url": "http://sh.people.com.cn/n2/2024/0124/c138654-40724477.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c86",
   "title": "袁小梅、孙建 道德与法治教育跨学科融合的意义、方法与策略 中国民族教育 2025-05-09",
   "url": "http://www.jyb.cn/rmtzcg/xwy/wzxw/202505/t20250509_2111341552.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c87",
   "title": "孙振坤 建设适性课堂 培育栋梁之材——南京市竹山中学 中国教育报 2025-03-16",
   "url": "http://paper.jyb.cn/zgjyb/h5/html5/2025-03/16/content_144743_18349092.htm",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c88",
   "title": "楚得群 高中化学课堂如何做到守正创新 中国教育报 2023-06-30",
   "url": "http://www.jyb.cn/rmtzgjyb/202306/t20230630_2111062695.html",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c89",
   "title": "Nancie Atwell (Wikipedia)",
   "url": "https://en.wikipedia.org/wiki/Nancie_Atwell",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c90",
   "title": "Andria Zafirakou (Wikipedia)",
   "url": "https://en.wikipedia.org/wiki/Andria_Zafirakou",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c91",
   "title": "Varkey Foundation: Global Teacher Prize winners page",
   "url": "https://varkeyfoundation.org/global-teacher-prize",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c92",
   "title": "NCETM/Maths Hubs, Shanghai Teachers: mid exchange report, Nov 2014 (NRICH copy)",
   "url": "https://nrich.maths.org/content/id/10757/Shanghai_teachers_special_report_Nov_2014.pdf",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c93",
   "title": "NCETM: Five Big Ideas in Teaching for Mastery",
   "url": "https://www.ncetm.org.uk/teaching-for-mastery/mastery-explained/five-big-ideas-in-teaching-for-mastery/",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c94",
   "title": "NCETM: Teaching mathematics for mastery at secondary school (2015 Shanghai exchange)",
   "url": "https://www.ncetm.org.uk/features/teaching-mathematics-for-mastery-at-secondary-school",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c95",
   "title": "Boylan et al. (2019). Longitudinal evaluation of the Mathematics Teacher Exchange: China-England, DfE RR902",
   "url": "https://assets.publishing.service.gov.uk/media/5c49b38340f0b61717193d2d/MTE_main_report.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c96",
   "title": "NCES (1999). The TIMSS Videotape Classroom Study",
   "url": "https://nces.ed.gov/pubs99/timssvid/index.asp",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c97",
   "title": "Takahashi, A. (2006). Characteristics of Japanese mathematics lessons, APEC Tsukuba slides",
   "url": "https://www.criced.tsukuba.ac.jp/math/apec/apec2006/pdf/takahashi_ppt_1.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c98",
   "title": "Takahashi, A. (2008). Beyond show and tell: neriage for teaching through problem-solving, ICME-11",
   "url": "https://lessonresearch.net/wp-content/uploads/2020/07/Characteristics-of-Japanese-Mathematics-Lessons-2.pdf",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c99",
   "title": "Batteau, Miyakawa & Ryu (2025). Collective problem-solving in Japanese primary mathematics lessons, Educational Studies in Mathematics",
   "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12145323/",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c100",
   "title": "Athabasca University: Engelmann's Direct Instruction (method)",
   "url": "https://psyc.athabascau.ca/open/engelmann/direct.php",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c101",
   "title": "Athabasca University: Direct Instruction evidence, Project Follow Through",
   "url": "https://psyc.athabascau.ca/open/engelmann/direct-evid.php",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c102",
   "title": "Stein & Rolf, The case for Direct Instruction, Chartered College Impact",
   "url": "https://my.chartered.college/impact_article/the-case-for-direct-instruction/",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c103",
   "title": "Direct instruction (Wikipedia): I do / We do / You do; 90% review",
   "url": "https://en.wikipedia.org/wiki/Direct_instruction",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c104",
   "title": "TES: 10 new teaching techniques Doug Lemov wants you to know (TLAC 3.0)",
   "url": "https://www.tes.com/magazine/teaching-learning/general/10-new-teaching-techniques-doug-lemov-wants-you-know",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c105",
   "title": "华容县教育体育局、华容县总工会 第一届中小学青年教师教学竞赛通知及评分表 2019",
   "url": "https://huarong.gov.cn/uploadfiles/201903/20190313153918233.docx",
   "kind": "rubric",
   "accessed": "2026-09-30"
  },
  {
   "id": "c106",
   "title": "岳阳市 第四届全市中小学青年教师教学竞赛实施方案及评分表 2025",
   "url": "https://edu.yueyang.gov.cn/uploadfiles/202512/2025120109155930581.doc",
   "kind": "rubric",
   "accessed": "2026-09-30"
  },
  {
   "id": "c107",
   "title": "中国教育电视协会、中央电化教育馆 中教电〔2016〕35号 2017全国教育电视优秀教学课例 评审标准（试行）",
   "url": "https://fz.sjtu.edu.cn/__local/3/36/71/8E261F07E250ED1650065D334EB_97D74B7F_D2A8B.pdf",
   "kind": "rubric",
   "accessed": "2026-09-30"
  },
  {
   "id": "c108",
   "title": "教师资格证面试大纲-小学（233网校转载，教学设计/实施/评价要求与试讲要求）",
   "url": "https://img3.233.com/2019-11/21/157430425098861.doc",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c109",
   "title": "中等职业学校教师资格考试面试大纲评分标准表（新东方转载；教学实施 35 分含板书 8 分）",
   "url": "https://file.koolearn.com/20211211/16392008171758.doc",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c110",
   "title": "杨艳、杨六兰《英语教学中的板书艺术》西昌学院学报（社会科学版）2012(1)（正/副板书、板书类型与要求）",
   "url": "https://xbsk.xcc.edu.cn/xcxyxbsk/article/pdf/20120146",
   "kind": "paper",
   "accessed": "2026-09-30"
  },
  {
   "id": "c111",
   "title": "陕西师范大学历史文化学院 说课简介（含高中历史说课示例）",
   "url": "https://his.snnu.edu.cn/__local/C/88/76/867429B3AF5DD1B914C5E12036A_D35D8845_9400.doc",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c112",
   "title": "陕西师范大学研究生院 说课·评课材料（目标全面/适当/具体/明确）",
   "url": "https://newyjs.snnu.edu.cn/__local/4/C0/56/B72A430A93B0783AB77C1B8FC1B_09E184DB_F400.doc",
   "kind": "school",
   "accessed": "2026-09-30"
  },
  {
   "id": "c113",
   "title": "教育部关于大力推进幼儿园与小学科学衔接的指导意见 2021",
   "url": "http://www.moe.gov.cn/srcsite/A06/s3327/202104/t20210408_525137.html",
   "kind": "official",
   "accessed": "2026-09-30"
  },
  {
   "id": "c114",
   "title": "中国新闻网 2022-04-21 义务教育课程方案和课程标准（2022年版）发布会报道（一至二年级活动化、游戏化、生活化）",
   "url": "https://www.chinanews.com.cn/gn/2022/04-21/9734982.shtml",
   "kind": "press",
   "accessed": "2026-09-30"
  },
  {
   "id": "c115",
   "title": "亿图 初中英语 教学设计模板（45分钟：导入5/新授20/巩固练习15/总结作业5）",
   "url": "https://mm.edrawsoft.cn/template/193411",
   "kind": "secondary",
   "accessed": "2026-09-30"
  },
  {
   "id": "c116",
   "title": "丁昱雯《小学英语教学游戏化的理念与策略》当代教育理论与实践 2016(7)",
   "url": "https://ddjy.hnust.edu.cn/ddjyllysj/article/pdf/6a",
   "kind": "paper",
   "accessed": "2026-09-30"
  }
 ],
 "notes": [
  "本文件是教学法知识库（teaching_craft.json），由五份研究笔记（docs/notes/research_notes/Teaching craft for the teacher agent/）整理而成：zh_textbooks.md、intl_textbooks.md、zh_master_teachers.md、intl_master_teachers.md、zh_rubrics_templates.md。整理日期 2026-09-30，来源访问日期均为 2026-09-30。",
  "出处标记：文本内的「（cN）」为来源编号，供审计用，程序在生成提示词时会去掉；每个条目的 sources 列出全部依据。",
  "哪些是引用、哪些是意译：环节规则、教师做法（moves）、板书规则和检查表的措辞都是编辑意译，不是原文；其依据是笔记中标为 cited 或 secondary 的材料（教育学与教学技能教材的考点条文、教育部标准与通知、竞赛评分表、Rosenshine/Wiliam/Hattie & Timperley 等原文、名师本人文章和主流媒体课例报道）。名师的姓名、学校、荣誉和方法只采用笔记标为 cited 或 secondary 的内容。",
  "数字的性质：候答 3-5 秒、教师讲话不超过 10 分钟、练习正确率约八成、洋思最后 15 分钟、Engelmann 每分钟 10-14 次齐答、Atwell 每年约 40 本、TIMSS 53% 等为引用（标「引用」或来自笔记的 cited 项）；各环节分钟数、各学段的互动频率、例题数、句长和「每条不超过 12 字」为估计（标「（估计）」）。作业时间限制引自教育部 2021 年作业管理通知（一二年级不布置书面家庭作业，小学其他年级每天不超 60 分钟，初中不超 90 分钟）。",
  "已排除的未核实内容：斯霞的特级教师称号、王崧舟的六字诀（举象、造境、入情、会意、求气、寻根）、吴正宪的八种课型、黄爱华的六步法、徐斌无痕教育的阶段名、张齐华社会化学习的课堂流程、章建跃的「三个理解」、东庐讲学稿、衡水双向六环节的环节名、张思明、刘德武、支玉恒、彭梦华、翟厚岚、黎世法、青浦四原理原文、魏书生六步的逐步内容（只保留中国教育报确认的六个步骤名）、李吉林六种创设情境途径之外的「形真情切意远理蕴」、洋思的逐环节分钟数、全国青教赛国家级评分权重、一师一优课评审指标、NTCE 小学/中学面试评分表权重（只引用已核实的中职表：教学实施 35 分含板书 8 分）。这些均未写入。",
  "荣誉栏说明：孙维刚（中国教育报 2015 只记载其实验班成绩，未核实特级教师称号）、邱学华（笔记未核实其荣誉与学校）、顾泠沅（青浦实验 1992 年由国家教委推广，摘要级来源）、章建跃（编审、教材主编为职务）、顾雨薇（只有课例报道，未核实获奖等级）、系统条目（日本课例研究、Engelmann 直接教学）的 honours 写的是笔记中有据的成就或职务，不是称号。刘善娜、邱学华的学校笔记未核实，school 留空。化学、生物学、地理、信息科技、科学以及初中历史、高中英语、高中物理未收录名师：笔记中没有达到做法层面且有可核实荣誉的人选（楚得群的化学课堂建议已并入「学生动手」做法）。",
  "笔记之间的差异：于永正五重教学法研讨会的年份，中国教师报记 1999 年、搜狐摘要记 1992 年，按笔记建议采用中国教师报，本文件未写年份。Project Follow Through 的规模两个来源不一致，本文件不写规模。Hattie 效应量各版本不同且受统计学批评，本文件不引用效应量数字。",
  "本文件不重复 pedagogy.json 的学段画像（学习者特点、教法、语气、句长、练习形式）；这里补充的是课的结构、可执行的教师做法、名师课例、板书规则和分节自检表。",
  "检查表的 scope：默认 section（对一节生成的板书和讲稿打分）；praise_correct 的 scope 是 feedback（只在批改反馈时适用，讲稿里学生还没有作答），分节自检不列出它。"
 ],
 "lesson_model": {
  "stages": [
   {
    "id": "hook",
    "name": "导入",
    "minutes": "2-5（估计）",
    "rules": [
     "用旧知、情境或问题引入，几分钟内揭示课题",
     "既引起注意又指向课题，不讲无关的故事",
     "温故导入要点名新知所依赖的旧知，以旧引新（c9）",
     "情境里藏一个冲突或悬念，让学生先猜、先试",
     "导入结束时说出这节课要学什么、能做到什么",
     "低年级用儿歌、游戏、实物；中学从问题或真实情境开始"
    ],
    "sources": [
     "c1",
     "c4",
     "c7",
     "c9",
     "c63",
     "c60",
     "c21",
     "c95"
    ]
   },
   {
    "id": "goal",
    "name": "明确目标",
    "minutes": "1（估计）",
    "rules": [
     "开课一分钟内写出课题和1-3条可检测的目标",
     "目标用可检测的动词：能说出、能算出、能写出",
     "说明为什么学、和已学内容有什么联系",
     "全课每个环节回到目标，结课逐条回应",
     "先想好最后要做的练习，再倒推讲解要讲什么（c31）"
    ],
    "sources": [
     "c7",
     "c10",
     "c2",
     "c112",
     "c31",
     "c29",
     "c30"
    ]
   },
   {
    "id": "explain",
    "name": "新授",
    "minutes": "10-20（估计）",
    "rules": [
     "小步子：一次一个要点，讲完就问再往下",
     "先具体后抽象：先例子或图，再规则术语",
     "例题边做边说，说清每一步的理由（c21）",
     "从学生已有知识出发，用观察、类比、归纳引出新知（c12）",
     "教师连续讲话不超过10分钟（估计），讲解结束在一个问题上而不是结论上",
     "指出易错点，给一个反例，说明什么不算",
     "术语第一次出现就用规范说法，之后坚持用",
     "板书只写关键词和图，讲图时指图说，不读板书"
    ],
    "sources": [
     "c21",
     "c12",
     "c7",
     "c1",
     "c6",
     "c38",
     "c40",
     "c102",
     "c92",
     "c41"
    ]
   },
   {
    "id": "check",
    "name": "提问与检查理解",
    "minutes": "贯穿全课（估计）",
    "rules": [
     "每个要点提一个要思考的问题，不做填空式问答",
     "答错先提示不给答案，答对追问为什么",
     "问后等3-5秒再说话；不问「懂了吗」，让学生复述或举例（c15）",
     "答错时依次：重复题意、分解难点、换角度、提示、补充修正",
     "一节课2-3个核心问题，放在重点、难点和新旧知识衔接处",
     "评价具体：说清对在哪、缺什么；弱答也肯定认真"
    ],
    "sources": [
     "c15",
     "c21",
     "c22",
     "c23",
     "c34",
     "c42",
     "c32"
    ]
   },
   {
    "id": "practice",
    "name": "练习",
    "minutes": "10-15（估计）",
    "rules": [
     "练在当堂：每个要点后一题，变式不重复",
     "正确率约八成（引用）：连错两题退一步重教",
     "先模仿练习，再独立完成的达标检测（c10）",
     "练习是例题的变式：换表面特征，留解法结构",
     "题不在多：一道好题胜过十道马虎题，按层次给题",
     "一二年级不留书面家庭作业；小学每天作业不超60分钟，初中不超90分钟（c16）"
    ],
    "sources": [
     "c7",
     "c10",
     "c13",
     "c12",
     "c21",
     "c16",
     "c78",
     "c92"
    ]
   },
   {
    "id": "feedback",
    "name": "反馈与纠错",
    "minutes": "贯穿全课（估计）",
    "rules": [
     "纠错先肯定再指错，表扬具体不滥用",
     "缺前置知识时重教一个例题，而不是多写评语",
     "把错误当资源：先让学生自己找原因再一起改（c59）",
     "反馈说任务和过程：哪里错、检查哪一步、下次怎么自查（c36）",
     "先说对在哪，再说错误类型和改的一步",
     "新技能学习时立即纠正，熟练练习时做完再评",
     "不做比较和排名式评价；不「一棒子打死」"
    ],
    "sources": [
     "c36",
     "c37",
     "c24",
     "c59",
     "c60",
     "c15",
     "c1",
     "c6"
    ]
   },
   {
    "id": "close",
    "name": "小结与结课",
    "minutes": "2-5（估计）",
    "rules": [
     "小结回应目标，学生先说收获，再留出门题",
     "按板书顺序归纳要点，点出重点和易错点",
     "留一道出门题检查本课核心，错点记下作下次导入",
     "可留一个延伸问题或下一课的悬念",
     "结课留一句习惯或感受，不只是结论（c53）"
    ],
    "sources": [
     "c1",
     "c2",
     "c70",
     "c35",
     "c26",
     "c53",
     "c62"
    ]
   }
  ]
 },
 "bands": [
  {
   "id": "primary_low",
   "name": "小学低年级",
   "grades": [
    1,
    2
   ],
   "plan": [
    "一课一得：一节课只教一个新点，每节一个新元素",
    "用儿歌、游戏、实物或图画导入，一分钟内进入活动",
    "每2-3分钟一次互动：说、指、画、动手",
    "1道例题、3-5道口头或看图小练习；不留书面家庭作业"
   ],
   "section": [
    "称呼小朋友或名字，句子短，一句一事，语气温暖",
    "先图或实物再符号；字不离词，词不离句",
    "表扬立即、具体；纠错说「再看看这里」",
    "老师先示范，孩子跟着做，节奏快、动作多"
   ],
   "stage_notes": {
    "hook": "用儿歌、游戏、实物或故事导入",
    "check": "抢答、齐答，一问一答",
    "practice": "口头、看图、动手，不留书面作业",
    "feedback": "表扬可公开、频繁"
   },
   "masters_note": "借鉴斯霞、李吉林、于永正、刘善娜的低年级做法",
   "sources": [
    "c16",
    "c113",
    "c114",
    "c52",
    "c14",
    "c67",
    "c36",
    "c100",
    "c18",
    "c116"
   ]
  },
  {
   "id": "primary_mid",
   "name": "小学中年级",
   "grades": [
    3,
    4
   ],
   "plan": [
    "一课一得；每个抽象说法配一个具体例子和图",
    "用复习、问题或生活情境导入，3-5分钟（估计）",
    "每1-2分钟一次互动；1-2道例题、3-5道短练习",
    "开始教学法：怎么检查自己的答案；加简单变式"
   ],
   "section": [
    "称呼同学们或名字，句子约15字，先例后理",
    "先具体再抽象，板书配图，新词配例子",
    "表扬具体到做法；纠错先肯定再指出，让学生自己改",
    "每节一个动手或说思路的活动"
   ],
   "stage_notes": {
    "hook": "情境里藏一个能感受到的冲突，让学生先试",
    "close": "学生先说本节学到什么，再对照板书"
   },
   "masters_note": "借鉴华应龙、张兴华、窦桂梅、薛法根的做法",
   "sources": [
    "c17",
    "c18",
    "c63",
    "c60",
    "c115",
    "c16",
    "c13"
   ]
  },
  {
   "id": "primary_high",
   "name": "小学高年级",
   "grades": [
    5,
    6
   ],
   "plan": [
    "一课一得；具体例子后可给符号化的规则和小结",
    "用问题、情境或复习导入，学生先独立尝试再讲",
    "1-2道例题、3-5道练习，含一道变式和一道迁移题",
    "练习分基础、提高两层；每天书面作业不超60分钟"
   ],
   "section": [
    "称呼同学们或名字，句子15-18字，术语配例子",
    "先让学生试，再讲没做出来的地方；追问为什么",
    "表扬具体；纠错先肯定再说错误类型，让学生自查",
    "每节一个大问题、一个学生活动，避免连串小问题"
   ],
   "stage_notes": {
    "hook": "情境或大问题导入，让学生先提出自己的问题",
    "check": "追问为什么，开始让学生自检"
   },
   "masters_note": "借鉴华应龙、黄爱华、俞正强、窦桂梅、王崧舟的做法",
   "sources": [
    "c17",
    "c13",
    "c66",
    "c60",
    "c16",
    "c7",
    "c19"
   ]
  },
  {
   "id": "junior",
   "name": "初中",
   "grades": [
    7,
    9
   ],
   "plan": [
    "一节课2-4个板块，每板块一个主问题、一个活动",
    "问题或情境导入3-5分钟（估计），从感性到理性",
    "先学后教：学生先做2-3分钟，再讲没做出的地方",
    "2-3道例题、3-4道练习，当堂检测；每天作业不超90分钟"
   ],
   "section": [
    "称呼同学们或名字，句子约20字，商量的语气",
    "从例子推出规则，让学生说出并论证，点明易错点",
    "纠错先肯定，再说错误类型（概念、计算、审题）",
    "表扬简短具体、针对方法不夸能力；反馈平和"
   ],
   "stage_notes": {
    "hook": "用问题或认知冲突导入，不从定义开始",
    "check": "让学生用自己的话教回一步再进下一节",
    "close": "学生自结，再写一道自测题"
   },
   "masters_note": "借鉴魏书生、钱梦龙、余映潮、李庾南、洋思中学的做法",
   "sources": [
    "c11",
    "c69",
    "c70",
    "c74",
    "c75",
    "c16",
    "c36",
    "c111",
    "c18",
    "c12"
   ]
  },
  {
   "id": "senior",
   "name": "高中",
   "grades": [
    10,
    12
   ],
   "plan": [
    "专题式：定义→定理或规则→论证→应用，一课一主线",
    "从问题或猜想导入，让学生先提出问题再解决",
    "2-3道例题带变式、2-3道练习；一题多解再归一",
    "留研究性延伸问题而不是更多题；作业分层弹性"
   ],
   "section": [
    "称呼同学们或名字，句子20-25字，理性平等，可幽默",
    "让学生选方法并辩护，多问分析、综合、评价的问题",
    "反馈简洁准确，指向严谨；表扬针对策略不针对人",
    "给较长的独立思考时间，等待后再点拨，不代说结论"
   ],
   "stage_notes": {
    "hook": "用谜题、悖论或真实问题导入，事后说出思维方法",
    "explain": "板书上把结论一般化成规律或公式",
    "close": "留一个可记录的研究性问题"
   },
   "masters_note": "借鉴于漪、孙维刚、章建跃、任勇、李惠军的做法",
   "sources": [
    "c111",
    "c18",
    "c78",
    "c82",
    "c83",
    "c84",
    "c94",
    "c46",
    "c36",
    "c40"
   ]
  }
 ],
 "moves": [
  {
   "id": "situation_conflict",
   "name": "情境冲突导入",
   "stages": [
    "hook"
   ],
   "what": "用生活情境藏一个矛盾，让学生先判断再试",
   "example": "8寸加4寸等于12寸，对吗？",
   "subjects": [
    "*"
   ],
   "origin": "张兴华 认知冲突；华应龙 课例",
   "rank": 1,
   "sources": [
    "c63",
    "c60",
    "c4"
   ]
  },
  {
   "id": "review_hook",
   "name": "温故导入",
   "stages": [
    "hook"
   ],
   "what": "先做2-3道旧知小题，点名新知要用到的旧知",
   "example": "上节课的方法还记得吗？",
   "subjects": [
    "*"
   ],
   "origin": "Rosenshine 2012；邱学华 以旧引新",
   "rank": 1,
   "sources": [
    "c21",
    "c9",
    "c4"
   ]
  },
  {
   "id": "game_song_hook",
   "name": "儿歌游戏导入",
   "stages": [
    "hook"
   ],
   "what": "用儿歌、口诀、拍手游戏、图画或实物引出课题",
   "example": "我们先来拍手数数：二、四、六……",
   "grades": [
    1,
    3
   ],
   "subjects": [
    "*"
   ],
   "origin": "幼小衔接·游戏化；李吉林 实物演示",
   "rank": 1,
   "sources": [
    "c113",
    "c114",
    "c116",
    "c14"
   ]
  },
  {
   "id": "experiment_hook",
   "name": "实验现象导入",
   "stages": [
    "hook"
   ],
   "what": "先演示一个现象，再问为什么",
   "example": "兔子的眼睛怎么变成月牙形了？",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "物理",
    "化学",
    "生物学",
    "科学"
   ],
   "origin": "顾雨薇 画兔点睛；十种导入法",
   "rank": 1,
   "sources": [
    "c85",
    "c4"
   ]
  },
  {
   "id": "question_hook",
   "name": "问题悬念导入",
   "stages": [
    "hook"
   ],
   "what": "提一个学生答不出但想知道的问题",
   "example": "为什么月亮总跟着我们走？",
   "subjects": [
    "*"
   ],
   "origin": "微格教学·导入技能（悬念导入）",
   "rank": 2,
   "sources": [
    "c4",
    "c1"
   ]
  },
  {
   "id": "story_hook",
   "name": "故事导入",
   "stages": [
    "hook"
   ],
   "what": "讲一个与内容有关的短故事或典故引出课题",
   "grades": [
    1,
    9
   ],
   "subjects": [
    "*"
   ],
   "origin": "微格教学·故事导入；Willingham 故事结构",
   "rank": 2,
   "sources": [
    "c4",
    "c1",
    "c38"
   ]
  },
  {
   "id": "big_question_hook",
   "name": "大问题导入",
   "stages": [
    "hook"
   ],
   "what": "让学生说对课题有什么问题，归成两个大问题",
   "example": "关于倒数，你有什么问题？",
   "grades": [
    4,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "黄爱华 大问题教学",
   "rank": 2,
   "sources": [
    "c66"
   ]
  },
  {
   "id": "puzzle_hook",
   "name": "谜题导入",
   "stages": [
    "hook"
   ],
   "what": "用一个小谜题或悖论开场，试一两次失败后再讲",
   "example": "不动绳子这端，怎么取出杯子？",
   "grades": [
    7,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "任勇 玩中育智",
   "rank": 2,
   "sources": [
    "c83"
   ]
  },
  {
   "id": "direct_hook",
   "name": "直接导入",
   "stages": [
    "hook"
   ],
   "what": "直接说明课题、目标和本课安排，不绕弯",
   "grades": [
    5,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "十种导入法·直接导入；邱学华 及早出示课题",
   "rank": 3,
   "sources": [
    "c4",
    "c7"
   ]
  },
  {
   "id": "state_goal",
   "name": "板书目标",
   "stages": [
    "goal"
   ],
   "what": "写下课题和1-3条能检测的目标，先写好结尾的练习再备讲解",
   "example": "学完你就能自己求斜边。",
   "subjects": [
    "*"
   ],
   "origin": "洋思 揭示目标；UbD 逆向设计",
   "rank": 1,
   "sources": [
    "c10",
    "c7",
    "c31",
    "c112"
   ]
  },
  {
   "id": "small_steps",
   "name": "限量小步",
   "stages": [
    "explain"
   ],
   "what": "新内容一次只给一点，一段讲解不超5分钟（估计）就练一题",
   "subjects": [
    "*"
   ],
   "origin": "Rosenshine 2012；顾泠沅 序进",
   "rank": 1,
   "sources": [
    "c21",
    "c12"
   ]
  },
  {
   "id": "model_example",
   "name": "例题边做边说",
   "stages": [
    "explain"
   ],
   "what": "示范例题时说出每一步的理由和依据的道理",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "Rosenshine 2012；认知负荷理论",
   "rank": 1,
   "sources": [
    "c21",
    "c40",
    "c76"
   ]
  },
  {
   "id": "concrete_abstract",
   "name": "具体到抽象",
   "stages": [
    "explain"
   ],
   "what": "先实物或图，再示意图，最后给符号和术语",
   "grades": [
    1,
    4
   ],
   "subjects": [
    "*"
   ],
   "origin": "直观性原则；NCETM 表征与结构",
   "rank": 1,
   "sources": [
    "c1",
    "c93",
    "c38",
    "c92"
   ]
  },
  {
   "id": "try_then_teach",
   "name": "先试后教",
   "stages": [
    "explain"
   ],
   "what": "先给一道尝试题做2-3分钟，再只讲做错的地方",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "邱学华 尝试教学；洋思 先学后教",
   "rank": 1,
   "sources": [
    "c8",
    "c9",
    "c11",
    "c75"
   ]
  },
  {
   "id": "examples_nonexamples",
   "name": "正例反例",
   "stages": [
    "explain"
   ],
   "what": "给两个正例一个反例，说清哪个特征不算数",
   "example": "这个不是，因为少了……",
   "subjects": [
    "*"
   ],
   "origin": "Engelmann 直接教学；顾泠沅 易错点",
   "rank": 2,
   "sources": [
    "c102",
    "c100",
    "c12"
   ]
  },
  {
   "id": "dual_coding",
   "name": "图讲结合",
   "stages": [
    "explain"
   ],
   "what": "讲图时指着图说，板书只写关键词，不读整句",
   "subjects": [
    "*"
   ],
   "origin": "Mayer 多媒体原则；直观与讲解结合",
   "rank": 2,
   "sources": [
    "c41",
    "c40",
    "c1"
   ]
  },
  {
   "id": "stem_sentence",
   "name": "句式复述",
   "stages": [
    "explain"
   ],
   "what": "给一个固定句式，换三个情境让学生套着说",
   "example": "整体是……，部分是……",
   "grades": [
    1,
    6
   ],
   "subjects": [
    "*"
   ],
   "origin": "上海数学 句式（NCETM 交流报告）",
   "rank": 2,
   "sources": [
    "c92"
   ]
  },
  {
   "id": "structure_map",
   "name": "知识结构图",
   "stages": [
    "explain",
    "close"
   ],
   "what": "在板书上画一张图，把新知和旧知连起来",
   "grades": [
    5,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "孙维刚 结构教学；魏书生 知识树",
   "rank": 2,
   "sources": [
    "c78",
    "c70"
   ]
  },
  {
   "id": "analogy_transfer",
   "name": "类比迁移",
   "stages": [
    "explain"
   ],
   "what": "从旧知类比引出新知，并点明类比失效的地方",
   "example": "分数分母不为零，分式呢？",
   "grades": [
    7,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "顾泠沅 类比迁移",
   "rank": 2,
   "sources": [
    "c12"
   ]
  },
  {
   "id": "situation_teaching",
   "name": "情境体验",
   "stages": [
    "explain"
   ],
   "what": "用表演、音乐、图画或生活场景让孩子进入课文",
   "grades": [
    1,
    6
   ],
   "subjects": [
    "语文",
    "英语"
   ],
   "origin": "李吉林 情境教学；王咏梅 情景剧",
   "rank": 1,
   "sources": [
    "c14",
    "c68"
   ]
  },
  {
   "id": "read_aloud_model",
   "name": "范读跟读",
   "stages": [
    "explain",
    "practice"
   ],
   "what": "老师先有感情地范读一句，学生跟读再表演",
   "example": "听老师读，再你来读。",
   "grades": [
    1,
    6
   ],
   "subjects": [
    "语文",
    "英语"
   ],
   "origin": "于永正 范读、以情带声",
   "rank": 1,
   "sources": [
    "c53",
    "c54"
   ]
  },
  {
   "id": "char_in_sentence",
   "name": "字不离句",
   "stages": [
    "explain"
   ],
   "what": "生字放在词里、词放在课文句子里教，不列生字表",
   "grades": [
    1,
    3
   ],
   "subjects": [
    "语文"
   ],
   "origin": "斯霞 随课文分散识字",
   "rank": 2,
   "sources": [
    "c52"
   ]
  },
  {
   "id": "guess_prove",
   "name": "猜想再证明",
   "stages": [
    "explain"
   ],
   "what": "让学生先猜结论，再一起证明或验证",
   "example": "先猜猜内角和是多少？",
   "grades": [
    7,
    12
   ],
   "subjects": [
    "数学",
    "物理"
   ],
   "origin": "孙维刚；章建跃 提出问题",
   "rank": 2,
   "sources": [
    "c78",
    "c82"
   ]
  },
  {
   "id": "person_plot",
   "name": "人物情节",
   "stages": [
    "explain"
   ],
   "what": "每段讲一个人、一件事、一个动机，配一手材料",
   "grades": [
    7,
    12
   ],
   "subjects": [
    "历史",
    "道德与法治/思想政治"
   ],
   "origin": "李惠军 谨防泛方法论",
   "rank": 1,
   "sources": [
    "c84"
   ]
  },
  {
   "id": "student_experiment",
   "name": "学生动手",
   "stages": [
    "explain",
    "practice"
   ],
   "what": "让学生自己做实验或观察，不是老师做学生看",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "物理",
    "化学",
    "生物学",
    "科学"
   ],
   "origin": "楚得群；竹山中学 实验导入",
   "rank": 2,
   "sources": [
    "c88",
    "c87"
   ]
  },
  {
   "id": "wait_time",
   "name": "候答等待",
   "stages": [
    "check"
   ],
   "what": "提问后等3-5秒再说话，学生答后再停一停再评价",
   "subjects": [
    "*"
   ],
   "origin": "微格教学·提问技能；Rowe 1986",
   "rank": 1,
   "sources": [
    "c15",
    "c42",
    "c34",
    "c62"
   ]
  },
  {
   "id": "no_opt_out",
   "name": "不放过",
   "stages": [
    "check"
   ],
   "what": "答不出就给提示或拆小问题，再回到原题直到答对",
   "example": "先想想第一步该做什么？",
   "subjects": [
    "*"
   ],
   "origin": "Lemov No Opt Out；助答五法",
   "rank": 1,
   "sources": [
    "c22",
    "c15"
   ]
  },
  {
   "id": "restate_check",
   "name": "复述检查",
   "stages": [
    "check"
   ],
   "what": "让学生用自己的话复述要点或步骤，不问懂了吗",
   "subjects": [
    "*"
   ],
   "origin": "Rosenshine 2012；洋思 兵教兵",
   "rank": 1,
   "sources": [
    "c21",
    "c11"
   ]
  },
  {
   "id": "probe_why",
   "name": "追问为什么",
   "stages": [
    "check"
   ],
   "what": "答对后追问为什么或怎么知道的，重难点处必追问",
   "example": "为什么是这个？",
   "subjects": [
    "*"
   ],
   "origin": "微格教学·追问；华应龙 装傻；Lemov Stretch It",
   "rank": 2,
   "sources": [
    "c15",
    "c62",
    "c23"
   ]
  },
  {
   "id": "name_call",
   "name": "点名回答",
   "stages": [
    "check"
   ],
   "what": "叫名字提问，不问「谁会」，每节至少叫一次",
   "example": "小明，你来说。",
   "subjects": [
    "*"
   ],
   "origin": "Lemov Cold Call；华应龙 记名字",
   "rank": 2,
   "sources": [
    "c26",
    "c62"
   ]
  },
  {
   "id": "choral_response",
   "name": "齐答抢答",
   "stages": [
    "check"
   ],
   "what": "口令后一起答或抢答，一分钟多次，错了立即纠",
   "example": "预备——答！",
   "grades": [
    1,
    4
   ],
   "subjects": [
    "*"
   ],
   "origin": "Engelmann 直接教学；邱学华 抢答",
   "rank": 2,
   "sources": [
    "c100",
    "c7",
    "c21"
   ]
  },
  {
   "id": "everybody_writes",
   "name": "先写再说",
   "stages": [
    "check"
   ],
   "what": "先让学生写下答案，再把答案放到板书上一起看",
   "example": "先写下来，写完给我看。",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "Lemov Everybody Writes、Show Call",
   "rank": 2,
   "sources": [
    "c28",
    "c25"
   ]
  },
  {
   "id": "hinge_question",
   "name": "诊断题",
   "stages": [
    "check",
    "practice"
   ],
   "what": "出一道选择题，每个错项对应一种典型误解",
   "grades": [
    5,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "Wiliam hinge question",
   "rank": 2,
   "sources": [
    "c33",
    "c35"
   ]
  },
  {
   "id": "immediate_practice",
   "name": "当堂练当堂改",
   "stages": [
    "practice"
   ],
   "what": "学生做完立即订正，错的当堂改对再往下",
   "subjects": [
    "*"
   ],
   "origin": "邱学华 练在当堂；洋思 当堂训练",
   "rank": 1,
   "sources": [
    "c7",
    "c10"
   ]
  },
  {
   "id": "variation",
   "name": "变式练习",
   "stages": [
    "practice",
    "explain"
   ],
   "what": "改情境或数字，保留解法结构；再加一道迁移题",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "顾泠沅 变式；卢仲衡；NCETM 小变化",
   "rank": 1,
   "sources": [
    "c12",
    "c13",
    "c93",
    "c79"
   ]
  },
  {
   "id": "two_round",
   "name": "模仿后独立",
   "stages": [
    "practice"
   ],
   "what": "先一道可看例题的模仿题，再一道独立的达标题",
   "subjects": [
    "*"
   ],
   "origin": "洋思 当堂训练两次",
   "rank": 1,
   "sources": [
    "c10",
    "c11"
   ]
  },
  {
   "id": "hands_on_practice",
   "name": "动手练习",
   "stages": [
    "practice"
   ],
   "what": "用摆、画、折、连线、指读代替书面题",
   "example": "读一句，画一步。",
   "grades": [
    1,
    3
   ],
   "subjects": [
    "*"
   ],
   "origin": "刘善娜 画数学、做数学；直观性原则",
   "rank": 1,
   "sources": [
    "c67",
    "c1"
   ]
  },
  {
   "id": "retrieval_practice",
   "name": "检索练习",
   "stages": [
    "practice"
   ],
   "what": "练习里混入前几课的题，让学生回忆而不是翻看",
   "subjects": [
    "*"
   ],
   "origin": "Make It Stick；Rosenshine 周复习",
   "rank": 2,
   "sources": [
    "c39",
    "c21",
    "c27"
   ]
  },
  {
   "id": "fading",
   "name": "逐步撤支架",
   "stages": [
    "practice"
   ],
   "what": "完整例题→填空题→独立题，做对两题就少给一步提示",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "认知负荷理论 guidance fading",
   "rank": 2,
   "sources": [
    "c40",
    "c21"
   ]
  },
  {
   "id": "tiered_practice",
   "name": "分层练习",
   "stages": [
    "practice"
   ],
   "what": "基础题必做、提高题选做；强生加难，弱生减量",
   "subjects": [
    "*"
   ],
   "origin": "邱学华 分层教学；双减 分层作业",
   "rank": 2,
   "sources": [
    "c7",
    "c16"
   ]
  },
  {
   "id": "multi_solution",
   "name": "一题多解",
   "stages": [
    "practice"
   ],
   "what": "求第二种解法，再问两种方法的共同点",
   "example": "还有别的算法吗？",
   "grades": [
    5,
    12
   ],
   "subjects": [
    "数学",
    "物理"
   ],
   "origin": "孙维刚 一题多解、多解归一；吴正宪",
   "rank": 2,
   "sources": [
    "c78",
    "c47"
   ]
  },
  {
   "id": "write_practice",
   "name": "读写练习",
   "stages": [
    "practice"
   ],
   "what": "读一段、仿写一句或复述一段，当堂读出来",
   "subjects": [
    "语文",
    "英语"
   ],
   "origin": "钱梦龙 读写听说训练；于永正 多读多写",
   "rank": 2,
   "sources": [
    "c71",
    "c53"
   ]
  },
  {
   "id": "self_test_item",
   "name": "学生出题",
   "stages": [
    "practice",
    "close"
   ],
   "what": "让学生按本课目标自己出一道题并解答",
   "grades": [
    5,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "魏书生 自测；Wiliam 学生出题",
   "rank": 3,
   "sources": [
    "c70",
    "c34"
   ]
  },
  {
   "id": "affirm_then_correct",
   "name": "先肯定再纠错",
   "stages": [
    "feedback"
   ],
   "what": "先说对在哪，再说错误类型和改的一步",
   "example": "思路对，单位漏了。",
   "subjects": [
    "*"
   ],
   "origin": "疏导原则；Hattie & Timperley 2007",
   "rank": 1,
   "sources": [
    "c1",
    "c36",
    "c15"
   ]
  },
  {
   "id": "precise_praise",
   "name": "具体表扬",
   "stages": [
    "feedback"
   ],
   "what": "表扬具体到做法或努力，不夸聪明",
   "example": "你想到画图，好办法！",
   "subjects": [
    "*"
   ],
   "origin": "Lemov Precise Praise；Sutton Trust 2014",
   "rank": 1,
   "sources": [
    "c24",
    "c37",
    "c36"
   ]
  },
  {
   "id": "error_resource",
   "name": "错误资源化",
   "stages": [
    "feedback"
   ],
   "what": "把错答说出来，先找对的部分，再问改哪一步",
   "example": "错得好，我们来欣赏一下。",
   "subjects": [
    "*"
   ],
   "origin": "华应龙 化错教学",
   "rank": 1,
   "sources": [
    "c59",
    "c60"
   ]
  },
  {
   "id": "find_and_fix",
   "name": "找错自改",
   "stages": [
    "feedback"
   ],
   "what": "只说有几处错，让学生自己找出来改；弱生给位置",
   "example": "有两处错，找找看。",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "Wiliam 评语式反馈；卢仲衡 自检",
   "rank": 2,
   "sources": [
    "c34",
    "c13",
    "c5"
   ]
  },
  {
   "id": "reteach_gap",
   "name": "缺前置就重教",
   "stages": [
    "feedback"
   ],
   "what": "缺前置知识时重讲一个例题，不多写评语",
   "subjects": [
    "*"
   ],
   "origin": "Hattie & Timperley 2007",
   "rank": 2,
   "sources": [
    "c36",
    "c21"
   ]
  },
  {
   "id": "private_correction",
   "name": "私下纠正",
   "stages": [
    "feedback"
   ],
   "what": "对青春期学生表扬和纠错都简短、对事不对人",
   "grades": [
    7,
    12
   ],
   "subjects": [
    "*"
   ],
   "origin": "Hattie & Timperley（年龄差异）；Lemov",
   "rank": 2,
   "sources": [
    "c36",
    "c104"
   ]
  },
  {
   "id": "walk_error",
   "name": "错步上板",
   "stages": [
    "feedback"
   ],
   "what": "把学生的错步骤写到板书上一步步走到矛盾处",
   "grades": [
    3,
    12
   ],
   "subjects": [
    "数学",
    "物理",
    "化学"
   ],
   "origin": "上海数学 4−4+4 课例（NCETM）；顾泠沅",
   "rank": 2,
   "sources": [
    "c92",
    "c12"
   ]
  },
  {
   "id": "student_summary",
   "name": "学生自结",
   "stages": [
    "close"
   ],
   "what": "学生先说学到了什么，再对照板书补全",
   "subjects": [
    "*"
   ],
   "origin": "魏书生 自结；于永正 把根留住",
   "rank": 1,
   "sources": [
    "c70",
    "c53"
   ]
  },
  {
   "id": "back_to_goal",
   "name": "回应目标",
   "stages": [
    "close"
   ],
   "what": "逐条对照开课目标，说哪条做到了",
   "subjects": [
    "*"
   ],
   "origin": "回应式结尾；顾泠沅 目标意识",
   "rank": 1,
   "sources": [
    "c1",
    "c2",
    "c63"
   ]
  },
  {
   "id": "exit_ticket",
   "name": "出门题",
   "stages": [
    "close"
   ],
   "what": "结课前一道核心题，错点留给下次导入",
   "subjects": [
    "*"
   ],
   "origin": "Lemov Exit Ticket；Wiliam exit pass",
   "rank": 1,
   "sources": [
    "c26",
    "c35"
   ]
  },
  {
   "id": "extend_hook",
   "name": "悬念延伸",
   "stages": [
    "close"
   ],
   "what": "留一个延伸问题或下一课的悬念",
   "example": "下次去，你怎么点餐？",
   "subjects": [
    "*"
   ],
   "origin": "开放型总结；华应龙 课例",
   "rank": 2,
   "sources": [
    "c1",
    "c62"
   ]
  },
  {
   "id": "rule_repeat",
   "name": "齐读结论",
   "stages": [
    "close"
   ],
   "what": "把本节结论写成一句话放在板书上，学生读一遍",
   "grades": [
    1,
    6
   ],
   "subjects": [
    "*"
   ],
   "origin": "上海数学 规则复述；日本课例 まとめ",
   "rank": 2,
   "sources": [
    "c92",
    "c99"
   ]
  }
 ],
 "masters": [
  {
   "id": "li_jilin",
   "name": "李吉林",
   "subjects": [
    "语文"
   ],
   "grades": [
    1,
    4
   ],
   "school": "江苏省南通师范第二附属小学",
   "honours": [
    "特级教师",
    "国家级教学成果奖特等奖 2014"
   ],
   "method": "情境教学",
   "moves": [
    "用图画、音乐、表演、实物或语言描绘创设情境",
    "以美为突破口，以情为纽带，以思为核心",
    "让儿童在角色扮演和活动中学",
    "用周围世界作教材的源泉"
   ],
   "rank": 1,
   "sources": [
    "c14",
    "c43"
   ]
  },
  {
   "id": "yu_yongzheng",
   "name": "于永正",
   "subjects": [
    "语文"
   ],
   "grades": [
    1,
    6
   ],
   "school": "江苏省徐州市大马路小学",
   "honours": [
    "江苏省特级教师 1985",
    "教育部“跨世纪名师工程”首位推出的名师"
   ],
   "method": "五重教学",
   "moves": [
    "先有感情地范读，再让学生跟读、表演",
    "朗读一个字、一个词、一个标点都不放过",
    "板书配简笔画",
    "为一次勇敢的尝试鼓掌",
    "布置作文前老师先写下水文"
   ],
   "example": "把语文的根留住",
   "rank": 1,
   "sources": [
    "c53",
    "c54"
   ]
  },
  {
   "id": "si_xia",
   "name": "斯霞",
   "subjects": [
    "语文"
   ],
   "grades": [
    1,
    2
   ],
   "school": "南京师范大学附属小学",
   "honours": [
    "最美奋斗者 2019"
   ],
   "method": "随课文分散识字",
   "moves": [
    "字不离词，词不离句：生字在课文句子里教",
    "童心母爱：具体关心加严格纠错",
    "检查后排能不能看清板书"
   ],
   "rank": 2,
   "sources": [
    "c52"
   ]
  },
  {
   "id": "dou_guimei",
   "name": "窦桂梅",
   "subjects": [
    "语文"
   ],
   "grades": [
    3,
    6
   ],
   "school": "清华大学附属小学",
   "honours": [
    "特级教师",
    "国家级教学成果奖一等奖 2014"
   ],
   "method": "主题教学",
   "moves": [
    "用一个主题词串起两三篇课文",
    "老师退居后台，把说话机会还给学生",
    "用思维导图、卡片等看得见的工具",
    "六步备课：提炼主题、定目标、重组内容、活动、支架、评价"
   ],
   "rank": 1,
   "sources": [
    "c50",
    "c51",
    "c43"
   ]
  },
  {
   "id": "xue_fagen",
   "name": "薛法根",
   "subjects": [
    "语文"
   ],
   "grades": [
    3,
    6
   ],
   "school": "江苏省苏州市吴江区盛泽实验小学",
   "honours": [
    "特级教师"
   ],
   "method": "组块教学",
   "moves": [
    "一节课教一个组块：字族、词串或句群",
    "阅读从段起步，因文而异",
    "教表达先呈现结构，再用结构，再化结构"
   ],
   "rank": 2,
   "sources": [
    "c57"
   ]
  },
  {
   "id": "wang_songzhou",
   "name": "王崧舟",
   "subjects": [
    "语文"
   ],
   "grades": [
    3,
    6
   ],
   "school": "杭州市拱宸桥小学（现杭州师范大学）",
   "honours": [
    "特级教师",
    "全国劳动模范"
   ],
   "method": "诗意语文",
   "moves": [
    "从一个意象出发：造境、入情、会意",
    "多篇课文围绕一个意象比较着读",
    "读出文化意味，如《梅花魂》"
   ],
   "rank": 2,
   "sources": [
    "c55",
    "c56"
   ]
  },
  {
   "id": "sun_shuangjin",
   "name": "孙双金",
   "subjects": [
    "语文"
   ],
   "grades": [
    1,
    6
   ],
   "school": "南京市金陵中学附属小学",
   "honours": [
    "江苏省特级教师",
    "正高级教师"
   ],
   "method": "情智语文",
   "moves": [
    "看学生状态：小脸通红、小眼发光、小手直举、小嘴常开",
    "披文入情，和作者共鸣",
    "生活化情境、分层任务单"
   ],
   "rank": 3,
   "sources": [
    "c58"
   ]
  },
  {
   "id": "wei_shusheng",
   "name": "魏书生",
   "subjects": [
    "语文"
   ],
   "grades": [
    7,
    9
   ],
   "school": "辽宁省盘锦市实验中学",
   "honours": [
    "特级教师 1984",
    "全国劳动模范"
   ],
   "method": "六步课堂教学法",
   "moves": [
    "定向：先说清本课的重点",
    "自学：学生先自读，留下不懂的",
    "答疑只讲学生自己解决不了的",
    "自测：学生自己出题自测",
    "自结：下课前学生说收获"
   ],
   "rank": 1,
   "sources": [
    "c69",
    "c70",
    "c20"
   ]
  },
  {
   "id": "qian_menglong",
   "name": "钱梦龙",
   "subjects": [
    "语文"
   ],
   "grades": [
    7,
    12
   ],
   "school": "上海市嘉定二中",
   "honours": [
    "上海市首批特级教师"
   ],
   "method": "三主导读法",
   "moves": [
    "让学生先读课文写下问题，从问题建课",
    "老师点拨三言两语，不串讲",
    "读书在文章里走几个来回：语言→内容→为什么这样写",
    "由扶到放"
   ],
   "rank": 2,
   "sources": [
    "c71",
    "c72",
    "c73"
   ]
  },
  {
   "id": "yu_yingchao",
   "name": "余映潮",
   "subjects": [
    "语文"
   ],
   "grades": [
    7,
    9
   ],
   "school": "湖北省荆州市教科院",
   "honours": [
    "特级教师"
   ],
   "method": "板块式思路",
   "moves": [
    "一课分2-4个板块，每块一个主问题",
    "提问精粹实在，学生活动充分",
    "品读细腻深入，课堂积累丰富"
   ],
   "rank": 2,
   "sources": [
    "c74"
   ]
  },
  {
   "id": "yu_yi",
   "name": "于漪",
   "subjects": [
    "语文"
   ],
   "grades": [
    10,
    12
   ],
   "school": "上海市杨浦高级中学",
   "honours": [
    "首批特级教师 1978",
    "全国教书育人楷模 2010",
    "人民教育家 2019"
   ],
   "method": "教文育人",
   "moves": [
    "每句讲解先写出来、删改、背熟再口语化",
    "不抄教学参考书，自己读透课文",
    "用学生熟悉的歌曲、时事作教材",
    "认真倾听学生，师生平等对话"
   ],
   "example": "时代的活水要在课堂上流淌",
   "rank": 1,
   "sources": [
    "c45",
    "c46"
   ]
  },
  {
   "id": "cheng_xiang",
   "name": "程翔",
   "subjects": [
    "语文"
   ],
   "grades": [
    10,
    12
   ],
   "school": "北京一〇一中学（曾任北大附中副校长）",
   "honours": [
    "特级教师",
    "国家“万人计划”教学名师"
   ],
   "method": "用教材教",
   "moves": [
    "课文是例子：由此及彼、举一反三",
    "教读课和自读课分轻重",
    "不把课文掰碎讲透、面面俱到"
   ],
   "rank": 2,
   "sources": [
    "c81"
   ]
  },
  {
   "id": "hua_yinglong",
   "name": "华应龙",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    6
   ],
   "school": "北京第二实验小学",
   "honours": [
    "特级教师",
    "正高级教师",
    "首都基础教育名家",
    "明远教育奖"
   ],
   "method": "化错教学",
   "moves": [
    "用生活情境藏一个错误开场，让学生判断",
    "把错答当资源：容错、融错、荣错",
    "刻意等待，多数学生举手了再叫答",
    "不停问为什么，老师学会装傻",
    "叫名字，为勇敢的错答鼓掌"
   ],
   "example": "错得好！我们来欣赏一下。",
   "rank": 1,
   "sources": [
    "c59",
    "c60",
    "c61",
    "c62"
   ]
  },
  {
   "id": "yu_zhengqiang",
   "name": "俞正强",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    6
   ],
   "school": "浙江省金华师范学校附属小学",
   "honours": [
    "浙江省特级教师 2002",
    "国家级教学成果奖一等奖",
    "全国教书育人楷模 2024"
   ],
   "method": "种子课",
   "moves": [
    "把课上对：种子课慢慢教透",
    "用比分、汇率、米水比等生活中的比引入",
    "上课要有乐趣，学生才主动学",
    "不设名额的达标式表扬"
   ],
   "rank": 1,
   "sources": [
    "c48",
    "c64",
    "c65"
   ]
  },
  {
   "id": "liu_shanna",
   "name": "刘善娜",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    2
   ],
   "school": "",
   "honours": [
    "特级教师"
   ],
   "method": "画数学",
   "moves": [
    "应用题读一句画一步，读完题图也画完",
    "一二年级多动手操作，不刷题",
    "用积木、香蕉、折纸做几何"
   ],
   "rank": 1,
   "sources": [
    "c67"
   ]
  },
  {
   "id": "zhang_xinghua",
   "name": "张兴华",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    6
   ],
   "school": "江苏省海门实验小学",
   "honours": [
    "江苏省特级教师 1984",
    "全国优秀教师"
   ],
   "method": "认知冲突",
   "moves": [
    "让旧工具不够用：用平方厘米量课桌",
    "舍得让儿童在思考中浪费时间",
    "把新知之舟停在旧知锚桩上，为迁移而教"
   ],
   "rank": 2,
   "sources": [
    "c63"
   ]
  },
  {
   "id": "wu_zhengxian",
   "name": "吴正宪",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    6
   ],
   "school": "北京教育科学研究院",
   "honours": [
    "特级教师",
    "国务院政府特殊津贴",
    "全国教书育人楷模候选人 2010"
   ],
   "method": "儿童数学教育",
   "moves": [
    "一题多解的题老师先自己做一遍",
    "传授知识、启迪智慧、完善人格三者结合",
    "编小题库、难题辨析、趣味数学"
   ],
   "rank": 2,
   "sources": [
    "c47"
   ]
  },
  {
   "id": "huang_aihua",
   "name": "黄爱华",
   "subjects": [
    "数学"
   ],
   "grades": [
    3,
    6
   ],
   "school": "广东省（深圳）",
   "honours": [
    "特级教师"
   ],
   "method": "大问题教学",
   "moves": [
    "先问学生对课题有什么问题",
    "归成两个大问题：是什么、怎么求",
    "先提问题后解决，一课两段"
   ],
   "rank": 2,
   "sources": [
    "c66"
   ]
  },
  {
   "id": "qiu_xuehua",
   "name": "邱学华",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    9
   ],
   "school": "",
   "honours": [
    "尝试教学法创始人（1980 年起实验，1982 年发表）"
   ],
   "method": "尝试教学法",
   "moves": [
    "先出尝试题，学生自学课本后先试做",
    "学生讨论后老师只针对尝试中的问题讲",
    "第二次尝试练习当堂订正",
    "教师讲话不超过10分钟，留30分钟给学生"
   ],
   "example": "请不要告诉我，让我先试一试",
   "rank": 3,
   "sources": [
    "c8",
    "c9",
    "c7"
   ]
  },
  {
   "id": "li_yunan",
   "name": "李庾南",
   "subjects": [
    "数学"
   ],
   "grades": [
    7,
    9
   ],
   "school": "江苏省南通市启秀中学",
   "honours": [
    "特级教师",
    "国家“万人计划”教学名师",
    "全国教书育人楷模",
    "国家级教学成果奖一等奖 2014、2022",
    "苏步青数学教育奖"
   ],
   "method": "自学·议论·引导",
   "moves": [
    "独立自学→群体议论→相机引导",
    "点拨为什么，不告诉是什么",
    "每句教学语言推敲到准确、清晰、简洁",
    "例题分析力求透彻到位",
    "允许学生犯错，帮助学生纠错"
   ],
   "rank": 1,
   "sources": [
    "c75",
    "c76",
    "c77",
    "c49"
   ]
  },
  {
   "id": "sun_weigang",
   "name": "孙维刚",
   "subjects": [
    "数学"
   ],
   "grades": [
    7,
    12
   ],
   "school": "北京市第二十二中学",
   "honours": [
    "三轮初一带到高三的实验班：第三轮 22 人考入北大清华（中国教育报 2015）"
   ],
   "method": "结构教学法",
   "moves": [
    "一题多解→多解归一→多题归一",
    "让学生先猜想定理再证明",
    "画知识结构图，八方联系",
    "题不在多但求精彩：每题先解十道选最好的"
   ],
   "example": "题海战术是覆舟之术",
   "rank": 1,
   "sources": [
    "c78"
   ]
  },
  {
   "id": "gu_lingyuan",
   "name": "顾泠沅（青浦实验）",
   "subjects": [
    "数学"
   ],
   "grades": [
    7,
    9
   ],
   "school": "上海市青浦区（教研员）",
   "honours": [
    "青浦实验 1992 年被国家教委定为基础教育改革重大成果向全国推广"
   ],
   "method": "尝试指导·效果回授",
   "moves": [
    "从学生原有知识出发，用观察、类比、归纳形成概念",
    "变式训练，避免大运动量重复",
    "从旧知引发冲突：两种方法答案为什么不一样",
    "根据学生反应随时调节节奏"
   ],
   "rank": 2,
   "sources": [
    "c12",
    "c79",
    "c80"
   ]
  },
  {
   "id": "zhang_jianyue",
   "name": "章建跃",
   "subjects": [
    "数学"
   ],
   "grades": [
    10,
    12
   ],
   "school": "人民教育出版社",
   "honours": [
    "人民教育出版社编审、人教A版高中数学教材主编"
   ],
   "method": "用数学的方式育人",
   "moves": [
    "让学生自己发现数学对象、提出问题",
    "推理是命根子，运算是童子功",
    "先讲道理再练，不先教技巧",
    "路径：抽象对象→研究路径→发现问题→探索→结论→建模"
   ],
   "rank": 2,
   "sources": [
    "c82"
   ]
  },
  {
   "id": "ren_yong",
   "name": "任勇",
   "subjects": [
    "数学"
   ],
   "grades": [
    7,
    12
   ],
   "school": "福建省厦门一中（原校长）",
   "honours": [
    "特级教师"
   ],
   "method": "玩中育智",
   "moves": [
    "用绳子穿杯、扑克周期等谜题开场，试过失败后再讲",
    "事后说出思维方法，如逆向思维",
    "一题多解与变式探究"
   ],
   "rank": 3,
   "sources": [
    "c83"
   ]
  },
  {
   "id": "wang_yongmei",
   "name": "王咏梅",
   "subjects": [
    "英语"
   ],
   "grades": [
    1,
    6
   ],
   "school": "江苏省盐城市第一小学",
   "honours": [
    "正高级教师",
    "江苏省特级教师"
   ],
   "method": "情境·内容·阅读圈",
   "moves": [
    "用道具、服装把课文变成情景剧",
    "形式之后回到文本和语言内容",
    "阅读圈六个角色，老师退到一旁观察"
   ],
   "rank": 1,
   "sources": [
    "c68"
   ]
  },
  {
   "id": "gu_yuwei",
   "name": "顾雨薇",
   "subjects": [
    "物理"
   ],
   "grades": [
    7,
    9
   ],
   "school": "上海市奉贤区崇实中学",
   "honours": [
    "课例载于国家级教学成果奖报道（解放网 2024）"
   ],
   "method": "认知冲突情境",
   "moves": [
    "一个道具两种现象：兔影与月牙形的眼睛",
    "用水透镜当晶状体讲凸透镜成像",
    "课后带学生到社区做科普"
   ],
   "rank": 1,
   "sources": [
    "c85"
   ]
  },
  {
   "id": "li_huijun",
   "name": "李惠军",
   "subjects": [
    "历史"
   ],
   "grades": [
    10,
    12
   ],
   "school": "上海市晋元高级中学",
   "honours": [
    "中学历史特级教师 1994"
   ],
   "method": "问题驱动的历史课",
   "moves": [
    "每课保留人物、情节和心态",
    "围绕一个人物设计层层递进的问题",
    "要求一手材料印证，不套用泛方法论"
   ],
   "example": "没有好的问题就没有探索的活水源泉",
   "rank": 1,
   "sources": [
    "c84"
   ]
  },
  {
   "id": "yuan_xiaomei",
   "name": "袁小梅",
   "subjects": [
    "道德与法治/思想政治"
   ],
   "grades": [
    7,
    9
   ],
   "school": "重庆市长寿区（初中政治教研员）",
   "honours": [
    "特级教师"
   ],
   "method": "主题学习·行为体验",
   "moves": [
    "单元四步：回顾知识—集思广益—问题解决—能力提升",
    "行为体验：读《背影》后写自己的父母再分享",
    "主题概念辨析"
   ],
   "rank": 1,
   "sources": [
    "c86"
   ]
  },
  {
   "id": "yangsi",
   "name": "洋思中学",
   "subjects": [
    "*"
   ],
   "grades": [
    7,
    9
   ],
   "school": "江苏省泰兴市洋思中学",
   "honours": [
    "国家级教学成果奖一等奖 2014"
   ],
   "method": "先学后教、当堂训练",
   "moves": [
    "揭示目标后学生先自学",
    "只讲学生自学后不会的",
    "最后15分钟当堂作业，堂堂清",
    "兵教兵：会的教不会的"
   ],
   "rank": 2,
   "sources": [
    "c11",
    "c10",
    "c43"
   ]
  },
  {
   "id": "shanghai_mastery",
   "name": "上海数学掌握教学",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    9
   ],
   "school": "上海市教委教研室（NCETM 中英交流记录）",
   "honours": [
    "国家级教学成果奖特等奖 2018（上海市教委教研室《走向世界的中国数学教育》）"
   ],
   "method": "小步变式·句式",
   "moves": [
    "每个问题和追问都提前设计",
    "具体和抽象同时呈现在板书上",
    "一个句式换三个情境让学生说",
    "每步小变化，规则学生复述",
    "做得快的给深一层题，当天补差"
   ],
   "rank": 2,
   "sources": [
    "c92",
    "c94",
    "c95",
    "c44"
   ]
  },
  {
   "id": "japan_lesson_study",
   "name": "日本课例研究",
   "subjects": [
    "数学"
   ],
   "grades": [
    1,
    9
   ],
   "school": "日本小学数学问题解决课（课例研究）",
   "honours": [
    "TIMSS 1995 录像研究：日本八年级 53% 的课含证明（引用）"
   ],
   "method": "一题一课·练り上げ",
   "moves": [
    "一节课一道题一个目标，老师不先示范",
    "学生先独立做，老师记下各人方法",
    "多种解法从最常见到最不同依次比较",
    "板书从左到右不擦，全课过程留在黑板上",
    "老师最后总结（まとめ）"
   ],
   "rank": 3,
   "sources": [
    "c97",
    "c98",
    "c99",
    "c96"
   ]
  },
  {
   "id": "engelmann_di",
   "name": "Engelmann 直接教学",
   "subjects": [
    "*"
   ],
   "grades": [
    1,
    3
   ],
   "school": "美国 Direct Instruction（Project Follow Through）",
   "honours": [
    "Project Follow Through 阅读、数学、拼写、语言四项第一（引用）"
   ],
   "method": "正例反例·齐答",
   "moves": [
    "正例反例并列，只剩一种解释",
    "口令齐答，每分钟10-14次（引用）",
    "错了立即纠正",
    "九成复习、一成新内容"
   ],
   "rank": 2,
   "sources": [
    "c100",
    "c101",
    "c102",
    "c103"
   ]
  },
  {
   "id": "atwell",
   "name": "Nancie Atwell",
   "subjects": [
    "语文",
    "英语"
   ],
   "grades": [
    5,
    9
   ],
   "school": "Center for Teaching and Learning, Maine",
   "honours": [
    "Global Teacher Prize 2015"
   ],
   "method": "读写工作坊",
   "moves": [
    "学生自选书，一年约40本（引用）",
    "短小的专题课加一对一写作面谈",
    "大量写作"
   ],
   "rank": 3,
   "sources": [
    "c89",
    "c91"
   ]
  },
  {
   "id": "zafirakou",
   "name": "Andria Zafirakou",
   "subjects": [
    "*"
   ],
   "grades": [
    7,
    9
   ],
   "school": "Alperton Community School, London",
   "honours": [
    "Global Teacher Prize 2018"
   ],
   "method": "先建立关系",
   "moves": [
    "用学生的母语打招呼建立信任",
    "先建立关系再教内容",
    "从学生自己文化的作品入门"
   ],
   "rank": 3,
   "sources": [
    "c90",
    "c91"
   ]
  }
 ],
 "board": {
  "rules": [
   "提纲式关键词，不写整句",
   "3-6条要点，与讲稿对应，边讲边写",
   "用箭头、对比或表格显示知识关系",
   "重点、公式和关键术语必须上板书并突出",
   "主板书不擦，副板书随用随清",
   "每条不超过12字（估计）；总量适中，不是教案缩写",
   "顺序与讲解顺序一致，先讲后写，不边写边擦",
   "图要有标注；讲图时指图说，不读板书整句",
   "板书是学生看的提纲，结课按板书回顾",
   "无错别字，术语规范，公式写法标准",
   "四边留白，不写到边缘",
   "开课先写课题；学生的错答可先上板书再改正",
   "板书类型按内容选：提纲、对比、图示、表格、设问"
  ],
  "sources": [
   "c110",
   "c105",
   "c109",
   "c1",
   "c3",
   "c5",
   "c99",
   "c41",
   "c60",
   "c92"
  ]
 },
 "checklist": [
  {
   "id": "goal_focus",
   "item": "讲解围绕本课目标和本节标题，没有跑题",
   "weight": "教学过程与方法策略 25/80（岳阳 2025）",
   "sources": [
    "c106",
    "c12"
   ]
  },
  {
   "id": "accuracy",
   "item": "知识、术语和结论准确，没有科学性错误",
   "weight": "教学内容表述准确 10/35（教师资格面试）",
   "sources": [
    "c109",
    "c108"
   ]
  },
  {
   "id": "point_reason_example",
   "item": "每条要点有解释原因和一个例子或小例题",
   "weight": "讲授精当、富有启发性 20/70（华容 2019）",
   "sources": [
    "c105",
    "c21"
   ]
  },
  {
   "id": "small_steps",
   "item": "一次讲一个要点，讲完一条再讲下一条，由浅入深",
   "sources": [
    "c21",
    "c1"
   ]
  },
  {
   "id": "concrete_first",
   "item": "抽象说法前有具体例子、图或情境",
   "sources": [
    "c1",
    "c38",
    "c92"
   ]
  },
  {
   "id": "question",
   "item": "有启发性提问，并给出答案或引导，不连着问",
   "weight": "提出的问题富有启发性 4/35（教师资格面试）",
   "sources": [
    "c109",
    "c15"
   ]
  },
  {
   "id": "key_difficulty",
   "item": "重点难点处有例题、变式或常见错误提醒",
   "weight": "突出重点、突破难点 20/70（华容 2019）",
   "sources": [
    "c105",
    "c12"
   ]
  },
  {
   "id": "board_outline",
   "item": "板书是提纲式关键词，3-6条，与讲稿一一对应",
   "weight": "板书设计突出主题、层次分明 8/35（教师资格面试）",
   "sources": [
    "c109",
    "c110"
   ]
  },
  {
   "id": "board_key",
   "item": "重点、公式或关键术语出现在板书上",
   "sources": [
    "c110",
    "c105"
   ]
  },
  {
   "id": "grade_language",
   "item": "语言符合年级：称呼、句长、用词，新词有例子解释",
   "weight": "学情分析 15/80（岳阳 2025）",
   "sources": [
    "c106",
    "c2"
   ]
  },
  {
   "id": "praise_correct",
   "item": "表扬具体到做法；指出错误先肯定再说错误类型",
   "weight": "评价与激励简单有效（电教馆 2016）",
   "sources": [
    "c107",
    "c36",
    "c24"
   ],
   "scope": "feedback"
  },
  {
   "id": "student_action",
   "item": "学生在本节有事可做：回答、复述、试做或练习",
   "weight": "学生主体、自主合作探究 20/70（华容 2019）",
   "sources": [
    "c105",
    "c108"
   ]
  },
  {
   "id": "exercise_match",
   "item": "练习紧扣本节要点，是例题的变式而不是重复",
   "sources": [
    "c12",
    "c21",
    "c13"
   ]
  },
  {
   "id": "summary_goal",
   "item": "小结回到本节要点或本课目标，不引入新内容",
   "sources": [
    "c1",
    "c112"
   ]
  },
  {
   "id": "no_filler",
   "item": "没有无关闲话、重复的开场白或空泛口号",
   "sources": [
    "c41",
    "c5"
   ]
  },
  {
   "id": "link_prior",
   "item": "新知从学生已有知识或前一节内容引出",
   "sources": [
    "c12",
    "c63"
   ]
  },
  {
   "id": "low_grade_play",
   "item": "一二年级有儿歌、游戏、实物或图画的元素",
   "grades": [
    1,
    2
   ],
   "sources": [
    "c113",
    "c114"
   ]
  },
  {
   "id": "secondary_reason",
   "item": "初高中让学生说出理由或规则并论证",
   "grades": [
    7,
    12
   ],
   "sources": [
    "c18",
    "c94"
   ]
  }
 ]
}