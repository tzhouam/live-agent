"""Exercises the teacher gives: shown on the board, answered by voice or text, graded, fed back into the profile.

An exercise is either multiple choice (graded by rule: the letter, or the option's text) or a short answer
(exact match by rule, else graded by the LLM against the reference answer). A pending exercise pauses the
lesson: the next lesson line waits until the student answers (or says they do not know).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from live_agent.lesson import Board, LessonLine, render_item, spoken
from live_agent.llm import ChatLLM, parse_json

LETTERS = "ABCD"
SKIP = re.compile(r"^(我)?(不会|不知道|跳过|不懂|想不出来?|没思路|算了)(做|写)?(吧|啊|呢)?[。.!！]?$")
# not a plain answer: a negation, a question or a hedge goes to the LLM ("我不选B", "B是什么意思？", "不会是B吧")
NOT_PLAIN = re.compile(r"不|没|别|吗|什么|为什么|怎么|哪|[?？]|或者|还是|吧")

EXERCISE_PROMPT = """你是用中文教学的老师「{name}」。请给学生出一道关于「{topic}」的练习题。
学生档案：
{profile}
难度按学生情况定：这个知识点薄弱就出基础题（直接用定义或公式一步能做），基本理解出中等题，已掌握出稍有变化的题；按学生年级出题。
{craft}{exercise_spec}"""

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
"feedback": [老师回应，2-3 句，每句不超过 {chars} 个汉字，自然口语：答对简短确认并点出关键；答错直接指出需要调整的那一步，再讲思路和答案；避免空泛夸奖、反复鼓励和「不太对哦」等幼儿化语气；公式用中文读出来]}}"""


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
    request_id: str | None = None  # activity owner assigned by the orchestrator, never by generated JSON

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
        return Board(key=self.key + ("a" if reveal_answer else ""), title=f"练习 · {self.concept}"[:24], items=items,
                     strip_numbering=False)

    def presentation(self) -> dict:
        """Question-only HTML uses the board's escaped text/MathML renderer; no answer is exposed."""
        return {"question_html": render_item(self.question, strip_numbering=False),
                "option_html": [render_item(option, strip_numbering=False) for option in self.options]}

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
    if SKIP.match(text):
        return {"is_answer": True, "correct": False, "skipped": True, "misconception": None}
    if NOT_PLAIN.search(text):
        return None
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
    if not isinstance(d, dict) or not isinstance(d.get("is_answer"), bool):
        raise ValueError("grader reply without a boolean is_answer")
    if not d["is_answer"]:
        return {"is_answer": False, "correct": False, "misconception": None}
    if not isinstance(d.get("correct"), bool):
        raise ValueError("grader reply without a boolean correct")
    mis = d.get("misconception")
    r = {"is_answer": True, "correct": d["correct"],
         "misconception": str(mis)[:40] if isinstance(mis, str) and mis.strip() and not d["correct"] else None}
    fb = d.get("feedback")
    fb = [fb] if isinstance(fb, str) else fb if isinstance(fb, list) else []
    said_fb = [p for x in fb if isinstance(x, str) for p in spoken(x, chars)][:4]
    r["feedback"] = feedback_lines(ex, r, chars, said_fb)
    return r


def feedback_lines(ex: Exercise, r: dict, chars: int, llm_lines: list[str] | None = None) -> list[str]:
    """What the teacher says after grading: praise or the correct answer, then the explanation."""
    if llm_lines:
        lines = list(llm_lines)
        stated = re.compile(rf"(答案|应该)(是|选)\s*{ex.answer}|选\s*{ex.answer}(?![A-Za-z])")
        if not r["correct"] and ex.kind == "choice" and not any(stated.search(x) for x in lines):
            lines.insert(1 if len(lines) > 1 else 0, f"正确答案是 {ex.answer}。")
        return lines
    expl = [p for x in ex.explanation for p in spoken(x, chars)][:3]
    if r.get("skipped"):
        head = ["没关系，我们一起来看。"]
        head += [f"答案是 {ex.answer}。"] if ex.kind == "choice" else spoken(f"答案是{ex.answer}。", chars)
        return head + expl
    if r["correct"]:
        return ["答对了。"] + expl[:2]
    head = [f"正确答案是 {ex.answer}，我们看一下原因。"] if ex.kind == "choice" else \
        ["这里的结果还需要调整。"] + spoken(f"答案是{ex.answer}。", chars)
    return head + expl


async def make_exercise(llm: ChatLLM, *, name: str, topic: str, profile: str, key: str, chars: int = 22,
                        source: str = "asked", craft: str = "") -> Exercise:
    """``craft``: the curriculum's practice-design rules for the student's grade ("" without craft data)."""
    raw = await llm.chat([{"role": "user", "content": EXERCISE_PROMPT.format(
        name=name, topic=topic, profile=profile, craft=(craft + "\n") if craft else "",
        exercise_spec=EXERCISE_SPEC.format(chars=chars, q_chars=60))}],
        max_tokens=600, temperature=0.5, json_mode=True)
    d = parse_json(raw)
    ex = Exercise.from_dict(d.get("exercise", d), key=key, source=source)
    if ex is None:
        raise ValueError("no usable exercise in the reply")
    return ex


__all__ = ["EXERCISE_SPEC", "Exercise", "feedback_lines", "grade", "make_exercise", "quick_grade"]
