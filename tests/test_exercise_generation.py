"""Exercise generation keeps profile grade guidance without a contradictory age role."""

import asyncio
import json

import pytest

from live_agent.exercise import Exercise, make_exercise
from live_agent.llm import ScriptedLLM


def test_exercise_presentation_keeps_the_boards_safe_math_fallback(monkeypatch):
    from latex2mathml import converter

    def unavailable(*args, **kwargs):
        raise ValueError("controlled conversion failure")

    monkeypatch.setattr(converter, "convert", unavailable)
    ex = Exercise(concept="比较", question="比较 $x < 3$", answer="不公开", options=["A. $x > 3$", "B. 保留 <文字>"])
    presentation = ex.presentation()
    assert presentation["question_html"] == "比较 <code>x &lt; 3</code>"
    assert presentation["option_html"] == ["A. <code>x &gt; 3</code>", "B. 保留 &lt;文字&gt;"]
    board = ex.board().view(None)
    assert board["items"] == [presentation["question_html"], *presentation["option_html"]]


def test_exercise_presentation_preserves_leading_decimals_and_numbered_options():
    from live_agent.lesson import render_item

    ex = Exercise(concept="小数", question="1.5 + 2 = ? <img src=x>", answer="不公开",
                  options=["1. $3.5$", "2. <script>alert(1)</script>"])
    presentation = ex.presentation()
    assert presentation["question_html"] == "1.5 + 2 = ? &lt;img src=x&gt;"
    assert presentation["option_html"][0].startswith("1. <math")
    assert presentation["option_html"][1] == "2. &lt;script&gt;alert(1)&lt;/script&gt;"
    assert ex.board().view(None)["items"] == [presentation["question_html"], *presentation["option_html"]]
    assert render_item("1. 板书仍自动编号") == "板书仍自动编号"


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
