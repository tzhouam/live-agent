"""Long-form teaching: lesson planning, board rendering, alignment of board points with spoken lines, and a
lesson that survives a question (answer first, then 'we continue' from the first line not yet shown)."""

from __future__ import annotations

import asyncio
import json

import pytest

import test_pipeline as tp
import test_teacher_persona as tt
from live_agent.lesson import Board, LessonPlanner, render_item, spoken
from live_agent.llm import ScriptedLLM
from live_agent.types import EventType, Utterance, now

OUTLINE = {"title": "光合作用", "sections": [{"title": "什么是光合作用", "goal": "定义"}, {"title": "原料和产物", "goal": "方程"}],
           "intro": ["今天我们学光合作用。", "分两部分来讲。"]}


def section(i):
    return {"board": {"title": f"第{i}节", "items": ["要点甲", "公式 $6CO_2+6H_2O \\to C_6H_{12}O_6+6O_2$"],
                      "figure": {"prompt": f"第{i}节示意图：一片叶子，箭头标出阳光、水、二氧化碳", "caption": "叶片<示意>"}},
            "lines": [{"text": f"第{i}节第一句讲要点甲。", "item": 0}, {"text": f"第{i}节第二句，还是要点甲。", "item": 0},
                      {"text": f"第{i}节第三句讲公式，二氧化碳加水生成葡萄糖和氧气，这句话很长需要拆开。", "item": 1}]}


def planner_llm(messages):
    text = messages[-1]["content"]
    if "课程大纲" in text:
        return json.dumps(OUTLINE, ensure_ascii=False)
    i = 1 if "第 1/2 节" in text else 2
    return json.dumps(section(i), ensure_ascii=False)


def test_spoken_lines_carry_no_latex_and_fit_one_request():
    assert spoken("公式是 $a^2+b^2=c^2$，记住它。", 22) == ["公式是 a的平方加b的平方等于c的平方，记住它。"]
    assert spoken("列式子：(a+b)平方等于c平方加2ab。", 22) == ["列式子：a加b的和的平方等于c平方加2ab。"]  # no 3-char request
    parts = spoken("第一句很长很长很长很长很长很长，第二句也很长很长很长很长很长很长很长。", 22)
    assert all(len(p) <= 22 for p in parts) and len(parts) == 2


def test_board_items_are_escaped_and_formulas_become_mathml():
    html = render_item("<script>x</script> **重点** $x^2$")
    assert "&lt;script&gt;" in html and "<b>重点</b>" in html and "<math" in html
    view = Board("s0", "标题<b>", ["a", "b"]).view(0)
    assert view["title"] == "标题&lt;b&gt;" and view["reveal"] == 0


def test_sections_align_lines_with_board_points():
    planner = LessonPlanner(ScriptedLLM(planner_llm), name="林老师", bio="")
    outline = asyncio.run(planner.outline("光合作用"))
    lines = asyncio.run(planner.section(outline, 0, []))
    assert [ln.item for ln in lines][:2] == [0, 0] and all(ln.item == 1 for ln in lines[2:])
    assert [ln.gesture for ln in lines][:3] == [True, False, True]  # the first line about each point presents it
    assert all(len(ln.text) <= 22 for ln in lines) and len(lines) >= 4  # the long line was split
    intro = planner.intro_lines(outline)
    assert intro[0].board.items == ["什么是光合作用", "原料和产物"]  # the outline is the first board


def test_answers_come_before_lesson_lines_and_the_lesson_resumes():
    d, _, _ = tt._director({"relation": "chat", "target_chain": None, "kind": "chat", "memory_note": None,
                            "forget_term": None, "steps": [{"intent": "", "line": "好问题。"}]})
    planner = LessonPlanner(ScriptedLLM(planner_llm), name="林老师", bio="")
    outline = asyncio.run(planner.outline("光合作用"))
    d.add_lesson_lines(asyncio.run(planner.section(outline, 0, [])))
    first = d.next_script(0)
    assert first.transcript.startswith("第1节第一句") and first.board["reveal"] == 0
    d.on_barge_in()
    d.on_interrupted([first])  # cut before it was shown
    tt._ask(d, "为什么？")
    assert d.next_script(1).transcript == "好问题。"  # the answer first
    resume = d.next_script(2)
    assert resume.transcript == "好，我们接着讲。" and resume.board["key"] == "s0"
    assert d.next_script(3).transcript.startswith("第1节第一句")  # the cut line again, not skipped


def test_a_lesson_plays_with_its_board_and_survives_a_question():
    def llm(messages):
        if messages[0]["role"] != "system":
            return planner_llm(messages)
        text = messages[-1]["content"]
        if "上一节" in text:
            return json.dumps({"relation": "new", "kind": "lesson", "topic": "光合作用",
                               "steps": [{"intent": "", "line": "好，我们来上一节光合作用。"}]}, ensure_ascii=False)
        return json.dumps({"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "植物需要光。"}],
                           "board": {"title": "答疑", "items": ["光是能量来源"]}}, ensure_ascii=False)

    orch, client = tp.build(max_requests=22)
    orch.director.llm.fn = llm
    asyncio.run(tp.run(orch, client, [(2.0, "给我上一节光合作用的课"), (14.0, "为什么要光？")]))
    stages = [e.data["stage"] for e in tp.events(orch, EventType.LESSON)]
    assert stages[:3] == ["outline", "section", "section"] and stages[-1] == "planned"
    locks = [e for e in tp.events(orch, EventType.LOCK)]
    said = [e.data["transcript"] for e in locks if e.data["transcript"]]
    assert "今天我们学光合作用。" in said and "植物需要光。" in said and "好，我们接着讲。" in said
    assert said.index("植物需要光。") < said.index("好，我们接着讲。")
    boards = {k: s.board for k, s in orch.scripts.items() if s.board}
    assert {b["key"] for b in boards.values()} >= {"outline", "s0"}
    lesson_lines = [t for t in said if t.startswith("第1节") or t.startswith("第2节")]
    assert len(lesson_lines) == len(set(lesson_lines))  # no line lost or repeated across the question


class FakeImages:
    def __init__(self):
        self.prompts = []

    async def make(self, prompt, seed=42):
        self.prompts.append(prompt)
        await asyncio.sleep(0.01)
        return f"/board/img/{len(self.prompts):016x}.png"


def test_a_section_figure_appears_on_the_board_once_generated():
    planner = LessonPlanner(ScriptedLLM(planner_llm), name="林老师", bio="")
    outline = asyncio.run(planner.outline("光合作用"))
    board = asyncio.run(planner.section(outline, 0, []))[0].board
    assert board.figure_prompt.startswith("第1节示意图") and "figure" not in board.view(0)  # not generated yet
    board.figure_url = "/board/img/0123456789abcdef.png"
    fig = board.view(0)["figure"]
    assert fig["url"].endswith(".png") and fig["caption"] == "叶片&lt;示意&gt;"


def test_lesson_figures_are_generated_in_the_background_and_shown_on_later_lines():
    def llm(messages):
        if messages[0]["role"] != "system":
            return planner_llm(messages)
        return json.dumps({"relation": "new", "kind": "lesson", "topic": "光合作用",
                           "steps": [{"intent": "", "line": "好，我们来上一节光合作用。"}]}, ensure_ascii=False)

    orch, client = tp.build(max_requests=14)
    orch.director.llm.fn = llm
    orch.image_maker = FakeImages()
    asyncio.run(tp.run(orch, client, [(2.0, "给我上一节光合作用的课")]))
    assert len(orch.image_maker.prompts) == 2  # one per section, generated once
    shown = [s.board for s in orch.scripts.values() if s.board and s.board["key"] == "s0"]
    assert shown and any("figure" in b for b in shown)
    assert any(e.data.get("stage") == "figure" for e in tp.events(orch, EventType.LESSON))


def test_image_maker_calls_the_images_api_and_reuses_files(tmp_path, monkeypatch):
    import base64

    import httpx

    from live_agent.board_images import ImageMaker

    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    maker = ImageMaker("http://127.0.0.1:8104", tmp_path)
    url = asyncio.run(maker.make("一个直角三角形"))
    assert url.startswith("/board/img/") and (tmp_path / url.rsplit("/", 1)[1]).read_bytes() == b"PNGDATA"
    assert calls[0]["num_inference_steps"] == 4 and calls[0]["size"] == "1024x768" and "直角三角形" in calls[0]["prompt"]
    assert asyncio.run(maker.make("一个直角三角形")) == url and len(calls) == 1  # same prompt: the file is reused


def test_figure_labels_are_checked_for_absence_and_misspelt_copies():
    from live_agent.board_images import expected_labels, missing_labels

    want = expected_labels("一片绿叶，太阳的箭头标注「阳光」，左侧标注「二氧化碳」，根部标注「水」")
    assert want == ["阳光", "二氧化碳", "水"]
    assert missing_labels(want, ["阳光", "二氧化碳", "水", "叶绿体"]) == []  # extra labels are fine
    assert missing_labels(want, ["阳光", "二氧化碳", "二氧化硼", "水"]) == ["二氧化硼"]  # seen live
    assert missing_labels(want, ["阳光", "水"]) == ["二氧化碳"]

    assert missing_labels(["细胞壁", "细胞膜"], ["细胞壁", "细胞膜", "液泡"]) == []  # one char apart, both asked for
    assert missing_labels(["x₁", "x₂"], ["x1", "x2", "顶点"]) == []  # subscripts read as digits


def test_exact_plots_parse_safely_and_render(tmp_path):
    from live_agent.board_plot import parse_function, render_plot

    f = parse_function("x^2-2*x-3")
    assert list(f(__import__("numpy").array([-1.0, 3.0]))) == [0.0, 0.0]
    for bad in ["__import__('os').system('id')", "x.real", "open('f')", "[x for x in ()]"]:
        with pytest.raises((ValueError, SyntaxError)):
            parse_function(bad)
    name = render_plot({"functions": ["x**2-2*x-3"], "x": [-3, 5], "points": [{"x": 1, "y": -4, "label": "顶点"}]}, tmp_path)
    assert name.startswith("p") and (tmp_path / name).stat().st_size > 10_000
    assert render_plot({"functions": ["x**2-2*x-3"], "x": [-3, 5], "points": [{"x": 1, "y": -4, "label": "顶点"}]},
                       tmp_path) == name  # same spec, same file


def test_a_figure_is_a_plot_or_an_illustration_and_prompt_text_on_a_picture_is_rejected():
    from live_agent.board_images import missing_labels
    from live_agent.lesson import set_figure

    b = Board("s0", "二次函数", [])
    assert set_figure(b, {"plot": {"functions": ["x**2"]}, "caption": "图像"}) and b.figure_plot and not b.figure_prompt
    b2 = Board("s1", "光合作用", [])
    assert set_figure(b2, {"prompt": "一片叶子，标注「水」"}) and b2.figure_prompt and b2.figure_plot is None
    assert not set_figure(Board("s2", "", []), {"caption": "only"})
    prompt = "一元二次方程的抛物线示意图：开口向上，顶点标注「顶点」"
    assert missing_labels(["顶点"], ["一元二次方程的抛物线", "顶点"], prompt) == ["一元二次方程的抛物线"]  # seen live


def test_a_lesson_plot_is_drawn_and_shown(tmp_path):
    def llm(messages):
        if messages[0]["role"] != "system":
            text = messages[-1]["content"]
            if "课程大纲" in text:
                return json.dumps(OUTLINE, ensure_ascii=False)
            sec = section(1)
            sec["board"]["figure"] = {"plot": {"functions": ["x**2-1"], "x": [-2, 2]}, "caption": "y=x²-1"}
            return json.dumps(sec, ensure_ascii=False)
        return json.dumps({"relation": "new", "kind": "lesson", "topic": "二次函数",
                           "steps": [{"intent": "", "line": "好，我们来上一节二次函数。"}]}, ensure_ascii=False)

    orch, client = tp.build(max_requests=12)
    orch.director.llm.fn = llm
    orch.figure_dir = tmp_path  # no image model needed for plots
    asyncio.run(tp.run(orch, client, [(2.0, "给我上一节二次函数的课")]))
    figs = [s.board["figure"] for s in orch.scripts.values() if s.board and "figure" in s.board]
    assert figs and figs[0]["url"].startswith("/board/img/p") and list(tmp_path.glob("p*.png"))
