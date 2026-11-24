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


DIAGRAM = {"title": "叶片吸收原料", "nodes": [
    {"id": "light", "text": "阳光", "column": 0, "row": 0, "shape": "ellipse"},
    {"id": "water", "text": "水", "column": 0, "row": 2, "shape": "box"},
    {"id": "leaf", "text": "叶片", "column": 2, "row": 1, "shape": "box"}],
    "arrows": [{"from": "light", "to": "leaf", "label": "吸收"}, {"from": "water", "to": "leaf", "label": "吸收"}]}


def test_cpu_diagram_maker_draws_requested_labels_and_reuses_actual_png(tmp_path):
    from PIL import Image, ImageChops
    from live_agent.board_images import LocalDiagramMaker

    calls = []
    def reply(messages):
        calls.append(messages)
        return json.dumps(DIAGRAM, ensure_ascii=False)
    maker = LocalDiagramMaker(ScriptedLLM(reply), tmp_path)
    async def draw():
        return await asyncio.gather(maker.make("一片叶子，标注「阳光」和「水」"), maker.make("一片叶子，标注「阳光」和「水」"))
    urls = asyncio.run(draw())
    assert urls[0] == urls[1] and urls[0].startswith("/board/img/d") and len(calls) == 1
    image = Image.open(tmp_path / urls[0].rsplit("/", 1)[1]).convert("RGB")
    assert image.size == (1024, 768)
    bounds = ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox()
    assert bounds and 0 < bounds[0] < bounds[2] < 1024 and 0 < bounds[1] < bounds[3] < 768
    assert maker.exact_labels and maker.kind == "diagram" and len(maker.timings) == 1


def test_cpu_diagram_never_publishes_a_missing_requested_label(tmp_path):
    from live_agent.board_images import LocalDiagramMaker
    maker = LocalDiagramMaker(ScriptedLLM(lambda _: json.dumps(DIAGRAM)), tmp_path)
    with pytest.raises(ValueError, match="preserve requested labels"):
        asyncio.run(maker.make("标注「二氧化碳」和「水」"))
    assert not list(tmp_path.glob("*.png"))


def test_cpu_diagram_keeps_an_unquoted_central_concept_from_the_request(tmp_path):
    from live_agent.board_images import LocalDiagramMaker
    data = {**DIAGRAM, "title": "光合作用"}
    maker = LocalDiagramMaker(ScriptedLLM(lambda _: json.dumps(data)), tmp_path)
    url = asyncio.run(maker.make("光合作用关系图，标注「阳光」和「水」"))
    assert (tmp_path / url.rsplit("/", 1)[1]).exists()


@pytest.mark.parametrize("failure", ["self arrow", "missing label"])
def test_cpu_diagram_repairs_invalid_model_data_before_publishing(tmp_path, failure):
    from copy import deepcopy
    from live_agent.board_images import LocalDiagramMaker
    bad = deepcopy(DIAGRAM)
    if failure == "self arrow":
        bad["arrows"][0]["to"] = "light"
    else:
        bad["nodes"][0]["text"] = "照明"
    requests = []
    def reply(messages):
        requests.append(messages)
        return json.dumps(bad if len(requests) == 1 else DIAGRAM, ensure_ascii=False)
    maker = LocalDiagramMaker(ScriptedLLM(reply), tmp_path)
    url = asyncio.run(maker.make("标注「阳光」和「水」"))
    assert len(requests) == 2 and len(requests[0]) == 1
    assert json.loads(requests[1][-2]["content"]) == bad
    assert "重新输出完整 JSON" in requests[1][-1]["content"]
    assert len(list(tmp_path.glob("*.png"))) == 1 and (tmp_path / url.rsplit("/", 1)[1]).exists()


def test_cpu_diagram_persistent_invalid_data_has_bounded_attempts_and_no_file(tmp_path):
    from live_agent.board_images import LocalDiagramMaker
    llm = ScriptedLLM(lambda _: '{"title":"错误","nodes":[]}')
    maker = LocalDiagramMaker(llm, tmp_path)
    with pytest.raises(ValueError, match="invalid after 3 planning attempts"):
        asyncio.run(maker.make("教学关系图"))
    assert len(llm.calls) == 3 and not list(tmp_path.glob("*.png")) and not maker.timings


def test_cpu_diagram_repairs_share_one_timeout_budget(tmp_path):
    from copy import deepcopy
    from live_agent.board_images import LocalDiagramMaker
    class SlowRepair:
        calls = 0
        async def chat(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                bad = deepcopy(DIAGRAM)
                bad["arrows"][0]["to"] = "light"
                return json.dumps(bad)
            await asyncio.sleep(.2)
            return json.dumps(DIAGRAM)
    llm = SlowRepair()
    maker = LocalDiagramMaker(llm, tmp_path, timeout_s=.02)
    with pytest.raises(TimeoutError):
        asyncio.run(maker.make("教学关系图"))
    assert llm.calls == 2 and not list(tmp_path.glob("*.png")) and not maker.timings


@pytest.mark.parametrize("change", [
    {"nodes": []}, {"nodes": [{"id": "a", "text": "x", "row": 3, "column": 0}]},
    {"arrows": [{"from": "water", "to": "unknown"}]},
    {"arrows": [{"from": [], "to": "leaf"}]},
    {"nodes": [{"id": "a", "text": "x", "row": 1, "column": 0}, {"id": "b", "text": "y", "row": 1, "column": 0}]},
    {"nodes": [{"id": "a", "text": "x" * 25, "row": 1, "column": 0}]},
    {"nodes": [{"id": "a", "text": "x", "row": 1, "column": 0, "shape": "eval"}]},
])
def test_cpu_diagram_rejects_unbounded_or_invalid_model_data(change):
    from live_agent.board_diagram import compile_diagram
    with pytest.raises(ValueError):
        compile_diagram({**DIAGRAM, **change})

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


def test_a_closing_quote_stays_with_its_sentence_when_lines_are_split():
    parts = spoken("老师说：“鲸很大，最大的有一百吨，比大象重得多。”用了什么方法？", 22)
    assert parts == ["老师说：“鲸很大，最大的有一百吨，", "比大象重得多。”用了什么方法？"]  # no line starts with ”
    assert spoken("他问：「为什么？」我答：「不知道。」", 22) == ["他问：「为什么？」我答：「不知道。」"]


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
    assert resume.transcript == "好，我们接着讲。" and resume.board["key"] == f"{outline.board_key}:s0"
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
    stages = [e.data["stage"] for e in tp.events(orch, EventType.LESSON) if not e.data["stage"].startswith("figure")]
    assert stages[:3] == ["outline", "section", "section"] and stages[-1] == "planned"
    locks = [e for e in tp.events(orch, EventType.LOCK)]
    said = [e.data["transcript"] for e in locks if e.data["transcript"]]
    assert "今天我们学光合作用。" in said and "植物需要光。" in said and "好，我们接着讲。" in said
    assert said.index("植物需要光。") < said.index("好，我们接着讲。")
    boards = {k: s.board for k, s in orch.scripts.items() if s.board}
    assert {b["key"].rsplit(":", 1)[-1] for b in boards.values()} >= {"outline", "s0"}
    lesson_lines = [t for t in said if t.startswith("第1节") or t.startswith("第2节")]
    assert len(lesson_lines) == len(set(lesson_lines))  # no line lost or repeated across the question


class FakeImages:
    def __init__(self):
        self.prompts = []

    async def make(self, prompt, seed=42):
        self.prompts.append(prompt)
        n = len(self.prompts)  # before the await: concurrent calls must not share a name
        await asyncio.sleep(0.01)
        return f"/board/img/{n:016x}.png"


def test_a_board_shows_the_figure_of_the_point_being_explained_only():
    from live_agent.lesson import set_figure

    board = Board("s0", "光合作用", ["原料", "场所", "产物"])
    f1 = set_figure(board, {"prompt": "叶绿体结构，标注「叶绿体」", "caption": "叶绿体<示意>"}, point=1)
    assert f1 is not None and "figure" not in board.view(1)  # not drawn yet
    f1.url = "/board/img/0123456789abcdef.png"
    assert board.view(1)["figure"] == {"url": f1.url, "caption": "叶绿体&lt;示意&gt;"}
    assert "figure" not in board.view(2) and "figure" not in board.view(0)  # never another point's picture
    whole = set_figure(board, {"plot": {"functions": ["x"]}})  # a board-level figure fills the other points
    whole.url = "/board/img/p123456789abcdef.png"
    assert board.view(2)["figure"]["url"] == whole.url and board.view(1)["figure"]["url"] == f1.url


def test_the_figure_judge_decides_per_point_and_caps_the_count():
    verdicts = {"points": [
        {"i": 0, "complexity": 1, "need": False, "why": "定义复述", "figure": None},
        {"i": 1, "complexity": 3, "need": True, "why": "结构复杂", "figure": {"prompt": "叶绿体结构，标注「类囊体」"}},
        {"i": 2, "complexity": 3, "need": True, "why": "过程", "figure": {"plot": {"functions": ["x**2"]}}},
        {"i": 2, "complexity": 3, "need": True, "why": "重复", "figure": {"prompt": "again"}},
        {"i": 9, "complexity": 3, "need": True, "why": "越界", "figure": {"prompt": "x"}}]}
    seen = {}

    def llm(messages):
        seen["prompt"] = messages[-1]["content"]
        return json.dumps(verdicts, ensure_ascii=False)

    planner = LessonPlanner(ScriptedLLM(llm), name="林老师", bio="")
    board = Board("s0", "光合作用", ["定义", "场所", "产物"])
    from live_agent.lesson import LessonLine
    lines = [LessonLine("先说定义。", board, 0), LessonLine("看黑板上的图。", board, 1), LessonLine("产物是糖。", board, 2)]
    out = asyncio.run(planner.judge_figures(lines, max_figs=2))
    assert "1. 场所：看黑板上的图。" in seen["prompt"]  # each point with what she says about it
    assert [(o["point"], o["need"], o["kind"]) for o in out] == [
        (0, False, None), (1, True, "illustration"), (2, True, "plot")]
    assert [f.point for f in board.figures] == [1, 2]  # capped at 2, out-of-range point ignored


def test_visual_first_policy_covers_simple_substantive_points_with_a_six_point_budget():
    from live_agent.lesson import MAX_ITEMS, LessonLine
    records = [{"i": i, "complexity": 1, "need": True, "why": "用具体例子帮助理解",
                "figure": {"prompt": f"用分类图讲解概念{i}，标注「例子{i}」"}} for i in range(MAX_ITEMS)]
    class RecordingLLM:
        async def chat(self, messages, **options):
            self.prompt, self.options = messages[0]["content"], options
            return json.dumps({"points": records}, ensure_ascii=False)
    llm = RecordingLLM()
    planner = LessonPlanner(llm, name="林老师", bio="")
    board = Board("visual-first", "具体概念和例子", [f"简单概念{i}" for i in range(MAX_ITEMS)])
    out = asyncio.run(planner.judge_figures([LessonLine(f"这是第{i}个具体例子。", board, i) for i in range(MAX_ITEMS)]))
    assert len(board.figures) == MAX_ITEMS == 6 and all(item["need"] for item in out)
    assert all(f"例子{i}" in fig.prompt for i, fig in enumerate(board.figures))
    assert "复杂程度不是是否配图的门槛" in llm.prompt and "纯问候" in llm.prompt
    assert llm.options["max_tokens"] >= 2000  # the complete labelled specs must fit, not truncate after three points


def test_visual_budget_never_exceeds_max_items_and_counts_existing_point_figures():
    from live_agent.lesson import MAX_ITEMS, LessonLine, set_figure
    records = [{"i": i, "need": True, "figure": {"prompt": f"图{i}"}} for i in range(MAX_ITEMS + 2)]
    planner = LessonPlanner(ScriptedLLM(lambda _: json.dumps({"points": records})), name="林老师", bio="")
    board = Board("cap", "八个要点", [str(i) for i in range(MAX_ITEMS + 2)])
    whole = set_figure(board, {"prompt": "整节概览"})
    existing = set_figure(board, {"plot": {"functions": ["x**2"]}, "caption": "已有函数图"}, point=1)
    existing.queued, existing.url = True, "/board/img/p000000000000001.png"
    lines = [LessonLine("全局讲解", board, None)]
    asyncio.run(planner.judge_figures(lines, max_figs=100))
    assert len([f for f in board.figures if f.point is not None]) == MAX_ITEMS
    assert whole in board.figures and board.figures[1] is existing
    before = list(board.figures)
    # Lowering a later planning budget must not destroy already queued or completed visuals.
    asyncio.run(planner.judge_figures(lines, max_figs=1))
    assert len(board.figures) == len(before) and all(a is b for a, b in zip(board.figures, before))
    assert existing.queued and existing.url.endswith("001.png") and existing.plot == {"functions": ["x**2"]}


def test_duplicate_and_invalid_figure_verdicts_cannot_replace_or_block_a_valid_visual():
    from live_agent.lesson import LessonLine, set_figure
    records = [
        {"i": True, "need": True, "figure": {"prompt": "布尔不是序号"}},
        {"i": False, "need": True, "figure": {"prompt": "布尔不是序号"}},
        {"i": "0", "need": True, "figure": {"prompt": "字符串不是序号"}},
        {"i": 1.0, "need": True, "figure": {"prompt": "小数不是序号"}},
        {"i": -1, "need": True, "figure": {"prompt": "负序号"}},
        {"i": 9, "need": True, "figure": {"prompt": "越界"}},
        {"i": 0, "need": True, "figure": {"caption": "无图数据"}},
        {"i": 0, "need": True, "figure": {"plot": {"functions": ["x**2"], "points": [{"x": 1, "y": 1, "label": "A"}]}}},
        {"i": 0, "need": True, "figure": {"prompt": "后来的重复图"}},
        {"i": 1, "need": False, "figure": None},
        {"i": 1, "need": True, "figure": {"prompt": "不能覆盖已排队的图"}},
        {"i": 2, "need": "false", "figure": {"prompt": "错误布尔类型"}},
    ]
    board = Board("dedupe", "三个要点", ["函数", "结构", "问候"])
    original = set_figure(board, {"prompt": "原始结构图，标注「叶绿体」", "caption": "原始图"}, point=1)
    original.queued, original.url = True, "/board/img/d000000000000002.png"
    planner = LessonPlanner(ScriptedLLM(lambda _: json.dumps({"points": records})), name="林老师", bio="")
    out = asyncio.run(planner.judge_figures([LessonLine("这是全局说明。", board, None)]))
    assert [(v["point"], v["need"], v["kind"]) for v in out] == [(0, True, "plot"), (1, True, "illustration"), (2, False, None)]
    assert len(board.figures) == 2 and board.figures[0] is original
    assert original.prompt == "原始结构图，标注「叶绿体」" and original.caption == "原始图" and original.queued
    assert original.url.endswith("002.png")
    graph = next(f for f in board.figures if f.point == 0)
    assert graph.plot["functions"] == ["x**2"] and graph.plot["points"][0]["label"] == "A"
    for invalid in (True, False, -1, 3, "0", 0.0):
        assert set_figure(board, {"prompt": "不应添加"}, point=invalid) is None
    assert set_figure(board, {"prompt": "仍不替换"}, point=0) is graph


def test_unassigned_speech_is_global_context_once_without_guessed_point_mapping():
    from live_agent.lesson import LessonLine
    llm = ScriptedLLM(lambda _: '{"points": []}')
    planner = LessonPlanner(llm, name="林老师", bio="")
    board = Board("answer", "回答", ["第一要点", "第二要点"])
    asyncio.run(planner.judge_figures([LessonLine("全局回答唯一标记", board, None),
                                      LessonLine("第一点专属讲解", board, 0), LessonLine("第二点专属讲解", board, 1)]))
    prompt = llm.calls[0][0]["content"]
    assert prompt.count("全局回答唯一标记") == 1
    assert "0. 第一点" not in prompt  # there is no fabricated sentence-to-point association
    assert "0. 第一要点：第一点专属讲解" in prompt and "1. 第二要点：第二点专属讲解" in prompt
    assert "0. 第一要点：全局回答唯一标记" not in prompt and "1. 第二要点：全局回答唯一标记" not in prompt


@pytest.mark.parametrize("malformed", [
    {"functions": "x**2"}, {"functions": [{"expression": "x**2"}]},
    {"points": {"x": 1, "y": 1}}, {"points": [{"x": 1}]},
    {"polygons": [{"points": "0,0;3,0;0,4"}]}, {"functions": ["x**2"], "x": "-2,2"},
])
def test_malformed_plot_containers_do_not_block_a_corrected_duplicate(malformed):
    from live_agent.lesson import LessonLine, set_figure
    exact = {"functions": ["x**2"], "x": [-2, 2], "points": [{"x": 1, "y": 1, "label": "A"}]}
    records = [{"i": 0, "need": True, "figure": {"plot": malformed}},
               {"i": 0, "need": True, "figure": {"plot": exact, "caption": "精确曲线"}}]
    board = Board("corrected", "曲线", ["函数关系"])
    assert set_figure(board, {"plot": malformed}, point=0) is None
    planner = LessonPlanner(ScriptedLLM(lambda _: json.dumps({"points": records})), name="林老师", bio="")
    out = asyncio.run(planner.judge_figures([LessonLine("看曲线和标记点。", board, 0)]))
    assert len(board.figures) == 1 and board.figures[0].plot == exact
    assert board.figures[0].caption == "精确曲线" and out[0]["kind"] == "plot"


def test_board_gallery_includes_ready_future_points_without_auto_selecting_them():
    from live_agent.lesson import Figure, set_figure
    board = Board("gallery", "课程", ["当前点", "未来点", "未配图点"])
    whole = set_figure(board, {"prompt": "概览", "caption": "概览 <img>"})
    first = set_figure(board, {"prompt": "第一点", "caption": "第一点"}, point=0)
    later = set_figure(board, {"plot": {"functions": ["x"]}, "caption": "未来 <script>"}, point=1)
    pending = set_figure(board, {"prompt": "未完成"}, point=2)
    whole.url, first.url, later.url = [f"/board/img/d00000000000000{i}.png" for i in range(1, 4)]
    # Stale/invalid extra entries must never leak into the active image or manual gallery.
    board.figures.extend([Figure(point=1, url="/board/img/d000000000000004.png", caption="重复"),
                          Figure(point=True, url="/board/img/d000000000000005.png"),
                          Figure(point=99, url="/board/img/d000000000000006.png"),
                          Figure(point=2, url="/board/img/d000000000000007.png", caption="排队点的旧图")])
    view = board.view(0, (1, 2))
    assert view["figure"]["url"] == first.url and view["progress"] == [1, 2]
    assert view["figures"] == [{"url": whole.url, "caption": "概览 &lt;img&gt;", "point": None},
                               {"url": first.url, "caption": "第一点", "point": 0},
                               {"url": later.url, "caption": "未来 &lt;script&gt;", "point": 1}]
    assert board.view(2)["figure"]["url"] == whole.url and board.view(None)["figure"]["url"] == whole.url
    assert pending.url == "" and Board("empty", "空", []).view(None)["figures"] == []


def test_lesson_figures_are_generated_in_the_background_and_shown_on_later_lines():
    def llm(messages):
        if messages[0]["role"] != "system":
            if "教学设计专家" in messages[-1]["content"]:
                return json.dumps({"points": [{"i": 0, "complexity": 3, "need": True, "why": "结构",
                                               "figure": {"prompt": "一片叶子，标注「叶绿体」"}}]}, ensure_ascii=False)
            return planner_llm(messages)
        return json.dumps({"relation": "new", "kind": "lesson", "topic": "光合作用",
                           "steps": [{"intent": "", "line": "好，我们来上一节光合作用。"}]}, ensure_ascii=False)

    orch, client = tp.build(max_requests=14)
    orch.director.llm.fn = llm
    orch.image_maker = FakeImages()
    asyncio.run(tp.run(orch, client, [(2.0, "给我上一节光合作用的课")]))
    prompts = orch.image_maker.prompts
    assert len(prompts) == 4  # per section: its board figure + one judged point, each drawn once
    shown = [s.board for s in orch.scripts.values() if s.board and s.board["key"].endswith(":s0")]
    on0 = {b["figure"]["url"] for b in shown if "figure" in b and b["reveal"] == 0}
    on1 = {b["figure"]["url"] for b in shown if "figure" in b and b["reveal"] == 1}
    assert on0 and not (on0 & on1)  # point 0's picture on point 0 only (point 1 falls back to the board figure)
    stages = [e.data.get("stage") for e in tp.events(orch, EventType.LESSON)]
    assert "figure_judgement" in stages and "figure" in stages


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
    f = set_figure(b, {"plot": {"functions": ["x**2"]}, "caption": "图像"})
    assert f and f.plot and not f.prompt
    f2 = set_figure(Board("s1", "光合作用", []), {"prompt": "一片叶子，标注「水」"})
    assert f2 and f2.prompt and f2.plot is None
    assert set_figure(Board("s2", "", []), {"caption": "only"}) is None
    assert set_figure(Board("s3", "勾股定理", []), {"plot": {"polygons": [{"points": [[0, 0], [3, 0], [0, 4]]}]}})
    prompt = "一元二次方程的抛物线示意图：开口向上，顶点标注「顶点」"
    assert missing_labels(["顶点"], ["一元二次方程的抛物线", "顶点"], prompt) == ["一元二次方程的抛物线"]  # seen live


def test_a_lesson_plot_is_drawn_and_shown(tmp_path):
    def llm(messages):
        if messages[0]["role"] != "system":
            text = messages[-1]["content"]
            if "课程大纲" in text:
                return json.dumps(OUTLINE, ensure_ascii=False)
            if "教学设计专家" in text:
                return json.dumps({"points": [{"i": 1, "complexity": 3, "need": True, "why": "函数图像",
                                               "figure": {"plot": {"functions": ["x**2-1"], "x": [-2, 2]},
                                                          "caption": "y=x²-1"}}]}, ensure_ascii=False)
            return json.dumps(section(1), ensure_ascii=False)
        return json.dumps({"relation": "new", "kind": "lesson", "topic": "二次函数",
                           "steps": [{"intent": "", "line": "好，我们来上一节二次函数。"}]}, ensure_ascii=False)

    orch, client = tp.build(max_requests=12)
    orch.director.llm.fn = llm
    orch.figure_dir = tmp_path  # no image model needed for plots
    asyncio.run(tp.run(orch, client, [(2.0, "给我上一节二次函数的课")]))
    figs = [s.board["figure"] for s in orch.scripts.values() if s.board and "figure" in s.board]
    assert figs and figs[0]["url"].startswith("/board/img/p") and list(tmp_path.glob("p*.png"))


def test_nested_points_keep_every_sentence_on_its_point_with_progress_and_a_neutral_summary():
    nested = {"board": {"title": "二次函数"},
              "points": [{"text": "一般式 $y=ax^2+bx+c$", "lines": ["首先看一般式。", "它有三项。"]},
                         {"text": "$a\\neq0$", "lines": ["注意 a 不能为零。"]}],
              "summary": ["这一节就讲到这里。"]}

    def llm(messages):
        return json.dumps(OUTLINE if "课程大纲" in messages[-1]["content"] else nested, ensure_ascii=False)

    planner = LessonPlanner(ScriptedLLM(llm), name="林老师", bio="")
    outline = asyncio.run(planner.outline("二次函数"))
    lines = asyncio.run(planner.section(outline, 0, []))
    assert [(ln.item, ln.progress, ln.gesture) for ln in lines] == [
        (0, (1, 2), True), (0, (2, 2), False), (1, (1, 1), True), (None, None, False)]
    assert lines[0].board.items[1] == "$a\\neq0$"
    assert lines[1].board.view(0, lines[1].progress)["progress"] == [2, 2]
    assert "progress" not in lines[3].board.view(None, None)  # the summary highlights no point


def test_geometry_is_drawn_to_scale(tmp_path):
    from live_agent.board_plot import render_plot

    spec = {"polygons": [{"points": [[0, 0], [4, 0], [0, 3]], "sides": ["4", "5", "3"]},
                         {"points": [[0, 0], [0, -4], [4, -4], [4, 0]], "label": "16"}], "grid": True}
    name = render_plot(spec, tmp_path)
    assert (tmp_path / name).stat().st_size > 10_000
    with pytest.raises(ValueError):
        render_plot({"polygons": [{"points": [[0, 0]]}]}, tmp_path)  # a one-point polygon is nothing to draw


def test_latex_with_a_backslash_eaten_by_json_is_repaired_and_commands_are_read_out():
    # seen live: the board showed "(a+b)² eq a²+b²" -- "\neq" in a JSON string became a newline + "eq"
    broken = json.loads('{"t": "$(a+b)^2 \\neq a^2+b^2$ 和 $2\\times 3$"}')["t"]
    html = render_item(broken)
    assert "<mo>&#x02260;</mo>" in html and "<mi>e</mi>" not in html  # the ≠ sign, no stray "eq"
    assert spoken(broken, 40) == ["a加b的和的平方 不等于 a的平方加b的平方 和 2乘 3"]
    assert spoken("$\\frac{1}{2}$", 22) == ["2分之1"]


def test_board_items_numbered_by_the_model_are_not_numbered_twice():
    # seen live on the two-GPU demo: "1. 1. 因式分解法" (the page's list numbers the points itself)
    assert render_item("1. 因式分解法").startswith("因式分解法") and render_item("2、配方法") == "配方法"
    assert render_item("2x+1=0") == "2x+1=0" and render_item("一、定义") == "定义"
