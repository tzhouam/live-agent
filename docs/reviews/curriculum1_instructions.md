# Codex review: student profile page and course knowledge base (commits b429013..5b8a67c, decisions D-039, D-040)

You are reviewing a change to a real-time digital-teacher demo (Python, asyncio, FastAPI). A video model renders the
teacher in ~5 s requests; a director pops one spoken line (<= 22 Chinese characters) per request; lessons are
planned by an LLM (outline, then one section at a time) and shown on a board beside the video. A saved student
profile (grade, exams, per-concept mastery) adapts lessons and is updated by graded exercises (D-038, reviewed
earlier as round adaptive1). This change adds:

1. **D-039, profile page** (`live_agent/server/static/profile.html`, `/profile`, `/api/students/...` in
   `live_agent/server/app.py`, `ProfileStore` in `live_agent/student.py`; diff inlined): teachers or students edit
   name, grade, exams, concept estimates (teacher-set until the next graded exercise), delete concepts, clear
   history, reset to the seed. One in-memory profile per allowed id shared by the editor and live sessions;
   versioned saves (409 on a stale version); open lesson pages refresh on edits.
2. **D-040, course knowledge base**: `configs/curriculum/*.json` (national curriculum per subject: per stage the
   standard's domains and paraphrased requirements, per grade textbook chapters, prerequisites, experiments) and
   `pedagogy.json` (per grade 1-12: learner traits, methods, content amount, tone, sentence length, vocabulary,
   examples, praise/correction, exercise style). `live_agent/curriculum.py` parses grades, finds where a topic is
   taught (string/bigram match, else an LLM picks chapters from a 16k-character index; picks must match a real
   chapter; cached), attaches the closest requirement (similarity floor), flags a topic above/below the student's
   grade, and renders the grade's teaching profile into planner/section/exercise/answer prompts. Data was
   researched from the MOE 2022 compulsory-education standards, the 2017/2020 senior-high standards and textbook
   tables of contents; sources and estimates are listed in each file. `tools/check_curriculum.py` validates files.

Inlined: `live_agent/curriculum.py`, `tests/test_curriculum.py`, `tools/check_curriculum.py`, the code diff of
the other files (`docs/reviews/curriculum1_diff.patch`), `configs/curriculum/pedagogy.json` and `math.json` in
full, and a generated summary of every subject file (`docs/reviews/curriculum1_data_summary.txt`: validator
output, then per grade the chapter count and first chapters, stages and domains, notes). The other subject files
are not inlined (about 330 KB); judge them from the summary.

Please find **correctness bugs and design risks**, most severe first. Focus on:
- `parse_grade` / `grade_name` edge cases on realistic inputs (e.g. "初中二年级", "高中一年级", "九年级", "十年级",
  "大一", "幼儿园", "二年级下", free text in a profile), and what a wrong grade does downstream;
- topic lookup and locator: false matches that would mislead the planner (wrong subject, wrong grade, a
  requirement that does not belong to the topic), the above/below-grade notes firing wrongly, cache keys, prompt
  injection through a topic string, LLM output handling, cost/latency on the lesson start path;
- how the grade profile reaches prompts (size, conflicts with the persona's fixed 22-character line limit and
  other prompt rules, "clean" stripping source tags) and whether the planner's role change by grade is sound;
- the profile page and API: access control (single shared token + id allow-list), input validation (types,
  sizes, mastery range, grade text), version/409 logic and races with live grading, reset/erasure interplay with
  D-038's `purge`/epoch, XSS in `profile.html` and in the lesson page's profile view;
- data quality and labelling in the curriculum files as far as the inlined material shows: grade/stage mapping
  (especially senior high, where 选择性必修 is not tied to a grade), claims presented as cited that look like
  estimates, requirements that are not paraphrases of a standard, missing grades;
- research-standard issues: numbers must be labelled cited / measured locally / estimate / proposed target.
For each finding give: file:line (or function), a concrete failure scenario, severity (high/medium/low), and a fix.
Do not restate what the code does; skip style nits. If something is fine, you need not mention it.
