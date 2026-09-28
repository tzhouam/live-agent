# Codex review: adaptive lessons and teacher exercises (commit 8433281, decision D-038)

You are reviewing a change to a real-time digital-teacher demo (Python, asyncio). A video model renders the teacher
in ~5 s requests; a director pops one spoken line per request; lessons are generated section by section by an LLM
and wait in a lesson backlog; a board beside the video shows points/formulas. The change adds:

1. `live_agent/student.py`: a saved student profile (grade, exams with lost-point concepts, per-concept mastery,
   exercise history) used to adapt planning; EMA mastery update; erasure (`purge`).
2. `live_agent/exercise.py`: exercises (choice / short), rule grading then LLM grading, feedback lines.
3. `live_agent/lesson.py`: adaptive outline (per-section concepts, depth, exercise flag) and sections (profile,
   this lesson's mistakes, exercise spec); exercise lines appended after a section's summary.
4. Director/orchestrator/app/page wiring (diff inlined): the lesson backlog pauses while an exercise waits; the
   next utterance is graded first (answer vs side question); feedback is applied as a reply and the answer is shown;
   the next section is generated after the answer; silence -> reminder, then the answer; the page shows the profile
   and answer buttons.

Please find **correctness bugs and design risks**, most severe first. Focus on:
- state machine races: barge-in / soft switch cuts (`on_interrupted`), `exercise` set on pop, lesson backlog gating,
  requeue of cut lines, the idle timer, stop_lesson, erasure while an exercise waits, grading superseded by a newer
  utterance (epoch), an asked exercise during a lesson;
- grading errors (rule grader false positives/negatives on realistic Chinese answers, LLM output handling);
- privacy: the profile is personal data (private sessions only, erasure coverage, what reaches logs/prompts/page);
- the mastery model and thresholds (they are labelled proposed; say if the labelling or behaviour is misleading);
- anything that could stall the lesson forever or loop.
For each finding give: file:line (or function), a concrete failure scenario, severity (high/medium/low), and a fix.
Do not restate what the code does; skip style nits. If something is fine, you need not mention it.
