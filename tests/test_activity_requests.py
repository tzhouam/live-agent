"""Activity ownership survives asynchronous work and remains distinct from answer request IDs."""

import asyncio
import json

import pytest
import test_pipeline as pipeline

from live_agent.backend.transport import panel_event
from live_agent.exercise import Exercise
from live_agent.llm import ScriptedLLM
from live_agent.types import EventType, Utterance, now


def lesson_events(orch):
    return [panel_event(event, 0)["data"] for event in orch.log.events if event.type == EventType.LESSON]


@pytest.mark.parametrize("owner", [None, "practice-A"])
def test_generated_exercise_owner_survives_open_snapshot_grade_and_close(owner):
    async def scenario():
        orch, _ = pipeline.build()

        def generate(messages):
            if messages[0]["role"] == "system":
                return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
            return json.dumps({"exercise": {"concept": "加法", "question": "一加一等于几？", "answer": "二",
                                            "request_id": "untrusted-model-owner"}}, ensure_ascii=False)

        orch.director.llm = ScriptedLLM(generate)
        await orch.on_user_utterance(Utterance("request", "user", "考考我", now(), request_id=owner))
        await asyncio.gather(*list(orch._aux))
        orch.director.next_script(0)
        orch._exercise_changed()
        assert orch.director.exercise is not None and orch.director.exercise.request_id == owner
        snapshot = orch.snapshot()["exercise"]
        assert snapshot["question"] == "一加一等于几？"
        assert snapshot.get("request_id") == owner
        if owner is None:
            assert "request_id" not in snapshot
        await orch.on_user_utterance(Utterance("answer", "user", "二", now(), request_id="answer-B"))
        activities = [event for event in lesson_events(orch)
                      if event["stage"] in ("exercise", "exercise_open", "exercise_graded", "exercise_closed")]
        assert [event["stage"] for event in activities] == ["exercise", "exercise_open", "exercise_graded", "exercise_closed"]
        assert all(event.get("request_id") == owner for event in activities)
        if owner is None:
            assert all("request_id" not in event for event in activities)
        answer = next(event.data for event in orch.log.events if event.type == EventType.UTTERANCE_END
                      and event.data.get("uid") == "answer" and "decision" in event.data)
        assert answer["request_id"] == "answer-B" and answer["applied"] is True

    asyncio.run(scenario())


@pytest.mark.parametrize("owner", [None, "practice-A"])
def test_failed_exercise_generation_keeps_its_owner(owner):
    async def scenario():
        orch, _ = pipeline.build()

        class BrokenGenerator:
            async def chat(self, messages, **kwargs):
                raise RuntimeError("cannot make this exercise")

        orch.director.llm = BrokenGenerator()
        await orch._give_exercise("加法", request_id=owner)
        failure = next(event for event in lesson_events(orch) if event["stage"] == "exercise_failed")
        assert failure.get("request_id") == owner
        if owner is None:
            assert "request_id" not in failure

    asyncio.run(scenario())


def test_timeout_keeps_the_closed_exercise_owner_when_a_new_exercise_exists():
    orch, _ = pipeline.build()
    old = Exercise("加法", "一加一等于几？", "二", request_id="practice-A")
    orch.director.exercise = old
    orch._exercise_changed()
    orch.director._exercise_idle = orch.director.exercise_reveal_after - 1
    orch.director._exercise_wait()
    orch._exercise_changed()
    orch.director.exercise = Exercise("减法", "二减一等于几？", "一", request_id="practice-B")
    orch._drain_director_events(now())
    activities = {event["stage"]: event for event in lesson_events(orch)}
    assert activities["exercise_closed"]["request_id"] == "practice-A"
    assert activities["exercise_timeout"]["request_id"] == "practice-A"
    assert orch.snapshot()["exercise"]["request_id"] == "practice-B"


def test_lesson_request_tags_planning_stages_and_generated_exercises():
    async def scenario():
        orch, _ = pipeline.build()
        orch.cfg.lesson_self_check = "off"

        def generate(messages):
            if messages[0]["role"] == "system":
                return json.dumps({"kind": "lesson", "topic": "加法", "steps": []})
            text = messages[-1]["content"]
            if "课程大纲" in text:
                return json.dumps({"title": "加法", "sections": [{"title": "认识加法", "exercise": True}],
                                   "intro": ["一起学加法。"]}, ensure_ascii=False)
            if "板书和讲稿" in text:
                return json.dumps({"board": {"title": "认识加法"},
                                   "points": [{"text": "一加一", "lines": ["一加一等于二。"]}],
                                   "exercise": {"concept": "加法", "question": "一加一等于几？", "answer": "二"}},
                                  ensure_ascii=False)
            return "{}"  # optional figure judgement has no requested figures

        orch.director.llm = ScriptedLLM(generate)
        await orch.on_user_utterance(Utterance("request", "user", "请上一节课", now(), request_id="lesson-A"))
        await orch._lesson_task
        if orch._aux:
            await asyncio.gather(*list(orch._aux))
        stages = {event["stage"]: event for event in lesson_events(orch)}
        assert {"outline", "section", "planned"} <= stages.keys()
        assert all(stages[stage]["request_id"] == "lesson-A" for stage in ("outline", "section", "planned"))
        exercises = [line.exercise for line in orch.director.lesson_backlog if line.exercise is not None]
        assert exercises and all(exercise.request_id == "lesson-A" for exercise in exercises)

    asyncio.run(scenario())


def test_outline_failure_keeps_its_request_owner():
    async def scenario():
        orch, _ = pipeline.build()
        orch.director.llm = ScriptedLLM(lambda messages: "{}")
        await orch._lesson_loop("加法", request_id="lesson-A")
        failure = next(event for event in lesson_events(orch) if event["stage"] == "outline_failed")
        assert failure["request_id"] == "lesson-A"

    asyncio.run(scenario())


@pytest.mark.parametrize("fails", [False, True])
def test_delayed_section_check_retains_its_original_activity_owner(fails):
    async def scenario():
        from live_agent.lesson import Outline

        orch, _ = pipeline.build()
        entered, release = asyncio.Event(), asyncio.Event()

        class HeldCheck:
            async def check_section(self, *args, **kwargs):
                entered.set()
                await release.wait()
                if fails:
                    raise RuntimeError("late advisory failure")
                return {"pass": True, "scores": {}, "problems": [], "fix": ""}

        check = asyncio.create_task(orch._check_section(HeldCheck(), Outline("加法", [{"title": "一加一"}], []),
                                                       0, [], request_id="lesson-A"))
        await asyncio.wait_for(entered.wait(), 2)
        await orch.on_user_utterance(Utterance("new", "user", "换个话题", now(), request_id="chat-B"))
        release.set()
        await check
        event = next(event for event in lesson_events(orch) if event["stage"] in ("check", "check_failed"))
        assert event["request_id"] == "lesson-A"

    asyncio.run(scenario())


@pytest.mark.parametrize("creator", [None, "practice-B"])
@pytest.mark.parametrize("kind", ["exercise", "content", "lesson"])
def test_new_input_reports_the_existing_standalone_question_without_reassigning_owner(creator, kind):
    async def scenario():
        orch, _ = pipeline.build()
        existing = Exercise("加法", "一加一等于几？", "B", kind="choice", options=["A. 一", "B. 二"],
                            source="asked", request_id=creator)
        orch.director.exercise = existing
        calls = []

        def classify(messages):
            calls.append(messages[0]["role"])
            if messages[0]["role"] != "system":
                return json.dumps({"is_answer": False, "correct": False})  # request is not an answer to B
            return json.dumps({"kind": kind, "topic": "减法", "steps": []})

        def unexpected_lesson(*args):
            raise AssertionError("an open standalone question must be recovered before a new lesson starts")

        orch.director.llm = ScriptedLLM(classify)
        orch._start_lesson = unexpected_lesson
        decision = await orch.on_user_utterance(Utterance("C", "user", "给我出一道别的练习", now(), request_id="practice-C"))
        assert decision["kind"] == kind and calls == ["user", "system"]
        assert not orch._aux and orch.director.exercise is existing and existing.request_id == creator
        event = next(event for event in lesson_events(orch) if event["stage"] == "exercise_existing")
        assert event == {"stage": "exercise_existing", "concept": "加法", "kind": "choice", "question": "一加一等于几？",
                         "options": ["A", "B"], "option_texts": ["A. 一", "B. 二"],
                         "request_id": "practice-C", "exercise_request_id": creator}
        assert all(segment.exercise is existing for segment in orch.director.queue if segment.exercise is not None)

    asyncio.run(scenario())


def test_new_lesson_can_still_replace_an_exercise_from_the_current_lesson():
    async def scenario():
        orch, _ = pipeline.build()
        orch.director.exercise = Exercise("加法", "一加一等于几？", "二", source="lesson", request_id="lesson-B")
        started = []

        def classify(messages):
            return json.dumps({"is_answer": False, "correct": False}) if messages[0]["role"] != "system" else \
                json.dumps({"kind": "lesson", "topic": "减法", "steps": []})

        orch.director.llm = ScriptedLLM(classify)
        orch._start_lesson = lambda topic, context, owner: started.append((topic, owner))
        await orch.on_user_utterance(Utterance("C", "user", "请改讲减法", now(), request_id="lesson-C"))
        assert started == [("减法", "lesson-C")]
        assert not any(event["stage"] == "exercise_existing" for event in lesson_events(orch))

    asyncio.run(scenario())
