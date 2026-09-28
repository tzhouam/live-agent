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
