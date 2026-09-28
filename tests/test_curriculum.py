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
