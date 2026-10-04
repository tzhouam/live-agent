"""A validated catalogue selection controls this lesson without rewriting the learner's grade."""

import asyncio
import json

import test_pipeline as pipeline
from live_agent.curriculum import Curriculum
from live_agent.llm import ScriptedLLM
from live_agent.student import StudentProfile
from live_agent.types import EventType, Utterance, now


def test_catalogue_context_survives_responder_topic_and_grade_profile_update():
    orch, _ = pipeline.build()
    orch.student = StudentProfile("learner", grade="初中二年级")
    selected = {"subject": "数学", "grade": 3, "topic": "共同章节"}
    orch.director.llm = ScriptedLLM(lambda messages: json.dumps({
        "kind": "lesson", "topic": "模型丢掉了原题目", "steps": [], "profile_update": {"grade": "小学三年级"},
    }, ensure_ascii=False))
    started = []
    orch._start_lesson = lambda topic, context=None, request_id=None: started.append((topic, context, request_id))
    asyncio.run(orch.on_user_utterance(Utterance("u1", "user", "请讲选中的章节。", now(), lesson_context=selected,
                                               request_id="chapter-ticket")))
    assert started == [("共同章节", selected, "chapter-ticket")]
    assert orch.student.grade == "初中二年级" and orch.student.version == 0


def test_selected_grade_and_subject_reach_outline_and_section_without_shared_mutation():
    orch, _ = pipeline.build()
    orch.cfg.lesson_self_check = "off"
    orch.student = StudentProfile("learner", grade="初中二年级")
    subjects = [{"subject": subject, "grades": [1, 12], "grade_topics": {
        "3": {"topics": ["共同章节"], "basis": "textbook"},
        "8": {"topics": ["共同章节"], "basis": "textbook"},
    }} for subject in ("数学", "科学")]
    orch.curriculum = Curriculum(subjects)
    prompts = []

    def generation(messages):
        text = messages[-1]["content"]
        prompts.append(text)
        if "课程大纲" in text:
            return json.dumps({"title": "共同章节", "subject": "科学", "sections": [
                {"title": "认识这个概念", "goal": "理解", "concepts": [], "exercise": False},
            ], "intro": ["我们一起学。"]}, ensure_ascii=False)
        return json.dumps({"board": {"title": "认识概念", "items": ["一个例子"]},
                           "lines": [{"text": "我们来看一个例子。", "item": 0}]}, ensure_ascii=False)

    orch.director.llm = ScriptedLLM(generation)

    async def lesson():
        await orch._lesson_loop("共同章节", {"subject": "数学", "grade": 3, "topic": "共同章节"})
        if orch._aux:
            await asyncio.gather(*list(orch._aux))

    asyncio.run(lesson())
    teaching = [text for text in prompts if text.startswith("你是小学老师")]
    assert len(teaching) == 2 and all("3年级" in text for text in teaching)
    outline = next(event for event in orch.log.events if event.type == EventType.LESSON and event.data.get("stage") == "outline")
    assert outline.data["subject"] == "数学"
    assert orch.student.grade == "初中二年级" and orch.student.version == 0
    assert orch.curriculum.subjects is subjects and len(orch.curriculum.subjects) == 2


def test_standalone_catalogue_practice_uses_selected_grade_and_subject_without_profile_write():
    orch, _ = pipeline.build()
    orch.student = StudentProfile("learner", grade="初中二年级")
    subjects = [{"subject": subject, "grades": [1, 12], "grade_topics": {
        "3": {"topics": ["共同章节"], "basis": "textbook"},
        "8": {"topics": ["共同章节"], "basis": "textbook"},
    }} for subject in ("数学", "科学")]
    orch.curriculum = Curriculum(subjects)
    selected = {"subject": "数学", "grade": 3, "topic": "共同章节"}
    prompts = []

    def generation(messages):
        if messages[0]["role"] == "system":
            return json.dumps({"kind": "exercise", "topic": "模型丢掉了章名", "steps": [],
                               "profile_update": {"grade": "小学三年级"}}, ensure_ascii=False)
        prompts.append(messages[-1]["content"])
        return json.dumps({"exercise": {"concept": "加法", "type": "choice", "question": "一加一等于几？",
                                        "options": ["A. 一", "B. 二"], "answer": "B", "subject": "数学"}}, ensure_ascii=False)

    orch.director.llm = ScriptedLLM(generation)

    async def practice():
        await orch.on_user_utterance(Utterance("u1", "user", "请给我所选章节的练习。", now(), lesson_context=selected))
        await asyncio.gather(*list(orch._aux))

    asyncio.run(practice())
    assert len(prompts) == 1 and "3年级" in prompts[0] and "初中二年级" not in prompts[0]
    assert "共同章节" in prompts[0] and "数学" in prompts[0] and "模型丢掉了章名" not in prompts[0]
    assert "科学" not in prompts[0]
    assert orch.student.grade == "初中二年级" and orch.student.version == 0
    assert orch.curriculum.subjects is subjects and len(orch.curriculum.subjects) == 2
    assert any(event.type == EventType.LESSON and event.data.get("stage") == "exercise" for event in orch.log.events)
