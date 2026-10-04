"""Adaptive teaching: the saved student profile (grade, exams, per-concept mastery) shapes the lesson plan; the
teacher's exercises pause the lesson, are graded (rules, then the LLM) and update the profile."""

from __future__ import annotations

import asyncio
import json

import test_pipeline as tp
import test_teacher_persona as tt
from live_agent.exercise import Exercise, grade, quick_grade
from live_agent.lesson import LessonPlanner
from live_agent.llm import ScriptedLLM
from live_agent.student import StudentProfile
from live_agent.types import EventType, Utterance, now

SEEDS = tt.CFG.parents[0] / "students"
CHOICE = {"concept": "完全平方公式", "type": "choice", "question": "$(a+b)^2$ 展开等于？",
          "options": ["A. $a^2+b^2$", "B. $a^2+2ab+b^2$", "C. $a^2+ab+b^2$"], "answer": "B",
          "explanation": ["两数和的平方，等于平方和再加两倍的乘积。"]}
OUTLINE = {"title": "完全平方公式", "plan_note": "期中考试这里失分，重点讲；整式乘法已掌握，只复习",
           "sections": [{"title": "复习整式乘法", "goal": "回顾", "concepts": ["整式乘法"], "depth": "review", "exercise": False},
                        {"title": "完全平方公式", "goal": "推导和使用", "concepts": ["完全平方公式"], "depth": "core",
                         "exercise": True}],
           "intro": ["今天我们学完全平方公式。"]}


def section(i):
    out = {"board": {"title": f"第{i}节"},
           "points": [{"text": f"要点{i}", "lines": [f"第{i}节讲要点。", f"第{i}节再举个例子。"]}],
           "summary": [f"第{i}节小结。"]}
    if i == 2:
        out["exercise"] = CHOICE
    return out


def planner_llm(messages):
    text = messages[-1]["content"]
    if "课程大纲" in text:
        return json.dumps(OUTLINE, ensure_ascii=False)
    return json.dumps(section(1 if "第 1/2 节" in text else 2), ensure_ascii=False)


def profile(tmp_path):
    return StudentProfile.load("demo", tmp_path, SEEDS)


def test_the_profile_loads_from_its_seed_and_exam_losses_set_a_low_prior(tmp_path):
    p = profile(tmp_path)
    assert p.grade == "初二" and p.level("整式乘法") == "mastered" and p.level("完全平方公式") == "weak"
    assert p.mastery("因式分解") == 0.4  # never practised, but the midterm lost points on it
    s = p.summary()
    assert "初二" in s and "期中考试 72/100" in s and "失分点：因式分解" in s
    assert s.index("完全平方公式") < s.index("整式乘法")  # weakest first


def test_exercises_move_mastery_and_the_profile_is_saved_and_erasable(tmp_path):
    p = profile(tmp_path)
    before = p.mastery("完全平方公式")
    up = p.record_exercise("完全平方公式", True, question="q", answer="B")
    assert up["before"] == before and up["after"] > before
    down = p.record_exercise("完全平方公式", False, misconception="漏了 2ab")
    assert down["after"] < up["after"] and p.concepts["完全平方公式"].notes[-1] == "漏了 2ab"
    p.save()
    again = StudentProfile.load("demo", tmp_path, SEEDS)  # the saved copy wins over the seed
    assert again.concepts["完全平方公式"].attempts == p.concepts["完全平方公式"].attempts
    assert again.purge("完全平方公式") >= 1 and "完全平方公式" not in again.concepts
    assert all("完全平方公式" not in json.dumps(h, ensure_ascii=False) for h in again.history)


def test_what_the_student_says_about_themselves_updates_the_profile(tmp_path):
    p = profile(tmp_path)
    changed = p.apply_update({"grade": "初三", "exam": {"subject": "数学", "name": "单元测", "score": 64, "weak": ["配方法"]}})
    assert changed == ["grade", "exam"] and p.grade == "初三" and p.level("配方法") == "weak"
    p.update_basics({"exams": [{"subject": "数学", "name": "期末", "score": "88"}, {"bad": 1}]})
    assert [(e.name, e.score) for e in p.exams] == [("期末", 88.0)]


def test_the_outline_and_sections_are_adapted_to_the_profile_and_carry_the_exercise(tmp_path):
    llm = ScriptedLLM(planner_llm)
    planner = LessonPlanner(llm, name="林老师", bio="")
    p = profile(tmp_path)
    outline = asyncio.run(planner.outline("完全平方公式", profile=p))
    prompt = llm.calls[0][-1]["content"]
    assert "期中考试 72/100" in prompt and "完全平方公式：薄弱" in prompt and "因材施教" in prompt
    assert outline.note.startswith("期中") and [s["depth"] for s in outline.sections] == ["review", "core"]
    review = asyncio.run(planner.section(outline, 0, [], profile=p))
    assert "复习" in llm.calls[1][-1]["content"] and "4-6" in llm.calls[1][-1]["content"]
    assert not any(ln.exercise for ln in review)
    core = asyncio.run(planner.section(outline, 1, ["复习整式乘法"], profile=p, mistakes=["整式乘法（符号错）"]))
    sp = llm.calls[2][-1]["content"]
    assert "重点" in sp and "初二" in sp and "漏了 2ab" in sp and "整式乘法（符号错）" in sp and '"exercise"' in sp
    posed = [ln for ln in core if ln.exercise is not None]
    assert posed and posed[0].text == "我们来做一道练习。" and core[-len(posed):] == posed  # after the summary
    assert posed[0].board.items[0] == CHOICE["question"] and posed[0].exercise.answer == "B"
    assert all(ln.item is None for ln in posed)  # the options are on the board while the question is read


def test_answers_are_graded_by_rule_when_unambiguous():
    ex = Exercise.from_dict(CHOICE, key="x1")
    assert quick_grade(ex, "选 B")["correct"] and not quick_grade(ex, "a")["correct"]
    assert quick_grade(ex, "$a^2+2ab+b^2$")["given"] == "B"  # the option's own text
    assert quick_grade(ex, "我不会")["skipped"]
    assert quick_grade(ex, "我觉得是 A 或者 B 吧，因为……") is None  # ambiguous: the LLM decides
    short = Exercise.from_dict({"concept": "方程", "question": "2x=6，x=?", "answer": "3"}, key="q1")
    assert short.kind == "short" and quick_grade(short, "x=3")["correct"]
    assert Exercise.from_dict({"question": "q", "options": ["A. 1", "B. 2"], "answer": "D"}, key="z") is None


def test_free_answers_and_side_questions_go_to_the_llm_grader():
    ex = Exercise.from_dict(CHOICE, key="x1")
    llm = ScriptedLLM(lambda m: json.dumps({"is_answer": True, "correct": False, "misconception": "漏了中间项",
                                            "feedback": ["思路不错，但漏了中间项。", "要加上两倍的 ab。"]},
                                           ensure_ascii=False))
    r = asyncio.run(grade(llm, ex, "应该是 a 方加 b 方吧"))
    assert r["is_answer"] and not r["correct"] and r["misconception"] == "漏了中间项"
    assert "正确答案是 B。" in r["feedback"]  # the right option is always said
    side = ScriptedLLM(lambda m: json.dumps({"is_answer": False, "correct": False}))
    assert not asyncio.run(grade(side, ex, "老师，这个公式是谁发现的？"))["is_answer"]


def _lesson_director():
    d, _, _ = tt._director(tt.ANSWER)
    planner = LessonPlanner(ScriptedLLM(planner_llm), name="林老师", bio="")
    outline = asyncio.run(planner.outline("完全平方公式"))
    d.lesson_title = outline.title
    d.add_lesson_lines(asyncio.run(planner.section(outline, 1, [])))
    d.add_lesson_lines(asyncio.run(planner.section(outline, 0, [])))  # the next section is already waiting
    return d


def test_a_posed_exercise_pauses_the_lesson_then_reminds_then_shows_the_answer():
    d = _lesson_director()
    said = [d.next_script(k).transcript for k in range(6)]  # two point lines, the summary, then the exercise
    assert said[3] == "我们来做一道练习。" and said[-1].startswith("选项在黑板上")
    assert d.exercise is not None and d.exercise.concept == "完全平方公式"
    waiting = [d.next_script(6 + k) for k in range(d.exercise_reminder_after)]
    assert all(not s.transcript for s in waiting[:-1])  # the next section waits for the answer
    assert waiting[-1].transcript.startswith("想好了吗") and waiting[-1].board["key"] == "x1"
    rest = [d.next_script(20 + k) for k in range(d.exercise_reveal_after - d.exercise_reminder_after + 3)]
    spoken = [s.transcript for s in rest if s.transcript]
    assert spoken[0] == "我们一起来看这道题。" and rest[-1].transcript.startswith("第1节")  # answer shown, lesson moves on
    assert d.exercise is None and any(s.board and s.board["key"] == "x1a" for s in rest)
    assert d.events.exercise_timeouts == ["完全平方公式"]


def test_the_answer_is_graded_the_profile_updated_and_the_lesson_continues(tmp_path):
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    lesson = _lesson_director()
    orch.director.lesson_backlog, orch.director.lesson_title = lesson.lesson_backlog, lesson.lesson_title
    d = orch.director
    for k in range(5):  # up to the question itself: the student answers before "选项在黑板上" is spoken
        d.next_script(k)
    assert d.exercise is not None
    before = orch.student.mastery("完全平方公式")
    asyncio.run(orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="选 B", t_end=now())))
    after = [d.next_script(5 + k).transcript for k in range(4)]
    assert after[0] == "答对了，很好！" and after[2].startswith("第1节")  # feedback, then the next section
    assert not any(t.startswith("选项在黑板上") for t in after)  # the rest of the question is dropped
    assert orch.student.mastery("完全平方公式") > before
    graded = [e.data for e in tp.events(orch, EventType.LESSON) if e.data["stage"] == "exercise_graded"]
    assert graded and graded[0]["correct"] and graded[0]["mastery"]["after"] > before
    assert StudentProfile.load("demo", tmp_path, SEEDS).concepts["完全平方公式"].attempts == 5  # saved


def test_a_side_question_during_an_exercise_is_answered_then_the_exercise_is_recalled(tmp_path):
    orch, _ = tp.build()
    d = orch.director

    def llm(messages):
        if messages[0]["role"] != "system":  # the grader: not an answer
            return json.dumps({"is_answer": False, "correct": False})
        return json.dumps({"relation": "chat", "kind": "content", "steps": [{"intent": "", "line": "是毕达哥拉斯。"}]},
                          ensure_ascii=False)
    d.llm.fn = llm
    d.exercise = Exercise.from_dict(CHOICE, key="x1")
    asyncio.run(orch.on_user_utterance(Utterance(uid="u2", speaker="user", text="这个公式谁发现的？", t_end=now())))
    said = [d.next_script(k).transcript for k in range(2)]
    assert said == ["是毕达哥拉斯。", "我们回到刚才这道练习，想好了告诉我。"] and d.exercise is not None


def test_asking_for_an_exercise_poses_one_at_the_profiles_level(tmp_path):
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    d = orch.director
    prompts = []

    def llm(messages):
        if messages[0]["role"] == "system":
            assert "学生档案" in messages[0]["content"] and "初二" in messages[0]["content"]
            return json.dumps({"relation": "chat", "kind": "exercise", "topic": "完全平方公式",
                               "steps": [{"intent": "", "line": "好，我给你出一道题。"}]}, ensure_ascii=False)
        prompts.append(messages[-1]["content"])
        return json.dumps({"exercise": CHOICE}, ensure_ascii=False)
    d.llm.fn = llm

    async def go():
        await orch.on_user_utterance(Utterance(uid="u3", speaker="user", text="考考我", t_end=now()))
        await asyncio.gather(*list(orch._aux))
    asyncio.run(go())
    assert "完全平方公式：薄弱" in prompts[0] and "基础题" in prompts[0]
    said = [d.next_script(k) for k in range(4)]
    assert said[0].transcript == "好，我给你出一道题。" and said[1].board["key"] == "q1"
    assert d.exercise is not None and d.exercise.source == "asked"


def test_a_question_line_cut_after_the_answer_is_not_said_again(tmp_path):
    # seen live: the soft switch cut "选项在黑板上…" after the answer was graded; it came back with "好，我们接着讲。"
    # and re-opened the closed exercise, pausing the lesson again
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    lesson = _lesson_director()
    orch.director.lesson_backlog, orch.director.lesson_title = lesson.lesson_backlog, lesson.lesson_title
    d = orch.director
    scripts = [d.next_script(k) for k in range(6)]  # the last one poses the exercise, not yet shown
    asyncio.run(orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="A", t_end=now())))
    d.on_interrupted([scripts[5]])  # the switch to the feedback drops it
    after = [d.next_script(6 + k).transcript for k in range(5)]
    assert after[0].startswith("不太对哦") and not any(t.startswith(("选项在黑板上", "好，我们接着讲")) for t in after)
    assert any(t.startswith("第1节") for t in after) and d.exercise is None


def test_the_section_after_an_exercise_is_written_after_the_answer_and_addresses_the_mistake(tmp_path):
    outline = {**OUTLINE, "sections": [{**OUTLINE["sections"][1], "title": "公式"},
                                       {"title": "应用", "goal": "用", "concepts": ["完全平方公式"], "depth": "new"}]}
    asked = []

    def llm(messages):
        text = messages[-1]["content"]
        if "课程大纲" in text:
            return json.dumps(outline, ensure_ascii=False)
        if "解释图" in text:  # the figure judge
            return json.dumps({"points": []})
        asked.append(text)
        return json.dumps(section(2 if "第 1/2 节" in text else 1), ensure_ascii=False)

    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    d = orch.director
    d.llm.fn = llm
    orch.cfg.lesson_lookahead = 100  # plenty of room: only the exercise holds the next section back

    async def go():
        task = asyncio.create_task(orch._lesson_loop("完全平方公式"))
        await asyncio.sleep(0.3)
        assert len(asked) == 1  # the section with the exercise; the next one waits for the answer
        for k in range(8):
            d.next_script(k)
        assert d.exercise is not None
        await orch.on_user_utterance(Utterance(uid="u1", speaker="user", text="A", t_end=now()))
        await asyncio.wait_for(task, 5)
    asyncio.run(go())
    assert len(asked) == 2 and "学生刚才的练习做错了：完全平方公式" in asked[1]


# ---------------------------------------------------------------- Codex review adaptive1 (regressions)
def test_negations_questions_and_hedges_are_not_rule_graded():  # finding 7
    ex = Exercise.from_dict(CHOICE, key="x1")
    for said in ["我不选B", "B是什么意思？", "不会是B吧", "是A还是B"]:
        assert quick_grade(ex, said) is None, said


def test_malformed_grader_output_is_rejected_not_trusted():  # finding 8
    ex = Exercise.from_dict(CHOICE, key="x1")
    bad = ScriptedLLM(lambda m: json.dumps({"is_answer": "true", "correct": "false"}))
    try:
        asyncio.run(grade(bad, ex, "差不多是平方和吧"))
        raise AssertionError("string booleans must not become a grade")
    except ValueError:
        pass
    ok = ScriptedLLM(lambda m: json.dumps({"is_answer": True, "correct": False, "feedback": "B也不对，再想想。"},
                                          ensure_ascii=False))
    r = asyncio.run(grade(ok, ex, "差不多是平方和吧"))
    assert "正确答案是 B。" in r["feedback"] and "B也不对，再想想。" in r["feedback"]  # a string, not characters


def test_mastered_needs_exercises_and_old_exam_losses_expire(tmp_path):  # finding 13
    p = profile(tmp_path)
    p.record_exercise("勾股定理", True)
    p.concepts["新概念"] = type(p.concepts["勾股定理"])(name="新概念", mastery=0.95)
    assert p.level("新概念") == "partial"  # a high number without graded exercises is not "mastered"
    assert p.mastery("平方差公式") == 0.62 and p.prior("平方差公式") is None  # the later midterm no longer lists it
    assert p.view()["concepts"][0]["source"] in ("exercise", "exam", None)


def test_erasure_clears_grade_exams_and_a_pending_exercise(tmp_path):  # findings 2, 3
    p = profile(tmp_path)
    assert p.purge("初二") >= 1 and p.grade == ""
    assert p.purge("物理") >= 1 and all(e.subject != "物理" for e in p.exams)
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    d = orch.director
    d.exercise = Exercise.from_dict(CHOICE, key="x1")
    d.remind_exercise()
    orch._lesson_mistakes = ["完全平方公式（漏了 2ab）", "整式乘法（符号错）"]
    epoch = orch._profile_epoch
    assert orch._erase_learning(["完全平方公式"]) >= 1
    assert d.exercise is None and not d.queue  # the open exercise and its reminder are gone
    assert "完全平方公式" not in orch.student.concepts and orch._lesson_mistakes == ["整式乘法（符号错）"]
    assert orch._profile_epoch == epoch + 1  # grading already in flight will not write back
    assert "完全平方公式" not in StudentProfile.load("demo", tmp_path, SEEDS).concepts  # saved


def test_one_exercise_at_a_time_and_mistakes_do_not_cross_lessons(tmp_path):  # findings 4, 12
    orch, _ = tp.build()
    d = orch.director
    d.llm.fn = lambda m: json.dumps({"relation": "chat", "kind": "exercise", "topic": "勾股定理",
                                     "steps": [{"intent": "", "line": "好，我给你出一道题。"}]}, ensure_ascii=False) \
        if m[0]["role"] == "system" else json.dumps({"is_answer": False})
    d.exercise = Exercise.from_dict(CHOICE, key="x1")
    asyncio.run(orch.on_user_utterance(Utterance(uid="u4", speaker="user", text="再出一道题", t_end=now())))
    assert not orch._aux and d.exercise.key == "x1"  # no second exercise generated; the open one is recalled
    assert any(s.line.startswith("我们回到刚才这道练习") for s in d.queue)
    orch._lesson_mistakes = ["完全平方公式（漏了 2ab）"]
    orch._stop_lesson()
    assert orch._lesson_mistakes == []


def test_an_answer_drops_the_pending_reminder_and_a_cut_first_line_reopens_later(tmp_path):  # findings 5, 9
    orch, _ = tp.build()
    orch.student = profile(tmp_path)
    lesson = _lesson_director()
    d = orch.director
    d.lesson_backlog, d.lesson_title = lesson.lesson_backlog, lesson.lesson_title
    scripts = [d.next_script(k) for k in range(4)]  # ... up to "我们来做一道练习。"
    assert d.exercise is not None
    d.on_interrupted([scripts[3]])  # cut before it was shown: the student never saw the question
    assert d.exercise is None and d.lesson_backlog[0].line == "我们来做一道练习。"
    for k in range(4, 7):
        d.next_script(k)
    d.remind_exercise()  # after a side question: queued, not yet spoken
    asyncio.run(orch.on_user_utterance(Utterance(uid="u5", speaker="user", text="B", t_end=now())))
    assert not any(s.line.startswith("我们回到刚才") for s in d.queue)


def test_the_plan_stays_on_the_requested_topic(tmp_path):
    # seen live: a 勾股定理 lesson got a "core" section on 完全平方公式 because the profile listed it as weak
    reply = {"title": "勾股定理", "sections": [
        {"title": "前置一", "role": "prerequisite", "concepts": ["整式乘法"], "depth": "review"},
        {"title": "前置二", "role": "prerequisite", "concepts": ["完全平方公式"], "depth": "core"},
        {"title": "定理", "role": "main", "concepts": ["勾股定理"], "depth": "new"},
        {"title": "晚到的前置", "role": "prerequisite", "concepts": ["平方根"], "depth": "review"},
        {"title": "应用", "concepts": ["勾股定理"], "depth": "new"}], "intro": ["今天学勾股定理。"]}
    llm = ScriptedLLM(lambda m: json.dumps(reply, ensure_ascii=False))
    outline = asyncio.run(LessonPlanner(llm, name="林老师", bio="").outline("勾股定理", profile=profile(tmp_path)))
    assert [s["title"] for s in outline.sections] == ["前置一", "定理", "应用"]  # one prerequisite, first only
    prompt = llm.calls[0][-1]["content"]
    assert "不改变「讲什么」" in prompt and "不要为了补弱点塞进这节课" in prompt


def test_a_knowledge_answer_without_a_board_gets_one_written_for_it():
    # seen live: "一元二次方程怎么解？" was answered with no board (the responder copied a board-less example)
    orch, _ = tp.build()
    orch.answer_boards = True
    d = orch.director

    def llm(messages):
        if messages[0]["role"] == "system":
            return json.dumps({"relation": "chat", "kind": "content", "steps": [
                {"intent": "", "line": "常用配方法和求根公式。"}, {"intent": "", "line": "先算判别式。"}]}, ensure_ascii=False)
        assert "学生问：「一元二次方程怎么解？」" in messages[-1]["content"]
        return json.dumps({"title": "一元二次方程", "items": ["求根公式 $x=\\\\frac{-b\\\\pm\\\\sqrt{b^2-4ac}}{2a}$",
                                                               "判别式 $\\\\Delta=b^2-4ac$"]}, ensure_ascii=False)
    d.llm.fn = llm

    async def go():
        await orch.on_user_utterance(Utterance(uid="u6", speaker="user", text="一元二次方程怎么解？", t_end=now()))
        await asyncio.gather(*list(orch._aux))
    asyncio.run(go())
    s = d.next_script(0)
    assert s.transcript == "常用配方法和求根公式。" and s.board["title"] == "一元二次方程" and len(s.board["items"]) == 2
    assert [e.data["stage"] for e in tp.events(orch, EventType.LESSON)] == ["answer_board"]


def test_the_teacher_persona_requires_a_board_for_knowledge_answers():
    canon = json.loads((tt.CFG / "canon.json").read_text(encoding="utf-8"))
    assert canon["board"] is True and "必须加字段 \"board\"" in canon["responder_style"]
    replies = [json.loads(x.split(" → ", 1)[1]) for x in canon["responder_examples"]]
    assert all(r["board"]["items"] for r in replies if r["kind"] == "content")
    # no knowledge example is one of the page's one-click questions: those answers would be replayed, not composed
    asked = [x.split(" → ", 1)[0].removeprefix("用户：") for x in canon["responder_examples"]]
    content_q = [q for q, r in zip(asked, replies) if r["kind"] == "content"]
    assert not any(q in chip or chip in q for q in content_q for chip in canon["examples"])


def test_a_reply_copying_an_example_is_composed_again():
    canon = json.loads((tt.CFG / "canon.json").read_text(encoding="utf-8"))
    lever = json.loads(next(x for x in canon["responder_examples"] if "杠杆为什么" in x).split(" → ", 1)[1])
    fresh = {"relation": "chat", "kind": "content", "board": {"title": "杠杆", "items": ["支点、动力臂、阻力臂"]},
             "steps": [{"intent": "", "line": "杠杆靠力臂的长短来省力。"}]}
    d, llm, _ = tt._director(lever)
    llm.fn = lambda m: json.dumps(lever if len(llm.calls) == 1 else fresh, ensure_ascii=False)
    r = asyncio.run(d.decide(Utterance(uid="u7", speaker="user", text="杠杆为什么能省力？", t_end=now()), None))
    assert len(llm.calls) == 2 and "照抄" in llm.calls[1][-1]["content"]
    assert r["steps"][0]["line"] == "杠杆靠力臂的长短来省力。" and r["regenerated"] == "copied_example"
    d2, llm2, _ = tt._director(fresh)
    asyncio.run(d2.decide(Utterance(uid="u8", speaker="user", text="杠杆为什么能省力？", t_end=now()), None))
    assert len(llm2.calls) == 1  # an answer in its own words is used as it is


# ---------------------------------------------------------------- profile page (API) and shared store
def _client(tmp_path, students="demo,e2e"):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from live_agent.backend.app import build_app
    args = SimpleNamespace(config=str(tt.CFG), student="demo", students=students, student_store=str(tmp_path),
                           record=False, generator="mock", log_dir=str(tmp_path / "logs"))
    return TestClient(build_app(args))


def test_the_profile_page_edits_a_profile_with_version_checks(tmp_path):
    c = _client(tmp_path)
    assert c.get("/profile").status_code == 404  # browser pages are owned by the standalone frontend
    assert [s["id"] for s in c.get("/api/students").json()["students"]] == ["demo", "e2e"]
    assert c.get("/api/students/someone-else").status_code == 404  # not on the allow-list
    p = c.get("/api/students/demo").json()
    body = {"version": p["version"], "grade": "初三", "exams": [{"subject": "数学", "name": "期末", "score": 91, "weak": ["函数"]}],
            "concepts": [{"name": "完全平方公式", "mastery": 0.7}, {"name": "光合作用", "delete": True},
                         {"name": "一次函数", "subject": "数学"}]}
    q = c.put("/api/students/demo", json=body).json()
    assert q["grade"] == "初三" and q["version"] == p["version"] + 1 and [e["name"] for e in q["exams"]] == ["期末"]
    cp = {x["name"]: x for x in q["concepts"]}
    assert cp["完全平方公式"]["mastery"] == 0.7 and cp["完全平方公式"]["source"] == "manual"
    assert "光合作用" not in cp and cp["一次函数"]["source"] is None and cp["函数"]["source"] == "exam"
    assert c.put("/api/students/demo", json=body).status_code == 409  # stale version: refused, not overwritten
    saved = StudentProfile.load("demo", tmp_path, SEEDS)
    assert saved.grade == "初三" and saved.concepts["完全平方公式"].manual
    assert c.post("/api/students/demo/reset", json={"version": p["version"]}).status_code == 409  # stale page
    r = c.post("/api/students/demo/reset", json={"version": q["version"]}).json()  # back to the seed, newer version
    assert r["grade"] == "初二" and r["version"] > q["version"] and "光合作用" in {x["name"] for x in r["concepts"]}


def test_sessions_and_the_page_share_one_profile_and_listeners_are_told(tmp_path):
    from live_agent.student import ProfileStore
    store = ProfileStore(tmp_path, SEEDS, ["demo"])
    a, b = store.get("demo"), store.get("demo")
    assert a is b and store.get("other") is None
    told = []
    store.subscribe("demo", lambda: told.append("session"))
    a.record_exercise("勾股定理", True)
    store.changed("demo")  # a page edit / another session: the open session hears about it
    assert told == ["session"] and StudentProfile.load("demo", tmp_path, SEEDS).concepts["勾股定理"].attempts == 4
    v = a.version
    store.reset("demo")
    assert store.get("demo") is a and a.version > v and a.concepts["勾股定理"].attempts == 3  # same object, seed data


def test_a_bad_field_refuses_the_whole_save_and_the_grade_is_normalised(tmp_path):
    c = _client(tmp_path)
    p = c.get("/api/students/demo").json()
    for bad in ({"concepts": [{"name": "新概念", "mastery": "oops"}]}, {"concepts": [{"name": "x", "mastery": 1.5}]},
                {"grade": "幼儿园"}, {"exams": [{"subject": "数学", "name": "期末", "score": 120, "full": 100}]},
                {"concepts": [{"name": "长" * 21}]}, {"clear_history": "yes"}):
        r = c.put("/api/students/demo", json={"version": p["version"], "grade": "初三", **bad})
        assert r.status_code == 422, bad
    q = c.get("/api/students/demo").json()
    assert q["version"] == p["version"] and q["grade"] == "初二" and "新概念" not in {x["name"] for x in q["concepts"]}
    assert c.put("/api/students/demo", json={"version": p["version"], "grade": "初中三年级"}).json()["grade"] == "初三"


def test_delete_and_clear_do_what_the_page_says(tmp_path):
    p = StudentProfile.load("demo", tmp_path, SEEDS)
    assert "完全平方公式" in {w for e in p.exams for w in e.weak}
    p.page_edit({"concepts": [{"name": "完全平方公式", "delete": True}]})  # also named by an exam: removed there too
    assert "完全平方公式" not in {x["name"] for x in p.view()["concepts"]}
    p.record_exercise("勾股定理", False, misconception="斜边搞错")
    p.page_edit({"concepts": [{"name": "整式乘法", "mastery": 0.9}], "clear_history": True})
    c = p.concepts["勾股定理"]
    assert p.history == [] and (c.attempts, c.correct, c.notes, c.mastery) == (0, 0, [], None)
    assert p.concepts["整式乘法"].mastery == 0.9  # a teacher-set estimate stays


def test_a_reset_invalidates_profile_work_in_flight(tmp_path):
    from live_agent.student import ProfileStore
    store = ProfileStore(tmp_path, SEEDS, ["demo"])
    orch, _ = tp.build(max_requests=2)
    orch.student, orch.profile_store = store.get("demo"), store
    store.subscribe("demo", orch.on_profile_edited)
    e0 = orch._profile_epoch
    store.get("demo").name = "改名"
    store.changed("demo")  # an ordinary edit: grading in flight still applies
    assert orch._profile_epoch == e0
    store.reset("demo")
    assert orch._profile_epoch == e0 + 1
