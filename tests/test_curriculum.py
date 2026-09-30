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
