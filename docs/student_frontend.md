# Student frontend: research and implementation notes

Owner request, 2026-10-02: make the frontend a student product with primary-school and secondary-school
editions in Chinese, and a university/adult edition in English. This document records the inspected
contracts, design references and implemented student flows. The student page and CPU/browser validation
are complete. Formal GPT-6 Sol source review finished through student9, confirming the named replacement
and correlated-error repairs; a final minor terminal-decision guard was repaired afterward and verified
locally in the browser. Review records and limits are in `docs/codex_reviews.md`. The edition names and
grade ranges below are product configuration categories, not efficacy claims.

## Primary-source design references

All sources were accessed on 2026-10-02. The design choices are our interpretation of the sources;
they do not establish that this implementation improves learning.

| Source | What the source describes | Design choice for this project |
|---|---|---|
| [CAST: Optimize choice and autonomy](https://udlguidelines.cast.org/engagement/interests-identities/choice-autonomy/) | Choices should align with a learning goal; learners differ in the amount and kind of choice they want | Offer a clear next activity and topic choice. Keep primary-school choices compact while allowing older learners to browse and search |
| [CAST: Set meaningful goals](https://udlguidelines.cast.org/action-expression/strategy-development/goals/) | Support meaningful goals and planning | Describe the selected topic and the current learning task before asking the student to start |
| [CAST: Monitor progress](https://udlguidelines.cast.org/action-expression/strategy-development/monitoring-progress/) | Make monitoring and reflecting on progress possible | Show concept history and evidence. Label existing understanding estimates as estimates; distinguish lesson preparation from playback and from demonstrated understanding |
| [CAST: Use multiple media for communication](https://udlguidelines.cast.org/action-expression/expression-communication/multiple-media/) | Offer different communication media | Keep a readable board and text answers alongside the teacher video and optional voice input |
| [Khan Academy: Content organization](https://support.khanacademy.org/hc/en-us/articles/18564282990861-What-types-of-content-can-I-assign-to-my-students) | Courses contain units; units contain lessons and quizzes; lessons combine explanations and practice | Navigate from subject to the stored textbook chapter, then to a live explanation or practice. The existing chapter index is not a complete courseware library |
| [Khan Academy: Mastery levels](https://support.khanacademy.org/hc/en-us/articles/5548760867853--How-do-Khan-Academy-s-Mastery-levels-work) | Skill states depend on exercise and assessment results | Keep unknown, attempted and estimated understanding distinguishable. Do not copy Khan Academy's scoring thresholds or claim their validation applies here |
| [Duolingo: Guided learning path](https://blog.duolingo.com/new-duolingo-home-screen-design/) | Descriptive topics, guided next activities, and review integrated into a learning path | Make the next learning action explicit and offer review as part of studying. Do not invent streaks, rewards or completed lessons |
| [Duolingo: Consistent interface craft](https://blog.duolingo.com/core-tabs-redesign/) | Consistent typography and spacing, balanced with purpose and clarity | Share navigation and layout conventions across editions; vary language and presentation density without adding unrelated controls |

## Editions and actual coverage

| Edition | Interface language | Intended presentation | Current teaching coverage |
|---|---|---|---|
| Primary school | Chinese | Short labels, prominent actions, a compact subject/topic choice | Stored Chinese school topics for grades 1–6, subject availability varying by grade |
| Secondary school | Chinese | Subject and chapter navigation, searchable topics, clearer practice/history detail | Stored Chinese school topics for grades 7–12, with senior-high placement estimates preserved |
| University/adult | English | English navigation, topic entry and a calm study workspace | The same school catalogue and Chinese/Mandarin teacher. There is no verified university/adult curriculum or English teaching mode in this change |

The last row distinguishes interface language from teaching language. An English interface does not
translate the stored curriculum, the teacher's spoken line, the board or the model prompts. A learner
can ask about a topic, but that is not evidence of reviewed university course coverage.

The inspected baseline is repository commit `3f99f19b8ab08ea2d56f2ff9b1eb003f7221dcee`; the new resource
and exercise payloads described below are local changes. `configs/curriculum/*.json` stores the
chapter index and its provenance; `configs/persona_teacher/canon.json` fixes the teacher's Chinese
language and Mandarin voice. `LessonPlanner._role` and the profile validator currently interpret
school grades, and the grade validator does not accept an adult/university grade string. This change
does not alter that policy.

## Backend interface used by the student page

The frontend's existing server proxies these APIs and `/ws` on the page's origin.

| Interface | Contract and use |
|---|---|
| `GET /api/curriculum` | Existing summary remains unchanged: subject coverage, source/topic counts and teaching-craft metadata |
| `GET /api/curriculum/topics` | `{topics: [{subject, grade, topic, basis, source?}]}`. Every title comes from a loaded `grade_topics` entry; `grade` is a school-grade integer and the provenance is retained. Empty curriculum data returns an empty list |
| `GET /api/students` | Operator-allowed profile IDs and their name/grade/saved metadata; not per-student authentication |
| `GET /api/students/{id}` | Current profile with version, exams, concepts, history and saved status. Concept understanding values are existing uncalibrated estimates |
| `PUT /api/students/{id}` | Validated edits requiring the loaded version; stale edits return `409` and invalid fields return `422` |
| `/ws` `hello` | Private mode, allowed student ID, user ID and supported codecs retain the existing contract |
| `/ws` `text` | `{type: "text", text, tp, request_id?}` goes through the responder; receipt interrupts playback before queuing. Every successful browser text submission carries a unique request ID, including ordinary input. The backend accepts legacy packets without it; supplied IDs must be bounded nonempty strings and are echoed in initial/decision utterance events, distinct from the server uid. Correlated decisions include `applied`: false for superseded work; initial events omit it. Optional `lesson_context` must match stored subject/grade/title exactly |
| `/ws` voice | The browser sends a unique request ID on each successful `speech_start`; `audio_end` and the complete binary recording keep their existing shape. The backend captures the ID and input epoch at recording start, attaches them to the ASR utterance, and echoes the ID in transcript/utterance events. Newer input can supersede that recording's result. Supplied invalid IDs are rejected before interruption and their recording is discarded; legacy no-ID speech/audio remain supported |
| Pending exercise state | `exercise` is null, or `{concept, kind, question, options, option_texts, request_id?}`. The optional ID belongs to the activity that created the exercise. `options` remains the existing letter list; `option_texts` contains the actual complete choices. The reference answer and explanation are not exposed |
| Lesson and exercise events | `event: "lesson"` carries optional `data.request_id` through outline/section/planned, generation failures and checks/revisions. `exercise_open` includes the same exercise fields; closed/graded/grading-failed/timeout events retain the creating exercise's owner, while an answer's utterance events use the answer request ID. Uncorrelated events omit the field |
| Existing question recovery | `data.stage: "exercise_existing"` carries the current input's `request_id`, the original creator's `exercise_request_id` or null, and authoritative concept/kind/question/letter options/full option text. It reminds and restores the existing question without new generation or changing its creator. A new lesson request reminds the learner to finish an open standalone question instead of starting another lesson; replacing an exercise from the current lesson retains the existing lesson behavior |

School topic selection should use the topic endpoint rather than fabricated examples presented as a
catalogue. Its `basis` may be `textbook` or `estimate`; the title's inclusion does not verify the
quality of a generated explanation. Topics that the catalogue does not contain should remain
explicit custom requests.

The current teacher responder recognizes lesson and exercise requests through its Chinese instruction
contract. There is no typed section-jump or resumable pause API in this change. A lesson event with
stage `planned` means the sections were prepared; it does not mean that the student watched them or
mastered them. The CPU `RuleResponder` supports simple action/forget/chat responses and cannot create
lessons or exercises. Once session status identifies that responder, lesson and practice controls are
disabled with a truthful explanation; queued lesson requests are not sent to it.

## Implemented student flows

The classroom, profile and recording pages share edition selection. Query values are `primary`,
`secondary` and `university`; query selection takes precedence over browser storage, with `secondary`
as the configuration default. Changing editions updates the query and `liveAgent.edition` storage.
Private links retain the selected allowed learner ID and edition, including while a newly selected
profile is loading or unavailable; public links carry public mode
and omit learner identity. The language of stored
topics and profile values is not rewritten by an interface translation.

The classroom shows teacher video, a readable board, student selection, a conversation and the current
learning task. Subject, school-grade and search filters navigate the real topic response. Primary and
secondary grade-filter bounds are the configuration categories in the edition table; the English
edition exposes the same school catalogue with a coverage notice. Padded catalogue titles are trimmed
consistently before selection and packet construction, preserving their validated chapter context.
Choosing a chapter fills a topic
draft, and a custom topic remains a request rather than an invented catalogue entry. Lesson controls wait for an actual teaching responder before enabling. A selected chapter sends
a Chinese utterance plus a validated `lesson_context` containing its subject, school grade and exact
title. Both lesson and standalone-practice planning use that grade and subject in a local planning
context; they do not rewrite the learner’s persisted grade. Custom topics retain the ordinary text request.
Prepared outline/section notices describe preparation, without claiming viewing or completion.
If the responder handles a learning request as another kind of turn, the page says that the activity
did not start, including a custom lesson decision without a topic. A matching decision with `applied: false`
is reported as superseded. Only its matching request ID can resolve that request; late activity events
and exercise snapshots with a retired or mismatched owner are filtered before changing status or answer
controls. Lesson/practice buttons are blocked while a request is pending, while its generated practice question
waits to open, and while a question is open. Successful practice moves through preparation, open, closed
and reviewed states. An `exercise_existing` response correlated to the current input restores the authoritative
question and adopts its original creator for subsequent activity events. An ordinary text or voice
answer has its own unique submission ID while preserving that question's creator for grading and close.
The latest input awaiting activity evidence is tracked separately from the visible question's creator.
A matching activity event or exercise snapshot with a nonnull owner can adopt a replacement lesson,
preserving the backend's existing replacement behavior for exercises from the current lesson. A newer
input replaces that candidate; matching terminal outcomes retire it so delayed events cannot revive it.
Terminal handling checks decision-property presence or `applied: false` and reads the decision safely;
null/false decisions and a missing decision with `applied: false` also retire the matching candidate or
pending lesson/practice request.
Request-correlated panel errors retire only the matching pending request. Unrelated, missing or null
error IDs leave that request waiting; session-wide failure retains the existing connection lifecycle.
Generation failures replace waiting text with a retry explanation. Superseded practice
generation cannot open a question or emit a spoken error after a newer turn finishes.

Practice shows the real exercise question and full choices or a text-answer prompt. Answer feedback
persists after the pending question closes. The page retains conversation input, optional voice and
the existing audiovisual calibration; input composition, service errors and retry are handled without
moving technical diagnostics into the main learning flow. Diagnostics and test-livestream settings
start collapsed.

Changing learners immediately clears the previous classroom conversation, board/video, memory/events
and learning goal before a new session. Interface language changes preserve the active session,
question and feedback without replaying profile events.

Study notes are stored only in this browser and grouped by selected learner. Test livestream mode uses
a separate notes bucket and no student profile. Switching modes clears private drafts, chat, event
logs, cached media/boards, lesson goals, exercise announcements and progress indicators. The current
URL preserves the new mode across reloads, and public navigation hides private profiles. Public hello
omits the learner and uses a public memory namespace. Public mode also works without a private profile list.
Notes and the current conversation can be exported as
text. Browser storage is not authentication or secure account isolation on a shared device, and notes
are not sent to the student-profile API. A storage failure is disclosed so the student can export a
copy rather than assuming the notes were saved. A failed-save warning survives interface language changes.

The profile editor preserves validated edits, loaded-version checks, explicit reset confirmation and
draft protection while polling. Changing learners immediately blanks the previous learner’s visible
fields and disables writes until the matching profile loads; failed loads stay blank until retry.
In the English edition, the grade control uses canonical school-grade
values; an unsupported adult grade is displayed as a disclosed blank. Example profiles and existing
uncalibrated understanding estimates are labelled. The recording page requests `/api/traces?student=<allowed id>` or `?mode=public`, with the same
scope on playback, downloads and readable text. Private/public session metadata is recorded before
session work; unknown legacy attribution is excluded from scoped lists. A direct unscoped page asks
for a learner rather than calling the operator index. Readable text is a planned-script aid containing
exact logged input and teacher scripts, explicitly unverified against audio. Requests missing complete
chunk acknowledgements are omitted when the expected count is known; remaining scripts show
full-chunk-ACK or unknown evidence and may include words that were never spoken. Missing ACKs do not
establish that playback stopped. It is not captions or a reliable equivalent of the audio. Exact declared session
filenames take precedence over multipart naming, consistently in the index and file authorization.
This is scoped navigation for a trusted local service, not authenticated per-learner account isolation.

## Runtime and verification scope

The launcher now defaults to `PERSONA=teacher`; `PERSONA=hanfu` still selects the existing reading-host
persona. The frontend/backend separation, port configuration and GPU reservation rules are unchanged.
`scripts/run_live.sh demo` remains a CPU transport and interface demo. Real teaching needs a configured
responder model; GPU generation needs its existing model runtime and scheduler allocation.

```bash
# Supervised CPU preview with the teacher persona; no model or GPU reservation
scripts/run_live.sh demo

# Or start the two processes independently, in separate terminals
python3 -m live_agent.backend.app --config configs/persona_teacher \
  --generator mock --llm-url scripted --vlm-url mock --asr-url "" \
  --dev-allow-uncalibrated --record --host 127.0.0.1 --port 8201
HOST=127.0.0.1 PORT=8200 BACKEND_URL=http://127.0.0.1:8201 npm --prefix frontend start

# Isolated CPU browser check; requires Playwright and its Chromium installation
python3 scripts/student_frontend_check.py --shots .cache/student-ui-check
```

The addresses above are configuration examples. Open `/` with `?edition=primary`,
`?edition=secondary` or `?edition=university`; `/profile` and `/traces` accept the same edition query,
with `student=<allowed id>` for the selected profile context. `hybrid`, `full` and `omni` retain their
existing model/GPU requirements. They were not started for this student-interface validation.

Validation on 2026-10-02 (*measured locally*):

| Check | Result and practical scope |
|---|---|
| `npm --prefix frontend test` | 97 passed: frontend helpers/state, profile/recording behavior, all-submission request IDs, stale activity/state filtering, language/error/choice cleanup and server proxy checks |
| Full CPU Python suite after student7 repairs | 423 passed, 1 GPU-only skip; counted from saved pytest progress marks in `.cache/student-ui-check/python-tests.txt`. Includes backend, lesson/practice context, profile, scheduler and media contracts |
| Affected backend/exercise/catalogue-lesson/student/lesson suite after student7 repairs | 95 passed: catalogue context, exercise supersession/ownership, actual WS text and voice IDs, stale recording epochs, bounded text-only supersession, existing-question recovery, scoped media/partial-ACK evidence and existing profile/curriculum rules |
| `scripts/student_frontend_check.py --shots .cache/student10-ui` | Nine classroom edition/viewport cases and thirty-three behavior scenarios without page errors or overflow; notes persistence/separation/export and failed-save warning, CPU session lifecycle, pending/generated activity gate, retirement/recovery, replacement-lesson event/snapshot adoption, null/false/missing terminal decisions for candidates and pending requests, matching panel errors and creator-owned answers, language changes, learner/public boundary clearing, recovery and padded catalogue context. Saved results: `.cache/student10_frontend_check.json`; stderr is empty; previews: `.cache/student10-ui/classroom-{edition}-preview.png` |
| Profile and recording browser checks | 12 initial edition/viewport cases with no JavaScript errors or horizontal overflow, using isolated data |
| Scoped recording browser checks | 12 private/public edition/viewport cases; real scoped backend data and readable scripts; no JavaScript errors or overflow |
| Final profile/recording browser repairs | Delayed/failed learner switch stays blank and emits no writes; all three mobile editions display unknown/full-ACK and omitted-partial-script warnings without errors or overflow |
| Existing `scripts/lipsync_page_check.py` | All 12 page checks passed against an isolated teacher CPU/JPEG environment; preserves the audiovisual scheduling path |

Browser check counts above are measured test outcomes, not users or teaching experiments. The synthetic
lesson/exercise fixtures verify presentation and state handling; the CPU session verifies transport.
A measured pre-repair check in `.cache/manual-lesson-owner/` replayed actual backend events in the browser
and reproduced rejection of a replacement lesson's new owner. The final browser cases exercise that
event order plus snapshot adoption and retirement of obsolete inputs. The frontend repairs did not
change the backend or live transport; the Python and npm counts above retain their recorded scope.
Formal GPT-6 Sol source review completed through student9 and confirmed the named student8 major
repairs; the reviewer did not run the reported checks. The final minor terminal-decision guard was
repaired after review and passed direct browser cases, recorded separately in `docs/codex_reviews.md`.
The recording-text alternative remains partially accepted: planned scripts are not verified captions
or an audio equivalent. These checks do not establish learning efficacy, university curriculum coverage, English speech quality, real
model-backed lesson quality, GPU performance or physical audiovisual timing on a viewer's devices.
