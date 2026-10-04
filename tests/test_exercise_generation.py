"""Exercise generation keeps profile grade guidance without a contradictory age role."""

import asyncio
import json

import pytest

from live_agent.exercise import make_exercise
from live_agent.llm import ScriptedLLM


@pytest.mark.parametrize("grade", ["小学三年级", "初中二年级"])
def test_exercise_prompt_uses_the_supplied_grade_without_middle_school_role(grade):
    prompts = []

    def generate(messages):
        prompts.append(messages[-1]["content"])
        return json.dumps({"exercise": {"concept": "加法", "type": "choice", "question": "一加一等于几？",
                                        "options": ["A. 一", "B. 二"], "answer": "B"}}, ensure_ascii=False)

    exercise = asyncio.run(make_exercise(ScriptedLLM(generate), name="林老师", topic="加法",
                                        profile=f"年级：{grade}；加法掌握情况：薄弱", key="test"))
    assert grade in prompts[0] and "按学生年级出题" in prompts[0]
    assert "你是中学老师" not in prompts[0] and "用中文教学" in prompts[0]
    assert exercise.question == "一加一等于几？" and exercise.kind == "choice"


@pytest.mark.parametrize("barge_in", [False, True])
@pytest.mark.parametrize("generation_fails", [False, True])
def test_old_exercise_generation_cannot_reopen_after_newer_turn_finishes(barge_in, generation_fails):
    import test_pipeline as pipeline
    from live_agent.types import EventType, Utterance, now

    async def scenario():
        orch, _ = pipeline.build()
        started, release = asyncio.Event(), asyncio.Event()

        class HeldLLM:
            async def chat(self, messages, **kwargs):
                if messages[0]["role"] == "system":
                    if "考考我" in messages[-1]["content"]:
                        return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
                    return json.dumps({"kind": "chat", "steps": [{"line": "我们换个话题。"}]}, ensure_ascii=False)
                started.set()
                await release.wait()
                if generation_fails:
                    raise RuntimeError("old generation failed after the newer decision")
                return json.dumps({"exercise": {"concept": "加法", "question": "旧请求的题目", "answer": "二"}}, ensure_ascii=False)

        orch.director.llm = HeldLLM()
        await orch.on_user_utterance(Utterance("A", "user", "考考我", now()))
        await asyncio.wait_for(started.wait(), timeout=2)
        tasks = list(orch._aux)
        assert tasks and orch.director.exercise is None
        if barge_in:
            await orch.on_speech_start()
        result = await orch.on_user_utterance(Utterance("B", "user", "换个话题吧", now()))
        assert result["kind"] == "chat" and not orch.director.listening
        release.set()
        await asyncio.gather(*tasks)
        scripts = []
        for request in range(6):
            scripts.append(orch.director.next_script(request))
            orch._exercise_changed()
        assert orch.director.exercise is None and all(script.board is None for script in scripts)
        assert any("换个话题" in script.transcript for script in scripts)
        assert not any("旧请求" in script.transcript or "抱歉，这道题" in script.transcript for script in scripts)
        events = [event.data for event in orch.log.events if event.type == EventType.LESSON]
        assert any(event.type == EventType.AUDIT and event.data.get("where") == "exercise_generation"
                   and event.data.get("reason") == "superseded" for event in orch.log.events)
        assert not any(event.get("stage") in ("exercise", "exercise_open", "exercise_failed") for event in events)

    asyncio.run(scenario())


def test_exercise_request_captures_its_turn_before_the_generation_task_starts():
    import test_pipeline as pipeline
    from live_agent.types import EventType, Utterance, now

    async def scenario():
        orch, _ = pipeline.build()
        generations = []

        def immediate(messages):
            if messages[0]["role"] == "system":
                return json.dumps({"kind": "exercise", "topic": "加法", "steps": []}) if "考考我" in messages[-1]["content"] else \
                    json.dumps({"kind": "chat", "steps": []})
            generations.append(messages)
            return json.dumps({"exercise": {"concept": "加法", "question": "旧请求的题目", "answer": "二"}}, ensure_ascii=False)

        orch.director.llm = ScriptedLLM(immediate)
        await orch.on_user_utterance(Utterance("A", "user", "考考我", now()))
        tasks = list(orch._aux)
        # Both immediate decisions finish without yielding to A's newly created task.
        await orch.on_user_utterance(Utterance("B", "user", "换个话题吧", now()))
        await asyncio.gather(*tasks)
        assert not generations
        assert any(event.type == EventType.AUDIT and event.data.get("reason") == "superseded" for event in orch.log.events)

    asyncio.run(scenario())
