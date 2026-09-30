# Codex review round `craft1`: teaching-craft knowledge base and the enriched lesson workflow

You are GPT-6 Sol reviewing a change to `live_agent/` (a real-time AI teacher persona that teaches one Chinese K-12
student at a time by live generated video with a text board rendered beside it). Reply in English. Rank findings by
severity (blocking / high / medium / low), each with file:line or symbol, the failure scenario, and the smallest fix.
Say explicitly which claims in the decision-log entry you could verify from the inlined material and which you could not.

## What changed (owner request: "enrich the teaching for the agent, including workflow, knowledge base, skill:
1. search for the textbooks teaching teachers how to teach; 2. search for outstanding teachers in top schools or
teaching-competition winners in each grade and analyse their teaching skills")

1. **Knowledge base** `configs/curriculum/teaching_craft.json` (inlined in full): 7 lesson stages with rules, 55 teacher
   moves (stage, grade range, subjects, rank, example line), 5 grade bands (plan / delivery notes), 34 master teachers
   with verified honours and imitable moves, 13 board rules, an 18-item lesson-quality checklist with rubric weights,
   116 sources. Built from five research notes (not inlined; ~430 KB; the synthesis report's structure is described
   in the decision-log entry). Every entry cites sources; unverified items are excluded and listed in `notes`.
2. **Rendering** (`live_agent/curriculum.py`, inlined): `plan_craft` (outline prompt), `section_craft` (section
   prompt), `practice_craft` (exercise prompt), `checklist` (self-check), `masters` / `moves` filtered by stage, grade
   and subject, `subject_of`. Source tags "（cN）" are stripped by `clean()`.
3. **Workflow** (`live_agent/lesson.py`, inlined): the outline returns subject, objectives, key point, difficulty and a
   hook type; the intro is a hook + objectives + parts; the section prompt gets the craft block, a focus line
   (objectives / 重点 / 难点), requires one guided question per section (ask, then answer on the next line) and a
   closing on the last section; `check_section` judges a section against the checklist (scores 0-2, problems, fix,
   pass); `section(..., feedback=...)` rewrites with the judge's problems.
4. **Orchestrator** (diff inlined): `lesson_self_check` = off / log (background, logged) / revise (sections after the
   first are judged before they play and rewritten once on a fail; lookahead doubled in that mode); server flag
   `--lesson-self-check`; requested exercises get the practice rules.
5. `tools/check_curriculum.py` validates the craft file; tests in `tests/test_curriculum.py` (inlined).

## Evidence (measured locally, hosted qwen3.8-flash, one run each, 2026-10-01; excerpts inlined)
Sample runs (grade 1 数学 20以内的进位加法, grade 5 语文 说明文的说明方法, grade 8 数学 勾股定理, grade 10 数学 函数的单调性):
outline 10.6-16.5 s, review section 4.5-5.6 s, core/new section 7.5-13.3 s, self-check 4.5-9.6 s per section. Before the
judge was told the section's planned depth and the not-applicable rule, it failed 7 of 8 sections, mostly on items that
a monologue section cannot show (praise after an answer, an exercise on a section not marked for one); those items are
now scoped out or marked not applicable. The runs after that change are inlined as `craft1_runs.txt`.

## Questions to answer
- Correctness of the rendering and filtering (grade bands, subject "*" semantics, rank ordering, `subject_of` fallbacks,
  `clean()` on the new tags, the checklist scope), and of the outline parsing (subject cross-check, objective limits).
- The self-check: is the pass rule sound; can the revise mode stall the lesson (lookahead, the first section, failures);
  does a rewrite ever lose the exercise or the mistakes-first correction; is a judge from the same model family as
  the writer worth anything (say what would make it a measurement rather than a judgement).
- Prompt-injection and data-quality risks from the knowledge base reaching prompts (names, quotes, "（估计）" labels,
  the claim that numbers are estimates), and whether the provenance claims in the decision log are supported.
- Anything in the decision-log entry that overclaims (e.g. that lessons "follow" master teachers, or that the
  self-check improves quality), and what the smallest experiment would be.
