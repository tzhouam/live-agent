Re-review the student frontend after student1. Read-only, no edits. The original numbered findings are supplied. Verify repair claims from the current source; identify unresolved blocking/major/minor issues with evidence. Do not equate test passes or author statements with independent verification. This is the owner-authorized local frontend product on an existing trusted loopback service, not a public deployment or new authentication system. Challenge any claim to account isolation, English teaching, university curriculum or media qualification.

Current repair intent:
1/6: Profile page gates loading/writing, pins writes to the loaded profile ID and generation, rejects stale completions. Controlled tests reproduce the pre-fix wrong-target writes and post-fix protection.
2/3/4: Mode change purges private visible content, unsent drafts, cached media/boards and selected chapter. Public hello omits learner identity; links omit student; public boot works without profile data.
5: Classroom clears both actual live profile and edit action during selection/failure and invalidates pre-session reads when connecting.
7: Chapter selections send exact subject/grade/title through validated lesson_context, with canonical topic and lesson-local profile/curriculum; original learner grade is retained. Free text remains unchanged.
8: Exercise generator says generic Chinese teacher with actual profile guidance instead of conflicting middle-school-only role.
9: Video and responder notices are separate; lesson start stays disabled before status and for rule responders.
10/13: Student recording views require learner or public scope. Declared first audit event attributes each new session. Scoped index/media/transcript enforce matching attribution; unknown legacy records are excluded. Unfiltered operator API remains compatible and is not called by student pages. Text is exact logged input and script for ACKed requests, expressly not verified audio transcription/captions. No account authentication or physical audio accuracy is claimed.
11/12: Dedicated polite live question announcement; exercise feedback persists after close/null; mastery evidence is visible, focusable and described rather than hover-only.
14/15: English student interface/evidence/basic diagnostics labels localized, factual curriculum and raw quoted log details retain their source language; recording intro says records, not saved study notes.

Validation evidence is local: frontend74passing tests at latest run; full CPU suite before new context/recording changes381passed and1GPUskip; newer affected backend checks running now. Classroom nine edition/viewport combinations and causal state/notes/privacy/recovery checks pass; profile/recording initial twelve combinations pass; scoped private/public recording twelve combinations pass; existing twelve AV checks passed before the later UI/metadata fixes. Explicit synthetic capability and exercise fixtures verify rendering/contracts, not model teaching. No GPU or real-LLM generation was run.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/reviews/student1_review.md =====
Findings from the inlined source and contracts. The reported mock-browser passes do not exercise the races or real teaching generation below.

1. **blocking — Profile switching can overwrite another learner’s record.** In [profile.js](/data/zhoutaichang/live-agent/frontend/public/assets/profile.js), the student change handler sets `sid` before `load()` finishes, while the old form and `server.version` remain editable. `save()` sends those old fields to the new student’s URL. Delay B’s GET, switch A→B, edit the still-visible form, and save; matching versions can write A’s data to B.

2. **blocking — Private session content survives a switch to public mode.** [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) clears the profile and changes the notes key, but does not clear the private chat, event log, memory, board, or `lessonTopic`. [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js) clears most of these only on the next connection; `lessonTopic` survives that too. End a private lesson, switch to public, then inspect/export the chat before connecting and inspect the topic afterward.

3. **major — Public mode still carries a private learner identity.** Private profile selection sets `uid` to `learner:<id>`; the public branch does not reset it, and the WebSocket hello always sends both `user_id` and `student`. Public mode also retains profile links containing the private student ID. Check the hello payload and links after switching modes; the supplied browser privacy check does not inspect either.

4. **major — Public mode is unusable without private profiles.** `bootstrap()` enables Connect only when `/api/students` returns a nonempty list, regardless of mode. A public session described as using no learner profile is therefore blocked if profiles are absent or that API fails. Check a healthy service with an empty student list.

5. **major — The classroom can display and reopen the wrong profile.** During an A→B selection, `selectProfile()` leaves A’s card and Edit button active until B’s GET resolves. If B’s GET fails, it replaces the card text but leaves [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js)’s `profile=A`, so Edit still opens A. The request counter prevents a late response; it does not fix this visible stale state.

6. **major — A save response can erase newer edits.** [profile.js](/data/zhoutaichang/live-agent/frontend/public/assets/profile.js) leaves fields editable during PUT, then unconditionally calls `render()` and `clean()` on success. Edit a field while the PUT is delayed: its response replaces and marks the newer draft clean.

7. **major — Selecting a catalogue chapter drops its grade and subject.** [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) displays those fields on a course card but stores only `topic.topic`; `requestLesson()` sends only that title. A Grade 3 card selected under a Grade 8 profile cannot reliably request the displayed chapter. Inspect the outgoing text for a cross-grade selection.

8. **major — The exercise generator conflicts with the primary edition.** [exercise.py](/data/zhoutaichang/live-agent/live_agent/exercise.py:22) instructs the model to act as a *middle-school teacher* for exercise generation, even when the UI offers primary-school practice. Its later instruction to use the student’s grade leaves conflicting guidance. The CPU RuleResponder and synthetic exercise events do not test generated primary-school questions.

9. **major — The preview notice combines independent capabilities.** `updateRuntime()` shows the same “placeholder video; lessons require a teaching model” notice for either a mock **video generator** or a rules **responder**. A mock-video session can have a teaching responder, and a rules session can use another generator. The lesson button is also enabled before connecting to a rules-only service, then disabled after status arrives. Check both mixed configurations.

10. **major — The recordings library crosses learner scope.** [traces.js](/data/zhoutaichang/live-agent/frontend/public/assets/traces.js) ignores its `student` query when fetching `/api/traces` and renders every returned recording and raw record link. The page discloses that it is service-wide, but that does not isolate private learners or public sessions. Check two private learners and one public recording in the same service.

11. **major — New exercise questions are not announced by the event UI.** On `exercise_open`, the question appears in a plain paragraph and answer buttons are replaced without moving focus or updating a live status. A screen-reader user focused in the composer gets no dependable announcement from this event. Check with an exercise event while focus remains in the input; tutor audio may happen to provide the question, but the event path does not.

12. **major — Evidence for classroom mastery estimates depends on hover.** `showProfile()` puts each concept’s source and attempt counts in a `title` attribute on a nonfocusable `.cp` element, while the heading says to hover for evidence. Touch and keyboard users cannot reliably inspect the basis for the percentages. Check a concept-bearing profile at the mobile viewport and by keyboard.

13. **major, pending media check — Recording playback has no in-page text alternative.** `recordingCard()` creates `<video controls>` with no caption track or readable transcript; the only text artifact is a raw JSONL download. Inspect a saved recording for captions and verify a learner can follow the spoken lesson without audio.

14. **minor — Some English interface labels remain Chinese.** The university edition translates page copy, but [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js) hard-codes profile evidence labels, capability badges, and diagnostic events in Chinese. These are interface labels, separate from the disclosed Chinese curriculum and teacher speech.

15. **minor — The English recordings page promises notes it does not show.** Its introduction says users can find saved “videos and notes,” while [traces.js](/data/zhoutaichang/live-agent/frontend/public/assets/traces.js) renders videos and session records only; study notes live in browser storage on the classroom page.
===== FILE: docs/student_frontend.md =====
# Student frontend: research and implementation notes

Owner request, 2026-10-02: make the frontend a student product with primary-school and secondary-school
editions in Chinese, and a university/adult edition in English. This document records the inspected
contracts, design references and implemented student flows. The student page and CPU/browser validation
are complete; formal GPT-6 Sol review is pending. The edition names and grade ranges below are product
configuration categories, not efficacy claims.

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
| `/ws` `text` | `{type: "text", text, tp}` goes through the responder; receipt interrupts playback before queuing the request. A topic-selection action requests a lesson through this text contract; optional `lesson_context` must match the stored subject/grade/title exactly |
| Pending exercise state | `exercise` is null, or `{concept, kind, question, options, option_texts}`. `options` remains the existing letter list; `option_texts` contains the actual complete choices. The reference answer and explanation are not exposed |
| Exercise event | `event: "lesson"`, `data.stage: "exercise_open"` includes the same exercise fields. `exercise_closed` removes the answer prompt; `exercise_graded` records the existing grading result |

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
Private links retain the selected allowed learner ID and edition; public links carry public mode
and omit learner identity. The language of stored
topics and profile values is not rewritten by an interface translation.

The classroom shows teacher video, a readable board, student selection, a conversation and the current
learning task. Subject, school-grade and search filters navigate the real topic response. Primary and
secondary grade-filter bounds are the configuration categories in the edition table; the English
edition exposes the same school catalogue with a coverage notice. Choosing a chapter fills a topic
draft, and a custom topic remains a request rather than an invented catalogue entry. Lesson controls wait for an actual teaching responder before enabling. A selected chapter sends
a Chinese utterance plus a validated `lesson_context` containing its subject, school grade and exact
title. The planner uses that grade and subject only for this lesson; it does not rewrite the learner’s
persisted grade. Custom topics retain the ordinary text request.
Prepared outline/section notices describe preparation, without claiming viewing or completion.

Practice shows the real exercise question and full choices or a text-answer prompt. Answer feedback
persists after the pending question closes. The page retains conversation input, optional voice and
the existing audiovisual calibration; input composition, service errors and retry are handled without
moving technical diagnostics into the main learning flow. Diagnostics and test-livestream settings
start collapsed.

Study notes are stored only in this browser and grouped by selected learner. Test livestream mode uses
a separate notes bucket and no student profile. Switching modes clears private drafts, chat, event
logs, cached media/boards and lesson goals; public hello omits the learner and uses a public memory
namespace. Public mode also works without a private profile list. Notes and the current conversation can be exported as
text. Browser storage is not authentication or secure account isolation on a shared device, and notes
are not sent to the student-profile API. A storage failure is disclosed so the student can export a
copy rather than assuming the notes were saved.

The profile editor preserves validated edits, loaded-version checks, explicit reset confirmation and
draft protection while polling. In the English edition, the grade control uses canonical school-grade
values; an unsupported adult grade is displayed as a disclosed blank. Example profiles and existing
uncalibrated understanding estimates are labelled. The recording page requests `/api/traces?student=<allowed id>` or `?mode=public`, with the same
scope on playback, downloads and readable text. Private/public session metadata is recorded before
session work; unknown legacy attribution is excluded from scoped lists. A direct unscoped page asks
for a learner rather than calling the operator index. Readable text contains exact logged input and
scripts for requests acknowledged as presented, explicitly unverified against the audio. This is
scoped navigation for a trusted local service, not authenticated per-learner account isolation.

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
| `npm --prefix frontend test` | 74 passed: frontend helpers/state, profile/recording behavior and server proxy checks |
| Focused Python backend/launcher/student/curriculum suite | 65 passed: stored-topic provenance and grade coverage, empty data, real pending-exercise payloads without reference answers, teacher default and explicit reading-host override, and existing profile/curriculum rules |
| `scripts/student_frontend_check.py` | Nine classroom edition/viewport cases with no JavaScript errors or horizontal overflow; browser-local notes persistence, learner separation and export; CPU session lifecycle; synthetic capability/lesson/exercise rendering, delayed private-profile privacy, identity, independent video/responder gating and recovery checks |
| Profile and recording browser checks | 12 initial edition/viewport cases with no JavaScript errors or horizontal overflow, using isolated data |
| Scoped recording browser checks | 12 private/public edition/viewport cases; real scoped backend data and readable scripts; no JavaScript errors or overflow |
| Existing `scripts/lipsync_page_check.py` | All 12 page checks passed against an isolated teacher CPU/JPEG environment; preserves the audiovisual scheduling path |

Browser check counts above are measured test outcomes, not users or teaching experiments. The synthetic
lesson/exercise fixtures verify presentation and state handling; the CPU session verifies transport.
Formal GPT-6 Sol review remains pending and will be recorded in `docs/codex_reviews.md`. These checks
do not establish learning efficacy, university curriculum coverage, English speech quality, real
model-backed lesson quality, GPU performance or physical audiovisual timing on a viewer's devices.

===== FILE: frontend/public/index.html =====
<!doctype html>
<html lang="zh-CN" data-edition="secondary">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#276653"><meta name="description" content="芽学：选一节课，听讲解，提问题，练一练。"><title>芽学 · 私人课堂</title><link rel="stylesheet" href="/assets/live.css"></head>
<body>
<a class="skip-link" href="#classroom" data-i18n="skip">跳到课堂</a>
<svg class="icon-defs" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs>
<symbol id="i-book" viewBox="0 0 24 24"><path d="M12 5v16m0-16C8 2 3 3 3 3v16s5-1 9 2c4-3 9-2 9-2V3s-5-1-9 2Z"/></symbol>
<symbol id="i-grid" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></symbol>
<symbol id="i-user" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></symbol>
<symbol id="i-play" viewBox="0 0 24 24"><path d="m9 5 11 7-11 7V5Z"/></symbol>
<symbol id="i-arrow" viewBox="0 0 24 24"><path d="M4 12h16m-6-6 6 6-6 6"/></symbol>
<symbol id="i-help" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01"/></symbol>
<symbol id="i-check" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></symbol>
<symbol id="i-leaf" viewBox="0 0 24 24"><path d="M5 19c-3-9 2-15 15-15 0 13-6 18-15 15Zm0 0L15 9"/></symbol>
</defs></svg>
<div class="app-shell">
<aside class="sidebar" aria-label="主导航" data-i18n-aria="navigation">
<a class="brand" href="/" aria-label="芽学首页"><span class="brand-mark"><svg><use href="#i-leaf"/></svg></span><span><strong data-i18n="brand">芽学</strong><small>LIVE AGENT</small></span></a>
<div class="sidebar-label" data-i18n="mySpace">我的学习空间</div>
<nav class="navigation"><a class="nav-item active" aria-label="私人课堂" data-i18n-aria="classroom" href="#classroom" aria-current="page"><svg><use href="#i-book"/></svg><span data-i18n="classroom">私人课堂</span></a><a class="nav-item" aria-label="探索课程" data-i18n-aria="courses" href="#courses"><svg><use href="#i-grid"/></svg><span data-i18n="courses">探索课程</span></a><a class="nav-item" id="profileNav" aria-label="学习档案" data-i18n-aria="profile" href="/profile"><svg><use href="#i-user"/></svg><span data-i18n="profile">学习档案</span></a><a class="nav-item" id="tracesNav" aria-label="课堂记录" data-i18n-aria="recordings" href="/traces"><svg><use href="#i-play"/></svg><span data-i18n="recordings">课堂记录</span></a></nav>
<div class="sidebar-note"><span>✦</span><p id="sidebarNote">每一个好问题，<br>都是进步的开始。</p></div>
<button class="nav-item help-button" id="helpOpen" aria-label="使用指南" data-i18n-aria="help"><svg><use href="#i-help"/></svg><span data-i18n="help">使用指南</span></button><div class="service-indicator"><i id="serviceDot"></i><span id="serviceStatus" role="status">正在检查课堂…</span></div>
</aside>
<div class="workspace">
<header class="topbar"><div class="breadcrumb"><span data-i18n="mySpace">我的学习空间</span><span aria-hidden="true">/</span><strong data-i18n="classroom">私人课堂</strong></div><label class="edition-control"><span data-i18n="experience">学习体验</span><select id="edition" aria-label="学习体验"><option value="primary">小学 · 中文</option><option value="secondary" selected>初高中 · 中文</option><option value="university">University & adult · English</option></select></label></header>
<main>
<section class="welcome" aria-labelledby="welcomeTitle"><div class="welcome-copy"><span class="eyebrow" id="welcomeEyebrow">给好奇心一点空间</span><h1 id="welcomeTitle">今天，想弄懂什么？</h1><p id="welcomeDescription">从一个问题开始。和 AI 老师一起，把复杂的知识慢慢理清。</p><div class="welcome-tags"><span><svg><use href="#i-check"/></svg><span data-i18n="tagAsk">随时提问</span></span><span><svg><use href="#i-check"/></svg><span data-i18n="tagPractice">边学边练</span></span><span><svg><use href="#i-check"/></svg><span data-i18n="tagPace">按你的节奏</span></span></div></div><svg class="welcome-art" viewBox="0 0 300 180" aria-hidden="true"><circle cx="158" cy="91" r="79" fill="#e5edce"/><circle cx="242" cy="43" r="8" fill="#eac87c"/><path d="m61 33 3 9 9 3-9 3-3 9-3-9-9-3 9-3Z" fill="#276653"/><path d="M93 58c22-8 44-4 62 8 18-12 40-16 62-8v86c-25-8-45-6-62 6-17-12-37-14-62-6V58Z" fill="#fffdf8" stroke="#276653" stroke-width="3" stroke-linejoin="round"/><path d="M155 66v84m-44-70c11-1 19 1 28 5m-28 11c11-1 19 1 28 5m-28 11c11-1 19 1 28 5m31-34c11-5 20-6 30-5m-30 21c11-5 20-6 30-5m-30 21c11-5 20-6 30-5" fill="none" stroke="#b4c7b1" stroke-width="3" stroke-linecap="round"/><path d="m208 133 20-59 12 4-20 59-12 11Z" fill="#eac87c" stroke="#276653" stroke-width="2"/><path d="m244 112 4 12 12 4-12 4-4 12-4-12-12-4 12-4Z" fill="#276653"/><ellipse cx="151" cy="164" rx="92" ry="5" fill="#276653" opacity=".08"/></svg></section>
<div class="connection-error" id="connectionError" role="alert" hidden><span id="connectionErrorText"></span><button id="connectionRetry" data-i18n="retry">重试</button></div><div class="notice" id="runtimeNotice" role="status" hidden></div>
<div id="exerciseAnnouncement" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>
<div class="learning-grid">
<section class="classroom-card card" id="classroom" aria-labelledby="classroomHeading" tabindex="-1">
<div class="card-heading"><div><span class="eyebrow" data-i18n="liveRoom">YOUR LIVE CLASSROOM</span><h2 id="classroomHeading" data-i18n="classroom">私人课堂</h2></div><span class="badge" id="conn" role="status">待开始</span></div>
<div class="room-meta"><span class="teacher-avatar" aria-hidden="true">✦</span><div><strong id="title">AI 学习伙伴</strong><span id="sessionHint" data-i18n="roomHint">选好学习档案，准备开始吧</span></div><span class="private-label" data-i18n="private">私人会话</span></div>
<div class="stagerow"><div class="screen" id="screenWrap"><canvas id="screen" width="480" height="864" aria-label="AI 老师视频" data-i18n-aria="video"></canvas><div class="video-decoration" aria-hidden="true"><svg><use href="#i-leaf"/></svg><span>LIVE AGENT</span></div><div class="overlay" id="overlay">课堂准备好了<br>点击「进入课堂」与老师见面</div><div class="avflash" id="avFlash" aria-hidden="true"></div></div><section class="board on" id="board" aria-label="课堂板书" data-i18n-aria="board"><h3 id="boardTitle" data-i18n="boardTitle">留一点空间，给新知识</h3><div class="body"><ol id="boardItems"><li data-i18n="boardIntro">老师的讲解要点会出现在这里。</li><li data-i18n="boardAsk">听不懂时，随时提问。</li><li data-i18n="boardPractice">学完一个知识点，再试着练一练。</li></ol><figure><img id="boardImg" alt="课程配图"><figcaption id="boardCap"></figcaption></figure></div><span class="board-signature">learn · ask · grow</span></section></div>
<div class="caption" id="caption" aria-live="polite"></div>
<div class="session-controls"><label class="student-picker" for="sid"><svg aria-hidden="true"><use href="#i-user"/></svg><span data-i18n="learner">学习档案</span><select id="sid" disabled><option value="">正在加载…</option></select></label><a href="/profile" id="profLink" data-i18n="editProfile">编辑档案</a><div class="session-actions"><button class="primary" id="connect" disabled data-i18n="connect">进入课堂 ↗</button><button id="disconnect" disabled data-i18n="disconnect">结束</button></div></div>
<div class="composer"><label class="sr-only" for="text" data-i18n="inputLabel">向老师提问</label><input type="text" id="text" maxlength="4000" placeholder="把你的问题写在这里…" disabled autocomplete="off"><button class="primary send-button" id="send" disabled data-i18n-aria="send"><svg aria-hidden="true"><use href="#i-arrow"/></svg><span data-i18n="send">发送</span></button></div>
<div class="input-toolbar"><button class="talk" id="talk" disabled data-i18n="talk">按住说话</button><button id="cam" hidden>开启专注检测</button><video id="camView" class="camview" muted playsinline hidden aria-label="摄像头预览"></video><button id="avBtn" aria-expanded="false" aria-controls="avPanel" data-i18n="avButton">声音与画面</button><span class="input-hint" data-i18n="inputHint">回车发送 · 新问题会打断当前讲解</span></div>
<div class="avsync" id="avPanel" hidden><label for="avOffset" data-i18n="avOffset">画面延后</label><input type="range" id="avOffset" min="-300" max="300" step="10" value="0" aria-describedby="avHelp"><output id="avOffsetV" for="avOffset">0 ms</output><button id="avTest" data-i18n="avTest">测试闪光与声音</button><button id="avReset" data-i18n="avReset">重置</button><p class="meta" id="avHelp" data-i18n="avHelp">若声音比画面慢，请向右调节；若画面比声音慢，请向左调节。设置保存在这个浏览器中，更换耳机后可以重新测试。</p><div class="meta" id="avInfo"></div></div>
<div class="suggestion-label" id="suggestionLabel" data-i18n="tryAsk">不知道怎么开口？试试这样问</div><div class="chips" id="chips" aria-label="提问建议" data-i18n-aria="suggestions"></div><p class="room-footnote" data-i18n="aiNotice">AI 讲解和练习反馈可能有误，重要内容请结合教材核对。</p>
</section>
<aside class="study-panel">
<section class="card lesson-card" aria-labelledby="lessonHeading"><div class="card-heading"><h2 id="lessonHeading" data-i18n="todayGoal">从一个目标开始</h2><svg class="small-icon"><use href="#i-book"/></svg></div><p class="meta" id="lessonHelp" data-i18n="lessonHelp">先进入课堂，再开始学习或练习。</p><label for="lessonTopic" data-i18n="topicLabel">今天想学</label><input id="lessonTopic" type="text" maxlength="80" placeholder="例如：一次函数" aria-describedby="lessonHelp"><button class="primary wide" id="startLesson" disabled data-i18n="startLesson">开始这节课 →</button><p class="meta" id="lessonStatus" role="status" data-i18n="lessonEmpty">也可以从下方课程中选一个知识点。</p><ol class="learning-steps"><li id="stepChoose" class="current"><span>✓</span><div><strong data-i18n="stepChoose">选个目标</strong><small data-i18n="stepChooseHelp">告诉老师，你想弄懂什么</small></div></li><li id="stepLearn"><span>○</span><div><strong data-i18n="stepLearn">一起学懂</strong><small data-i18n="stepLearnHelp">看板书，听讲解，随时问</small></div></li><li id="stepPractice"><span>○</span><div><strong data-i18n="stepPractice">试一试</strong><small data-i18n="stepPracticeHelp">做一道题，看看理解得怎样</small></div></li></ol><button class="text-button" id="practice" disabled data-i18n="practice">给我一道练习题 ↗</button></section>
<section class="card exercise-card" id="exerciseCard" hidden aria-labelledby="exerciseHeading"><span class="eyebrow" data-i18n="yourTurn">轮到你啦</span><h2 id="exerciseHeading" data-i18n="exercise">课堂练习</h2><p id="exerciseQuestion"></p><div id="exerciseFeedback" role="status"></div><p class="meta" data-i18n="exerciseHelp">用课堂下方的选项或输入框作答。</p></section>
<section class="card prof" id="profCard"><div class="card-heading"><h2 data-i18n="profileGlance">我的学习档案</h2><button class="text-button" id="profEdit" hidden data-i18n="manage">编辑 ↗</button></div><div id="prof"><div class="empty" data-i18n="profileEmpty">选择档案后，查看年级、成绩和学习记录。</div></div><p class="meta profile-disclaimer" id="profileDisclaimer"></p></section>
<section class="gentle-note"><span aria-hidden="true">✧</span><p id="gentleMessage">不用一次就会。<br>把不懂的地方，变成下一个问题。</p></section>
</aside>
</div>
<section class="course-section" id="courses" aria-labelledby="courseHeading"><div class="section-heading"><div><span class="eyebrow" data-i18n="discover">A LITTLE CURIOSITY GOES A LONG WAY</span><h2 id="courseHeading" data-i18n="courseHeading">找到你想学的下一课</h2></div><button class="text-button" id="catalogueRetry" hidden data-i18n="retry">重试</button></div><p class="meta" id="catalogueNote" data-i18n="catalogueNote">课程建议来自已接入的中国中小学课程库。</p><div class="course-filters"><label><span data-i18n="subject">学科</span><select id="subjectFilter"><option value="" data-i18n="allSubjects">全部学科</option></select></label><label><span data-i18n="grade">年级</span><select id="gradeFilter"></select></label><label class="course-search"><span class="sr-only" data-i18n="searchCourses">搜索课程</span><input type="search" id="courseSearch" placeholder="搜索一个知识点…" data-i18n-placeholder="searchPlaceholder"></label></div><div class="course-list" id="courseList" aria-live="polite"><p class="empty" data-i18n="coursesLoading">正在加载课程…</p></div><button class="text-button more-courses" id="moreCourses" hidden data-i18n="moreCourses">查看更多课程 ↓</button></section>
<div class="reflection-grid"><section class="card conversation-card"><div class="card-heading"><h2 data-i18n="conversation">课堂对话</h2><button class="text-button" id="exportChat" data-i18n="export">导出</button></div><div class="chat" id="chat" role="log" aria-live="polite" aria-relevant="additions"><div class="empty" data-i18n="conversationEmpty">你的问题和老师的讲解，会留在这里。</div></div></section><section class="card notes-card"><div class="card-heading"><h2 data-i18n="notes">我的随手记</h2><span class="note-save" id="noteStatus" role="status" data-i18n="localOnly">仅保存于本浏览器</span></div><label class="sr-only" for="notes" data-i18n="notes">我的随手记</label><textarea id="notes" placeholder="一个新思路，一句还想追问的话…" data-i18n-placeholder="notesPlaceholder" maxlength="20000"></textarea><div class="notes-footer"><span class="meta" data-i18n="notesHelp">笔记按档案保存在当前设备。</span><button class="text-button" id="exportNotes" data-i18n="export">导出</button></div></section></div>
<details class="diagnostics" id="diagnostics"><summary data-i18n="diagnostics">课堂设置与技术诊断</summary><div class="diagnostic-grid"><div class="card"><h2 data-i18n="sessionSettings">会话设置</h2><div class="settings-row"><label><span data-i18n="sessionMode">模式</span><select id="mode"><option value="private">私人课堂</option><option value="public">测试直播 · 不读取档案</option></select></label><label><span data-i18n="memoryIdentity">记忆标识</span><input type="text" id="uid" value="" maxlength="100"></label></div><p class="meta" data-i18n="settingsHelp">测试直播不读取学生档案。记忆标识只关联会话记忆，不是登录账号。</p><div class="badges" id="badges"></div><div class="focusline" id="focus">专注检测：未开启</div><p class="meta" data-i18n="cameraHelp">专注检测需主动开启摄像头；画面用于判断状态，不保存。</p></div><div class="card"><h2 data-i18n="metrics">运行诊断 · 本地测量 / 估计</h2><div class="stats"><div class="stat"><b id="sLatency">–</b><span>Onset (s) · measured</span></div><div class="stat"><b id="sLambda">–</b><span>Λ (s) · estimate</span></div><div class="stat"><b id="sReq">–</b><span>Requests · measured</span></div><div class="stat"><b id="sVerified">0</b><span>Verified · measured</span></div><div class="stat"><b id="sRepairs">0</b><span>Repairs · measured</span></div><div class="stat"><b id="sRtt">–</b><span>RTT (ms) · measured</span></div></div><p class="meta" data-i18n="metricsHelp">开口时间按音频能量起点测量，不代表回答正确。模拟判定不能验证真实动作。</p></div><div class="card"><h2 data-i18n="intent">指令状态</h2><div id="chains"><div class="empty">–</div></div><div class="meta" id="flags"></div></div><div class="card"><h2 data-i18n="timeline">事件记录</h2><div class="feed" id="feed"><div class="empty">–</div></div></div><div class="card"><h2 data-i18n="memory">会话记忆</h2><div id="memory" class="feed"><div class="empty">–</div></div></div></div></details>
</main>
<footer><span data-i18n="footer">芽学 · 带着问题来，带着理解走。</span><span data-i18n="footerDetail">由 Live Agent 提供 AI 课堂</span></footer>
</div></div>
<dialog id="helpDialog" aria-labelledby="helpTitle"><div class="dialog-heading"><h2 id="helpTitle" data-i18n="help">使用指南</h2><button id="helpClose" aria-label="关闭" data-i18n-aria="close">×</button></div><ol class="help-steps"><li data-i18n="helpOne">选择学习档案，再点击「进入课堂」。</li><li data-i18n="helpTwo">选择课程或写下主题，点击「开始这节课」。也可以直接在输入框提问。</li><li data-i18n="helpThree">听不懂时随时打断；老师出题后，用选项或文字作答。</li><li data-i18n="helpFour">档案可编辑、删除学习记录或恢复示例。笔记只保存在当前浏览器。</li></ol><p class="meta" data-i18n="helpLimit">英语版切换界面语言；课程库当前为中国中小学内容。语音和视频是否可用取决于服务配置。</p><p class="meta" data-i18n="privacyHelp">这是受信任设备上的本地课堂，没有学生登录或账号隔离。课堂记录可能包含对话，使用共享设备时请谨慎填写个人信息。</p></dialog>
<noscript><p class="connection-error">请启用 JavaScript 以使用课堂。 / Enable JavaScript to use the classroom.</p></noscript>
<script src="/assets/api.js"></script><script src="/assets/product.js"></script><script src="/assets/live.js"></script>
</body></html>

===== FILE: frontend/public/assets/product.js =====
// Student experience: data, navigation and edition copy. Streaming stays in live.js.
(() => {
  const el = id => document.getElementById(id);
  const editions = ['primary', 'secondary', 'university'];
  const storage = {get(key) { try { return localStorage.getItem(key); } catch { return null; } }, set(key,value) { try { localStorage.setItem(key,value); return true; } catch { return false; } }};
  const query = new URLSearchParams(location.search);
  let edition = editions.includes(query.get('edition')) ? query.get('edition') : storage.get('liveAgent.edition');
  if (!editions.includes(edition)) edition = 'secondary';
  let connection = 'disconnected', status = null, serviceReady = false, studentsReady = false;
  let students = [], topics = [], catalogueFailed = false, limit = 6, pendingLesson = null, profileRequest = 0, selectedProfile = null;
  let noteKey = null, loadingProfile = false, recentExercise = null, healthInfo = null, bootstrapAttempt = 0, selectedTopic = null;
  const originals = new Map(), originalAttributes = new Map();
  document.querySelectorAll('[data-i18n-aria]').forEach(node=>originalAttributes.set(node,node.getAttribute('aria-label')));
  document.querySelectorAll('[data-i18n]').forEach(node => originals.set(node,node.textContent));
  const en = {
    skip:'Skip to classroom',navigation:'Main navigation',brand:'YāLearn',mySpace:'My learning space',classroom:'Live classroom',courses:'Explore topics',profile:'Learning profile',recordings:'Session recordings',help:'Quick guide',experience:'Experience',tagAsk:'Ask freely',tagPractice:'Learn & practice',tagPace:'Your own pace',retry:'Try again',liveRoom:'YOUR LIVE CLASSROOM',roomHint:'Choose a learner profile to get started',private:'Private session',video:'AI tutor video',board:'Lesson board',boardTitle:'A little space for a new idea',boardIntro:'Your tutor’s key points will appear here.',boardAsk:'Ask a question whenever you need.',boardPractice:'Try a practice question as you learn.',learner:'Learner',editProfile:'Edit profile',connect:'Enter classroom ↗',disconnect:'End session',inputLabel:'Ask your tutor',send:'Send',talk:'Hold to speak',avButton:'Audio / video sync',inputHint:'Enter to send · A new question interrupts playback',avOffset:'Video delay',avTest:'Test flash & sound',avReset:'Reset',avHelp:'If the sound is late, move right. If the picture is late, move left. This setting stays in this browser; test again after changing headphones.',tryAsk:'A starting point for your next question',suggestions:'Suggested questions',aiNotice:'AI explanations and grading can be wrong. Check important details against your course materials.',todayGoal:'Start with a learning goal',lessonHelp:'Enter your classroom, then request an explanation or practice.',topicLabel:'I want to understand',startLesson:'Start a lesson →',lessonEmpty:'Choose a topic below, or enter your own question.',stepChoose:'Choose a goal',stepChooseHelp:'Make your next learning task clear',stepLearn:'Explore the idea',stepLearnHelp:'Follow the board and ask questions',stepPractice:'Check your understanding',stepPracticeHelp:'Try a question and reflect on feedback',practice:'Request a practice question ↗',yourTurn:'YOUR TURN',exercise:'Practice question',exerciseHelp:'Use the choices below the classroom or type your answer.',profileGlance:'My learning profile',manage:'Edit ↗',profileEmpty:'Select a profile to see your learning records.',discover:'FOLLOW YOUR CURIOSITY',courseHeading:'Explore a topic worth understanding',catalogueNote:'Available catalogue: Chinese school subjects. Chapter titles and teaching are currently in Chinese; university courses are not included.',subject:'Subject',grade:'School grade',allSubjects:'All subjects',searchCourses:'Search topics',searchPlaceholder:'Search a chapter title…',coursesLoading:'Loading available topics…',moreCourses:'Show more topics ↓',conversation:'Classroom conversation',export:'Export',conversationEmpty:'Your questions and your tutor’s responses appear here.',notes:'My study notes',localOnly:'Stored in this browser only',notesPlaceholder:'An idea to remember. A question to revisit…',notesHelp:'Notes stay on this device, grouped by learner.',diagnostics:'Classroom settings & technical details',sessionSettings:'Session settings',sessionMode:'Mode',memoryIdentity:'Memory identifier',settingsHelp:'Test livestream mode does not use a student profile. The memory identifier connects session memories; it is not a login.',cameraHelp:'Focus check requires camera permission. Images are analyzed without being saved.',metrics:'Runtime diagnostics · measurements / estimates',metricsHelp:'Onset is measured from audio energy; it does not measure answer correctness. Simulated judging does not verify real actions.',intent:'Instruction state',timeline:'Event log',memory:'Session memory',footer:'YāLearn · Bring a question. Leave with understanding.',footerDetail:'AI classroom by Live Agent',close:'Close',helpOne:'Choose a learner profile, then enter the classroom.',helpTwo:'Choose a topic or enter a goal, then request a lesson. You can also type a question directly.',helpThree:'Interrupt to ask for clarification. Use the choices or text box to answer a practice question.',helpFour:'Edit or reset the profile and learning history. Notes are stored only in this browser.',helpLimit:'This edition translates the interface. The current curriculum covers Chinese school subjects and the teacher speaks Mandarin. Voice and video depend on service configuration.',privacyHelp:'This is a local classroom for trusted devices, without student authentication or account isolation. Recordings may include conversations; take care with personal information on shared devices.',
    ready:'Classroom available',unavailable:'Classroom unavailable',checking:'Checking classroom…',idle:'Ready when you are',connecting:'Preparing your classroom…',ended:'Session ended. Start again whenever you’re ready.',readyHint:'Your tutor is ready. Ask your first question.',demoProfile:'Example profile · Sample records are not your assessment.',profileEvidence:'Understanding values are uncalibrated estimates from the stored profile.',profileLoadFailed:'Could not load this profile. Try selecting it again.',studentsFailed:'Could not load learner profiles. Check that the backend is running, then try again.',serviceFailed:'The classroom service is not available. Start the backend and try again.',mockNotice:'Preview mode: placeholder video. Simple conversation is available; lesson and exercise generation require a configured teaching model.',languageNotice:'English interface · The current teaching language and school catalogue are Chinese. University course coverage is not available.',rulesLesson:'This preview cannot create lessons or practice questions. Configure a teaching model to use these actions.',noTeacher:'This persona does not support classroom lessons. Start the service with PERSONA=teacher.',selectGoal:'Enter a topic first.',lessonWaiting:'Preparing your lesson request…',lessonSent:'Lesson requested. Waiting for the tutor’s plan…',lessonPrepared:'Lesson material is prepared. Follow the live explanation.',lessonFailed:'The lesson could not be prepared. Ask a smaller question or try again.',outlineReady:'Your lesson plan is ready:',sectionReady:'Prepared section:',practiceWaiting:'Practice requested. Waiting for the question…',practiceClosed:'This question is closed. Ask for another when you’re ready.',correct:'The tutor marked this answer correct.',incorrect:'The tutor marked this answer incorrect. Ask for a hint and try again.',skipped:'You chose to skip. Ask the tutor to explain the idea.',gradingFailed:'The answer could not be graded. Ask the tutor to try again.',exercisePending:'A practice question is waiting for your answer.',noTopics:'No matching topics. Try another grade or subject, or enter a custom goal.',catalogueError:'The topic catalogue could not be loaded.',allGrades:'All school grades',topicAction:'Choose topic ↗',textbook:'Textbook chapter',estimate:'Estimated placement',reference:'Catalogue reference',customTopic:'Custom topic request',emptyExport:'There is nothing to export yet.',noteSaved:'Saved on this device',noteFailed:'Could not save. Export your notes to keep a copy.',savedExample:'Example profile',noProfiles:'No learner profiles are available. Ask the operator to configure one.',publicMode:'Test livestream · No learner profile',localStorageHelp:'Notes could not be loaded from this browser. Export any new notes before leaving.'
  };
  const zh = {ready:'课堂服务可用',unavailable:'课堂服务不可用',checking:'正在检查课堂…',idle:'课堂准备好了',connecting:'正在准备课堂…',ended:'课堂已结束，随时可以重新开始。',readyHint:'老师准备好了，说说你的第一个问题吧。',demoProfile:'示例档案 · 这里的样例记录不是你的测评结果。',profileEvidence:'理解程度为档案中的估计值，尚未校准。',profileLoadFailed:'档案暂时加载失败，请重新选择。',studentsFailed:'学习档案加载失败，请确认后端运行后重试。',serviceFailed:'课堂服务暂时不可用，请启动后端后重试。',mockNotice:'演示模式：当前是占位视频，可体验简单对话；生成课程和练习需要配置教学模型。',rulesLesson:'当前演示不能生成课程和练习。启用教学模型后即可使用。',noTeacher:'当前人设不支持教学课程，请以 PERSONA=teacher 启动服务。',selectGoal:'先写下你想学的主题吧。',lessonWaiting:'正在准备你的课程请求…',lessonSent:'已请求课程，等待老师准备大纲…',lessonPrepared:'课程内容已备好，请跟随老师的实时讲解。',lessonFailed:'备课暂时失败了，可以换一个更具体的问题再试。',outlineReady:'课程大纲已准备：',sectionReady:'已备好：',practiceWaiting:'已请求练习，正在等待题目…',practiceClosed:'这道练习已结束，准备好后可以再来一道。',correct:'老师判定这次作答正确。',incorrect:'老师判定这次作答有误，可以请老师给你一个提示。',skipped:'这次先跳过，可以请老师再讲一遍思路。',gradingFailed:'这次未能完成批改，可以请老师重试。',exercisePending:'有一道练习在等你作答。',noTopics:'没有找到匹配课程，试试其他年级、学科，或直接填写学习目标。',catalogueError:'课程目录暂时加载失败。',allGrades:'全部年级',topicAction:'选这个主题 ↗',textbook:'教材章节',estimate:'年级归属为估计',reference:'课程目录参考',customTopic:'自选主题请求',emptyExport:'还没有可以导出的内容。',noteSaved:'已保存到当前设备',noteFailed:'保存失败，请导出笔记以保留内容。',savedExample:'示例档案',noProfiles:'尚未配置学习档案，请联系服务维护者。',publicMode:'测试直播 · 不读取学习档案',localStorageHelp:'无法读取本浏览器中的笔记，离开前请导出新笔记。'};
  const primary = {classroom:'我的小课堂',courses:'找点新知识',profile:'我的学习卡',recordings:'看看课堂记录',todayGoal:'今天想学什么呀？',lessonHelp:'先和老师见个面，再开始学一学。',topicLabel:'我想知道',startLesson:'和老师一起学 →',stepChoose:'选一个小目标',stepChooseHelp:'你想知道什么呀？',stepLearn:'一起找答案',stepLearnHelp:'看一看，听一听，不懂就问',stepPractice:'动手试一试',stepPracticeHelp:'答一道题，说说你的想法',practice:'老师，给我一道题 ↗',courseHeading:'下一个发现，等着你',tryAsk:'可以这样问老师',inputHint:'回车发送 · 想提问，随时打断老师'};
  function t(key, fallback='') { return (edition === 'university' ? en[key] : (edition === 'primary' ? primary[key] ?? zh[key] : zh[key])) ?? fallback; }
  function examples() {
    if (edition === 'university') return [{label:'Walk me through an example',text:'请给我讲一道例题'}, {label:'Explain that step again',text:'这一步我还没明白，请再解释一下'}, {label:'Let’s try a question',text:'给我出道练习题'}, {label:'A slower explanation',text:'请讲慢一点'}];
    return edition === 'primary' ? ['老师，可以举个例子吗？','这一步我还不懂','请讲慢一点','给我出道练习题'] : ['请给我讲一道例题','这一步我还没明白','给我出道练习题','请讲慢一点'];
  }
  if(query.get('mode')==='public'){el('mode').value='public';el('uid').value='public-preview';}
  const product = {get edition(){return edition;},t,examples,sessionChanged};
  window.LiveAgentProduct = product;
  function links() {
    const parameters = new URLSearchParams({edition});if(el('mode').value!=='public')parameters.set('student',el('sid').value);
    ['profileNav','profLink'].forEach(id=>el(id).href='/profile?'+parameters);
    if(el('mode').value==='public')parameters.set('mode','public');el('tracesNav').href='/traces?'+parameters;
    document.querySelector('.brand').href='/?'+parameters;
  }
  function modePresentation(){const publicMode=el('mode').value==='public';document.querySelector('.private-label').textContent=publicMode?t('publicMode'):t('private','私人会话');document.querySelector('.student-picker').hidden=publicMode;el('profLink').hidden=publicMode;el('profCard').hidden=publicMode;}
  function setEdition(next,initial=false) {
    edition=next; document.documentElement.dataset.edition=next; document.documentElement.lang=next==='university'?'en':'zh-CN';
    el('edition').value=next; el('edition').setAttribute('aria-label',t('experience','学习体验')); storage.set('liveAgent.edition',next);
    const pageURL=new URL(location.href);pageURL.searchParams.set('edition',next);history.replaceState(null,'',pageURL);
    document.title=next==='university'?'YāLearn · Live classroom':'芽学 · 私人课堂';
    document.querySelectorAll('[data-i18n]').forEach(node=>node.textContent=t(node.dataset.i18n, originals.get(node)));
    document.querySelectorAll('[data-i18n-aria]').forEach(node=>node.setAttribute('aria-label',t(node.dataset.i18nAria,originalAttributes.get(node))));
    document.querySelectorAll('[data-i18n-placeholder]').forEach(node=>node.placeholder=t(node.dataset.i18nPlaceholder,next==='university'?'':node.dataset.i18nPlaceholder==='notesPlaceholder'?'一个新思路，一句还想追问的话…':'搜索一个知识点…'));
    const copy={primary:['今天也来发现一点新知识','你好，小小探索家！','想知道为什么？带着你的问题，和 AI 老师一起找答案。'],secondary:['给好奇心一点空间','今天，想弄懂什么？','从一个问题开始。和 AI 老师一起，把复杂的知识慢慢理清。'],university:['MAKE ROOM FOR A NEW IDEA','What will you understand today?','A focused space to ask, explore, and work through an idea at your own pace.']}[next];
    ['welcomeEyebrow','welcomeTitle','welcomeDescription'].forEach((id,i)=>el(id).textContent=copy[i]);
    el('sidebarNote').textContent=next==='university'?'A good question is a good beginning.':'每一个好问题，都是进步的开始。';
    el('gentleMessage').textContent=next==='university'?'Understanding takes time. Turn uncertainty into your next question.':next==='primary'?'还不会，也没关系。再问一个问题，我们一起想。':'不用一次就会。把不懂的地方，变成下一个问题。';
    el('text').placeholder=next==='university'?'Write your question here…':next==='primary'?'老师，我想问…':'把你的问题写在这里…';
    el('lessonTopic').placeholder=next==='primary'?'例如：分数是什么':next==='university'?'A topic or question to explore…':'例如：一次函数';
    el('mode').options[0].textContent=t('classroom','私人课堂');el('mode').options[1].textContent=t('publicMode','测试直播 · 不读取档案');
    if(connection!=='ready'&&connection!=='connecting'){el('conn').textContent=t('idle','待开始');el('overlay').textContent=next==='university'?'Your classroom is ready.\nEnter to meet your AI tutor.':next==='primary'?'小课堂准备好啦！\n点「进入课堂」和老师见面吧。':'课堂准备好了\n点击「进入课堂」与老师见面';}
    if(!status)el('title').textContent=next==='university'?'AI learning companion':'AI 学习伙伴';
    populateGrades(!initial);renderSubjects();renderCourses();updateService();updateRuntime();modePresentation();links();for(const option of el('sid').options){const student=students.find(s=>s.id===option.value);if(student)option.textContent=(student.name||student.id)+(student.id==='demo'?' · '+t('savedExample'):'');}
    if(selectedProfile&&typeof window.showProfile==='function') window.showProfile(selectedProfile);
    if(typeof window.setChips==='function'&&!recentExercise)window.setChips(examples(),connection==='ready');
  }
  function gradeLabel(n){return edition==='university'?'Grade '+n:n<=6?'小学'+'一二三四五六'[n-1]+'年级':(n<=9?'初':'高')+'一二三'[(n-7)%3];}
  function populateGrades(reset) {
    const old=el('gradeFilter').value;el('gradeFilter').replaceChildren();
    const bounds=edition==='primary'?[1,6]:edition==='secondary'?[7,12]:[1,12];
    const add=(v,label)=>{const option=document.createElement('option');option.value=v;option.textContent=label;el('gradeFilter').append(option);};
    add('',t('allGrades'));for(let n=bounds[0];n<=bounds[1];n++)add(String(n),gradeLabel(n));
    const fallback=edition==='primary'?'3':edition==='secondary'?'8':'';
    el('gradeFilter').value=reset?fallback:([...el('gradeFilter').options].some(o=>o.value===old)&&old?old:fallback);limit=6;
  }
  function renderSubjects(){const old=el('subjectFilter').value;el('subjectFilter').replaceChildren();const values=['',...new Set(topics.map(x=>x.subject))];values.forEach(value=>{const o=document.createElement('option');o.value=value;o.textContent=value||t('allSubjects','全部学科');el('subjectFilter').append(o);});el('subjectFilter').value=values.includes(old)?old:'';}
  function renderCourses(){
    const list=el('courseList');list.replaceChildren();el('catalogueRetry').hidden=!catalogueFailed;
    const grade=el('gradeFilter').value,subject=el('subjectFilter').value,search=el('courseSearch').value.trim().toLocaleLowerCase();
    const matches=topics.filter(x=>(!grade||String(x.grade)===grade)&&(!subject||x.subject===subject)&&(!search||(x.topic+' '+x.subject).toLocaleLowerCase().includes(search)));
    if(!matches.length){const p=document.createElement('p');p.className='empty';p.textContent=t(catalogueFailed?'catalogueError':'noTopics');list.append(p);}
    for(const topic of matches.slice(0,limit)){
      const card=document.createElement('button');card.type='button';card.className='course-card';
      const top=document.createElement('span');top.className='course-subject';const icon=document.createElement('span');icon.className='course-icon';icon.setAttribute('aria-hidden','true');icon.textContent=({'数学':'∑','英语':'Aa','语文':'文','物理':'↗','化学':'⚗','生物':'♧','历史':'◷','地理':'◎'})[topic.subject]||'✦';top.append(icon,document.createTextNode(topic.subject+' · '+gradeLabel(topic.grade)));
      const title=document.createElement('strong');title.textContent=topic.topic;
      const bottom=document.createElement('span');bottom.className='course-bottom';const basis=document.createElement('span');basis.textContent=t(topic.basis.includes('estimate')?'estimate':topic.basis.includes('textbook')?'textbook':'reference');const action=document.createElement('span');action.textContent=t('topicAction');bottom.append(basis,action);card.append(top,title,bottom);
      card.onclick=()=>{selectedTopic=topic;el('lessonTopic').value=topic.topic;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+basis.textContent;updateLessonActions();el('classroom').scrollIntoView({behavior:'smooth',block:'start'});el('lessonTopic').focus({preventScroll:true});};list.append(card);
    }
    el('moreCourses').hidden=matches.length<=limit;
  }
  async function requestJson(path){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);try{return await window.LiveAgentAPI.fetchJson(path,{signal:controller.signal});}finally{clearTimeout(timer);}}
  async function loadCatalogue(){catalogueFailed=false;el('catalogueRetry').hidden=true;try{const data=await requestJson('/api/curriculum/topics');topics=(data.topics||[]).filter(x=>typeof x.subject==='string'&&typeof x.topic==='string'&&Number.isInteger(x.grade)&&x.grade>=1&&x.grade<=12).map(x=>({...x,basis:String(x.basis||'')}));const order=['数学','英语','语文','物理','化学','生物','历史','地理'];topics.sort((a,b)=>(order.indexOf(a.subject)<0?99:order.indexOf(a.subject))-(order.indexOf(b.subject)<0?99:order.indexOf(b.subject))||a.grade-b.grade);}catch{catalogueFailed=true;topics=[];}renderSubjects();renderCourses();}
  function updateService(){el('serviceStatus').textContent=t(serviceReady?'ready':'unavailable');el('serviceDot').className=serviceReady?'ready':'error';}
  function updateRuntime(){const messages=[];if(edition==='university')messages.push(t('languageNotice'));if((status?.generator||healthInfo?.generator)==='mock')messages.push(edition==='university'?'Video preview: the teacher video is a placeholder. Teaching availability is shown after connecting.':'视频演示：当前为占位画面，教学功能会在连接后确认。');if(status?.responder==='rules')messages.push(t('rulesLesson'));if(status&&!status.board)messages.push(t('noTeacher'));el('runtimeNotice').textContent=messages.join(' ');el('runtimeNotice').hidden=!messages.length;}
  function updateLessonActions(){const allowed=serviceReady&&connection==='ready'&&status?.board&&status.responder!=='rules';el('startLesson').disabled=!allowed||!el('lessonTopic').value.trim();el('practice').disabled=connection!=='ready'||!status?.board||status?.responder==='rules'||!!recentExercise;}
  function sessionChanged(state,detail={}){
    connection=state;status=state==='ready'?detail.status:state==='connecting'?null:status;
    if(state==='connecting'){profileRequest++;loadingProfile=false;selectedProfile=null;el('connectionError').hidden=true;recentExercise=null;el('exerciseCard').hidden=true;el('exerciseFeedback').textContent='';['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
    if(state==='error'){pendingLesson=null;el('connectionError').hidden=false;el('connectionErrorText').textContent=detail.message||t('serviceFailed');}
    if(state==='disconnected'){pendingLesson=null;recentExercise=null;el('exerciseCard').hidden=true;el('lessonStatus').textContent=t('ended');}
    el('sessionHint').textContent=t(state==='ready'?'readyHint':state==='connecting'?'connecting':state==='disconnected'?'ended':'serviceFailed');
    if(state!=='connecting'&&state!=='ready')el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);
    updateLessonActions();updateRuntime();
  }
  function profileDisclaimer(p){el('profileDisclaimer').textContent=!p?'':p.id==='demo'?t('demoProfile'):t('profileEvidence');}
  async function selectProfile(){
    const request=++profileRequest;const id=el('sid').value;selectedProfile=null;window.showProfile?.(null);profileDisclaimer(null);if(el('mode').value==='public'){selectedProfile=null;loadingProfile=false;window.showProfile?.(null);profileDisclaimer(null);loadNotes();return;}loadingProfile=true;el('prof').textContent=edition==='university'?'Loading this learner’s profile…':'正在加载这个学习档案…';links();storage.set('liveAgent.student',id);el('uid').value='learner:'+id;loadNotes();
    try{const p=await requestJson('/api/students/'+encodeURIComponent(id));if(request!==profileRequest)return;selectedProfile=p;window.showProfile?.(p);profileDisclaimer(p);}
    catch{if(request!==profileRequest)return;selectedProfile=null;window.showProfile?.(null);el('prof').textContent=t('profileLoadFailed');el('profileDisclaimer').textContent='';}
    finally{if(request===profileRequest)loadingProfile=false;}
  }
  async function bootstrap(){
    const attempt=++bootstrapAttempt;el('connectionRetry').disabled=true;
    const results=await Promise.allSettled([requestJson('/api/health'),el('mode').value==='public'?Promise.resolve({students:[]}):requestJson('/api/students')]);
    if(attempt!==bootstrapAttempt)return;el('connectionRetry').disabled=false;
    serviceReady=results[0].status==='fulfilled';healthInfo=serviceReady?results[0].value:null;studentsReady=results[1].status==='fulfilled'&&Array.isArray(results[1].value.students)&&results[1].value.students.length>0;
    el('sid').replaceChildren();
    students=studentsReady?results[1].value.students:[];
    if(studentsReady){for(const student of students){const option=document.createElement('option');option.value=student.id;option.textContent=(student.name||student.id)+(student.id==='demo'?' · '+t('savedExample'):'');el('sid').append(option);}const preferred=query.get('student')||storage.get('liveAgent.student');if([...el('sid').options].some(o=>o.value===preferred))el('sid').value=preferred;el('sid').disabled=connection==='ready'||connection==='connecting';await selectProfile();}
    else{const option=document.createElement('option');option.value='';option.textContent=t('noProfiles');el('sid').append(option);el('sid').disabled=true;}
    if(connection!=='ready'&&connection!=='connecting')el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);
    updateService();updateLessonActions();updateRuntime();
    if(!serviceReady||(el('mode').value!=='public'&&!studentsReady)){el('connectionError').hidden=false;el('connectionErrorText').textContent=t(!serviceReady?'serviceFailed':'studentsFailed');}
    else{el('connectionError').hidden=true;}
    if(el('mode').value==='public')loadNotes();loadCatalogue();
  }
  function requestLesson(){
    const topic=el('lessonTopic').value.trim();if(!topic){el('lessonStatus').textContent=t('selectGoal');el('lessonTopic').focus();return;}
    if(status&&(status.responder==='rules'||!status.board)){el('lessonStatus').textContent=t(status.responder==='rules'?'rulesLesson':'noTeacher');return;}
    const chosen=selectedTopic&&selectedTopic.topic===topic?selectedTopic:null;const grade=chosen?(chosen.grade<=6?'小学'+'一二三四五六'[chosen.grade-1]+'年级':(chosen.grade<=9?'初':'高')+'一二三'[(chosen.grade-7)%3]):'';const prompt=chosen?'给我上一节'+grade+chosen.subject+'「'+topic+'」的课，请按照'+grade+'的课程要求讲解。':'给我上一节'+topic+'的课';
    if(connection==='ready'){if(window.sendText(prompt,chosen)){el('lessonStatus').textContent=t('lessonSent');el('stepLearn').classList.add('current');}}
    else{pendingLesson={text:prompt,context:chosen};el('lessonStatus').textContent=t('lessonWaiting');el('connect').click();}
  }
  function renderExercise(ex){const announcement=el('exerciseAnnouncement');const spoken=ex?[t('yourTurn','轮到你啦'),ex.question||ex.concept,...(ex.option_texts||[])].join(' '):'';if(announcement.textContent!==spoken)announcement.textContent=spoken;recentExercise=ex||null;el('exerciseCard').hidden=!ex&&!el('exerciseFeedback').textContent;if(ex){const question=ex.question||ex.concept;el('exerciseQuestion').textContent=[question,...(ex.option_texts||[])].join('\n');el('suggestionLabel').textContent=t('exercisePending');el('stepPractice').classList.add('current');}else el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));updateLessonActions();}
  function onLessonEvent(event){const message=event.detail;if(message.event!=='lesson')return;const data=message.data||{};
    if(data.stage==='outline'){el('lessonStatus').textContent=t('outlineReady')+' '+(data.title||data.topic||'');el('stepLearn').classList.add('current');}
    if(data.stage==='section')el('lessonStatus').textContent=t('sectionReady')+' '+(data.title||'');
    if(data.stage==='planned')el('lessonStatus').textContent=t('lessonPrepared');
    if(data.stage==='outline_failed')el('lessonStatus').textContent=t('lessonFailed');
    if(data.stage==='exercise_open'){el('exerciseFeedback').textContent='';renderExercise(data);}
    if(data.stage==='exercise_closed'){renderExercise(null);}
    if(data.stage==='exercise_graded'){el('exerciseCard').hidden=false;el('exerciseFeedback').textContent=t(data.skipped?'skipped':data.correct?'correct':'incorrect');el('stepPractice').classList.add('current');}
    if(data.stage==='grading_failed')el('exerciseFeedback').textContent=t('gradingFailed');
  }
  function loadNotes(){noteKey='liveAgent.notes.'+(el('mode').value==='public'?'public':encodeURIComponent(el('sid').value||'unselected'));el('notes').value=storage.get(noteKey)||'';el('noteStatus').textContent=t('localOnly',originals.get(el('noteStatus')));}
  function download(contents,name){if(!contents.trim()){el('noteStatus').textContent=t('emptyExport');return;}const url=URL.createObjectURL(new Blob([contents],{type:'text/plain;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  el('edition').onchange=()=>setEdition(el('edition').value);
  el('sid').onchange=selectProfile;el('mode').onchange=()=>{profileRequest++;selectedProfile=null;loadingProfile=false;pendingLesson=null;selectedTopic=null;recentExercise=null;window.resetSessionView?.();el('text').value='';el('lessonTopic').value='';el('courseSearch').value='';el('exerciseFeedback').textContent='';el('exerciseQuestion').textContent='';el('exerciseCard').hidden=true;el('lessonStatus').textContent=t('lessonEmpty',originals.get(el('lessonStatus')));el('uid').value=el('mode').value==='public'?'public-preview':'learner:'+el('sid').value;modePresentation();links();selectProfile();renderCourses();updateLessonActions();el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);el('connectionError').hidden=serviceReady&&(el('mode').value==='public'||studentsReady);if(el('mode').value!=='public'&&!studentsReady)bootstrap();window.layoutStage?.();};el('lessonTopic').oninput=()=>{selectedTopic=null;updateLessonActions();};el('startLesson').onclick=requestLesson;
  el('practice').onclick=()=>{if(window.sendText('给我出道'+el('lessonTopic').value.trim()+'练习题'))el('lessonStatus').textContent=t('practiceWaiting');};
  ['subjectFilter','gradeFilter','courseSearch'].forEach(id=>el(id).addEventListener(id==='courseSearch'?'input':'change',()=>{limit=6;renderCourses();}));
  el('moreCourses').onclick=()=>{limit+=6;renderCourses();};el('catalogueRetry').onclick=loadCatalogue;
  el('connectionRetry').onclick=()=>{if(serviceReady&&(studentsReady||el('mode').value==='public'))el('connect').click();else bootstrap();};
  el('helpOpen').onclick=()=>el('helpDialog').showModal();el('helpClose').onclick=()=>el('helpDialog').close();
  el('notes').oninput=()=>el('noteStatus').textContent=t(storage.set(noteKey||'liveAgent.notes.unselected',el('notes').value)?'noteSaved':'noteFailed');
  el('exportNotes').onclick=()=>download(el('notes').value,'study-notes.txt');
  el('exportChat').onclick=()=>download([...el('chat').querySelectorAll('.msg')].map(n=>n.textContent).join('\n\n'),'classroom-conversation.txt');
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)el('lessonStatus').textContent=t(status.responder==='rules'?'rulesLesson':'noTeacher');else if(window.sendText(queued.text,queued.context))el('lessonStatus').textContent=t('lessonSent');}updateLessonActions();});
  window.addEventListener('live-agent:profile',event=>{if(loadingProfile&&!event.detail)return;selectedProfile=event.detail;profileDisclaimer(event.detail);});
  window.addEventListener('live-agent:state',event=>renderExercise(event.detail.exercise));
  window.addEventListener('live-agent:event',onLessonEvent);
  window.addEventListener('DOMContentLoaded',()=>{setEdition(edition,true);bootstrap();});
})();

===== FILE: frontend/public/assets/live.js =====
const $ = (id) => document.getElementById(id);
const canvas = $("screen"), g = canvas.getContext("2d");
let ws = null, audioCtx = null, playhead = 0, queue = [], pending = null, recorder = null, epoch = 0, decoding = [];
let lastUtterT = null, verified = 0, repairs = 0, pingTimer = null;
let connectionAttempt = 0, sessionState = "disconnected", sessionStatus = null, pingTimeouts = [], startupTimer = null;
const EXAMPLES = ["请给我讲一道例题", "这一步我还没明白", "给我一道练习题", "请讲慢一点"];
const ENGLISH = {
  "session.connecting": "Connecting…", "session.starting": "Preparing your tutor…",
  "session.ready": "Tutor ready", "session.ended": "Session ended. You can start again.",
  "session.closed": "Disconnected", "session.connectFailed": "We could not connect to your tutor. Please try again.",
  "session.failed": "Your session stopped. Please reconnect to continue.",
  "session.audioUnavailable": "Audio is unavailable in this browser. Please use a browser with audio support.",
  "session.protocolError": "The tutor connection could not be read. Please reconnect.",
  "session.started": "Your tutoring session has started.", "session.notReady": "Please wait until your tutor is ready.",
  "session.startTimeout": "Your tutor is taking longer than expected. Please try connecting again.",
  "session.sendFailed": "Your message was not sent. Please reconnect and try again.",
  "voice.hold": "Hold to speak", "voice.release": "Release to send", "voice.permission": "Waiting for microphone permission…",
  "voice.unavailable": "Voice input is unavailable here. You can type your question instead.",
  "voice.disabled": "Voice recognition is unavailable in this session. Please type your question.",
  "voice.denied": "Microphone permission was declined. Allow it in your browser, or type your question.",
  "voice.missing": "No microphone was found. Connect a microphone or type your question.",
  "voice.busy": "The microphone is being used elsewhere. You can type your question instead.",
  "voice.failed": "We could not record your voice. You can type your question instead.",
  "camera.on": "Enable focus check", "camera.off": "Stop focus check", "camera.permission": "Waiting for camera permission…",
  "camera.disabled": "Focus check is off", "camera.enabled": "Focus check is on. Images are analyzed without being saved.",
  "camera.denied": "Camera permission was declined. You can continue without a camera.",
  "camera.missing": "No camera was found. You can continue without a camera.",
  "camera.busy": "The camera is being used elsewhere. You can continue without it.",
  "camera.failed": "We could not use the camera. You can continue without it.",
  "board.title": "Lesson board", "board.ask": "Ask a question: your tutor explains it on the board.",
  "board.lesson": "Choose a topic to start a lesson.", "profile.none": "This session does not use a learner profile.",
  "profile.learner": "Learner", "profile.gradeMissing": "Grade not set", "profile.noExams": "No exam results yet",
  "profile.mastery": "Concept mastery (uncalibrated estimates; evidence shown below)",
  "profile.examWeak": "Areas to revisit: ", "profile.estimated": "Uncalibrated estimate",
  "profile.source.exercise": "Based on recorded practice", "profile.source.exam": "Inferred from exam errors",
  "profile.source.none": "No recorded evidence", "profile.attempts": "Recorded practice: ", "profile.correct": " correct",
  "profile.level.mastered": "Mastered", "profile.level.partial": "Partly understood", "profile.level.weak": "Needs work", "profile.level.unknown": "Not assessed",
  "badge.generator": "Video", "badge.mock": "Mock video (CPU preview)", "badge.director": "Director",
  "badge.openLoop": "A1 open loop", "badge.online": "A2 online director", "badge.responder": "Responder",
  "badge.rules": "Rules (preview)", "badge.judge": "Judging", "badge.mockJudge": "Simulated judging (preview)",
  "badge.none": "None", "badge.speech": "Input", "badge.voice": "Voice enabled", "badge.text": "Text only",
  "state.listening": "Listening", "state.deciding": "Preparing a response", "state.erasure": "Deletion in progress (generation paused)",
  "status.open": "In progress", "status.complied": "Verified complete", "status.failed": "Failed", "status.refused": "Declined / fallback",
  "status.withdrawn": "Withdrawn", "status.capacity_skipped": "Capacity skip", "status.presented": "Presented (not assessed)",
  "kind.action": "Action", "kind.multistep": "Multiple steps", "kind.content": "Content", "kind.memory": "Memory", "kind.chat": "Conversation",
  "state.steps": "Steps ", "state.revisions": "Corrections ", "state.requests": "Requests ",
  "memory.recalled": "Recalled: ", "memory.erased": "This page’s conversation and memory records have been cleared as requested.",
  "attention.label": "Focus check: ", "attention.focused": "Focused", "attention.distracted": "Distracted",
  "attention.absent": "Outside the camera view", "attention.unknown": "Unclear", "attention.off": "Off",
  "av.reportOutput": "Reported audio output delay ≈ ", "av.reportRefresh": " ms; display refresh ≈ ", "av.reportCompensated": " ms (automatically compensated)",
  "profile.noConcepts": "Concept records appear after practice.", "exercise.unsure": "I’m not sure",
  "profile.edit": "Edit ↗", "profile.viewAll": "See all records ↗",
  "exercise.choose": "Choose ", "caption.label": "Tutor", "device.changed": "Your audio device changed. Use audio/video sync if the picture and sound no longer match.",
};
function tr(key, fallback) {
  const product = window.LiveAgentProduct;
  const value = product?.edition === "university" ? (ENGLISH[key] ?? fallback) : fallback;
  return product?.t?.(key, value) ?? value;
}
function productEvent(name, detail) { window.dispatchEvent(new CustomEvent(`live-agent:${name}`, {detail})); }
function activeSocket(socket, attempt) { return socket === ws && attempt === connectionAttempt; }
function ready() { return sessionState === "ready" && ws?.readyState === 1; }
function idleExamples() { return window.LiveAgentProduct?.examples?.() || personaChips || EXAMPLES; }
const STATUS = {open: "进行中", complied: "已验证完成", failed: "失败", refused: "拒绝/降级", withdrawn: "已撤回",
                capacity_skipped: "容量跳过", presented: "已呈现（未判定）"};
const KIND = {action: "动作", multistep: "多步动作", content: "内容", memory: "记忆", chat: "闲聊"};

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function send(o, socket = ws) {
  if (!socket || socket !== ws || socket.readyState !== 1) return false;
  try { socket.send(JSON.stringify(o)); return true; }
  catch (e) { console.warn("WebSocket send failed", e); return false; }
}
function setConn(s, live) { const el = $("conn"); el.textContent = s; el.className = "badge" + (live ? " live" : ""); }
function sessionChanged(state, detail = {}) {
  sessionState = state;
  const live = state === "ready", busy = state === "connecting" || live;
  $("connect").disabled = busy; $("disconnect").disabled = !busy;
  ["text", "send"].forEach(id => $(id).disabled = !live);
  $("talk").disabled = !live || !sessionStatus?.asr || micUploading;
  $("cam").disabled = !live || !sessionStatus?.attention || camPending;
  ["mode", "uid", "sid"].forEach(id => { if ($(id)) $(id).disabled = busy; });
  document.querySelectorAll("#chips .chip").forEach(button => button.disabled = !live);
  const failure = $("connectionError");
  if (failure) {
    failure.hidden = state !== "error";
    const message = failure.querySelector("#connectionErrorText") || failure;
    message.textContent = state === "error" ? detail.message || "" : "";
  }
  window.LiveAgentProduct?.sessionChanged?.(state, {...detail, status: sessionStatus});
}
function notice(key, fallback, error) {
  if (error) feed(null, "bad", "Browser", error.message || String(error));
  chat("sys", tr(key, fallback));
}
function clearEmpty(el) { const e = el.querySelector(".empty"); if (e) e.remove(); }

function chat(kind, text) {
  const el = $("chat"); clearEmpty(el);
  const d = document.createElement("div"); d.className = "msg " + kind; d.textContent = text;
  el.appendChild(d); el.scrollTop = el.scrollHeight;
}
function feed(t, cls, what, detail) {
  const el = $("feed"); clearEmpty(el);
  const d = document.createElement("div"); d.className = "ev " + (cls || "");
  const labels = {"理解": "Interpretation", "锁定": "Locked", "动作质检": "Action check", "语音质检": "Speech check",
    "前向修正": "Forward correction", "完成声明": "Completion claim", "拒绝/降级": "Declined / fallback", "容量跳过": "Capacity skip",
    "叙述守卫": "Narration guard", "删除": "Deletion", "打断": "Interrupted", "审核": "Audit", "错误": "Error",
    "备课": "Lesson preparation", "因材施教": "Adapted lesson", "教案": "Lesson plan", "练习": "Practice", "批改": "Grading",
    "提醒学生": "Focus reminder", "场景锚定": "Scene anchors", "场景连续性": "Scene continuity", "未通过": "Not passed", "无法判定": "Unclear", "通过": "Passed"};
  if (window.LiveAgentProduct?.edition === "university") {
    for (const label of Object.keys(labels).sort((a, b) => b.length - a.length)) what = String(what).replaceAll(label, labels[label]);
  }
  d.innerHTML = `<span class="t">${t != null ? t.toFixed(1) : ""}</span><span><span class="what">${esc(what)}</span>${esc(detail || "")}</span>`;
  el.appendChild(d); while (el.children.length > 200) el.firstChild.remove(); el.scrollTop = el.scrollHeight;
}
function memo(text, cls) {
  const el = $("memory"); clearEmpty(el);
  const d = document.createElement("div"); d.className = "ev " + (cls || "");
  d.innerHTML = `<span class="t"></span><span>${esc(text)}</span>`;
  el.appendChild(d); el.scrollTop = el.scrollHeight;
}

function setChips(list, enabled) {  // one-click examples; the server sends the persona's own in "status"
  const container = $("chips"), active = document.activeElement;
  const focused = active && container.contains(active) && active.classList.contains("chip") ? active.dataset.prompt : null;
  container.innerHTML = "";
  let replacement = null;
  list.forEach(x => {
    const b = document.createElement("button"); b.className = "chip";
    b.textContent = typeof x === "object" ? x.label : x; b.disabled = !enabled;
    b.dataset.prompt = typeof x === "object" ? x.text : x;
    if (typeof x === "object" && x.description) b.setAttribute("aria-label", x.description);
    b.onclick = () => sendText(typeof x === "object" ? x.text : x); $("chips").appendChild(b);
    if (focused != null && b.dataset.prompt === focused) replacement = b;
  });
  if (focused != null && enabled) (replacement || $("text")).focus({preventScroll: true});
}
setChips(window.LiveAgentProduct?.examples?.() || EXAMPLES, false);

// ---------------------------------------------------------------- connection
function clearStartupTimer() { clearTimeout(startupTimer); startupTimer = null; }
function finishSession(socket, attempt, state, message) {
  if (!activeSocket(socket, attempt)) return;
  ws = null; connectionAttempt++;
  clearStartupTimer();
  clearInterval(pingTimer); pingTimer = null;
  pingTimeouts.forEach(clearTimeout); pingTimeouts = [];
  cancelSpeech(); camOff(false); stopAll();
  sessionStatus = null;
  setConn(tr("session.closed", "连接已关闭"));
  $("overlay").style.display = "flex"; $("overlay").textContent = message;
  sessionChanged(state, {message});
}
function resetSessionView() {
  stopAll();
  g.clearRect(0, 0, canvas.width, canvas.height);
  ["chat", "feed", "memory", "chains"].forEach(id => $(id).innerHTML = "");
  $("flags").textContent = "";
  ["sLambda", "sReq", "sRtt", "sLatency"].forEach(id => $(id).textContent = "–");
  verified = repairs = 0; lastUtterT = null; lastGraded = null; exerciseKey = "";
  $("sVerified").textContent = "0"; $("sRepairs").textContent = "0";
  personaChips = EXAMPLES; setChips(idleExamples(), false); showProfile(null);
  shownBoard = null; lastBoard = null; onScreen = null;
  $("board").classList.remove("on"); $("boardTitle").textContent = ""; $("boardItems").innerHTML = "";
  $("boardImg").removeAttribute("src"); $("boardCap").textContent = "";
  delete $("board").dataset.key;
}
$("connect").onclick = async () => {
  if (sessionState === "connecting" || sessionState === "ready") return;
  const attempt = ++connectionAttempt;
  const student = $("student") || $("sid");
  const mode = $("mode").value === "public" ? "public" : "private";
  const hello = {type: "hello", mode, user_id: mode === "public" ? "public-preview" : $("uid").value};
  if (mode === "private") hello.student = student.value.trim();
  sessionStatus = null;
  resetSessionView();
  sessionChanged("connecting");
  setConn(tr("session.connecting", "连接中…"));
  $("overlay").style.display = "flex"; $("overlay").textContent = tr("session.starting", "正在准备老师…");
  startupTimer = setTimeout(() => {
    if (attempt !== connectionAttempt || sessionState !== "connecting") return;
    const message = tr("session.startTimeout", "老师准备的时间有点长，请重新连接试试。");
    const socket = ws;
    if (socket) { finishSession(socket, attempt, "error", message); socket.close(); }
    else {
      connectionAttempt++; clearStartupTimer();
      setConn(tr("session.closed", "连接已关闭")); $("overlay").textContent = message;
      sessionChanged("error", {message});
    }
  }, 30000);
  try {
    if (!audioCtx || audioCtx.state === "closed") {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) throw new Error("AudioContext unavailable");
      audioCtx = new Audio(); master = null;
    }
    await audioCtx.resume();
  } catch (error) {
    if (attempt !== connectionAttempt) return;
    clearStartupTimer();
    const message = tr("session.audioUnavailable", "浏览器暂时无法播放声音，请使用支持音频的浏览器后重试。");
    feed(null, "bad", "AudioContext", error.message);
    setConn(tr("session.closed", "连接已关闭"));
    $("overlay").textContent = message; sessionChanged("error", {message});
    return;
  }
  if (attempt !== connectionAttempt || sessionState !== "connecting") return;
  let socket;
  try { socket = new WebSocket(window.LiveAgentAPI.websocketUrl()); }
  catch (error) {
    clearStartupTimer();
    const message = tr("session.connectFailed", "暂时连接不上老师，请重试。");
    feed(null, "bad", "WebSocket", error.message); $("overlay").textContent = message;
    setConn(tr("session.closed", "连接已关闭")); sessionChanged("error", {message}); return;
  }
  ws = socket; socket.binaryType = "arraybuffer";
  socket.onopen = async () => {
    // H.264 segments need ~1/6 of the bandwidth of per-frame JPEG (a remote bridge cannot carry JPEG in real time)
    const video_codecs = (await h264Supported()) ? ["h264"] : [];
    if (!activeSocket(socket, attempt) || socket.readyState !== 1) return;
    if (!send({...hello, video_codecs}, socket)) {
      finishSession(socket, attempt, "error", tr("session.connectFailed", "暂时连接不上老师，请重试。"));
      socket.close(); return;
    }
    const ping = () => activeSocket(socket, attempt) && send({type: "ping", t: performance.now()}, socket);
    ping(); pingTimeouts = [setTimeout(ping, 300), setTimeout(ping, 600)]; pingTimer = setInterval(ping, 3000);
  };
  socket.onclose = event => {
    if (!activeSocket(socket, attempt)) return;
    const starting = sessionState === "connecting";
    const state = starting || event?.wasClean === false || (event?.code && event.code !== 1000) ? "error" : "disconnected";
    finishSession(socket, attempt, state, state === "error"
      ? (starting ? tr("session.connectFailed", "暂时连接不上老师，请重试。") : tr("session.failed", "会话暂时中断了，请重新连接后继续。"))
      : tr("session.ended", "会话已结束，可以重新开始。"));
  };
  socket.onerror = () => {
    finishSession(socket, attempt, "error", tr("session.connectFailed", "暂时连接不上老师，请重试。"));
    socket.close();
  };
  socket.onmessage = ev => onMessage(ev, socket, attempt);
  startRender();
};
$("disconnect").onclick = () => {
  const socket = ws;
  if (socket) {
    finishSession(socket, connectionAttempt, "disconnected", tr("session.ended", "会话已结束，可以重新开始。"));
    socket.close();
  } else if (sessionState === "connecting") {
    connectionAttempt++; clearStartupTimer(); sessionChanged("disconnected");
    setConn(tr("session.closed", "连接已关闭")); $("overlay").textContent = tr("session.ended", "会话已结束，可以重新开始。");
  }
};

async function onMessage(ev, socket = ws, attempt = connectionAttempt) {
  if (!activeSocket(socket, attempt)) return;
  if (typeof ev.data === "string") {
    let m;
    try {
      m = JSON.parse(ev.data);
      if (!m || typeof m !== "object" || Array.isArray(m) || typeof m.type !== "string") throw new Error("Invalid message envelope");
    }
    catch (error) {
      feed(null, "bad", "Protocol", error.message);
      finishSession(socket, attempt, "error", tr("session.protocolError", "暂时无法读取老师的回应，请重新连接。")); socket.close(); return;
    }
    if (m.type === "chunk") { pending = {meta: m, frames: [], pcm: null, epoch}; }
    else if (m.type === "stop") { stopAll(); }
    else if (m.type === "event") { onEvent(m); }
    else if (m.type === "state") { onState(m); }
    else if (m.type === "transcript") { if (m.text) chat("user", "🎙 " + m.text); }
    else if (m.type === "status") { onStatus(m); }
    else if (m.type === "profile") { showProfile(m.profile, lastGraded); }
    else if (m.type === "error") {
      feed(null, "bad", "错误", m.error);
      finishSession(socket, attempt, "error", tr("session.failed", "会话暂时中断了，请重新连接后继续。")); socket.close();
    }
    else if (m.type === "pong") {
      const rtt = performance.now() - m.t;
      send({type: "clock", t_client: m.t, t_server: m.ts, rtt});
      $("sRtt").textContent = rtt.toFixed(0);
    }
    return;
  }
  if (!pending) return;
  const h264 = pending.meta.codec === "h264";
  if (h264 && !pending.video) {
    pending.video = decodeH264(ev.data, pending.meta);  // one Annex-B segment: all of the chunk's frames
    pending.video.catch(() => {});  // handled when the chunk completes (below)
  } else if (!h264 && pending.frames.length < pending.meta.n_frames) {
    pending.frames.push(createImageBitmap(new Blob([ev.data], {type: "image/jpeg"})));
  } else {
    pending.pcm = new Int16Array(ev.data);
    const c = pending; pending = null;
    decoding.push(c);  // arrival order = presentation order; decodes may finish out of order
    try {
      c.frames = h264 ? await c.video : await Promise.all(c.frames);
    } catch (e) {  // this browser cannot decode the segment: ask for JPEG from now on
      console.warn("H.264 decode failed, falling back to JPEG", e);
      if (activeSocket(socket, attempt) && c.epoch === epoch) send({type: "video_codec", codec: "jpeg"}, socket);
      c.frames = [];
    }
    if (!activeSocket(socket, attempt) || c.epoch !== epoch) {
      c.frames.forEach(frame => frame.close?.()); return;
    }
    c.decoded = true;
    // arrival + decode time of the chunk: the server adds it to its lock lead (transport over a remote bridge)
    send({type: "chunk_received", request: c.meta.request, chunk: c.meta.chunk, tp: performance.now()});
    while (decoding.length && decoding[0].decoded) {  // schedule only the contiguous head
      const h = decoding.shift();
      if (h.epoch === epoch) schedule(h);
    }
  }
}

function onStatus(m) {
  clearStartupTimer();
  const firstReady = sessionState !== "ready";
  sessionStatus = m;
  setConn(tr("session.ready", "老师已就绪"), true);
  if (Array.isArray(m.examples) && m.examples.length) personaChips = m.examples;
  if (!exerciseKey) setChips(m.board ? idleExamples() : personaChips, true);
  showProfile(m.student);
  if (m.board && (!shownBoard || shownBoard.key === "idle"))
    showBoard({key: "idle", title: esc(tr("board.title", "学习黑板")), reveal: null,
               items: [esc(tr("board.ask", "可以提问题，老师会边讲边写。")), esc(tr("board.lesson", "选一个学习主题，就可以开始上课。"))]});
  $("cam").hidden = !m.attention;
  const b = $("badges"); b.querySelectorAll(".badge:not(#conn)").forEach(x => x.remove());
  const items = [
    [tr("badge.generator", "生成"), m.generator === "mock" ? tr("badge.mock", "占位视频（CPU 演示）") : m.generator],
    [tr("badge.director", "导演"), m.director === "open_loop" ? tr("badge.openLoop", "A1 开环") : tr("badge.online", "A2 在线导演")],
    [tr("badge.responder", "应答"), m.responder === "rules" ? tr("badge.rules", "规则（演示）") : m.responder],
    [tr("badge.judge", "质检"), {mock: tr("badge.mockJudge", "模拟判定（演示）"), vlm: "VLM", none: tr("badge.none", "无")}[m.judge] || m.judge],
    [tr("badge.speech", "输入"), m.asr ? tr("badge.voice", "语音已启用") : tr("badge.text", "仅文字")],
  ];
  for (const [k, v] of items) {
    const s = document.createElement("span"); s.className = "badge"; s.textContent = `${k}: ${v}`; b.appendChild(s);
  }
  if (m.persona) $("title").textContent = m.persona;
  $("talk").title = m.asr ? "" : tr("voice.disabled", "这次会话暂时不能识别语音，请用文字提问。");
  sessionChanged("ready", {status: m});
  if (firstReady) chat("sys", tr("session.started", "老师已准备好，可以开始提问了。"));
  productEvent("status", m);
}

// ---------------------------------------------------------------- panel
// ---------------------------------------------------------------- student profile and exercises
let personaChips = EXAMPLES, profile = null, exerciseKey = "", lastGraded = null;
const LEVEL = {mastered: "已掌握", partial: "基本理解", weak: "薄弱", unknown: "未评估"};
function showProfile(p, flash) {
  profile = p || null;
  productEvent("profile", profile);
  $("profEdit").hidden = !p;
  const el = $("prof");
  if (!p) { el.innerHTML = `<div class="empty">${esc(tr("profile.none", "这次会话未使用学生档案。"))}</div>`; return; }
  $("profEdit").textContent = (p.exams || []).length > 2 || (p.concepts || []).length > 4
    ? tr("profile.viewAll", "完整记录见档案 ↗") : tr("profile.edit", "编辑 ↗");
  const exams = (p.exams || []).slice(-2).map(e => `<li>${esc(e.date || "")} ${esc(e.subject)}${esc(e.name)} <b>${e.score}</b>/${e.full}` +
    (e.weak && e.weak.length ? ` · ${esc(tr("profile.examWeak", "失分："))}${esc(e.weak.join("、"))}` : "") + "</li>").join("");
  const SRC = {exercise: tr("profile.source.exercise", "据记录的练习"), exam: tr("profile.source.exam", "据考试失分推断")};
  const cps = (p.concepts || []).slice(0, 4).map((c, index) => {
    const evidence = tr(`profile.level.${c.level}`, LEVEL[c.level] || c.level) + " · " + tr("profile.estimated", "未校准的估计") +
      " · " + (SRC[c.source] || tr("profile.source.none", "无记录依据")) +
      (typeof c.attempts === "number" ? " · " + tr("profile.attempts", "记录练习：") + (c.correct ?? 0) + "/" + c.attempts + tr("profile.correct", " 次正确") : "");
    return `<div class="concept-record"><div class="cp ${esc(c.level)}${flash === c.name ? " flash" : ""}" tabindex="0" aria-describedby="concept-evidence-${index}" title="${esc(evidence)}">
      <span>${esc(c.name)}</span><span class="bar" aria-hidden="true"><i style="width:${Math.round((c.mastery ?? 0) * 100)}%"></i></span>
      <span class="v">${c.mastery == null ? "–" : (c.source === "exam" ? "≈" : "") + Math.round(c.mastery * 100) + "%"}</span></div>
      <p class="meta concept-evidence" id="concept-evidence-${index}">${esc(evidence)}</p></div>`;
  }).join("");
  el.innerHTML = `<div class="who">${esc(p.name || tr("profile.learner", "同学"))} · ${esc(p.grade || tr("profile.gradeMissing", "年级未填"))}</div>` +
    (exams ? `<ul class="exams">${exams}</ul>` : `<div class="meta">${esc(tr("profile.noExams", "还没有考试成绩"))}</div>`) +
    (cps ? `<div class="meta">${esc(tr("profile.mastery", "知识点掌握度（未校准的估计；每条记录下方列出依据）"))}</div>` + cps : `<div class="meta">${esc(tr("profile.noConcepts", "做练习后，这里会出现知识点记录。"))}</div>`);
}
$("profEdit").onclick = () => {
  const id = profile ? profile.id : $("sid").value;
  window.location.href = `/profile?student=${encodeURIComponent(id)}&edition=${encodeURIComponent(window.LiveAgentProduct?.edition || "primary")}`;
};
function showExercise(ex) {  // answer buttons while an exercise waits; the persona's examples otherwise
  const key = ex ? JSON.stringify([ex.concept, ex.question, ex.options || [], ex.option_texts || []]) : "";
  if (key === exerciseKey) return;
  exerciseKey = key;
  const live = ready();
  if (!ex) { setChips(sessionStatus?.board ? idleExamples() : personaChips, live); return; }
  setChips([...(ex.options || []).map((o, index) => ({label: tr("exercise.choose", "选 ") + o, text: "选 " + o,
              description: ex.option_texts?.[index] ? tr("exercise.choose", "选 ") + o + ": " + ex.option_texts[index] : undefined})),
            {label: tr("exercise.unsure", "我不会"), text: "我不会"}], live);
  document.querySelectorAll("#chips .chip").forEach(b => b.classList.add("answer"));
}

function onState(s) {
  productEvent("state", s);
  showExercise(s.exercise);
  $("sLambda").textContent = typeof s.lambda_s === "number" ? s.lambda_s.toFixed(1) : "–";
  $("sReq").textContent = s.next_lock ?? "–";
  const flags = [];
  if (s.listening) flags.push(tr("state.listening", "聆听中"));
  if (s.awaiting_decision) flags.push(tr("state.deciding", "等待应答决策"));
  if (!s.erasure_gate_open) flags.push(tr("state.erasure", "删除进行中（已暂停生成）"));
  $("flags").textContent = flags.join(" · ");
  const el = $("chains");
  if (!s.chains || !s.chains.length) return;
  el.innerHTML = "";
  for (const c of s.chains.slice().reverse()) {
    const steps = c.steps && c.steps.length > 1 ? ` · ${tr("state.steps", "步骤 ")}${Math.min(c.step_index, c.steps.length)}/${c.steps.length}` : "";
    const d = document.createElement("div"); d.className = "chain";
    d.innerHTML = `<div class="top"><span class="intent">${esc(c.intent)}</span><span class="pill ${esc(c.status)}">${esc(tr(`status.${c.status}`, STATUS[c.status] || c.status))}</span></div>
      <div class="meta">${esc(tr(`kind.${c.kind}`, KIND[c.kind] || c.kind))}${steps}${c.revisions ? ` · ${tr("state.revisions", "改口 ")}${c.revisions}` : ""}${c.requests.length ? ` · ${tr("state.requests", "请求 ")}${c.requests.join(", ")}` : ""}</div>`;
    el.appendChild(d);
  }
}

function onEvent(m) {
  productEvent("event", m);
  const d = m.data || {}, t = m.t, k = m.request;
  switch (m.event) {
    case "utterance_end":
      if (d.text) { lastUtterT = t; }
      if (d.decision) {
        const dec = d.decision;
        feed(t, "", "理解", `${dec.relation || ""}/${dec.kind || ""}` + (dec.forget_term ? ` · 删除「${dec.forget_term}」` : ""));
        (d.recalled || []).forEach(x => memo(tr("memory.recalled", "召回：") + x));
      }
      break;
    case "lock":
      if (d.transcript) chat("persona", d.transcript);
      feed(t, "", `锁定 #${k}`, (d.action ? d.action.slice(0, 70) : "") + (d.transcript ? ` · 「${d.transcript}」` : "") +
           (d.retry_of != null ? ` · 重试 #${d.retry_of}` : "") + ((d.corrections || []).length ? " · 附修正" : ""));
      break;
    case "verdict":
      if (d.kind === "action") {
        if (d.label === "complied") verified++;
        $("sVerified").textContent = verified;
        feed(t, d.label === "complied" ? "ok" : d.label === "not_complied" ? "bad" : "warn",
             `动作质检 #${k}: ${{complied: "通过", not_complied: "未通过", unknown: "无法判定"}[d.label] || d.label}`,
             d.rationale ? " · " + d.rationale : "");
      } else {
        feed(t, d.label === "complied" ? "ok" : "warn", `语音质检 #${k}: ${d.label === "complied" ? "通过" : "未通过"}`,
             d.rationale ? " · " + d.rationale : "");
      }
      break;
    case "repair":
      repairs++; $("sRepairs").textContent = repairs;
      feed(t, "warn", `前向修正 #${k}→#${d.earliest_correctable}`, d.correction ? " · " + d.correction.slice(0, 80) : "（重复原指令）");
      break;
    case "completion_claim": feed(t, "ok", "完成声明", `「${d.text || "好了。"}」（在验证之后）`); break;
    case "refusal": feed(t, "bad", "拒绝/降级", d.reason || ""); break;
    case "capacity_skip": feed(t, "warn", "容量跳过", d.reason || "被更新的指令取代"); break;
    case "narration_guard": feed(t, "warn", "叙述守卫", `去掉未验证的完成说法：「${d.original}」`); break;
    case "speech_onset":
      if (lastUtterT != null && (d.chain_ids || []).length) {
        $("sLatency").textContent = (t - lastUtterT).toFixed(1); lastUtterT = null;
      }
      break;
    case "playback_stop":
      if (d.erasure) {
        if (d.erasure_complete) {
          // this page kept its own copy of what was typed and recalled: clear it too
          $("chat").innerHTML = ""; $("memory").innerHTML = ""; $("caption").textContent = "";
          document.querySelectorAll("#feed .ev").forEach(e => e.remove());
          chat("sys", tr("memory.erased", "已按删除请求清除本页的对话与记忆记录"));
        }
        memo(d.erasure_complete ? `已删除 ${d.deleted ?? ""} 条记录（含派生内容、日志与生成器状态）` : "删除未完成：已暂停生成，等待处理",
             d.erasure_complete ? "ok" : "bad");
        feed(t, d.erasure_complete ? "ok" : "bad", "删除", d.erasure_complete ? "完成" : "未完成（安全暂停）");
      } else { feed(t, "", "打断", "停止播放，丢弃未呈现内容"); }
      break;
    case "audit":
      if ((d.issues || []).length) feed(t, "warn", "审核", d.issues.join(", "));
      break;
    case "error": feed(t, "bad", "错误", `${d.where || ""} ${d.error || ""}`); break;
    case "lesson": {
      const s = {outline: `课程大纲：${d.title || ""}（${(d.sections || []).length} 节）`,
                 section: `第 ${(d.section ?? 0) + 1} 节已备好：${d.title || ""}（${d.lines} 句，${d.points} 条板书）`,
                 section_failed: `第 ${(d.section ?? 0) + 1} 节生成失败${d.attempt ? "，已跳过" : "，重试中"}`,
                 outline_failed: "课程大纲生成失败", planned: `整节课已备好：${d.title || ""}`,
                 figure_judgement: `配图判断「${d.title || ""}」：` + (d.judgements || []).map(j =>
                   `第 ${j.point + 1} 条 复杂度 ${j.complexity ?? "?"} ${j.need ? "→ 配图" : "→ 不配"}${j.why ? "（" + j.why + "）" : ""}`).join("；"),
                 figure: `第 ${(d.point ?? 0) + 1} 条的配图已画好（${d.kind === "plot" ? "精确作图" : "插图"}）`,
                 figure_failed: `配图失败：${d.error || ""}`,
                 exercise: `出题（${d.concept || ""}）：${d.exercise || ""}`,
                 exercise_failed: `出题失败：${d.error || ""}`,
                 exercise_timeout: `练习「${d.concept || ""}」无人作答，老师讲解后继续`,
                 grading_failed: `批改失败：${d.error || ""}`,
                 profile_updated: `学生档案已更新（${(d.changed || []).join("、")}）`}[d.stage];
      if (s) feed(t, d.stage.endsWith("failed") ? "bad" : "", "备课", s);
      if (d.stage === "outline" && d.plan) {
        const dep = {review: "复习", core: "重点", new: "新课"};
        feed(t, "", d.adaptive ? "因材施教" : "教案", (d.note ? d.note + "；" : "") + d.plan.map((x, i) =>
          `${i + 1}.${x.title}[${dep[x.depth] || x.depth}${x.exercise ? "+练习" : ""}]`).join(" "));
      }
      if (d.stage === "section" && d.exercise) feed(t, "", "练习", `本节后出题：${d.exercise}`);
      if (d.stage === "exercise_graded") {
        const m = d.mastery;
        feed(t, d.correct ? "ok" : "bad", "批改", `${d.concept}：${d.skipped ? "不会" : d.correct ? "答对" : "答错"}` +
             (d.misconception ? `（${d.misconception}）` : "") +
             (m && m.after != null ? ` · 掌握度 ${m.before == null ? "–" : Math.round(m.before * 100) + "%"} → ${Math.round(m.after * 100)}%` : ""));
      }
      if (d.stage === "exercise_graded") lastGraded = d.concept;
      if (d.stage === "exercise_open") showExercise(d);
      if (d.stage === "exercise_closed") showExercise(null);
      break;
    }
    case "attention": {
      const name = {focused: "专注", distracted: "走神", absent: "不在画面", unknown: "无法判断", off: "未开启"};
      const el = $("focus"), st = d.stable || d.state;
      el.className = "focusline " + (st || "");
      el.textContent = d.state === "off" ? tr("camera.disabled", "专注检测未开启") :
        tr("attention.label", "专注检测：") + tr(`attention.${st}`, name[st] || st) + (d.reason ? ` (${d.reason})` : "");
      if (d.nudge) feed(t, "warn", "提醒学生", `「${d.nudge}」`);
      break;
    }
    case "continuity":
      if ((d.anchor_removed || []).length) feed(t, "", `场景锚定 #${k}`, `首个镜头未出现：${d.anchor_removed.join("、")}（不再在提示中描述）`);
      if (d.wrong && Object.keys(d.wrong).length) {
        feed(t, (d.corrections || []).length ? "warn" : "", `场景连续性 #${k}`,
             Object.entries(d.wrong).map(([n, c]) => `${n}×${c.join("/")}`).join("，") +
             ((d.corrections || []).length ? ` · 修正→#${d.target}` : ""));
      }
      break;
  }
}

// ---------------------------------------------------------------- board (server-rendered, escaped HTML + MathML)
function layoutStage() {  // video + 3:4 board side by side at one height (stacked on narrow screens)
  const row = document.querySelector(".stagerow"), board = $("board"), cv = $("screen");
  const on = board.classList.contains("on"), W = row.clientWidth, gap = 12, va = cv.width / cv.height;
  const cap = innerWidth <= 620 ? 300 : innerWidth <= 860 ? 390 : Infinity;
  let H;
  if (!on) { H = Math.min(0.68 * innerHeight, W / va, cap); }
  else if (innerWidth <= 860) { H = Math.min(0.6 * innerHeight, W / va, cap); board.style.width = W + "px"; board.style.height = (W * 3 / 4) + "px"; }
  else { H = Math.min(0.55 * innerHeight, (W - gap) / (va + 4 / 3)); board.style.width = (H * 4 / 3) + "px"; board.style.height = H + "px"; }
  cv.style.height = H + "px"; cv.style.width = (H * va) + "px"; cv.style.maxHeight = "none";
  if (on) { board.dataset.base = Math.max(12, parseFloat(board.style.height) / 22); fitBoard(); }
}

function fitBoard() {  // shrink the text until every shown point fits: the point being spoken is never clipped
  const el = $("board"), ol = $("boardItems");
  let fs = parseFloat(el.dataset.base || "19");
  el.style.fontSize = fs + "px";
  while (fs > 11 && (ol.scrollHeight > ol.clientHeight + 1 || el.scrollHeight > el.clientHeight + 1)) {
    fs -= 1; el.style.fontSize = fs + "px";
  }
}
addEventListener("resize", layoutStage);
addEventListener("load", layoutStage);

let shownBoard = null;  // the board view on display (the chunk on screen switches it only when it differs)
function showBoard(b) {
  shownBoard = b;
  const el = $("board");
  if (!el.classList.contains("on")) { el.classList.add("on"); layoutStage(); }
  if (el.dataset.key !== b.key) {
    el.dataset.key = b.key;
    $("boardTitle").innerHTML = b.title;
    $("boardItems").innerHTML = b.items.map(x => `<li>${x}</li>`).join("");
  }
  const fig = b.figure;
  el.classList.toggle("hasfig", !!fig);
  if (fig && $("boardImg").getAttribute("src") !== fig.url) { $("boardImg").src = fig.url; $("boardCap").innerHTML = fig.caption || ""; }
  const lis = [...$("boardItems").children];
  lis.forEach((li, i) => {
    li.classList.toggle("hidden", b.reveal !== null && b.reveal !== undefined && i > b.reveal);
    li.classList.toggle("now", i === b.reveal);
    li.querySelector(".dots")?.remove();
  });
  const cur = (b.reveal !== null && b.reveal !== undefined) ? lis[b.reveal] : null;
  if (cur && b.progress) {  // how far into this point the teacher is: one dot per sentence about it
    const [k, n] = b.progress, d = document.createElement("span");
    d.className = "dots"; d.textContent = "●".repeat(k) + "○".repeat(Math.max(0, n - k));
    d.setAttribute("aria-label", `第 ${k}/${n} 句`); cur.appendChild(d);
  }
  fitBoard();
  if (cur) cur.scrollIntoView({block: "nearest"});
}

// ---------------------------------------------------------------- H.264 (WebCodecs)
const H264 = "avc1.42E01F";  // baseline, level 3.1 (480x864 @ 24 fps)
async function h264Supported() {
  try {
    if (typeof VideoDecoder === "undefined") return false;
    const r = await VideoDecoder.isConfigSupported({codec: H264, codedWidth: 480, codedHeight: 864});
    return !!r.supported;
  } catch (e) { return false; }
}
function decodeH264(buf, meta) {
  return new Promise((resolve, reject) => {
    const out = [];
    const dec = new VideoDecoder({
      output: f => out.push(createImageBitmap(f).finally(() => f.close())),
      error: e => reject(e),
    });
    dec.configure({codec: H264, codedWidth: meta.width, codedHeight: meta.height, optimizeForLatency: true});
    let off = 0;
    meta.sizes.forEach((n, i) => {
      dec.decode(new EncodedVideoChunk({type: i === 0 ? "key" : "delta", timestamp: Math.round(i * 1e6 / meta.fps),
                                        data: new Uint8Array(buf, off, n)}));
      off += n;
    });
    dec.flush().then(() => Promise.all(out)).then(frames => { dec.close(); resolve(frames); }, reject);
  });
}

// ---------------------------------------------------------------- playback (master clock = AudioContext)
function schedule(c) {
  const m = c.meta, sr = m.sample_rate;
  if (canvas.width !== m.width || canvas.height !== m.height) { canvas.width = m.width; canvas.height = m.height; layoutStage(); }
  const buf = audioCtx.createBuffer(1, Math.max(1, c.pcm.length), sr);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < c.pcm.length; i++) ch[i] = c.pcm[i] / 32768;
  const start = Math.max(audioCtx.currentTime + 0.05, playhead);
  const dur = m.duration || m.n_frames / m.fps;
  const src = audioCtx.createBufferSource(); src.buffer = buf; src.connect(outGain()); src.start(start);
  playhead = start + dur;
  if (c.meta.board) lastBoard = c.meta.board;  // chunk 0 of a request carries its board; later chunks show the same
  const q = {...c, start, end: start + dur, src, startedSent: false, endedSent: false, board: lastBoard};
  // Playback acks also come from the audio clock: in a background tab requestAnimationFrame stops (no frames are
  // painted, so render() sends nothing) while the audio plays on, and the server would stop locking new clips.
  // In a visible tab the picture can still be on this chunk when its audio ends (output delay, "画面延后"), and
  // render() sends chunk_end with the complete list of painted frames when the picture ends; this is the fallback.
  const ep = epoch;
  src.onended = () => {
    const check = () => {
      if (ep !== epoch || q.endedSent) return;
      // no frame rendered (without an error) for 0.5 s: the render loop is stalled or failing, ack from the audio clock
      if (document.hidden || performance.now() - lastGoodRender > 500) ackChunk(q);
      else setTimeout(check, 250);  // render() sends chunk_end itself when the picture reaches the end
    };
    check();
  };
  queue.push(q);
}

function ackChunk(q) {  // start/end acks with their scheduled times; painted frames only as actually painted
  if (!q.startedSent) {
    q.startedSent = true;
    send({type: "chunk_start", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.start)});
  }
  if (!q.endedSent) {
    q.endedSent = true;
    send({type: "chunk_end", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.end),
          painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint});
  }
}

function stopAll() {
  if (window.__avTrace) window.__avTrace.push({stop: true, p: performance.now()});  // test hook
  epoch += 1;
  if (pending) {
    pending.frames.forEach(frame => Promise.resolve(frame).then(image => image.close?.()).catch(() => {}));
    pending.video?.then(frames => frames.forEach(image => image.close?.())).catch(() => {});
  }
  pending = null; decoding = [];
  $("caption").textContent = "";  // the scripted caption must not outlive a barge-in or erasure
  for (const q of queue) {
    try { q.src.stop(); } catch (e) {}
    q.frames.forEach(frame => frame.close?.());
  }
  queue = []; playhead = audioCtx ? audioCtx.currentTime : 0;
}

// AudioContext time -> performance clock (ms) at the audio *output* (includes output latency).
function ctxToPerf(t) {
  const o = audioCtx.getOutputTimestamp ? audioCtx.getOutputTimestamp() : null;
  if (!o || !o.performanceTime) return performance.now() + (t - audioCtx.currentTime) * 1000;
  return o.performanceTime + (t - o.contextTime) * 1000;
}

// The context time of the sample the listener hears right now. audioCtx.currentTime runs ahead of the speaker by the
// output latency (tens of ms wired, 150-300 ms on Bluetooth), so frames picked by it show the mouth before the voice.
function heardTime() {
  const o = audioCtx.getOutputTimestamp ? audioCtx.getOutputTimestamp() : null;
  if (o && o.performanceTime > 0 && o.contextTime > 0) return o.contextTime + (performance.now() - o.performanceTime) / 1000;
  return audioCtx.currentTime - ((audioCtx.baseLatency || 0) + (audioCtx.outputLatency || 0));  // both stages
}

// ---------------------------------------------------------------- lip sync
// A frame is drawn for the sound the listener hears when that frame reaches the screen: the heard time (above), plus
// one display refresh (a canvas drawn now appears at the next vsync at the earliest; the real display delay is not
// observable from a page, so this is an estimate), minus the viewer's own offset ("画面延后": Bluetooth headsets often
// add more delay than the device reports; the beep-and-flash test measures the whole chain by eye and ear).
// Caption and board switch on the same clock.
// chunks stay drawable this long after their end: the slider can move the picture back by its whole range (-300 -> +300)
const AV_KEY = "liveagent.avOffsetMs", AV_MAX_S = 0.3, RETAIN_S = 2 * AV_MAX_S + 0.05;
let avOffsetMs = 0, refreshS = 1 / 60, lastRaf = 0, rendering = false, calib = null, onScreen = null, lastBoard = null;
let lastGoodRender = 0;  // performance time of the last frame rendered without an error
try { avOffsetMs = Math.max(-300, Math.min(300, Number(localStorage.getItem(AV_KEY)) || 0)); } catch (e) {}
function mediaTime() { return heardTime() + refreshS - avOffsetMs / 1000; }
function startRender() { if (!rendering) { rendering = true; requestAnimationFrame(render); } }
function setAvOffset(ms) {
  avOffsetMs = Math.max(-AV_MAX_S * 1000, Math.min(AV_MAX_S * 1000, Math.round(ms / 10) * 10));
  $("avOffset").value = avOffsetMs; $("avOffsetV").textContent = `${avOffsetMs > 0 ? "+" : ""}${avOffsetMs} ms`;
  try { localStorage.setItem(AV_KEY, String(avOffsetMs)); } catch (e) {}
}
function avInfo() {
  if (!audioCtx) { $("avInfo").textContent = ""; return; }
  const out = Math.max(0, audioCtx.currentTime - heardTime());
  $("avInfo").textContent = tr("av.reportOutput", "声卡报告的输出延迟 ≈ ") + Math.round(out * 1000) +
    tr("av.reportRefresh", " ms，屏幕刷新 ≈ ") + Math.round(refreshS * 1000) + tr("av.reportCompensated", " ms（均已自动补偿）");
}
$("avBtn").onclick = () => {
  const p = $("avPanel"), open = p.hidden;
  p.hidden = !open; $("avBtn").setAttribute("aria-expanded", String(open));
  if (open) avInfo();
};
$("avOffset").oninput = (e) => setAvOffset(+e.target.value);
$("avReset").onclick = () => setAvOffset(0);
$("avTest").onclick = () => {  // six beeps on the audio clock, each with a white flash drawn on the media clock
  audioCtx = audioCtx || new AudioContext();
  audioCtx.resume();
  if (calib) calib.oscs.forEach(o => { try { o.stop(); } catch (e) {} });  // a second click restarts the test
  const t0 = audioCtx.currentTime + 0.3, times = [], oscs = [];
  for (let i = 0; i < 6; i++) {
    const t = t0 + i * 0.8, osc = audioCtx.createOscillator(), env = audioCtx.createGain();
    osc.frequency.value = 1000; env.gain.setValueAtTime(0, t);
    env.gain.linearRampToValueAtTime(0.5, t + 0.005); env.gain.setValueAtTime(0.5, t + 0.07);
    env.gain.linearRampToValueAtTime(0, t + 0.08);
    osc.connect(env).connect(audioCtx.destination);  // not through outGain: push-to-talk ducking must not mute it
    osc.start(t); osc.stop(t + 0.09);
    times.push(t); oscs.push(osc);
  }
  calib = {times, oscs, until: t0 + 6 * 0.8};
  startRender(); setTimeout(avInfo, 500);
};
setAvOffset(avOffsetMs);
if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {  // a new headset has its own delay
  navigator.mediaDevices.addEventListener("devicechange", () => {
    if (avOffsetMs) chat("sys", tr("device.changed", "音频设备变了；如果口型和声音对不上，可以打开音画同步重新测试。"));
  });
}

function render(ts) {
  try { renderFrame(ts); lastGoodRender = performance.now(); }
  catch (e) { console.error("render", e); }  // one bad frame must not stop the picture for the rest of the session
  if (rendering) requestAnimationFrame(render);
}

function renderFrame(ts) {
  if (window.__avTrace) window.__avRenders = (window.__avRenders || 0) + 1;  // test hook: one loop, not two
  if (lastRaf && ts > lastRaf) {  // the display's refresh interval, smoothed (60 Hz: 16.7 ms)
    const dt = (ts - lastRaf) / 1000;
    if (dt > 0.004 && dt < 0.05) refreshS += 0.1 * (dt - refreshS);
  }
  lastRaf = ts || lastRaf;
  if (calib && audioCtx) {
    const mt = mediaTime(), on = calib.times.some(b => mt >= b && mt < b + 0.08);
    if (on && !calib.on && window.__avFlashLog) window.__avFlashLog.push(heardTime());  // test hook
    calib.on = on; $("avFlash").style.opacity = on ? "0.9" : "0";
    if (mt > calib.until) { calib = null; $("avFlash").style.opacity = "0"; }
  }
  if (audioCtx) {
    const t = mediaTime();  // frames, caption and board follow the sound as heard (lip sync)
    for (const q of queue) {
      if (!q.startedSent && t >= q.start) {
        q.startedSent = true; $("overlay").style.display = "none";
        send({type: "chunk_start", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.start)});
      }
      if (t >= q.start && t < q.end && onScreen !== q) {  // caption and board of the chunk on screen, in either
        onScreen = q;                                      // direction (the slider can move the picture back)
        if (q.meta.transcript) $("caption").innerHTML = `<small>${esc(tr("caption.label", "老师"))}</small>${esc(q.meta.transcript)}`;
        if (q.board && q.board !== shownBoard) showBoard(q.board);  // the board point being spoken
      }
      if (q.startedSent && t >= q.start && t < q.end && q.frames.length) {  // t can move back (offset change)
        const idx = Math.max(0, Math.min(q.frames.length - 1, Math.floor((t - q.start) / (q.end - q.start) * q.frames.length)));
        g.drawImage(q.frames[idx], 0, 0, canvas.width, canvas.height);
        (q.painted = q.painted || new Set()).add(idx);  // frames actually shown (QC evidence)
        q.lastPaint = performance.now();
        if (window.__avTrace) window.__avTrace.push({t, heard: heardTime(), ctx: audioCtx.currentTime, p: performance.now(),
                                                     start: q.start, end: q.end, idx, n: q.frames.length,
                                                     key: `${q.meta.request}/${q.meta.chunk}`, line: q.meta.transcript || "",
                                                     cap: $("caption").textContent, ended: q.endedSent,
                                                     board: q.board ? q.board.key : null,
                                                     shown: shownBoard ? shownBoard.key : null});
      }
      if (!q.endedSent && t >= q.end) {  // a snapshot: if the slider later takes the picture back into this chunk,
        q.endedSent = true;              // those paints are not reported (painted stays conservative, E a lower bound)
        send({type: "chunk_end", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.end),
              painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint});
      }
    }
    // a chunk leaves only when its picture is done plus the slider's whole range: moving the slider can take the
    // picture back into a chunk that ended, and its frames must still be there
    queue = queue.filter(q => !(q.endedSent && t >= q.end + RETAIN_S));
  }
}

// ---------------------------------------------------------------- camera focus check (opt-in)
// A 320x240 frame every 3 s goes to the server only while the student has switched this on; the server analyses it
// in memory (focused / distracted / absent) and never stores or records it.
let camStream = null, camTimer = null, camPending = false, camRequest = 0;
const camCanvas = document.createElement("canvas"); camCanvas.width = 320; camCanvas.height = 240;
async function camOn() {
  if (!ready() || !sessionStatus?.attention || camStream || camPending) return;
  const request = ++camRequest, socket = ws, attempt = connectionAttempt;
  camPending = true; $("cam").disabled = true; $("cam").textContent = tr("camera.permission", "等待摄像头授权…");
  let stream;
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera unavailable");
    stream = await navigator.mediaDevices.getUserMedia({video: {width: {ideal: 320}, height: {ideal: 240}, facingMode: "user"}, audio: false});
  } catch (e) {
    if (request === camRequest && activeSocket(socket, attempt)) {
      camPending = false; $("cam").disabled = false; $("cam").textContent = tr("camera.on", "开启专注检测");
      permissionNotice("camera", e);
    }
    return;
  }
  if (request !== camRequest || !activeSocket(socket, attempt) || !ready()) {
    stream.getTracks().forEach(track => track.stop()); return;
  }
  camPending = false; camStream = stream; $("cam").disabled = false;
  const v = $("camView"); v.srcObject = camStream; v.hidden = false; v.play().catch(() => {});
  camTimer = setInterval(() => {
    if (!activeSocket(socket, attempt) || !ready() || !v.videoWidth) return;
    camCanvas.getContext("2d").drawImage(v, 0, 0, 320, 240);
    send({type: "camera", jpeg: camCanvas.toDataURL("image/jpeg", 0.6).split(",")[1]});
  }, 3000);
  $("cam").textContent = tr("camera.off", "关闭专注检测");
  $("focus").textContent = tr("camera.enabled", "专注检测已开启：画面用于判断，不保存。");
}
function camOff(tell = true) {
  camRequest++; camPending = false;
  if (camTimer) clearInterval(camTimer);
  camTimer = null;
  if (camStream) camStream.getTracks().forEach(t => t.stop());
  const was = !!camStream; camStream = null;
  $("camView").srcObject = null; $("camView").hidden = true; $("cam").textContent = tr("camera.on", "开启专注检测");
  if (was && tell) send({type: "camera_off"});
  $("cam").disabled = !ready() || !sessionStatus?.attention;
  $("focus").className = "focusline"; $("focus").textContent = tr("camera.disabled", "专注检测未开启");
}
$("cam").onclick = () => camStream ? camOff() : camOn();

// ---------------------------------------------------------------- input
// A comment does not cut the video here: the server keeps it playing and sends "stop" when the reply is ready.
// While the user holds push-to-talk the persona's audio is muted (not the video) so the mic hears only the user.
let master = null;  // output gain: every chunk's audio goes through it
function outGain() {
  if (!master) { master = audioCtx.createGain(); master.connect(audioCtx.destination); }
  return master;
}
function duck(on) { if (audioCtx) outGain().gain.setTargetAtTime(on ? 0 : 1, audioCtx.currentTime, 0.03); }
let micPressed = false, micRequest = 0, micStream = null, micUploading = false;
function permissionNotice(device, error) {
  const kind = {NotAllowedError: "denied", SecurityError: "denied", NotFoundError: "missing", NotReadableError: "busy"}[error.name] || "failed";
  const messages = {
    voice: {denied: "麦克风未获授权，可以在浏览器里允许，或者用文字提问。", missing: "没有找到麦克风，可以接上麦克风，或者用文字提问。", busy: "麦克风正在被别的程序使用，可以先用文字提问。", failed: "暂时无法录音，可以用文字提问。"},
    camera: {denied: "摄像头未获授权，不开摄像头也可以继续学习。", missing: "没有找到摄像头，不开摄像头也可以继续学习。", busy: "摄像头正在被别的程序使用，不开摄像头也可以继续学习。", failed: "暂时无法使用摄像头，不开摄像头也可以继续学习。"},
  };
  notice(`${device}.${kind}`, messages[device][kind], error);
}
function resetTalkButton() {
  $("talk").classList.remove("recording"); $("talk").textContent = tr("voice.hold", "按住说话");
}
function cancelSpeech() {
  micPressed = false; micUploading = false; micRequest++;
  if (recorder) {
    recorder.onstop = null; recorder.ondataavailable = null;
    if (recorder.state !== "inactive") { try { recorder.stop(); } catch (e) {} }
  }
  micStream?.getTracks().forEach(track => track.stop()); micStream = null; recorder = null;
  duck(false); resetTalkButton();
}
$("talk").onpointerdown = async event => {
  if (!ready() || !sessionStatus?.asr || micPressed || micUploading || recorder?.state === "recording") return;
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    notice("voice.unavailable", "这个浏览器暂时不能录音，可以用文字提问。"); return;
  }
  micPressed = true;
  const request = ++micRequest, socket = ws, attempt = connectionAttempt;
  $("talk").textContent = tr("voice.permission", "等待麦克风授权…");
  try { if (event?.pointerId != null) $("talk").setPointerCapture(event.pointerId); } catch (e) {}
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
    if (!micPressed || request !== micRequest || !activeSocket(socket, attempt) || !ready()) {
      stream.getTracks().forEach(track => track.stop()); return;
    }
    const parts = [];
    const recording = new MediaRecorder(stream); recorder = recording; micStream = stream;
    recording.ondataavailable = e => { if (e.data.size) parts.push(e.data); };
    recording.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      if (recorder === recording) { recorder = null; micStream = null; }
      if (!parts.length || !activeSocket(socket, attempt) || request !== micRequest) return;
      micUploading = true; $("talk").disabled = true;
      try {
        const bytes = await new Blob(parts).arrayBuffer();
        if (!activeSocket(socket, attempt) || request !== micRequest || !ready()) return;
        if (send({type: "audio_end", tp: recording.endedAt ?? performance.now()}, socket)) socket.send(bytes);
      } catch (error) { if (activeSocket(socket, attempt)) permissionNotice("voice", error); }
      finally {
        if (request === micRequest && activeSocket(socket, attempt)) {
          micUploading = false; $("talk").disabled = !ready() || !sessionStatus?.asr;
        }
      }
    };
    recording.onerror = error => {
      if (request === micRequest && activeSocket(socket, attempt)) {
        cancelSpeech(); permissionNotice("voice", error.error || error);
      }
    };
    recording.start();
    if (!send({type: "speech_start"}, socket)) throw new Error("Unable to start voice input");
    duck(true); $("talk").classList.add("recording"); $("talk").textContent = tr("voice.release", "松开发送");
  } catch (error) {
    stream?.getTracks().forEach(track => track.stop());
    if (request === micRequest && activeSocket(socket, attempt)) {
      cancelSpeech(); permissionNotice("voice", error);
    }
  }
};
function endSpeech(cancel = false) {
  if (cancel) { cancelSpeech(); return; }
  if (!micPressed) return;
  micPressed = false;
  duck(false);
  if (recorder?.state === "recording") { recorder.endedAt = performance.now(); recorder.stop(); }
  else micRequest++;  // releasing while permission is pending cancels that request
  resetTalkButton();
}
$("talk").onpointerup = () => endSpeech();
$("talk").onpointerleave = event => { if (!$("talk").hasPointerCapture?.(event?.pointerId)) endSpeech(); };
$("talk").onpointercancel = () => endSpeech();
$("talk").onkeydown = event => {
  if ([" ", "Enter"].includes(event.key) && !event.repeat) { event.preventDefault(); $("talk").onpointerdown(); }
};
$("talk").onkeyup = event => {
  if ([" ", "Enter"].includes(event.key)) { event.preventDefault(); endSpeech(); }
};
$("talk").onblur = () => { if (micPressed) endSpeech(); };
addEventListener("blur", () => { if (micPressed || recorder) endSpeech(); });
function sendText(v, lessonContext) {
  v = (v ?? $("text").value).trim(); if (!v || !ready()) return false;
  const packet = {type: "text", text: v, tp: performance.now()};
  if (lessonContext && typeof lessonContext.subject === "string" && lessonContext.subject.trim() &&
      Number.isInteger(lessonContext.grade) && lessonContext.grade >= 1 && lessonContext.grade <= 12 &&
      typeof lessonContext.topic === "string" && lessonContext.topic.trim()) {
    packet.lesson_context = {subject: lessonContext.subject.trim(), grade: lessonContext.grade, topic: lessonContext.topic.trim()};
  }
  if (!send(packet)) {
    notice("session.sendFailed", "消息还没有发出去，请重新连接后再试。"); return false;
  }
  chat("user", v); $("text").value = ""; return true;
}
$("send").onclick = () => sendText();
$("text").onkeydown = e => { if (e.key === "Enter" && !e.isComposing && !e.shiftKey) { e.preventDefault(); sendText(); } };
addEventListener("pagehide", () => { $("disconnect").onclick(); cancelSpeech(); camOff(false); });

===== FILE: frontend/public/assets/live.css =====
:root{color-scheme:light;--bg:#f7f8f2;--panel:#fff;--ink:#20342f;--muted:#63746b;--line:#e3e9df;--accent:#276653;--accent-soft:#edf3e7;--lime:#ddecad;--ok:#276653;--bad:#a83e38;--warn:#906021;--info:#466e80;--chip:#f0f4eb;--stage:#243f36;--radius:20px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC","PingFang SC",sans-serif}a{color:var(--accent);text-underline-offset:4px}button,input,select,textarea{font:inherit;color:inherit}button,select,input,textarea{border:1px solid var(--line);border-radius:10px;background:var(--panel)}button{padding:10px 15px;min-height:44px;cursor:pointer;font-weight:600;transition:background .16s,transform .16s}button:hover:not(:disabled){background:var(--accent-soft)}button:active:not(:disabled){transform:translateY(1px)}button:disabled,input:disabled,select:disabled{opacity:.48;cursor:not-allowed}input,select,textarea{padding:10px 12px;min-height:44px;min-width:0}select{cursor:pointer}input,textarea{outline-offset:3px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}[hidden]{display:none!important}.icon-defs{position:absolute;width:0;height:0;overflow:hidden}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}.skip-link{position:fixed;top:10px;left:10px;z-index:100;background:white;padding:12px;transform:translateY(-150%)}.skip-link:focus{transform:none}h1,h2,h3,p{margin-top:0}h2{font-size:18px;line-height:1.4;letter-spacing:-.025em;margin-bottom:0}h3{font-size:17px}p{margin-bottom:12px}strong{font-weight:650}.app-shell{display:flex;min-height:100vh}.sidebar{width:226px;flex:0 0 226px;background:#fffdf7;border-right:1px solid var(--line);padding:35px 20px 20px;display:flex;flex-direction:column;height:100vh;position:sticky;top:0}.brand{display:flex;align-items:center;gap:12px;text-decoration:none;padding:0 12px 40px}.brand-mark{display:grid;place-items:center;width:42px;height:44px;border-radius:16px 16px 16px 4px;background:var(--accent);color:var(--lime)}.brand strong{font-size:24px;letter-spacing:.14em;line-height:1}.brand small{display:block;font-size:8px;letter-spacing:.2em;color:var(--muted);margin-top:7px}.sidebar-label{font-size:10px;letter-spacing:.07em;color:var(--muted);padding:0 16px;margin-bottom:12px}.navigation{display:grid;gap:6px}.nav-item{display:flex;align-items:center;gap:13px;padding:13px 15px;border:0;border-radius:11px;color:var(--muted);font-weight:550;text-decoration:none;background:transparent;white-space:nowrap}.nav-item.active{color:var(--accent);background:var(--accent-soft);font-weight:700}.nav-item:hover{background:var(--accent-soft)}.sidebar-note{margin:auto 12px 20px;padding:24px 14px 12px;background:#f1f3e7;border-radius:16px;transform:rotate(-2deg)}.sidebar-note>span{font-size:24px;color:var(--accent)}.sidebar-note p{font-size:12px;line-height:2;color:#637252;margin-top:8px}.help-button{width:100%;text-align:left}.service-indicator{display:flex;align-items:center;gap:8px;padding:13px 15px 0;color:var(--muted);font-size:10px}.service-indicator i{width:6px;height:6px;border-radius:50%;background:#aaa}.service-indicator i.ready{background:var(--ok)}.service-indicator i.error{background:var(--bad)}.workspace{flex:1;min-width:0;max-width:1800px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;min-height:88px;border-bottom:1px solid var(--line);padding:20px 40px}.breadcrumb{display:flex;gap:13px;font-size:11px;color:var(--muted)}.breadcrumb strong{font-weight:500;color:var(--ink)}.edition-control{display:flex;align-items:center;gap:12px;font-size:11px;color:var(--muted)}.edition-control select{font-size:12px;background:transparent;border-color:var(--line);min-height:38px;padding:8px 10px;color:var(--ink);max-width:250px}main{padding:24px 40px 40px;max-width:1480px;margin:auto}.welcome{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:24px;min-height:177px}.welcome-copy{padding-top:10px}.eyebrow{display:block;font-size:9px;font-weight:650;letter-spacing:.16em;color:var(--muted);margin-bottom:10px}.welcome h1{font-size:clamp(25px,2.4vw,36px);line-height:1.35;font-weight:650;letter-spacing:-.045em;margin:8px 0 12px}.welcome p{color:var(--muted);font-size:12px;margin-bottom:20px}.welcome-tags{display:flex;gap:20px;font-size:11px;color:var(--accent)}.welcome-tags>span{display:flex;align-items:center;gap:5px}.welcome-tags svg{width:14px;height:14px}.welcome-art{width:250px;height:160px;stroke:none;flex:0 0 250px}.learning-grid{display:grid;grid-template-columns:minmax(0,1fr) 288px;gap:24px;align-items:start}.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:24px;min-width:0;box-shadow:0 4px 20px #213b2703}.card-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px}.card-heading .eyebrow{margin-bottom:6px}.badge{padding:5px 11px;border-radius:30px;background:var(--chip);color:var(--muted);font-size:10px;white-space:nowrap;display:inline-flex;gap:5px;align-items:center}.badge:before{content:"";width:5px;height:5px;background:currentColor;border-radius:50%}.badge.live{background:#eaf4e8;color:var(--accent)}.room-meta{display:flex;align-items:center;gap:10px;margin-bottom:20px}.teacher-avatar{display:grid;place-items:center;width:35px;height:35px;background:#f2ebd9;border-radius:12px;font-size:20px;color:var(--accent)}.room-meta strong{display:block;font-size:12px}.room-meta>div>span{display:block;font-size:10px;color:var(--muted)}.private-label{margin-left:auto;font-size:9px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:1px 7px}.stagerow{display:flex;gap:12px;align-items:stretch;min-width:0}.screen{position:relative;border-radius:13px;background:#29473c;display:flex;justify-content:center;align-items:center;overflow:hidden;flex:0 1 auto;min-width:0;min-height:150px}canvas{display:block;max-width:100%;width:auto;height:auto}.screen:has(.overlay[style*="none"]) .video-decoration{display:none}.video-decoration{position:absolute;top:24%;left:0;right:0;display:flex;flex-direction:column;align-items:center;gap:10px;pointer-events:none;color:#cedbc3}.video-decoration svg{width:46px;height:46px;stroke-width:1}.video-decoration span{font-size:7px;letter-spacing:.2em;color:#b1c3aa}.overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:16px;text-align:center;font-size:11px;line-height:2;color:#e9eedf;white-space:pre-line;pointer-events:none;padding-top:60px}.avflash{position:absolute;inset:0;background:white;opacity:0;pointer-events:none}.board{display:none;position:relative;flex:0 0 auto;min-width:0;overflow:hidden;border-radius:13px;background:#f2f5ec;color:#344f3b;padding:25px 25px 30px;font-size:17px;line-height:1.9;background-image:linear-gradient(#d9e0d14d 1px,transparent 1px);background-size:100% 29px;background-position:0 17px}.board.on{display:flex;flex-direction:column}.board h3{margin:0 0 15px;font-size:18px;font-weight:600;border-bottom:1px solid #c6d2bc;padding-bottom:11px;line-height:1.45}.board .body{flex:1;min-height:0;display:grid;grid-template-columns:1fr;gap:3%}.board.hasfig .body{grid-template-columns:52% 45%}.board ol{margin:0;padding-left:1.3em;overflow:hidden;min-height:0}.board li{margin:10px 0;transition:opacity .3s}.board li.hidden{opacity:0}.board li.now{color:var(--accent);font-weight:650}.board figure{margin:0;display:none;flex-direction:column;align-items:center;justify-content:center;min-height:0}.board.hasfig figure{display:flex}.board figure img{max-width:100%;max-height:88%;border-radius:6px;background:#fff;object-fit:contain}.board figcaption{font-size:.8em;margin-top:.4em;text-align:center}.board .dots{font-size:.6em;letter-spacing:.18em;margin-left:.5em}.board-signature{position:absolute;bottom:9px;right:16px;color:#8d9e81;font:italic 9px Georgia,serif;letter-spacing:2px}.caption{font-size:14px;min-height:22px;margin:10px 0;line-height:1.6;overflow-wrap:anywhere}.caption small{font-size:10px;color:var(--muted);margin-right:6px}.session-controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:15px 0;border-top:1px solid var(--line);margin-top:8px}.student-picker{display:flex;align-items:center;gap:7px;font-size:10px;color:var(--muted);min-width:0}.student-picker svg{width:15px;height:15px}.student-picker select{min-height:34px;padding:5px 6px;max-width:180px;font-size:11px;border:0;background:var(--chip)}.session-controls>a{font-size:10px;text-decoration:none}.session-actions{display:flex;gap:6px;margin-left:auto}.session-actions button{font-size:11px;min-height:38px;padding:8px 13px}.primary{background:var(--accent);border-color:var(--accent);color:#fff}.primary:hover:not(:disabled){background:#1c4d3e;border-color:#1c4d3e}.composer{display:flex;gap:8px;border:1px solid var(--line);border-radius:12px;padding:6px;background:#fcfdf9}.composer:focus-within{border-color:var(--accent)}.composer input{flex:1;border:0;background:transparent;width:100%;font-size:12px;min-height:40px}.send-button{display:flex;align-items:center;justify-content:center;gap:5px;font-size:11px;min-height:38px;padding:7px 12px}.send-button svg{width:16px;height:16px}.input-toolbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:10px 0 17px}.input-toolbar button{min-height:32px;padding:4px 8px;border:0;background:#f4f6ee;font-size:10px;font-weight:500}.input-hint{margin-left:auto;font-size:9px;color:var(--muted)}.talk.recording{background:var(--bad);color:white}.camview{width:72px;height:54px;object-fit:cover;transform:scaleX(-1);border-radius:8px}.avsync{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:14px;border:1px solid var(--line);border-radius:12px;font-size:12px;margin-bottom:18px}.avsync input[type=range]{width:min(230px,100%);padding:0;min-height:20px}.avsync button{font-size:11px;min-height:34px;padding:6px 10px}.avsync p,.avsync .meta{flex-basis:100%;margin:0}.suggestion-label{font-size:10px;color:var(--muted);margin-bottom:8px}.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{font-size:10px;min-height:32px;padding:5px 10px;border:1px solid var(--line);background:white;border-radius:7px;font-weight:500}.chip.answer{border-color:var(--accent);background:var(--accent-soft);font-weight:650}.room-footnote{font-size:9px;color:var(--muted);margin:16px 0 0}.study-panel{display:flex;flex-direction:column;gap:18px}.study-panel .card{padding:22px}.study-panel h2{font-size:15px}.small-icon{width:18px;height:18px;color:var(--accent)}.meta{font-size:11px;color:var(--muted);line-height:1.8}.lesson-card .card-heading{margin-bottom:10px}.lesson-card>label{display:block;font-size:10px;font-weight:600;margin:16px 0 6px}.lesson-card>input{width:100%;background:#fbfcf7;font-size:11px}.wide{width:100%;font-size:12px;margin-top:10px}.lesson-card>p:last-of-type{margin:10px 0 18px;font-size:10px}.learning-steps{list-style:none;padding:0;margin:0;border-top:1px solid var(--line);padding-top:17px}.learning-steps li{display:flex;align-items:center;gap:12px;margin-bottom:17px;color:var(--muted)}.learning-steps li>span{display:grid;place-items:center;border:1px solid var(--line);border-radius:50%;width:26px;height:26px;font-size:10px}.learning-steps li.current>span{background:var(--lime);color:var(--accent);border-color:var(--lime)}.learning-steps strong{display:block;font-size:11px}.learning-steps small{display:block;font-size:9px;color:var(--muted)}.learning-steps .current strong{color:var(--accent)}.text-button{border:0;background:transparent;color:var(--accent);padding:3px 0;min-height:32px;font-size:11px;font-weight:550;text-decoration:none}.lesson-card .text-button{font-size:10px}.prof .who{font-size:12px;font-weight:600;margin-bottom:10px}.prof .exams{font-size:10px;color:var(--muted);margin:0 0 13px;padding-left:14px}.prof .meta{font-size:9px}.prof .cp{display:grid;grid-template-columns:minmax(60px,7em) 1fr 3.4em;gap:6px;align-items:center;font-size:10px;margin:7px 0}.prof .bar{height:5px;border-radius:4px;background:var(--chip);overflow:hidden}.prof .bar i{display:block;height:100%;background:var(--info)}.prof .cp.weak .bar i{background:#c39466}.prof .cp.partial .bar i{background:#bbaf60}.prof .cp.mastered .bar i{background:var(--ok)}.prof .v{font-size:9px;color:var(--muted);text-align:right}.profile-disclaimer{margin:14px 0 0;padding-top:10px;border-top:1px solid var(--line)}.gentle-note{display:flex;gap:14px;padding:2px 15px;color:#637451}.gentle-note>span{font-size:28px;color:#a2b88c}.gentle-note p{font-size:11px;line-height:1.9;margin:0}.course-section{padding-top:38px;scroll-margin-top:24px}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:10px}.section-heading h2{font-size:22px}.course-filters{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0 18px}.course-filters label{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted)}.course-filters select,.course-filters input{font-size:11px;min-height:38px}.course-search{margin-left:auto}.course-search input{width:220px;background:transparent}.course-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.course-card{position:relative;text-align:left;border:1px solid var(--line);border-radius:14px;padding:20px 20px 16px;background:white;min-height:134px;display:flex;flex-direction:column;align-items:flex-start;overflow:hidden}.course-card:hover{border-color:#aabf99!important;background:white!important;box-shadow:0 6px 20px #2e4c2310}.course-subject{font-size:9px;color:var(--muted);display:flex;gap:8px;align-items:center;margin-bottom:12px}.course-icon{width:26px;height:26px;background:var(--accent-soft);border-radius:8px;display:grid;place-items:center;font-size:13px;color:var(--accent)}.course-card strong{font-size:15px;line-height:1.5;font-weight:600;margin:0 30px 10px 0;overflow-wrap:anywhere}.course-bottom{font-size:9px;color:var(--muted);display:flex;justify-content:space-between;gap:10px;width:100%;margin-top:auto}.course-bottom>span:last-child{color:var(--accent)}.more-courses{display:block;margin:16px auto 0}.reflection-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:32px}.reflection-grid h2{font-size:15px}.chat{height:190px;overflow:auto;display:flex;flex-direction:column;gap:8px;overscroll-behavior:contain}.msg{max-width:90%;padding:9px 12px;border-radius:12px;font-size:12px;overflow-wrap:anywhere}.msg.user{align-self:flex-end;background:var(--accent);color:white;border-bottom-right-radius:3px}.msg.persona{align-self:flex-start;background:var(--chip);border-bottom-left-radius:3px}.msg.sys{align-self:center;color:var(--muted);font-size:10px;background:transparent;padding:3px}.empty{font-size:12px;line-height:1.8;color:var(--muted);padding:6px 0}.note-save{font-size:9px;color:var(--muted)}.notes-card textarea{display:block;width:100%;height:151px;min-height:151px;resize:vertical;border:0;background:repeating-linear-gradient(transparent,transparent 29px,#e7ecdf 29px,#e7ecdf 30px);font-size:12px;line-height:30px;padding:0 6px;border-radius:0}.notes-footer{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:10px}.notes-footer .meta{font-size:9px}.diagnostics{margin-top:26px;border-top:1px solid var(--line);padding-top:14px}.diagnostics summary{color:var(--muted);font-size:11px;cursor:pointer;min-height:36px}.diagnostic-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px}.diagnostic-grid h2{font-size:13px;margin-bottom:12px}.settings-row{display:flex;flex-wrap:wrap;gap:10px}.settings-row label{display:grid;gap:5px;font-size:11px;flex:1;min-width:140px}.settings-row input,.settings-row select{width:100%;font-size:11px}.badges{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.stat{padding:8px;background:var(--chip);border-radius:10px}.stat b{display:block;font-size:17px;font-variant-numeric:tabular-nums}.stat span{font-size:9px;color:var(--muted)}.feed{max-height:220px;overflow:auto;font-size:11px}.ev{display:grid;grid-template-columns:40px 1fr;gap:6px;padding:5px;border-radius:6px}.ev:nth-child(odd){background:var(--chip)}.ev .t{color:var(--muted)}.ev .what{font-weight:600;margin-right:4px}.ev.ok{color:var(--ok)}.ev.bad{color:var(--bad)}.ev.warn{color:var(--warn)}.chain{border:1px solid var(--line);border-radius:8px;padding:8px;margin-bottom:6px;font-size:11px}.chain .top{display:flex;justify-content:space-between;gap:10px}.pill{font-size:9px;background:var(--chip);padding:2px 6px;border-radius:10px;white-space:nowrap}.focusline{font-size:11px;margin:10px 0;padding:8px;background:var(--chip);border-radius:8px}.connection-error,.notice{padding:14px 18px;background:#fff6e9;border:1px solid #e4ceaa;color:#765627;border-radius:12px;font-size:12px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;gap:12px}.connection-error{background:#fff3ee;border-color:#e6c5b9;color:#903f30}.connection-error button{white-space:nowrap;min-height:32px;font-size:11px}.exercise-card{background:#f5f8ea}.exercise-card p{font-size:13px;white-space:pre-line}.exercise-card .meta{font-size:10px}.exercise-card #exerciseFeedback{font-size:12px;font-weight:600;color:var(--accent);margin:12px 0}footer{display:flex;justify-content:space-between;gap:14px;font-size:10px;color:var(--muted);padding:22px 40px;border-top:1px solid var(--line)}dialog{color:var(--ink);border:1px solid var(--line);border-radius:22px;width:min(540px,calc(100% - 32px));padding:28px;box-shadow:0 20px 80px #20342f30}dialog::backdrop{background:#20342f66;backdrop-filter:blur(3px)}.dialog-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.dialog-heading button{font-size:24px;border:0;min-width:44px;padding:0}.help-steps{padding-left:22px;font-size:13px;line-height:1.9}.help-steps li{padding-bottom:13px}dialog p{margin:14px 0 0}
html[data-edition=primary]{--bg:#fff9ee;--accent:#397458;--accent-soft:#edf4dd;--lime:#e7eeb0;--radius:24px}html[data-edition=primary] body{font-size:16px}html[data-edition=primary] .welcome h1{font-size:38px}html[data-edition=primary] .chip{min-height:40px;font-size:12px}html[data-edition=primary] .composer input{font-size:14px}html[data-edition=primary] .learning-steps strong{font-size:13px}html[data-edition=primary] .learning-steps small{font-size:11px}html[data-edition=primary] .room-footnote{font-size:10px}html[data-edition=primary] .lesson-card>input{font-size:13px}html[data-edition=primary] .session-actions button{font-size:13px;min-height:44px}
html[data-edition=university]{--accent:#355b78;--accent-soft:#eef3f6;--lime:#dce9ee;--stage:#294151;--radius:14px}html[data-edition=university] .welcome-art{opacity:.7}html[data-edition=university] .welcome h1{font-weight:550;letter-spacing:-.05em}html[data-edition=university] .screen{background:#294151}html[data-edition=university] .board{color:#31495b;background-color:#f0f4f5}html[data-edition=university] .sidebar-note{transform:none;background:#eff3f3}html[data-edition=university] .brand strong{letter-spacing:-.04em;font-size:23px}
@media(min-width:1600px){.learning-grid{grid-template-columns:minmax(0,1fr) 330px}.study-panel .card{padding:26px}.course-card strong{font-size:18px}.welcome h1{font-size:40px}}
@media(max-width:1180px){.sidebar{width:185px;flex-basis:185px;padding:30px 12px 16px}.topbar{padding:18px 24px}main{padding:20px 24px 32px}.learning-grid{grid-template-columns:minmax(0,1fr) 260px;gap:16px}.card{padding:20px}.welcome-art{width:190px;flex-basis:190px;height:145px}.input-hint{flex-basis:100%;margin-left:0}.session-controls{gap:8px}.session-actions{margin-left:0}.study-panel .card{padding:20px}.course-list{gap:10px}.course-card{padding:15px}.course-card strong{font-size:13px}}
@media(max-width:980px){.sidebar{width:80px;flex-basis:80px;padding:28px 10px 14px}.brand{padding:0 8px 30px}.brand>span:last-child,.sidebar-label,.nav-item>span,.sidebar-note,.service-indicator span{display:none}.nav-item{justify-content:center;padding:15px}.service-indicator{justify-content:center;padding:20px 0}.help-button{margin-top:auto}.learning-grid{grid-template-columns:minmax(0,1fr) 252px}.welcome h1{font-size:28px}.welcome-art{width:170px;flex-basis:170px}.welcome p{max-width:380px}.topbar .breadcrumb{font-size:10px}.edition-control>span{display:none}}
@media(max-width:860px){.learning-grid{grid-template-columns:1fr}.study-panel{display:grid;grid-template-columns:1fr 1fr;align-items:start}.gentle-note{display:none}.stagerow{flex-direction:column}.screen{align-self:center;width:100%;max-height:390px}.screen canvas{max-height:390px!important}.board{align-self:center}.video-decoration{top:25%}.overlay{font-size:13px}.study-panel .exercise-card{grid-column:1/-1}.course-list{grid-template-columns:repeat(2,minmax(0,1fr))}.reflection-grid{gap:16px}.welcome{min-height:150px}.session-actions{margin-left:auto}.room-footnote{font-size:10px}.course-search{margin-left:0;flex:1}.course-search input{width:100%}.study-panel .lesson-card{height:100%}}
@media(max-width:620px){.app-shell{display:block}.sidebar{position:relative;width:100%;height:auto;padding:14px 18px;border-right:0;border-bottom:1px solid var(--line);flex-direction:row;justify-content:space-between;align-items:center}.brand{padding:0;gap:8px}.brand>span:last-child{display:block}.brand strong{font-size:18px}.brand small{font-size:6px;margin-top:4px}.brand-mark{width:32px;height:34px;border-radius:11px 11px 11px 3px}.brand-mark svg{width:19px;height:19px}.navigation{display:flex;gap:3px}.nav-item{padding:9px;min-height:40px}.nav-item svg{width:18px;height:18px}.help-button,.service-indicator{display:none}.topbar{min-height:66px;padding:12px 18px;gap:8px}.breadcrumb>span:first-child,.breadcrumb>span:nth-child(2){display:none}.edition-control select{font-size:10px;max-width:210px;min-height:36px}.breadcrumb strong{font-size:11px}main{padding:17px 18px 24px}.welcome{align-items:center;gap:0;margin-bottom:20px;min-height:145px}.welcome-art{display:none}.welcome-copy{padding-top:0}.welcome h1{font-size:28px;margin-top:6px}.welcome p{font-size:12px;line-height:1.8;margin-bottom:14px}.welcome-tags{gap:16px;font-size:10px}.eyebrow{font-size:8px}.card{padding:18px;border-radius:16px}.card-heading h2{font-size:16px}.classroom-card .card-heading{margin-bottom:16px}.private-label{font-size:8px}.screen{max-height:300px}.screen canvas{max-height:300px!important}.board{padding:18px 20px}.board h3{font-size:18px}.session-controls{gap:10px}.student-picker{flex:1}.student-picker select{max-width:155px}.session-actions{width:100%;margin-left:0}.session-actions .primary{flex:1}.session-controls>a{font-size:11px}.input-toolbar{gap:7px}.input-toolbar button{font-size:11px;min-height:38px}.input-hint{font-size:9px}.chips .chip{font-size:11px;min-height:36px}.study-panel{display:flex;gap:16px}.study-panel .card{padding:20px}.study-panel h2{font-size:17px}.lesson-card>input,.lesson-card>label{font-size:13px}.lesson-card>.meta{font-size:12px}.learning-steps strong{font-size:13px}.learning-steps small{font-size:11px}.learning-steps{display:grid;grid-template-columns:1fr;gap:0}.lesson-card .wide{font-size:14px}.prof .who{font-size:14px}.prof .exams,.prof .cp{font-size:12px}.prof .meta{font-size:11px}.prof .bar{height:6px}.prof .v{font-size:11px}.course-section{padding-top:28px}.section-heading h2{font-size:21px}.course-section>.meta{font-size:11px}.course-filters{gap:8px;margin-top:16px}.course-filters label{font-size:10px}.course-filters select{font-size:11px;max-width:150px}.course-search{flex-basis:100%}.course-search input{font-size:12px}.course-list{gap:10px}.course-card{padding:15px;min-height:137px}.course-card strong{font-size:14px}.course-bottom{flex-wrap:wrap;gap:4px}.reflection-grid{grid-template-columns:1fr;margin-top:24px}.reflection-grid h2{font-size:17px}.note-save{font-size:10px}.chat{height:220px}.msg{font-size:13px}.notes-card textarea{font-size:13px}.notes-footer .meta{font-size:10px}.diagnostic-grid{grid-template-columns:1fr}.connection-error,.notice{font-size:11px;padding:12px}.notice{display:block}footer{padding:18px;flex-direction:column;gap:3px;font-size:9px}html[data-edition=primary] .welcome h1{font-size:32px}html[data-edition=university] .welcome h1{font-size:30px}.edition-control{max-width:70%}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{animation:none!important;transition:none!important}}
/* Keep supporting text readable on a student's everyday laptop. */
.welcome p{font-size:14px}.welcome-tags{font-size:12px}.eyebrow{font-size:10px}.badge{font-size:12px}.room-meta strong{font-size:14px}.room-meta>div>span{font-size:12px}.private-label{font-size:10px}.student-picker,.student-picker select,.session-controls>a{font-size:12px}.session-actions button{font-size:13px}.composer input{font-size:14px}.send-button{font-size:12px}.input-toolbar button,.suggestion-label{font-size:12px}.input-hint,.room-footnote{font-size:11px}.chip{font-size:12px;min-height:36px}.study-panel h2{font-size:17px}.meta{font-size:12px}.lesson-card>label,.lesson-card>input{font-size:12px}.lesson-card>p:last-of-type{font-size:11px}.learning-steps strong{font-size:13px}.learning-steps small{font-size:11px}.prof .who{font-size:13px}.prof .exams,.prof .cp{font-size:11px}.prof .meta{font-size:10px}.prof .v{font-size:10px}.profile-disclaimer{font-size:11px!important}.course-filters label,.course-filters select,.course-filters input{font-size:12px}.course-subject,.course-bottom{font-size:11px}.course-card strong{font-size:16px}.note-save,.notes-footer .meta{font-size:11px}.text-button{font-size:12px}.notes-card textarea{font-size:14px}.gentle-note p{font-size:12px}html[data-edition=primary] .prof .who{font-size:15px}html[data-edition=primary] .prof .exams,html[data-edition=primary] .prof .cp,html[data-edition=primary] .prof .v{font-size:12px}html[data-edition=primary] .prof .meta{font-size:11px}html[data-edition=primary] .nav-item{min-height:44px}
@media(max-width:620px){.eyebrow{font-size:9px}.badge{font-size:11px}.input-hint{font-size:10px}.private-label{font-size:9px}.student-picker,.student-picker select{font-size:11px}.room-meta>div>span{font-size:11px}.welcome p{font-size:13px}.welcome-tags{font-size:11px}.course-card strong{font-size:14px}.course-subject,.course-bottom{font-size:10px}.nav-item{min-height:44px}.profile-disclaimer{font-size:11px!important}}

@media(max-width:620px){.sidebar .help-button{display:flex;width:auto;margin:0;padding:9px}.help-button svg{width:18px;height:18px}}
@media(max-width:360px){.sidebar .brand>span:last-child{display:none}.sidebar{padding:14px}}
.prof .concept-record{padding-bottom:9px;margin-bottom:8px;border-bottom:1px solid var(--line)}.prof .concept-record:last-child{border:0;margin-bottom:0}.prof .concept-evidence{margin:4px 0 0;line-height:1.6;font-size:10px;color:var(--muted)}html[data-edition=primary] .prof .concept-evidence{font-size:11px}

===== FILE: frontend/public/profile.html =====
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>学习档案 · Live Agent</title>
<link rel="stylesheet" href="/assets/profile.css">
</head>
<body>
<a class="skip-link" href="#main" data-copy="skip">跳到主要内容</a>
<aside class="sidebar">
  <a class="brand" href="/" data-link="classroom"><span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 19c-3-9 2-15 15-15 0 13-6 18-15 15Zm0 0L15 9"/></svg></span><span><strong data-copy="brand">芽学</strong><small>LIVE AGENT</small></span></a>
  <div class="nav-label" data-copy="space">我的学习空间</div>
  <nav aria-label="主导航" id="mainNav">
    <a data-link="classroom" href="/"><span aria-hidden="true">↗</span><span data-copy="classroom">学习课堂</span></a><a data-link="courses" href="/#courses"><span aria-hidden="true">▦</span><span data-copy="courses">探索课程</span></a>
    <a class="active" aria-current="page" data-link="profile" href="/profile"><span aria-hidden="true">◎</span><span data-copy="profile">学习档案</span></a>
    <a data-link="recordings" href="/traces"><span aria-hidden="true">▷</span><span data-copy="recordings">课堂回顾</span></a>
  </nav>
  <div class="sidebar-note"><span class="note-orbit" aria-hidden="true">✳</span><strong data-copy="sideTitle">每个人，都有自己的节奏。</strong><p data-copy="sideText">告诉老师你学到了哪里，从这里继续向前。</p></div>
  <label class="edition-control"><span data-copy="editionLabel">学习阶段</span><select id="editionSelect" aria-label="学习阶段"><option value="primary">小学 · 中文</option><option value="secondary">中学 · 中文</option><option value="university">University & adult · English</option></select></label>
  <div class="sidebar-footer" data-copy="privateSpace">一对一学习 · 本地演示</div>
</aside>
<div class="workspace">
  <header class="topbar"><div><span data-copy="space">我的学习空间</span><span class="crumb-divider">/</span><strong data-copy="profile">学习档案</strong></div><a id="back" class="back-link" data-link="classroom" href="/" data-copy="back">返回课堂 ↗</a></header>
  <main id="main" tabindex="-1">
    <div class="page-heading"><div><span class="eyebrow" data-copy="eyebrow">A LITTLE ABOUT YOU</span><h1 data-copy="title">让学习更适合你。</h1><p data-copy="intro">补充你的年级和学习情况，老师会用更合适的例子、节奏和练习陪你学习。</p></div><span class="edition-pill" id="editionBadge">中学版</span></div>
    <section class="identity-card" aria-label="当前学习档案" id="identityCard">
      <div class="avatar" id="avatar" aria-hidden="true">同</div><div class="identity-text"><h2 id="profileName">学习档案</h2><p id="profileGrade">正在载入…</p></div><span class="demo-badge" id="demoBadge" hidden data-copy="demo">演示档案</span>
      <label class="student-picker"><span data-copy="studentLabel">当前学生</span><select id="student" aria-label="选择学生"></select></label>
    </section>
    <p class="privacy-note"><span aria-hidden="true">◇</span><span data-copy="privacy">档案只用于一对一学习。掌握度是未经校准的估计，可以手动修正。</span></p>
    <div class="profile-layout">
      <div class="editor-sections">
        <section class="card" aria-labelledby="h-basic"><div class="section-heading"><div><span class="section-kicker" data-copy="basicKicker">先认识一下</span><h2 id="h-basic" data-copy="basic">基本信息</h2></div><span class="section-icon" aria-hidden="true">◎</span></div>
          <div class="basic-fields"><label><span data-copy="nameLabel">怎么称呼你</span><input id="name" maxlength="20" autocomplete="given-name" data-placeholder="namePlaceholder" placeholder="如 小明" aria-describedby="basicHelp" data-profile-control disabled></label><label><span data-copy="gradeLabel">年级 / 学习阶段</span><input id="grade" maxlength="12" list="grades" data-placeholder="gradePlaceholder" placeholder="如 初二" aria-describedby="basicHelp" data-profile-control disabled></label><datalist id="grades"></datalist></div>
          <p class="field-help" id="basicHelp" data-copy="basicHelp">只填写你愿意分享的信息。不确定的内容可以留空。</p><span class="profile-meta" id="meta"></span>
        </section>
        <section class="card" aria-labelledby="h-exams"><div class="section-heading"><div><span class="section-kicker" data-copy="examKicker">找到下一步</span><h2 id="h-exams" data-copy="exams">考试与测验</h2></div><button id="addExam" class="secondary-button" data-copy="addExam" data-profile-control disabled>＋ 添加成绩</button></div>
          <p class="field-help" id="examHelp" data-copy="examHelp">写下最近的测验成绩。需要再练习的知识点，用逗号或顿号分开。</p><div id="exams"><div class="skeleton" aria-hidden="true"></div></div>
        </section>
        <section class="card" aria-labelledby="h-concepts"><div class="section-heading"><div><span class="section-kicker" data-copy="conceptKicker">看看学习进展</span><h2 id="h-concepts" data-copy="concepts">知识点掌握度</h2></div><span class="estimate-badge" data-copy="estimate">估计值</span></div>
          <p class="field-help" id="conceptHelp" data-copy="conceptHelp">这些估计来自测验、练习或手动调整，不是正式评定。滑块可以用方向键调整。</p>
          <div class="legend"><span class="l-weak" data-copy="weak">值得再练习</span><span class="l-partial" data-copy="partial">正在理解</span><span class="l-mastered" data-copy="mastered">比较熟悉</span><span class="l-unknown" data-copy="unknown">还未评估</span></div><div id="concepts"><div class="skeleton" aria-hidden="true"></div></div>
          <div class="add-concept"><label><span data-copy="newConcept">添加知识点</span><input id="newName" maxlength="20" data-placeholder="conceptPlaceholder" placeholder="如 因式分解" data-profile-control disabled></label><label><span data-copy="subject">学科</span><input id="newSubject" maxlength="12" data-placeholder="subjectPlaceholder" placeholder="如 数学" data-profile-control disabled></label><label><span data-copy="masteryInput">估计掌握度 %</span><input id="newMastery" type="number" min="0" max="100" data-placeholder="masteryPlaceholder" placeholder="可留空" aria-describedby="newConceptHelp" data-profile-control disabled></label><button id="addConcept" class="secondary-button" data-copy="addConcept" data-profile-control disabled>＋ 添加</button></div>
          <p class="field-help" id="newConceptHelp" data-copy="newConceptHelp">留空表示还未评估；填写后作为手动估计保存。</p>
        </section>
        <section class="card" aria-labelledby="h-hist"><div class="section-heading"><div><span class="section-kicker" data-copy="historyKicker">一步一步的积累</span><h2 id="h-hist" data-copy="history">最近练习</h2></div><span class="section-icon" aria-hidden="true">↗</span></div>
          <div class="tablewrap"><table class="hist"><thead><tr><th scope="col" data-copy="time">时间</th><th scope="col" data-copy="concept">知识点</th><th scope="col" data-copy="result">结果</th><th scope="col" data-copy="question">题目</th><th scope="col" data-copy="answer">你的回答</th></tr></thead><tbody id="hist"></tbody></table></div>
          <details class="data-options"><summary data-copy="dataOptions">管理练习记录</summary><label class="checkbox-label"><input type="checkbox" id="clearHist" data-profile-control disabled><span data-copy="clearHistory">保存时清空练习记录、练习次数、错因和练习得出的掌握度</span></label></details>
        </section>
      </div>
      <aside class="profile-guide"><div class="guide-card"><span class="guide-icon" aria-hidden="true">✳</span><h2 data-copy="guideTitle">从你现在的位置出发。</h2><p data-copy="guideText">成绩是线索，不是标签。告诉老师哪里有点难，让下一次练习更有帮助。</p><div class="guide-divider"></div><strong data-copy="guideTipTitle">小提示</strong><p data-copy="guideTip">课堂中的练习结果会自动更新这里。手动改动后，记得点击「保存档案」。</p><a data-link="classroom" href="/" data-copy="guideLink">去课堂试一试 ↗</a></div></aside>
    </div>
  </main>
  <footer class="actions"><div class="save-status"><span class="status-dot" aria-hidden="true"></span><span class="status" id="status" role="status" aria-live="polite">载入中…</span><button id="retryLoad" class="ghost" hidden data-copy="retry">重新载入</button></div><div class="action-buttons"><button class="danger" id="reset" data-copy="reset" data-profile-control disabled>恢复初始档案</button><button class="ghost" id="discard" data-copy="discard" disabled>放弃修改</button><button class="primary" id="save" data-copy="save" disabled>保存档案</button></div></footer>
</div>
<script src="/assets/api.js"></script><script src="/assets/profile.js"></script>
</body>
</html>

===== FILE: frontend/public/assets/profile.js =====
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const editions = ["primary", "secondary", "university"];
let preferredEdition = "secondary";
try { preferredEdition = localStorage.getItem("liveAgent.edition") || preferredEdition; } catch (_) {}
const requestedEdition = new URLSearchParams(location.search).get("edition");
const edition = editions.includes(requestedEdition) ? requestedEdition : editions.includes(preferredEdition) ? preferredEdition : "secondary";
try { localStorage.setItem("liveAgent.edition", edition); } catch (_) {}
const english = edition === "university";
const zh = {
  skip:"跳到主要内容", brand:"芽学", courses:"探索课程", brandSub:"陪你把知识学明白", space:"我的学习空间", classroom:"私人课堂", profile:"学习档案", recordings:"课堂记录",
  sideTitle:"每个人，都有自己的节奏。", sideText:"告诉老师你学到了哪里，从这里继续向前。", editionLabel:"学习阶段", privateSpace:"一对一学习 · 本地演示", back:"返回课堂 ↗", eyebrow:"A LITTLE ABOUT YOU", title:"让学习更适合你。", intro:"补充你的年级和学习情况，老师会用更合适的例子、节奏和练习陪你学习。", demo:"演示档案", studentLabel:"当前学生", privacy:"档案只用于一对一学习。掌握度是未经校准的估计，可以手动修正。",
  basicKicker:"先认识一下", basic:"基本信息", nameLabel:"怎么称呼你", gradeLabel:"年级 / 学习阶段", namePlaceholder:"如 小明", gradePlaceholder:"如 初二", basicHelp:"只填写你愿意分享的信息。不确定的内容可以留空。", examKicker:"找到下一步", exams:"考试与测验", addExam:"＋ 添加成绩", examHelp:"写下最近的测验成绩。需要再练习的知识点，用逗号或顿号分开。", conceptKicker:"看看学习进展", concepts:"知识点掌握度", estimate:"估计值", conceptHelp:"这些估计来自测验、练习或手动调整，不是正式评定。滑块可以用方向键调整。",
  weak:"值得再练习", partial:"正在理解", mastered:"比较熟悉", unknown:"还未评估", newConcept:"添加知识点", subject:"学科", masteryInput:"估计掌握度 %", conceptPlaceholder:"如 因式分解", subjectPlaceholder:"如 数学", masteryPlaceholder:"可留空", addConcept:"＋ 添加", newConceptHelp:"留空表示还未评估；填写后作为手动估计保存。", historyKicker:"一步一步的积累", history:"最近练习", time:"时间", concept:"知识点", result:"结果", question:"题目", answer:"你的回答", dataOptions:"管理练习记录", clearHistory:"保存时清空练习记录、练习次数、错因和练习得出的掌握度",
  guideTitle:"从你现在的位置出发。", guideText:"成绩是线索，不是标签。告诉老师哪里有点难，让下一次练习更有帮助。", guideTipTitle:"小提示", guideTip:"课堂中的练习结果会自动更新这里。手动改动后，记得点击「保存档案」。", guideLink:"去课堂试一试 ↗", retry:"重新载入", reset:"恢复初始档案", discard:"放弃修改", save:"保存档案", loading:"载入中…", dirty:"有未保存的修改", noStudents:"暂时没有可用的学习档案。请联系这台服务的管理者。", loaded:"已载入 · 版本 {version}", initial:" · 初始演示内容，尚未保存", meta:"档案 {id} · 版本 {version}", gradeEmpty:"还没有填写学习阶段", noExams:"还没有测验成绩。需要时再添加就好。", examName:"测验名称", examPlaceholder:"如 期中考试", date:"日期", score:"分数（必填）", full:"满分（必填）", subjectRequired:"学科（必填）", weakConcepts:"需要再练习的知识点", weakPlaceholder:"如 因式分解、浮力", removeExam:"删除这次测验", remove:"删除", manual:"手动设定", exerciseSource:"练习 {correct}/{attempts} 对", examSource:"据测验失分推断", clearing:"保存时清除估计", manualUnsaved:"手动估计（未保存）", noConcepts:"还没有知识点记录。做一次练习，或者添加你想学的内容。", masteryLabel:"{name}的估计掌握度", sliderTitle:"方向键可调整估计掌握度", latestError:"最近的错因：", clear:"清除", clearTitle:"清除手动估计；若有相关测验，将使用测验推断的估计", undo:"撤销", correct:"正确", tryAgain:"需要再练习", noHistory:"还没有练习记录。你的课堂练习会出现在这里。", badExam:"请为每次测验填写学科、分数和满分。", saving:"正在保存…", saved:"已保存 · 版本 {version} · 课堂会同步更新", conflict:"档案在你编辑时更新了。请点击「放弃修改」载入最新内容，再重新编辑。", saveFailed:"保存失败：{message}", loadFailed:"暂时无法载入档案：{message}", resetConfirm:"恢复「{name}」的初始档案？保存的成绩、估计掌握度和练习记录都会删除。", resetDone:"已恢复初始档案", resetFailed:"恢复失败：{message}", switchConfirm:"有未保存的修改。继续会放弃这些修改。", refreshed:"已自动更新课堂练习 · 版本 {version}", navLabel:"主导航"
};
const en = {
  skip:"Skip to content", brand:"YāLearn", courses:"Explore topics", brandSub:"A little clearer, every day", space:"My learning space", classroom:"Live classroom", profile:"Learning profile", recordings:"Session recordings", sideTitle:"Your pace. Your next step.", sideText:"Help your tutor understand where you are, and where you want to go.", editionLabel:"Learning edition", privateSpace:"One-to-one learning · Local demo", back:"Back to study room ↗", eyebrow:"A LITTLE ABOUT YOU", title:"Make this space yours.", intro:"Share your study stage and recent work so your tutor can adapt the examples, pace and practice.", demo:"Demo profile", studentLabel:"Active learner", privacy:"Profiles are used only in private sessions. Mastery values are uncalibrated estimates that you can adjust.",
  basicKicker:"Start with the essentials", basic:"About you", nameLabel:"Preferred name", gradeLabel:"School grade (optional)", namePlaceholder:"Your name", gradePlaceholder:"Choose a school grade, or leave blank", basicHelp:"Only Chinese school grades are supported in profiles. Leave the grade blank if none applies. This edition changes the interface language; teaching and the current catalogue remain Chinese school subjects.", examKicker:"Find your next step", exams:"Assessments & results", addExam:"＋ Add result", examHelp:"Add a recent assessment. Separate topics that need practice with commas.", conceptKicker:"A view of your progress", concepts:"Topic understanding", estimate:"Estimated", conceptHelp:"These estimates come from assessments, practice or manual adjustments. They are not formal evaluations. Use arrow keys to adjust sliders.",
  weak:"Needs practice", partial:"Developing", mastered:"More comfortable", unknown:"Not assessed", newConcept:"New topic", subject:"Subject", masteryInput:"Estimated mastery %", conceptPlaceholder:"e.g. Derivatives", subjectPlaceholder:"e.g. Maths", masteryPlaceholder:"Optional", addConcept:"＋ Add", newConceptHelp:"Leave blank for not assessed. A value is saved as a manual estimate.", historyKicker:"Build on your practice", history:"Recent practice", time:"When", concept:"Topic", result:"Result", question:"Question", answer:"Your answer", dataOptions:"Manage practice data", clearHistory:"Clear practice history, attempt counts, error notes and practice-derived mastery when saving",
  guideTitle:"Start where you are.", guideText:"A result is a clue, not a label. Let your tutor know what feels difficult so the next practice can help.", guideTipTitle:"Good to know", guideTip:"Classroom practice updates this profile automatically. Save your profile after making manual changes.", guideLink:"Return to your study room ↗", retry:"Try again", reset:"Restore initial profile", discard:"Discard changes", save:"Save profile", loading:"Loading profile…", dirty:"You have unsaved changes", noStudents:"No learning profiles are available. Ask the operator of this service to enable one.", loaded:"Profile loaded · Version {version}", initial:" · Initial demo content, not saved yet", meta:"Profile {id} · Version {version}", gradeEmpty:"Study stage not set", noExams:"No assessments yet. Add a result whenever it helps.", examName:"Assessment name", examPlaceholder:"e.g. Midterm", date:"Date", score:"Score (required)", full:"Maximum (required)", subjectRequired:"Subject (required)", weakConcepts:"Topics to revisit", weakPlaceholder:"e.g. Derivatives, vectors", removeExam:"Remove this assessment", remove:"Remove", manual:"Manual estimate", exerciseSource:"Practice: {correct}/{attempts} correct", examSource:"Inferred from assessment gaps", clearing:"Estimate clears when saved", manualUnsaved:"Manual estimate (unsaved)", noConcepts:"No topics yet. Try a practice question or add something you want to study.", masteryLabel:"Estimated mastery of {name}", sliderTitle:"Use arrow keys to adjust estimated mastery", latestError:"Recent error: ", clear:"Clear", clearTitle:"Clear the manual estimate; a relevant assessment estimate may still apply", undo:"Undo", correct:"Correct", tryAgain:"Try again", noHistory:"No practice yet. Your classroom answers will appear here.", badExam:"Enter a subject, score and maximum for every assessment.", saving:"Saving your profile…", saved:"Saved · Version {version} · Your session will update", conflict:"Your profile changed while you were editing. Select “Discard changes” to load the latest version, then edit again.", saveFailed:"Could not save: {message}", loadFailed:"Could not load your profile: {message}", resetConfirm:"Restore the initial profile for “{name}”? Saved results, mastery estimates and practice history will be deleted.", resetDone:"Initial profile restored", resetFailed:"Could not restore: {message}", switchConfirm:"You have unsaved changes. Continuing will discard them.", refreshed:"Classroom practice updated · Version {version}", navLabel:"Main navigation"
};
const copy = english ? en : {...zh, ...(edition === "primary" ? {
  classroom:"我的小课堂", profile:"我的学习卡", recordings:"看看课堂记录", courses:"找点新知识", title:"学习小档案，从这里开始。", eyebrow:"我的学习小档案", intro:"让老师知道你读几年级、哪些地方还想练一练。遇到不会填的，可以请爸爸妈妈帮忙。", sideTitle:"一点点，也会变成大进步。", sideText:"不着急，我们从你会的地方一起出发。", nameLabel:"老师怎么称呼你", gradePlaceholder:"如 小学四年级", basicKicker:"让老师认识你", conceptPlaceholder:"如 分数加减法", weakPlaceholder:"如 分数加减法、面积", guideTitle:"不会也没关系。", guideText:"告诉老师你哪里卡住了，一起换个办法，再试一次。", guideTip:"可以和家长一起填写。课堂练习后，老师会自动更新档案；自己改动后记得保存。"
} : {})};
function t(key, values = {}) { return String(copy[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? "")); }
const LEVEL = {mastered:t("mastered"), partial:t("partial"), weak:t("weak"), unknown:t("unknown")};
const SCHOOL_GRADES = ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"];
const GRADES = english ? SCHOOL_GRADES : edition === "primary" ? SCHOOL_GRADES.slice(0,6) : SCHOOL_GRADES.slice(6);
document.documentElement.lang = english ? "en" : "zh-CN";
document.documentElement.dataset.edition = edition;
document.title = t("profile") + " · " + t("brand");
document.querySelectorAll("[data-copy]").forEach(el => { el.textContent = t(el.dataset.copy); });
document.querySelectorAll("[data-placeholder]").forEach(el => { el.placeholder = t(el.dataset.placeholder); });
$("mainNav").setAttribute("aria-label", t("navLabel"));
$("editionSelect").setAttribute("aria-label", t("editionLabel"));
$("student").setAttribute("aria-label", t("studentLabel"));
$("identityCard").setAttribute("aria-label", t("profile"));
$("editionSelect").value = edition;
$("editionBadge").textContent = english ? "University & adult" : edition === "primary" ? "小学版" : "中学版";
$("status").textContent = t("loading");
$("grades").innerHTML = GRADES.map(g => `<option value="${g}"${english ? ` label="Grade ${SCHOOL_GRADES.indexOf(g) + 1} · ${g}"` : ""}>`).join("");
let sid = new URLSearchParams(location.search).get("student") || "";
let server = null;          // the profile as last loaded
let exams = [];             // editable copy
let edits = new Map();      // concept name -> {mastery?, delete?, subject?}
let dirty = false;
let state = "loading";
let generation = 0;        // invalidates responses from an earlier load or write

function canEdit() { return state === "ready" && server?.id === sid; }
function isCurrent(requestGeneration, requestSid) { return generation === requestGeneration && sid === requestSid; }

function setStatus(text, cls) { const el = $("status"); el.textContent = text; el.className = "status " + (cls || ""); }
function markDirty() {
  if (!canEdit()) return;
  dirty = true; $("save").disabled = false; $("discard").disabled = false;
  setStatus(t("dirty"), "dirty");
}
function clean() { dirty = false; $("save").disabled = true; $("discard").disabled = true; }

const api = window.LiveAgentAPI.fetchJson;

function pageLink(path, selectedEdition = edition) {
  const query = new URLSearchParams({edition:selectedEdition});
  if (sid) query.set("student", sid);
  const [route, hash] = path.split("#");
  return route + "?" + query.toString() + (hash ? "#" + hash : "");
}
function updateLinks() {
  const paths = {classroom:"/", courses:"/#courses", profile:"/profile", recordings:"/traces"};
  document.querySelectorAll("[data-link]").forEach(el => { el.href = pageLink(paths[el.dataset.link]); });
  $("back").href = pageLink("/");
}
function setReady(ready) {
  document.querySelectorAll("[data-profile-control], #exams input, #exams button, #concepts input, #concepts button").forEach(el => { el.disabled = !ready; });
  $("save").disabled = !ready || !dirty;
  $("discard").disabled = !ready || !dirty;
}
$("editionSelect").onchange = () => {
  if (dirty && !confirm(t("switchConfirm"))) { $("editionSelect").value = edition; return; }
  const next = $("editionSelect").value;
  if (!editions.includes(next)) return;
  try { localStorage.setItem("liveAgent.edition", next); } catch (_) {}
  location.href = pageLink("/profile", next);
};
updateLinks();


async function loadList() {
  const requestGeneration = ++generation;
  state = "loading"; setReady(false); setStatus(t("loading"));
  try {
    const {students} = await api("/api/students");
    if (generation !== requestGeneration) return false;
    if (!students.length) { state = "failed"; setStatus(t("noStudents"), "err"); return false; }
    if (!students.some(s => s.id === sid)) sid = students[0].id;
    $("student").innerHTML = students.map(s =>
      `<option value="${esc(s.id)}"${s.id === sid ? " selected" : ""}>${esc(s.name || s.id)}${s.grade ? " · " + esc(s.grade) : ""} (${esc(s.id)})</option>`).join("");
    return await load();
  } catch (err) {
    if (generation === requestGeneration) loadError(err);
    return false;
  }
}

async function load() {
  const requestSid = sid, requestGeneration = ++generation;
  state = "loading"; setReady(false); setStatus(t("loading"));
  try {
    const loaded = await api(`/api/students/${encodeURIComponent(requestSid)}`);
    if (!isCurrent(requestGeneration, requestSid)) return false;
    if (loaded.id !== requestSid) throw new Error("Profile identity mismatch");
    server = loaded;
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false;
    history.replaceState(null, "", pageLink("/profile"));
    updateLinks();
    state = "ready"; render(); clean(); setReady(true);
    $("retryLoad").hidden = true;
    setStatus(t("loaded", {version:server.version}) + (server.saved ? "" : t("initial")), "ok");
    return true;
  } catch (err) {
    if (isCurrent(requestGeneration, requestSid)) loadError(err);
    return false;
  }
}

function render() {
  $("name").value = server.name || ""; $("grade").value = server.grade || "";
  $("meta").textContent = t("meta", {id:server.id, version:server.version});
  $("profileName").textContent = server.name || t("profile");
  $("profileGrade").textContent = server.grade || t("gradeEmpty");
  $("avatar").textContent = Array.from(server.name || (english ? "L" : "同"))[0];
  $("demoBadge").hidden = server.id !== "demo" && !!server.saved;
  renderExams(); renderConcepts(); renderHistory(); updateLinks();
}

function renderExams() {
  const el = $("exams");
  if (!exams.length) { el.innerHTML = `<div class="empty">${t("noExams")}</div>`; return; }
  el.innerHTML = exams.map((e, i) => {
    const pct = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
    return `<div class="exam" data-i="${i}">
      <label>${t("subjectRequired")} <input aria-describedby="examHelp" data-k="subject" value="${esc(e.subject)}" maxlength="12"></label>
      <label>${t("examName")} <input data-k="name" value="${esc(e.name)}" maxlength="20" placeholder="${t("examPlaceholder")}"></label>
      <label>${t("date")} <input data-k="date" type="date" value="${esc(e.date)}"></label>
      <label>${t("score")} <input data-k="score" type="number" min="0" step="0.5" value="${esc(e.score)}"></label>
      <label>${t("full")} <input data-k="full" type="number" min="1" step="1" value="${esc(e.full)}"></label>
      <label>${t("weakConcepts")} <input aria-describedby="examHelp" data-k="weak" value="${esc(e.weak)}" placeholder="${t("weakPlaceholder")}"></label>
      <span class="pct">${pct}</span>
      <button class="ghost" data-del="${i}" aria-label="${t("removeExam")}">${t("remove")}</button></div>`;
  }).join("");
}
$("exams").addEventListener("input", (ev) => {
  if (!canEdit()) return;
  const row = ev.target.closest(".exam"), k = ev.target.dataset.k;
  if (!row || !k) return;
  const e = exams[+row.dataset.i];
  e[k] = (k === "score" || k === "full") ? (ev.target.value === "" ? "" : +ev.target.value) : ev.target.value;
  if (k === "score" || k === "full") row.querySelector(".pct").textContent = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
  markDirty();
});
$("exams").addEventListener("click", (ev) => {
  if (!canEdit()) return;
  const i = ev.target.dataset.del;
  if (i === undefined) return;
  exams.splice(+i, 1); renderExams(); markDirty();
});
$("addExam").onclick = () => {
  if (!canEdit()) return;
  exams.push({subject: "", name: "", date: new Date().toISOString().slice(0, 10), score: "", full: 100, weak: ""});
  renderExams(); markDirty();
  $("exams").lastElementChild.querySelector("input").focus();
};

function srcText(c) {
  if (c.source === "manual") return `<span class="src manual">${t("manual")}</span>`;
  if (c.source === "exercise") return `<span class="src">${t("exerciseSource", {correct:c.correct, attempts:c.attempts})}</span>`;
  if (c.source === "exam") return `<span class="src">${t("examSource")}</span>`;
  return `<span class="src">${t("unknown")}</span>`;
}
function levelOf(m, c) {
  if (m == null) return "unknown";
  if (m >= 0.8) return (c.attempts >= 3 || c.source === "manual" || edits.get(c.name)?.mastery != null) ? "mastered" : "partial";
  return m >= 0.5 ? "partial" : "weak";
}
function renderConcepts() {
  const el = $("concepts");
  const list = server.concepts.slice();
  for (const [name, e] of edits) if (e.added && !list.some(c => c.name === name))
    list.push({name, subject: e.subject || "", mastery: null, source: null, attempts: 0, correct: 0, notes: []});
  if (!list.length) { el.innerHTML = `<div class="empty">${t("noConcepts")}</div>`; return; }
  el.innerHTML = list.map(c => {
    const e = edits.get(c.name) || {};
    const m = "mastery" in e ? e.mastery : c.mastery;
    const lvl = levelOf(m, c);
    const pct = m == null ? "–" : (c.source === "exam" && !("mastery" in e) ? "≈" : "") + Math.round(m * 100) + "%";
    const src = "mastery" in e ? (e.mastery == null ? `<span class="src">${t("clearing")}</span>` : `<span class="src manual">${t("manualUnsaved")}</span>`) : srcText(c);
    return `<div class="concept ${lvl}${e.delete ? " removed" : ""}${Object.keys(e).length ? " changed" : ""}" data-name="${esc(c.name)}">
      <span class="name">${esc(c.name)}</span>
      <span class="muted">${esc(c.subject || "")}</span>
      <span class="grow"><input type="range" min="0" max="100" value="${m == null ? 50 : Math.round(m * 100)}" aria-label="${esc(t("masteryLabel", {name:c.name}))}" aria-describedby="conceptHelp"
               title="${t("sliderTitle")}" aria-valuetext="${m == null ? t("unknown") : Math.round(m * 100) + '% · ' + t("estimate")}"></span>
      <span class="v">${pct}</span>
      <span class="grow">${src}${c.notes && c.notes.length ? `<div class="muted">${t("latestError")}${esc(c.notes[c.notes.length - 1])}</div>` : ""}
        <div class="muted">${LEVEL[lvl]}</div></span>
      <span class="row" style="gap:4px">
        <button class="ghost" data-act="clear" title="${t("clearTitle")}">${t("clear")}</button>
        <button class="ghost" data-act="${e.delete ? "undo" : "delete"}">${t(e.delete ? "undo" : "remove")}</button></span></div>`;
  }).join("");
}
$("concepts").addEventListener("input", (ev) => {
  if (!canEdit()) return;
  if (ev.target.type !== "range") return;
  const name = ev.target.closest(".concept").dataset.name;
  edits.set(name, {...(edits.get(name) || {}), mastery: +ev.target.value / 100, delete: false});
  const row = ev.target.closest(".concept");
  row.querySelector(".v").textContent = ev.target.value + "%";
  markDirty();
});
$("concepts").addEventListener("change", (ev) => { if (canEdit() && ev.target.type === "range") renderConcepts(); });
$("concepts").addEventListener("click", (ev) => {
  if (!canEdit()) return;
  const act = ev.target.dataset.act; if (!act) return;
  const name = ev.target.closest(".concept").dataset.name, e = edits.get(name) || {};
  if (act === "clear") edits.set(name, {...e, mastery: null, delete: false});
  if (act === "delete") edits.set(name, {...e, delete: true});
  if (act === "undo") { const {delete: _, ...rest} = e; Object.keys(rest).length ? edits.set(name, rest) : edits.delete(name); }
  renderConcepts(); markDirty();
});
$("addConcept").onclick = () => {
  if (!canEdit()) return;
  const name = $("newName").value.trim(); if (!name) { $("newName").focus(); return; }
  const raw = $("newMastery").value.trim();
  const e = {added: true, subject: $("newSubject").value.trim()};
  if (raw !== "") e.mastery = Math.max(0, Math.min(100, +raw)) / 100;
  edits.set(name, e);
  $("newName").value = ""; $("newMastery").value = "";
  renderConcepts(); markDirty();
};

function renderHistory() {
  const h = server.history || [];
  $("hist").innerHTML = h.length ? h.map(x => `<tr><td>${esc(x.t)}</td><td>${esc(x.concept)}</td>
      <td class="${x.correct ? "ok" : "bad"}">${t(x.correct ? "correct" : "tryAgain")}</td><td>${esc(x.question)}</td><td>${esc(x.answer)}</td></tr>`).join("")
    : `<tr><td colspan="5" class="empty">${t("noHistory")}</td></tr>`;
}

["name", "grade"].forEach(id => $(id).addEventListener("input", markDirty));
$("clearHist").addEventListener("change", markDirty);

$("save").onclick = async () => {
  if (!canEdit() || !dirty) return;
  const requestSid = server.id;
  const bad = exams.find(e => !String(e.subject).trim() || e.score === "" || !(e.full > 0));
  if (bad) { setStatus(t("badExam"), "err"); return; }
  const body = {
    version: server.version, name: $("name").value.trim(), grade: $("grade").value.trim(),
    exams: exams.map(e => ({subject: e.subject.trim(), name: e.name.trim(), date: e.date, score: +e.score, full: +e.full,
                            weak: String(e.weak).split(/[、,，;；\s]+/).filter(Boolean)})),
    concepts: [...edits].map(([name, e]) => ({name, ...(e.delete ? {delete: true} : {}),
      ...("mastery" in e && !e.delete ? {mastery: e.mastery} : {}), ...(e.added ? {subject: e.subject} : {})})),
    clear_history: $("clearHist").checked,
  };
  const requestGeneration = ++generation;
  state = "saving"; setReady(false); setStatus(t("saving"));
  try {
    const saved = await api(`/api/students/${encodeURIComponent(requestSid)}`, {method: "PUT", body: JSON.stringify(body)});
    if (!isCurrent(requestGeneration, requestSid)) return;
    if (saved.id !== requestSid) throw new Error("Profile identity mismatch");
    server = saved;
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false; state = "ready"; render(); clean(); setReady(true);
    setStatus(t("saved", {version:server.version}), "ok");
  } catch (err) {
    if (!isCurrent(requestGeneration, requestSid)) return;
    state = "ready"; setReady(true);
    if (err.status === 409) setStatus(t("conflict"), "err");
    else setStatus(t("saveFailed", {message:err.message}), "err");
  }
};
$("discard").onclick = () => { if (canEdit()) return load(); };
$("reset").onclick = async () => {
  if (!canEdit()) return;
  if (!confirm(t("resetConfirm", {name:server.name || sid}))) return;
  const requestSid = server.id, requestGeneration = ++generation, version = server.version;
  state = "resetting"; setReady(false); setStatus(t("loading"));
  try {
    await api(`/api/students/${encodeURIComponent(requestSid)}/reset`, {method: "POST", body: JSON.stringify({version})});
    if (!isCurrent(requestGeneration, requestSid)) return;
    const reloading = load(), reloadGeneration = generation;
    if (await reloading && isCurrent(reloadGeneration, requestSid)) setStatus(t("resetDone"), "ok");
  } catch (err) {
    if (!isCurrent(requestGeneration, requestSid)) return;
    state = "ready"; setReady(true); setStatus(t("resetFailed", {message:err.message}), "err");
  }
};
$("student").onchange = async () => {
  if (dirty && !confirm(t("switchConfirm"))) { $("student").value = sid; return; }
  sid = $("student").value; await load();
};
window.addEventListener("beforeunload", (ev) => { if (dirty) { ev.preventDefault(); ev.returnValue = ""; } });

// while nothing is being edited, follow changes made by a running lesson (graded exercises)
setInterval(async () => {
  if (dirty || !canEdit() || document.hidden) return;
  const refreshSid = server.id, refreshProfile = server, refreshGeneration = generation;
  try {
    const now = await api(`/api/students/${encodeURIComponent(refreshSid)}`);
    // Fetching can overlap edits, saves, student changes or another refresh.
    if (dirty || !canEdit() || !isCurrent(refreshGeneration, refreshSid) || server !== refreshProfile || document.hidden || now.id !== refreshSid) return;
    if (now.version !== server.version) { server = now; exams = now.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
      render(); setStatus(t("refreshed", {version:now.version}), "ok"); }
  } catch (_) { /* offline for a moment: try again next time */ }
}, 5000);

function loadError(e) { state = "failed"; setReady(false); setStatus(t("loadFailed", {message:e.message}), "err"); $("retryLoad").hidden = false; }
$("retryLoad").onclick = loadList;
loadList();

===== FILE: frontend/public/assets/traces.js =====
const params = new URLSearchParams(location.search), editions = ["primary", "secondary", "university"];
let preferredEdition = "secondary";
try { preferredEdition = localStorage.getItem("liveAgent.edition") || preferredEdition; } catch (_) {}
const requestedEdition = params.get("edition");
const edition = editions.includes(requestedEdition) ? requestedEdition : editions.includes(preferredEdition) ? preferredEdition : "secondary";
const publicMode = params.get("mode") === "public";
const student = publicMode ? "" : params.get("student") || "", english = edition === "university";
try { localStorage.setItem("liveAgent.edition", edition); } catch (_) {}
const copy = english ? {
  skip:"Skip to content", brand:"YāLearn", courses:"Explore topics", brandSub:"A little clearer, every day", space:"My learning space", classroom:"Live classroom", profile:"Learning profile", recordings:"Session recordings", sideTitle:"Keep a good explanation close.", sideText:"Return to an idea and see what makes more sense the second time.", editionLabel:"Learning edition", privateSpace:"One-to-one learning · Local demo", back:"Back to study room ↗", eyebrow:"LEARNING, WORTH REVISITING", title:"A little reflection goes a long way.", intro:"Replay an explanation and collect your thoughts. Find the videos and session records actually saved from your sessions.", savedSessions:"Saved sessions", refresh:"↻ Refresh library", scope:"Showing private sessions for learner {student}. Older records without learner attribution are excluded. This trusted local service has no account authentication; library filtering does not control access to files.", loading:"Looking for saved sessions…", emptyEyebrow:"YOUR NEXT CHAPTER", emptyTitle:"Your first session is still ahead.", emptyText:"There are no saved sessions yet. Bring a question to the study room. Sessions recorded by the service will appear here after they finish.", emptyLink:"Go to your study room ↗", libraryNote:"Recordings show what was saved, not proof of topic mastery. Bring any remaining questions to your next session.", count:"{count} saved sessions", session:"Study session", noVideo:"No presented video was saved. The session record is still available below.", download:"Download recording", part:"Recording part {part}", details:"Session files", trace:"Download session record", generatedNote:"Generated material may include content that was never shown in the session.", generated:"Generated material", generatedPart:"Generated material · Part {part}", error:"We couldn’t load the library. Try refreshing the list.", navLabel:"Main navigation", videoLabel:"Recorded session from {date}"
} : {
  skip:"跳到主要内容", brand:"芽学", courses:edition === "primary" ? "找点新知识" : "探索课程", brandSub:"陪你把知识学明白", space:"我的学习空间", classroom:edition === "primary" ? "我的小课堂" : "私人课堂", profile:edition === "primary" ? "我的学习卡" : "学习档案", recordings:edition === "primary" ? "看看课堂记录" : "课堂记录", sideTitle:"学过的，还可以再看看。", sideText:"回到当时的讲解，把一个小疑问再想明白。", editionLabel:"学习阶段", privateSpace:"一对一学习 · 本地演示", back:"返回课堂 ↗", eyebrow:"LEARNING, WORTH REVISITING", title:edition === "primary" ? "再看一遍，又懂一点。" : "好好学过，慢慢回顾。", intro:edition === "primary" ? "想再听一次老师的讲解？保存好的课堂可以在这里重新看看。" : "重看一段讲解，整理一次思路。这里收好已保存的课堂视频和会话记录。", savedSessions:"已保存的课堂", refresh:"↻ 刷新列表", scope:"只显示学生「{student}」的私人课堂，没有学生归属的旧记录不显示。当前服务用于可信的本地环境，没有账号登录；列表筛选不等于文件访问权限隔离。", loading:"正在寻找已保存的课堂…", emptyEyebrow:"YOUR NEXT CHAPTER", emptyTitle:edition === "primary" ? "第一节课，还在等你呢。" : "第一节课，还在前面等你。", emptyText:"现在还没有保存的会话。先去课堂聊一个想学的问题；开启录制的会话结束后会出现在这里。", emptyLink:"开始学习 ↗", libraryNote:"回放是实际保存的课堂内容，不代表知识点已经掌握。可以把看完后仍有疑问的地方，带回下一次课堂。", count:"已保存 {count} 段会话", session:"学习课堂", noVideo:"这次会话没有保存已播放的视频，会话记录仍可下载。", download:"下载课堂回放", part:"课堂回放 · 第 {part} 部分", details:"会话文件", trace:"下载会话记录", generatedNote:"生成素材可能包含课堂中没有播放的内容。", generated:"生成素材", generatedPart:"生成素材 · 第 {part} 部分", error:"暂时无法载入课堂记录。请刷新列表重试。", navLabel:"主导航", videoLabel:"{date}的课堂录像"
};
function t(key, values = {}) { return String(copy[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? "")); }
Object.assign(copy, english ? {
  chooseLearner:"Choose a learner in the study room to see their saved private sessions.",
  publicScope:"Showing public sessions only. Older records without clear scope are excluded. This trusted local service has no account authentication; library filtering does not control access to files.",
  transcript:"Read session text", transcriptLabel:"Recorded session text", transcriptNote:"This is logged tutor script and recorded user input, not verified audio captions or a word-for-word transcript. Only tutor scripts for requests acknowledged as presented are included; their audio and timing are not verified.",
  transcriptLoading:"Loading session text…", transcriptEmpty:"No readable text was saved for this session.", transcriptMissing:"Readable text is unavailable for this record.", transcriptError:"Session text couldn’t be loaded. Try again.", transcriptRetry:"Retry session text", tutorScript:"Tutor script", userInput:"Recorded user input"
} : {
  chooseLearner:"请先去课堂选择学生，再查看这个学生保存的私人课堂。",
  publicScope:"只显示公开会话，没有明确归属的旧记录不显示。当前服务用于可信的本地环境，没有账号登录；列表筛选不等于文件访问权限隔离。",
  transcript:"阅读会话文字", transcriptLabel:"会话文字记录", transcriptNote:"这里是保存的老师讲稿和用户输入，不是经过核对的音频字幕或逐字转写。只显示已收到播放确认的请求所对应的讲稿；实际音频内容和时间位置尚未核对。",
  transcriptLoading:"正在载入会话文字…", transcriptEmpty:"这次会话没有保存可读的文字。", transcriptMissing:"这份记录暂时没有可读文字。", transcriptError:"暂时无法载入会话文字，请重试。", transcriptRetry:"重试载入文字", tutorScript:"老师讲稿", userInput:"保存的用户输入"
});
copy.scope = publicMode ? t("publicScope") : student ? t("scope", {student}) : t("chooseLearner");
if (publicMode) {
  copy.privateSpace = english ? "Public sessions · Local demo" : "公开会话 · 本地演示";
  copy.intro = english ? "Return to saved public sessions. Find the videos and session records actually saved by this service." : "回顾已保存的公开会话。这里显示这台服务保存的公开录像和会话记录。";
}
function pageLink(path, selectedEdition = edition) {
  const [route,hash] = path.split("#"), query = new URLSearchParams({edition:selectedEdition});
  if (publicMode) query.set("mode", "public");
  else if (student) query.set("student", student);
  return route + "?" + query.toString() + (hash ? "#" + hash : "");
}
document.documentElement.lang = english ? "en" : "zh-CN";
document.documentElement.dataset.edition = edition;
document.title = t("recordings") + " · " + t("brand");
document.querySelectorAll("[data-copy]").forEach(el => { el.textContent = t(el.dataset.copy); });
const paths = {classroom:"/", courses:"/#courses", profile:"/profile", recordings:"/traces"};
document.querySelectorAll("[data-link]").forEach(el => {
  if (publicMode && el.dataset.link === "profile") { el.hidden = true; el.removeAttribute("href"); }
  else el.href = pageLink(paths[el.dataset.link]);
});
document.getElementById("mainNav").setAttribute("aria-label", t("navLabel"));
document.getElementById("editionSelect").setAttribute("aria-label", t("editionLabel"));
document.getElementById("editionSelect").value = edition;
document.getElementById("editionBadge").textContent = english ? "University & adult" : edition === "primary" ? "小学版" : "中学版";
document.getElementById("editionSelect").onchange = () => {
  const next = document.getElementById("editionSelect").value;
  if (!editions.includes(next)) return;
  try { localStorage.setItem("liveAgent.edition", next); } catch (_) {}
  location.href = pageLink("/traces", next);
};
function traceLink(url, label, className = "") {
  const link = document.createElement("a");
  link.href = url; link.textContent = label; link.className = className;
  return link;
}
function traceUpdateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(english ? "en" : "zh-CN", {year:"numeric", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"}).format(date);
}
function recordingPart(file) {
  const part = /(?:-|\s)part(\d+)$/.exec(file.label);
  return part ? Number(part[1]) : 1;
}
function fileSize(bytes) { return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`; }
function transcriptSection(session) {
  const section = document.createElement("section"); section.className = "session-transcript";
  if (!session.transcript_url) {
    const text = document.createElement("p"); text.textContent = t("transcriptMissing"); section.append(text); return section;
  }
  const button = document.createElement("button"); button.type = "button"; button.className = "secondary-button"; button.textContent = t("transcript");
  const panel = document.createElement("div"); panel.className = "transcript-panel"; panel.id = "transcript-" + session.id; panel.hidden = true;
  panel.setAttribute("role", "region"); panel.setAttribute("aria-label", t("transcriptLabel"));
  button.setAttribute("aria-expanded", "false"); button.setAttribute("aria-controls", panel.id);
  let loaded = false, pending = false;
  async function loadText() {
    if (loaded || pending) return;
    pending = true;
    const note = document.createElement("p"); note.className = "transcript-note"; note.textContent = t("transcriptNote");
    const status = document.createElement("p"); status.setAttribute("role", "status"); status.textContent = t("transcriptLoading");
    panel.replaceChildren(note, status);
    try {
      const transcript = await window.LiveAgentAPI.fetchJson(session.transcript_url);
      if (transcript.id !== session.id || !matchesScope(transcript)) throw new Error("Transcript scope mismatch");
      const entries = transcript.entries.filter(entry => entry.text && (entry.role === "user" || entry.role === "teacher" && entry.presented === true));
      if (!entries.length) { status.textContent = t("transcriptEmpty"); }
      else {
        panel.replaceChildren(note);
        const lines = document.createElement("ol"); lines.className = "transcript-lines";
        entries.forEach(entry => {
          const line = document.createElement("li"), label = document.createElement("strong"), text = document.createElement("p");
          label.textContent = t(entry.role === "teacher" ? "tutorScript" : "userInput"); text.textContent = entry.text;
          line.append(label, text); lines.append(line);
        });
        panel.append(lines);
      }
      loaded = true;
    } catch (_) {
      status.textContent = t("transcriptError");
      const retry = document.createElement("button"); retry.type = "button"; retry.className = "ghost"; retry.textContent = t("transcriptRetry"); retry.onclick = loadText; panel.append(retry);
    } finally { pending = false; }
  }
  button.onclick = () => {
    panel.hidden = !panel.hidden; button.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) return loadText();
  };
  section.append(button, panel); return section;
}
function matchesScope(session) { return publicMode ? session.mode === "public" && session.student_id == null : session.mode === "private" && session.student_id === student; }
function recordingCard(session) {
  const card = document.createElement("article"); card.className = "recording-card";
  const presented = session.videos.filter(video => video.label.startsWith("presented")).sort((a,b) => recordingPart(a) - recordingPart(b));
  const generated = session.videos.filter(video => video.label.startsWith("generated")).sort((a,b) => recordingPart(a) - recordingPart(b));
  const when = traceUpdateTime(session.updated_at);
  if (presented.length) {
    const video = document.createElement("video"); video.controls = true; video.preload = "none"; video.playsInline = true;
    video.src = presented[0].url; video.setAttribute("aria-label", t("videoLabel", {date:when})); card.append(video);
  } else {
    const empty = document.createElement("div"); empty.className = "recording-no-video";
    const icon = document.createElement("span"); icon.textContent = "▷"; icon.setAttribute("aria-hidden", "true");
    const text = document.createElement("p"); text.textContent = t("noVideo"); empty.append(icon, text); card.append(empty);
  }
  const content = document.createElement("div"); content.className = "recording-content";
  const title = document.createElement("h3"); title.textContent = t("session");
  const time = document.createElement("p"); time.className = "recording-time"; time.textContent = when; time.title = session.updated_at;
  content.append(title, time);
  if (presented.length) {
    const links = document.createElement("div"); links.className = "recording-downloads";
    presented.forEach(file => links.append(traceLink(file.url, recordingPart(file) === 1 ? t("download") : t("part", {part:recordingPart(file)}), "download-link")));
    content.append(links);
  }
  const details = document.createElement("details"); details.className = "file-details";
  const summary = document.createElement("summary"); summary.textContent = t("details");
  const id = document.createElement("p"); id.className = "session-id"; id.textContent = session.id;
  const files = document.createElement("div"); files.className = "file-list";
  files.append(traceLink(session.trace_url, `${t("trace")} · ${fileSize(session.size_bytes)}`));
  details.append(summary, id, files);
  if (generated.length) {
    const note = document.createElement("p"); note.textContent = t("generatedNote"); details.append(note);
    const generatedFiles = document.createElement("div"); generatedFiles.className = "file-list";
    generated.forEach(file => {
      const label = recordingPart(file) === 1 ? t("generated") : t("generatedPart", {part:recordingPart(file)});
      generatedFiles.append(traceLink(file.url, label));
    });
    details.append(generatedFiles);
  }
  content.append(transcriptSection(session), details); card.append(content); return card;
}
async function loadTraces() {
  const status = document.getElementById("status"), refresh = document.getElementById("refresh");
  if (!publicMode && !student) {
    refresh.disabled = true; status.hidden = false; status.textContent = t("chooseLearner");
    return;
  }
  refresh.disabled = true; status.hidden = false; status.className = "load-message"; status.textContent = t("loading");
  try {
    const scope = publicMode ? new URLSearchParams({mode:"public"}) : new URLSearchParams({student});
    const response = await window.LiveAgentAPI.fetchJson("/api/traces?" + scope.toString());
    const sessions = response.sessions.filter(matchesScope);
    const body = document.getElementById("sessions"); body.replaceChildren(...sessions.map(recordingCard));
    document.getElementById("sessionCount").textContent = t("count", {count:sessions.length});
    document.getElementById("emptyState").hidden = sessions.length > 0;
    status.hidden = true;
  } catch (_) { status.textContent = t("error"); status.className = "load-message error"; }
  finally { refresh.disabled = false; }
}
document.getElementById("refresh").onclick = loadTraces;
loadTraces();

===== FILE: live_agent/backend/app.py =====
"""API-only FastAPI backend: scoped resources and one session per WebSocket.

The standalone frontend owns HTML, CSS, JavaScript and its same-origin proxy.
HTTP routes and the existing /ws media protocol are documented in
``docs/frontend_backend.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import SessionView
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import EventType, Utterance, new_id, now
from live_agent.backend.config import BOARD_IMAGES, CURRICULUM, STUDENT_SEEDS, parse_args
from live_agent.backend.resources import register_resources
from live_agent.backend.runtime import llm_api_key, make_generator, make_memory
from live_agent.backend.transport import WSTransport, encode_h264, encode_jpeg, panel_event, to_pcm16

log = logging.getLogger("live_agent.backend")


def _validated_lesson_context(curriculum, value) -> dict | None:
    if not isinstance(value, dict) or type(value.get("grade")) is not int:
        return None
    subject, grade, topic = value.get("subject"), value["grade"], value.get("topic")
    if not isinstance(subject, str) or not isinstance(topic, str) or not 1 <= grade <= 12:
        return None
    for entry in curriculum.subjects:
        grades = entry.get("grade_topics")
        if entry.get("subject") != subject or not isinstance(grades, dict):
            continue
        chapter = grades.get(str(grade))
        if isinstance(chapter, dict) and isinstance(chapter.get("topics"), list) and any(
                isinstance(title, str) and title.strip() == topic for title in chapter["topics"]):
            return {"subject": subject, "grade": grade, "topic": topic}
    return None


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI(title="Live Agent Backend", version="1.0")

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/", "/traces/file/", "/board/img/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()
    from live_agent.student import ProfileStore

    # one shared copy per student for sessions and the profile page; only ids on the allow-list are reachable
    profiles = ProfileStore(Path(args.student_store), STUDENT_SEEDS,
                            [x for x in (args.students or args.student).split(",")
                             if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", x)])
    app.state.profiles = profiles
    from live_agent.curriculum import Curriculum

    curriculum = Curriculum.load(CURRICULUM)  # course knowledge base (empty if not present)
    app.state.curriculum = curriculum

    @app.get("/api/curriculum")
    async def curriculum_summary() -> dict:
        return curriculum.summary()

    @app.get("/api/curriculum/topics")
    async def curriculum_topics() -> dict:
        topics = []
        for subject in curriculum.subjects:
            name = subject.get("subject")
            entries = subject.get("grade_topics")
            if not isinstance(name, str) or not isinstance(entries, dict):
                continue
            for grade_text, entry in entries.items():
                if not re.fullmatch(r"[0-9]{1,2}", str(grade_text)) or not 1 <= int(grade_text) <= 12 or not isinstance(entry, dict):
                    continue
                values = entry.get("topics")
                if not isinstance(values, list):
                    continue
                for topic in values:
                    if not isinstance(topic, str) or not topic.strip():
                        continue
                    basis = entry.get("basis")
                    item = {"subject": name, "grade": int(grade_text), "topic": topic.strip(),
                            "basis": basis if isinstance(basis, str) else ""}
                    if isinstance(entry.get("source"), str):
                        item["source"] = entry["source"]
                    topics.append(item)
        return {"topics": topics}

    @app.on_event("startup")
    async def _startup() -> None:
        if args.record:  # recordings left unfinished by a killed session
            from live_agent.sim import salvage_recordings

            fixed = await asyncio.to_thread(salvage_recordings, args.log_dir)
            if fixed:
                log.info("finalised %d interrupted recording(s): %s", len(fixed), ", ".join(fixed))
        from live_agent.llm import OpenAICompatLLM, make_chat_llm

        if args.llm_url != "scripted":
            await make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args)).warmup()  # SDK lazy imports
        # Heavy generators are started once and shared (reset per session); the mock is per session.
        if args.generator != "mock":
            gen = make_generator(args)
            try:
                await gen.start()
            except BaseException:
                await gen.close()  # workers / listener of a partial start must not linger
                raise
            app.state.shared_gen = gen

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.shared_gen is not None:
            await app.state.shared_gen.close()

    register_resources(app, args, profiles)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = "public" if hello.get("mode") == "public" else "private"
        session_id = new_id("sess")
        record_path = Path(args.log_dir) / f"{session_id}.mp4" if args.record else None
        if record_path is not None:
            record_path.parent.mkdir(parents=True, exist_ok=True)
        codec = "h264" if args.video_codec == "auto" and "h264" in (hello.get("video_codecs") or []) else "jpeg"
        transport = WSTransport(ws, record_path, video_codec=codec)
        shared = app.state.shared_gen is not None
        if shared:
            if app.state.session_lock.locked():
                await ws.send_text(json.dumps({"type": "error", "error": "generator busy (one live session at a time)"}))
                await ws.close()
                return
            await app.state.session_lock.acquire()
        orch = None
        inputs: asyncio.Queue = asyncio.Queue()
        worker = None
        try:
            from live_agent.llm import OpenAICompatLLM, make_chat_llm

            manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
            if args.llm_url == "scripted":  # CPU-only demo: rule-based responder, no model server
                from live_agent.llm import RuleResponder

                llm = RuleResponder(manifest)
            else:
                llm = make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args))
            if args.dev_allow_uncalibrated:
                manifest.min_status = Status.DOCUMENTED
            ledger = StateLedger.from_config(cfg_dir / "canon.json")
            intents = canon.get("intents", {})  # persona filler gestures (idle / listen / while speaking)
            director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                                persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode),
                                idle_intent=intents.get("idle", "idle_read"),
                                listen_intent=intents.get("listen", "listen"),
                                speak_intent=intents.get("speak"),
                                responder_style=canon.get("responder_style", ""),
                                responder_examples=canon.get("responder_examples"))
            director.present_intent = intents.get("present")  # gesture toward the page's board
            generator = SessionView(app.state.shared_gen) if shared else make_generator(args)
            sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
                                                  lambda_prior_s=args.lambda_prior))
            judge = speech = None
            if args.vlm_url == "mock":  # demo only: simulated verdicts (p=0.8), never a measurement
                from live_agent.qc.judge import MockJudge

                # the placeholder video always "performs" the locked action, so by default the simulated
                # judge agrees (p=1); a lower --mock-judge-p demonstrates the repair loop
                judge = MockJudge(p_default=args.mock_judge_p)
            elif args.vlm_url:
                from live_agent.qc.judge import VLMJudge

                hosted = not args.vlm_url.startswith(("http://127.", "http://localhost"))
                judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model,
                                                 api_key=llm_api_key(args) if hosted else "EMPTY", timeout_s=60.0),
                                 k=8, contrast=True)
            asr = None
            if args.asr_url.startswith("wss://"):  # hosted realtime audio model: user speech only (no per-request
                from live_agent.asr import HostedRealtimeASR  # speech QC: an API call per 5 s line, ~6 s each)

                asr = HostedRealtimeASR(args.asr_url, args.asr_model, llm_api_key(args))
            elif args.asr_url:
                from live_agent.asr import OpenAIASR
                from live_agent.qc.judge import SpeechCheck

                asr = OpenAIASR(args.asr_url, args.asr_model)
                speech = SpeechCheck(asr.transcribe_sync)
            from live_agent.qc.judge import ForwardCorrector

            log_dir = Path(args.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=ForwardCorrector(None if args.llm_url == "scripted" else llm),
                                speech_check=speech, memory=make_memory(args, hello, session_id, mode),
                                log=EventLog(log_dir / f"{session_id}.jsonl"),
                                cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                       correction_mode=CorrectionMode(args.correction_mode),
                                                       # the demo's vLLM-Omni configs hold for every prompt
                                                       generator_holds=args.generator == "vllm_omni_h3",
                                                       lesson_self_check=args.lesson_self_check))
            transport.orchestrator = orch
            if args.image_url:
                from live_agent.board_images import ImageMaker

                orch.image_maker = ImageMaker(args.image_url, BOARD_IMAGES)
            orch.figure_dir = BOARD_IMAGES  # exact plots need no model
            orch.answer_boards = bool(canon.get("board"))
            orch.curriculum = curriculum  # a persona with a board writes one for every knowledge answer
            # the page may pick a profile only from the server's allow-list: the demo has one shared access token and no
            # per-student accounts, so the operator decides which profiles this deployment exposes
            allowed = profiles.allowed
            student_id = str(hello.get("student") or args.student)
            if student_id not in allowed:
                student_id = args.student
            if mode == "private" and student_id in allowed:
                # personal data: only a private session reads or updates the saved profile (the shared copy)
                orch.student = profiles.get(student_id)
                orch.profile_store = profiles
                if orch.student is not None:
                    profiles.subscribe(student_id, orch.on_profile_edited)
            orch.log.emit(EventType.AUDIT, now(), where="session_start", session_id=session_id,
                          mode=mode, student_id=orch.student.student_id if orch.student is not None else None)
            if getattr(judge, "vlm", None) is not None:  # the camera focus check uses the judge's VLM (opt-in)
                from live_agent.attention import AttentionMonitor

                orch.attention = AttentionMonitor(judge.vlm)
            if args.record:  # everything the generator produced, incl. chunks dropped by barge-ins
                from live_agent.sim import Recorder

                parts = iter(range(1, 10**6))

                def gen_rec():
                    n = next(parts)
                    return Recorder(Path(args.log_dir) / (f"{session_id}.generated.mp4" if n == 1
                                                          else f"{session_id}.generated-part{n}.mp4"))

                orch.gen_recorder, orch.gen_recorder_factory = gen_rec(), gen_rec
            # live panel: timeline events + a 2 Hz state snapshot to the page (display only)
            panel_q: asyncio.Queue = asyncio.Queue(maxsize=500)
            t_session = now()

            def on_event(ev) -> None:
                msg = panel_event(ev, t_session)
                if msg is not None and not panel_q.full():
                    panel_q.put_nowait(msg)

            orch.log.listeners.append(on_event)

            async def panel_sender() -> None:
                while True:
                    try:
                        msg = await asyncio.wait_for(panel_q.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        msg = {"type": "state", **orch.snapshot()}
                    await transport.send_json(msg)

            panel_task = asyncio.create_task(panel_sender())
            await orch.start()
            await ws.send_text(json.dumps({"type": "status", "session": session_id, "mode": mode,
                                           "generator": generator.info.name, "director": args.director_mode,
                                           "judge": "mock" if args.vlm_url == "mock" else ("vlm" if args.vlm_url else "none"),
                                           "responder": "rules" if args.llm_url == "scripted" else args.llm_model,
                                           "asr": bool(args.asr_url), "persona": canon.get("display_name", ""),
                                           "examples": canon.get("examples", []),
                                           "attention": orch.attention is not None,
                                           "board": bool(canon.get("board")),
                                           "student": orch.student.view() if orch.student is not None else None},
                                          ensure_ascii=False))

            async def handle_inputs() -> None:
                """Utterances are processed in order, off the receive loop, so presentation acks
                and barge-in keep being read (and timestamped) while ASR / the LLM run."""
                while True:
                    kind, payload, t_end, epoch, lesson_context = await inputs.get()  # epoch stamped at receipt
                    try:
                        if kind == "audio":
                            from live_agent.asr import decode_audio_bytes

                            audio = decode_audio_bytes(payload, 16000)
                            text = await asr.transcribe(audio, 16000)
                            await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                        else:
                            text = payload
                        if text:
                            # t_end = when the user stopped speaking / sent (client clock, mapped), so
                            # ASR and queueing delay count toward the deadlines (proposal §7)
                            await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, t_end,
                                                                   session_id=session_id, scope=mode,
                                                                   lesson_context=lesson_context),
                                                         epoch=epoch)
                    except Exception:  # noqa: BLE001
                        log.exception("input handling failed")

            worker = asyncio.create_task(handle_inputs())
            audio_end = now()
            done = asyncio.create_task(orch.wait_done())
            while True:
                recv = asyncio.create_task(ws.receive())
                await asyncio.wait({recv, done}, return_when=asyncio.FIRST_COMPLETED)
                if not recv.done():  # the orchestrator stopped (fatal error or bounded run)
                    recv.cancel()
                    err = f"{type(orch.error).__name__}: {orch.error}" if orch.error else "session ended"
                    try:
                        await ws.send_text(json.dumps({"type": "error", "error": err}))
                        await ws.close()
                    except Exception:  # noqa: BLE001
                        pass
                    break
                msg = recv.result()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    if asr is not None:
                        inputs.put_nowait(("audio", msg["bytes"], audio_end, orch.input_epoch, None))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end", "chunk_received"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    await orch.on_speech_start()
                elif t == "text" and data.get("text", "").strip():
                    lesson_context = None
                    if "lesson_context" in data:
                        lesson_context = _validated_lesson_context(curriculum, data["lesson_context"])
                        if lesson_context is None:
                            await ws.send_json({"type": "error", "error": "invalid catalogue topic selection"})
                            continue
                    # a typed instruction interrupts like speech does (before its LLM work is queued)
                    await orch.on_speech_start()
                    inputs.put_nowait(("text", data["text"].strip(), transport._to_server(data), orch.input_epoch, lesson_context))
                elif t == "audio_end":  # precedes the recorded audio bytes
                    audio_end = transport._to_server(data)
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
                elif t == "clock":
                    transport.on_clock(data)
                elif t == "camera" and isinstance(data.get("jpeg"), str) and len(data["jpeg"]) <= 400_000:
                    try:  # opt-in attention check: analysed in memory, never stored or recorded
                        orch.on_camera(base64.b64decode(data["jpeg"]))
                    except (ValueError, TypeError):
                        pass
                elif t == "camera_off":
                    orch.camera_off()
                elif t == "profile" and orch.student is not None and isinstance(data.get("profile"), dict):
                    orch.student.update_basics(data["profile"])  # name, grade, exams (mastery comes from exercises)
                    orch._save_profile()
                    orch._emit_profile()
                elif t == "video_codec" and data.get("codec") == "jpeg":
                    transport.video_codec = "jpeg"  # the page failed to decode H.264
        except WebSocketDisconnect:
            pass
        finally:
            try:
                if "panel_task" in locals():
                    panel_task.cancel()
                if worker is not None:
                    worker.cancel()
                if orch is not None:
                    if orch.student is not None:
                        profiles.unsubscribe(orch.student.student_id, orch.on_profile_edited)
                    await orch.stop()
                if transport.recorder is not None:
                    await asyncio.to_thread(transport.recorder.close)  # mux video + audio
            except Exception:  # noqa: BLE001
                log.exception("session cleanup failed")
            finally:
                if shared:
                    app.state.session_lock.release()

    return app


def main() -> None:
    import uvicorn

    args = parse_args()
    # Media binary frames need no deflate; it stalls the event loop.
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info", ws_per_message_deflate=False)


if __name__ == "__main__":
    main()

===== FILE: live_agent/backend/resources.py =====
"""Backend resource APIs and media files; browser views belong to frontend/."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

from live_agent.backend.config import BOARD_IMAGES
from live_agent.student import ProfileStore

TRACE_NAME = re.compile(r"^sess-[A-Za-z0-9_-]+(\.generated(-part\d+)?)?\.(jsonl|mp4)$")
TRACE_ID = re.compile(r"^sess-[A-Za-z0-9_-]+$")
BOARD_IMAGE = re.compile(r"^(p[0-9a-f]{15}|[0-9a-f]{16})\.png$")
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


def _trace_events(path: Path, *, metadata_only: bool = False) -> list[dict]:
    """Read only the declared trace file; an unfinished final line is harmless."""
    if not path.is_file() or path.is_symlink():
        return []
    events = []
    with path.open(encoding="utf-8", errors="replace") as trace:
        for line in trace:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and isinstance(event.get("data"), dict):
                events.append(event)
                if metadata_only:
                    break  # new server traces declare scope before any session work
    return events


def _trace_metadata(events: list[dict], session_id: str) -> dict | None:
    records = [event["data"] for event in events
               if event.get("type") == "audit" and event["data"].get("where") == "session_start"]
    if len(records) != 1 or records[0].get("session_id") != session_id:
        return None
    data = records[0]
    student = data.get("student_id")
    if data.get("mode") == "public" and student is None:
        return {"mode": "public", "student_id": None}
    if data.get("mode") == "private" and isinstance(student, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", student):
        return {"mode": "private", "student_id": student}
    return None


def register_resources(app: FastAPI, args: argparse.Namespace, profiles: ProfileStore) -> None:
    def scope_query(student: str | None, mode: str | None) -> tuple[str | None, str | None]:
        if mode not in (None, "private", "public") or mode == "public" and student is not None:
            raise HTTPException(400, "choose a learner or public recordings")
        if student is not None:
            if student not in profiles.allowed:
                raise HTTPException(404, "unknown student")
            return "private", student
        if mode == "private":
            raise HTTPException(400, "private recordings require a student")
        return mode, None

    def matches_scope(metadata: dict | None, mode: str | None, student: str | None) -> bool:
        if mode is None:
            return True  # compatibility: the operator's unfiltered index
        return metadata is not None and metadata["mode"] == mode and metadata["student_id"] == student

    def scope_suffix(mode: str | None, student: str | None) -> str:
        values = {"student": student} if student is not None else {"mode": mode} if mode else {}
        return "?" + urlencode(values) if values else ""

    @app.get("/api/health")
    async def health() -> dict:
        # Uvicorn does not serve until model startup has completed.
        return {"status": "ok", "generator": args.generator, "protocol_version": 1}

    @app.get("/api/traces")
    def traces(student: str | None = None, mode: str | None = None) -> dict:
        """Structured trace metadata for the frontend's recorded-session view."""
        mode, student = scope_query(student, mode)
        suffix = scope_suffix(mode, student)
        directory = Path(args.log_dir)
        sessions = []
        files = [f for f in directory.glob("sess-*.jsonl") if TRACE_NAME.fullmatch(f.name) and f.is_file() and not f.is_symlink()]
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
            metadata = _trace_metadata(_trace_events(f, metadata_only=True), f.stem)
            if not matches_scope(metadata, mode, student):
                continue
            stat = f.stat()
            video_name = re.compile(re.escape(f.stem) + r"(\.generated(-part\d+)?|-part\d+)?\.mp4$")
            videos = []
            for video in sorted(directory.glob(f"{f.stem}*.mp4")):
                if not video.is_file() or video.is_symlink() or not video_name.fullmatch(video.name):
                    continue
                rest = video.name[len(f.stem):-4].lstrip(".-")
                label = rest if rest.startswith("generated") else "presented" + (" " + rest if rest else "")
                videos.append({"name": video.name, "label": label, "url": f"/traces/file/{video.name}{suffix}"})
            sessions.append({"id": f.stem, "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                             "size_bytes": stat.st_size, "trace_url": f"/traces/file/{f.name}{suffix}", "videos": videos,
                             "mode": metadata["mode"] if metadata else "unknown",
                             "student_id": metadata["student_id"] if metadata else None,
                             "transcript_url": f"/api/traces/{f.stem}/transcript{suffix}"})
            if len(sessions) >= 200:
                break
        return {"sessions": sessions}

    @app.get("/api/traces/{session_id}/transcript")
    def transcript(session_id: str, student: str | None = None, mode: str | None = None) -> dict:
        mode, student = scope_query(student, mode)
        path = Path(args.log_dir) / f"{session_id}.jsonl"
        if not TRACE_ID.fullmatch(session_id) or not path.is_file() or path.is_symlink():
            raise HTTPException(404)
        events = _trace_events(path)
        metadata = _trace_metadata(events, session_id)
        if not matches_scope(metadata, mode, student):
            raise HTTPException(404)
        presented = {event["request_index"] for event in events if event.get("type") == "chunk_presented"
                     and type(event.get("request_index")) is int}
        entries = []
        for event in events:
            data = event["data"]
            if event.get("type") == "utterance_end" and isinstance(data.get("text"), str) and data["text"].strip():
                entries.append({"role": "user", "text": data["text"], "source": "utterance_end"})
            elif event.get("type") == "lock" and isinstance(data.get("transcript"), str) and data["transcript"].strip():
                request = event.get("request_index")
                if type(request) is int and request in presented:
                    entries.append({"role": "teacher", "text": data["transcript"], "source": "lock",
                                    "request_index": request, "presented": True})
        return {"id": session_id, "mode": metadata["mode"] if metadata else "unknown",
                "student_id": metadata["student_id"] if metadata else None,
                "kind": "scripted", "verified_audio": False, "entries": entries}

    @app.get("/traces/file/{name}")
    async def trace_file(name: str, student: str | None = None, mode: str | None = None) -> FileResponse:
        mode, student = scope_query(student, mode)
        if not TRACE_NAME.fullmatch(name):
            raise HTTPException(404)
        path = Path(args.log_dir) / name
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404)
        if mode is not None:
            session_id = name[:-6] if name.endswith(".jsonl") else re.sub(r"(\.generated(-part\d+)?|-part\d+)?\.mp4$", "", name)
            metadata = _trace_metadata(_trace_events(Path(args.log_dir) / f"{session_id}.jsonl", metadata_only=True), session_id)
            if not matches_scope(metadata, mode, student):
                raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "application/x-ndjson",
                            filename=name, headers=PRIVATE_HEADERS)

    @app.get("/board/img/{name}")
    async def board_img(name: str) -> FileResponse:
        path = BOARD_IMAGES / name
        if not BOARD_IMAGE.fullmatch(name) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/png", headers=PRIVATE_HEADERS)

    def profile_or_404(student_id: str):
        profile = profiles.get(student_id)
        if profile is None:
            raise HTTPException(404, "unknown student")
        return profile

    def full(profile) -> dict:
        return {**profile.view(), "saved": profiles.exists(profile.student_id)}

    @app.get("/api/students")
    async def list_students() -> dict:
        return {"students": [{"id": sid, "name": profiles.get(sid).name, "grade": profiles.get(sid).grade,
                              "saved": profiles.exists(sid)} for sid in profiles.allowed]}

    @app.get("/api/students/{student_id}")
    async def get_student(student_id: str) -> dict:
        return full(profile_or_404(student_id))

    @app.put("/api/students/{student_id}")
    async def put_student(student_id: str, body: dict = Body(...)) -> dict:
        profile = profile_or_404(student_id)
        if body.get("version") != profile.version:
            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
        try:
            profile.page_edit(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        profiles.changed(student_id)
        return full(profile)

    @app.post("/api/students/{student_id}/reset")
    async def reset_student(student_id: str, body: dict = Body(default={})) -> dict:
        profile = profile_or_404(student_id)
        if body.get("version") != profile.version:
            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
        return full(profiles.reset(student_id))

===== FILE: .cache/student-review/contracts2.txt =====

FILE live_agent/orchestrator.py
940:         except Exception as e:  # noqa: BLE001 - no verdict this time
941:             self.log.emit(EventType.ATTENTION, now(), state="unknown", reason=f"check failed: {str(e)[:80]}")
942:             return
943:         if r is None:
944:             return
945:         nudge = None
946:         d = self.director
947:         if self._episode[0] != r["stable"]:
948:             self._episode = (r["stable"], 0)  # a new episode: the student came back, or drifted off again
949:         cap = {"absent": 1, "distracted": 3}.get(r["stable"], 0)  # asking an empty room again helps nobody
950:         if (r["stable"] in NUDGES and r["run"] >= self.cfg.attention_nudge_after and d.lesson_title
951:                 and self._episode[1] < cap
952:                 and now() - self._last_nudge >= self.cfg.attention_cooldown_s
953:                 and not d.queue and not d.awaiting_decision):
954:             lines = NUDGES[r["stable"]]
955:             nudge = lines[self._nudge_i % len(lines)]
956:             self._nudge_i += 1
957:             self._last_nudge = now()
958:             self._episode = (r["stable"], self._episode[1] + 1)
959:             d.nudge(nudge)  # spoken next, with a gesture toward the board; the lesson continues after it
960:         self.log.emit(EventType.ATTENTION, now(), state=r["state"], stable=r["stable"],
961:                       confidence=round(r["confidence"], 2), reason=r["reason"], nudge=nudge)
962: 
963:     # ------------------------------------------------------------------ lessons
964:     def _start_lesson(self, topic: str, lesson_context: dict | None = None) -> None:
965:         self._stop_lesson()
966:         self._lesson_mistakes = []
967:         self.director.lesson_title = topic
968:         self._lesson_task = asyncio.create_task(self._guarded(self._lesson_loop(topic, lesson_context), "lesson", fatal=False))
969:         self._aux.add(self._lesson_task)
970:         self._lesson_task.add_done_callback(lambda t: (self._aux.discard(t), self._maybe_finish()))
971: 
972:     def _make_figures(self) -> None:
973:         """Generate the images boards asked for, in the background (a board shows its figure on requests locked
1080:         self._exercise_changed()
1081:         return decision
1082: 
1083:     async def _give_exercise(self, topic: str) -> None:
1084:         """The student asked for an exercise: one on ``topic`` at the level the profile suggests."""
1085:         from live_agent.exercise import make_exercise
1086: 
1087:         d = self.director
1088:         self._exercises += 1
1089:         profile_epoch, plan = self._profile_epoch, d.plan_version
1090:         profile = self._student_context() or "无（新学生，没有档案）"
1091:         if self.curriculum and self.student is not None:
1092:             from live_agent.curriculum import parse_grade
1093: 
1094:             g = parse_grade(self.student.grade)
1095:             profile += "\n" + self.curriculum.topic_context(topic, g)
1120:         """Tell the page when an exercise opens or closes (its answer buttons); the 2 Hz state snapshot is only
1121:         sent in gaps between events, which a lesson rarely leaves."""
1122:         ex = self.director.exercise
1123:         if ex is self._shown_exercise:
1124:             return
1125:         self._shown_exercise = ex
1126:         if ex is None:
1127:             self.log.emit(EventType.LESSON, now(), stage="exercise_closed")
1128:         else:
1129:             self.log.emit(EventType.LESSON, now(), stage="exercise_open", concept=ex.concept,
1130:                           kind=ex.kind, question=ex.question, option_texts=list(ex.options),
1131:                           options=[o[:1] for o in ex.options])
1132: 
1133:     def _erase_learning(self, terms: list[str]) -> int:
1134:         """Erasure of teaching state: the student profile, a pending exercise that mentions a term (with its queued
1135:         lines and answer board), this lesson's mistakes; in-flight grading / exercise generation is invalidated."""
1136:         n = 0
1137:         self._profile_epoch += 1  # grading / exercise generation in flight must not write back erased data
1138:         ex = self.director.exercise
1139:         if ex is not None and any(x in json.dumps(ex.__dict__, ensure_ascii=False, default=str) for x in terms):
1140:             self.director.close_exercise(set(id(s) for s in self.director.queue))  # its lines go too
1141:             self.director.queue = type(self.director.queue)(s for s in self.director.queue
1142:                                                            if s.board is None or s.board.key not in (ex.key, ex.key + "a"))
1143:         if self.student is not None:
1217:     async def _lesson_loop(self, topic: str, lesson_context: dict | None = None) -> None:
1218:         """Outline first (its intro plays with the outline on the board), then one section at a time, each
1219:         generated while the previous one plays (a section is ~1 min of speech, ~10-20 s to generate)."""
1220:         from live_agent.lesson import LessonLine, LessonPlanner
1221: 
1222:         d = self.director
1223:         lesson_profile, lesson_curriculum = self.student, self.curriculum
1224:         if lesson_context is not None:
1225:             from live_agent.curriculum import Curriculum
1226:             from live_agent.student import StudentProfile
1227: 
1228:             grade = f"{lesson_context['grade']}年级"
1229:             lesson_profile = replace(self.student, grade=grade) if self.student is not None else \
1230:                 StudentProfile(student_id="catalogue", grade=grade)
1231:             lesson_curriculum = Curriculum([s for s in self.curriculum.subjects if s.get("subject") == lesson_context["subject"]],
1232:                                            self.curriculum.pedagogy, self.curriculum.craft)
1233:         planner = LessonPlanner(d.llm, name=d.persona_name, bio=d.persona_bio, curriculum=lesson_curriculum)
1234:         context = "；".join(t for r, t in d.dialogue if r == "user")[-300:]
1235:         try:
1236:             outline = await planner.outline(topic, context, profile=lesson_profile)
1237:         except Exception as e:  # noqa: BLE001
1238:             self.log.emit(EventType.LESSON, now(), stage="outline_failed", topic=topic, error=str(e)[:160])
1239:             d.add_lesson_lines([LessonLine("抱歉，这节课我还没准备好，你可以先问我问题。", None, None)])
1240:             return
1241:         d.lesson_title = outline.title
1242:         d.add_lesson_lines(planner.intro_lines(outline))
1243:         self.log.emit(EventType.LESSON, now(), stage="outline", topic=topic, title=outline.title,
1244:                       sections=[s["title"] for s in outline.sections],
1245:                       plan=[{"title": s["title"], "concepts": s.get("concepts", []), "depth": s.get("depth"),
1246:                              "exercise": s.get("exercise", False)} for s in outline.sections],
1247:                       note=outline.note, adaptive=self.student is not None, subject=outline.subject,
1248:                       subject_source=getattr(planner, "last_subject", None), objectives=outline.objectives,
1249:                       key_point=outline.key_point, difficulty=outline.difficulty, hook=outline.hook_type)
1250:         covered: list[str] = []
1251:         waiting_for = None  # the previous section's exercise: its result shapes the next section
1252:         for i in range(len(outline.sections)):
1253:             # a judged-and-rewritten section takes about twice as long to produce: start it earlier
1254:             lookahead = self.cfg.lesson_lookahead * (2 if self.cfg.lesson_self_check == "revise" and i > 0 else 1)
1255:             while not self._stop.is_set() and (
1256:                     len(d.lesson_backlog) >= lookahead
1257:                     or (waiting_for is not None and (d.exercise is waiting_for
1258:                                                      or any(x.exercise is waiting_for for x in d.lesson_backlog)))
1259:                     or (self.student is not None and d.exercise is not None)):
1260:                 await asyncio.sleep(0.5)
1261:             waiting_for = None
1262:             lines = None
1263:             for attempt in range(2):
1264:                 try:
1265:                     lines = await planner.section(outline, i, covered, profile=lesson_profile,
1266:                                                   mistakes=list(self._lesson_mistakes))
1267:                     break
1268:                 except Exception as e:  # noqa: BLE001 - retry once, then skip the section
1269:                     self.log.emit(EventType.LESSON, now(), stage="section_failed", section=i, attempt=attempt,
1270:                                   error=str(e)[:160])
1271:             if lines and self.cfg.lesson_self_check == "revise" and i > 0:
1272:                 lines = await self._revise_section(planner, outline, i, covered, lines, profile=lesson_profile)
1273:             if lines:
1274:                 if self.cfg.lesson_self_check == "log" or (self.cfg.lesson_self_check == "revise" and i == 0):
1275:                     self._spawn(self._check_section(planner, outline, i, lines, profile=lesson_profile), "lesson_check")
1276:                 self._lesson_mistakes.clear()  # addressed by this section
1277:                 d.add_lesson_lines(lines)
1278:                 if self.student is not None and outline.sections[i].get("concepts"):
1279:                     self.student.mark_taught(outline.sections[i]["concepts"])
1280:                     self._save_profile()
1281:                 self._make_figures()
1282:                 self._spawn(self._judge_figures(planner, lines), "figure_judgement")
1283:                 ex = next((ln.exercise for ln in lines if getattr(ln, "exercise", None) is not None), None)
1284:                 waiting_for = ex if self.student is not None else None  # adapt the next section to the answer
1285:                 self.log.emit(EventType.LESSON, now(), stage="section", section=i,
1286:                               title=outline.sections[i]["title"], lines=len(lines),
1287:                               points=len(lines[0].board.items), depth=outline.sections[i].get("depth"),
1288:                               exercise=(ex.question if ex is not None else None))
1289:             covered.append(outline.sections[i]["title"])
1290:         self.log.emit(EventType.LESSON, now(), stage="planned", title=outline.title)
1291: 
1292:     async def _check_section(self, planner, outline, i: int, lines, *, revised: bool = False, profile=None) -> dict:
1293:         """Judge a section against the lesson-quality checklist and log the verdict (never raises)."""
1294:         try:
1295:             v = await planner.check_section(outline, i, lines, profile=profile if profile is not None else self.student)
1296:         except Exception as e:  # noqa: BLE001 - the check is advisory
1297:             self.log.emit(EventType.LESSON, now(), stage="check_failed", section=i, error=str(e)[:160])
1298:             return {}
1299:         if v:
1300:             self.log.emit(EventType.LESSON, now(), stage="check", section=i, title=outline.sections[i]["title"],
1301:                           passed=v["pass"], scores=v["scores"], problems=v["problems"], fix=v["fix"], revised=revised)
1302:         return v
1303: 
1304:     async def _revise_section(self, planner, outline, i: int, covered: list[str], lines, *, profile=None):
1305:         """Self-check before the section plays; on a fail, one rewrite with the judge's problems. The rewrite is
1306:         kept only if it keeps the planned exercise and the opening correction of the last mistake, and only if
1307:         judge and rewrite finish within ``lesson_revise_deadline_s`` (else the original plays: the check is
1308:         advisory, the lesson's continuity is not). A second opinion on the rewrite is logged, not enforced."""
1309:         from live_agent.lesson import rewrite_keeps
1310: 
1311:         async def judge_and_rewrite():
1312:             v = await self._check_section(planner, outline, i, lines, profile=profile)
1313:             if not v or v["pass"]:
1314:                 return lines
1315:             feedback = "；".join(v["problems"]) + (f"；改法：{v['fix']}" if v["fix"] else "")
1316:             try:
1317:                 new = await planner.section(outline, i, covered, profile=profile if profile is not None else self.student,
1318:                                             mistakes=list(self._lesson_mistakes), feedback=feedback)
1319:             except Exception as e:  # noqa: BLE001 - keep the first version
1320:                 self.log.emit(EventType.LESSON, now(), stage="revise_failed", section=i, error=str(e)[:160])
1321:                 return lines
1322:             lost = rewrite_keeps(lines, new, list(self._lesson_mistakes))
1380: 
1381:     async def _on_user_utterance(self, utt: Utterance, epoch: int) -> dict[str, Any]:
1382:         self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text)
1383:         # A forget request must not recall the very fact it asks to erase into the responder.
1384:         memories, memory_ids, recall_id = None, [], None
1385:         if self.memory and not _FORGET.search(utt.text):
1386:             hits_fn = getattr(self.memory, "recall_hits", None)
1387:             if hits_fn is not None:
1388:                 hits = hits_fn(utt.text, mode=self.cfg.scope)
1389:                 memories, memory_ids = [h.rendered for h in hits], [h.id for h in hits]
1390:                 recall_id = getattr(hits, "recall_id", None)
1391:             else:
1392:                 memories, memory_ids = self.memory.recall(utt.text, mode=self.cfg.scope), None
1393:         elif self.memory and hasattr(self.memory, "no_recall"):
1394:             # nothing recalled for a forget request; the responder prompt then contains no memory
1395:             # (the director never injects memory notes), so the context is isolated
1396:             recall_id = self._no_recall()
1397:         if self.memory:
1398:             self.memory.on_user_utterance(utt)
1399:         if self.director.exercise is not None and not _FORGET.search(utt.text):
1400:             graded = await self._grade_answer(utt, epoch)
1401:             if graded is not None:
1402:                 self._drain_director_events(now())
1403:                 self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=graded,
1404:                               chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1405:                               recalled=[])
1406:                 return graded
1407:         self.director.student_context = self._student_context()
1408:         decision = await self.director.decide(utt, memories)
1409:         term = (decision or {}).get("forget_term")
1410:         if epoch != self._input_epoch:
1411:             # The user barged in again while this decision was computed: it must not change the plan
1412:             # (the newer utterance decides). An erasure request is still honoured.
1413:             self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
1414:         else:
1415:             if term:  # the confirmation is spoken only after the erasure is verified (below)
1416:                 decision = {**decision, "steps": []}
1417:             queued_before = {id(x) for x in self.director.queue}
1418:             self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
1419:             self._decisions += 1  # only applied decisions end the post-interruption wait
1420:             if self.answer_boards and (decision or {}).get("kind") == "content" \
1421:                     and self.director.answer_board_missing(decision):
1422:                 segs = [x for x in self.director.queue if id(x) not in queued_before and x.board is None and x.line]
1423:                 if segs:  # the responder left it out: write one now and show it from the next unlocked line
1424:                     self._spawn(self._answer_board(utt.text, segs), "answer_board")
1425:             self._make_figures()
1426:             kind = (decision or {}).get("kind")
1427:             if kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
1428:                 topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
1429:                 self._start_lesson(topic, utt.lesson_context)
1430:             elif kind == "lesson_stop":
1431:                 self._stop_lesson()
1432:             elif kind == "exercise" and self.director.exercise is not None:
1433:                 self.director.remind_exercise()  # one exercise at a time: the open one first
1434:             elif kind == "exercise":
1435:                 self._spawn(self._give_exercise(str((decision or {}).get("topic") or "").strip()
1436:                                                 or self.director.lesson_title or "刚才讲的内容"), "exercise")
1437:             elif self.director.exercise is not None:
1438:                 self.director.remind_exercise()  # a question while an exercise waits: back to it afterwards
1439:             if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
1440:                 changed = self.student.apply_update(decision["profile_update"])
1441:                 if changed:
1442:                     self._save_profile()
1443:                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
1444:                     self._emit_profile()
1445:         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
1446:         if term and self.memory is not None and hasattr(self.memory, "forget"):
1447:             complete = await self._erase(term)
1448:             line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
1449:             self.director.say_verified(line)  # a verified statement: not subject to the narration guard
1450:         if term:  # the decision itself names erased terms
1451:             raw = json.dumps(decision, ensure_ascii=False)
1452:             for x in sorted(self.director.erased_terms, key=len, reverse=True):
1453:                 raw = raw.replace(x, "[已删除]")
1454:             decision = json.loads(raw)
1455:         self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
1555:             "chains": [{"id": c.chain_id, "status": c.status.value, "kind": c.kind.value, "intent": c.final_intent,
1556:                         "revisions": len(c.revisions), "steps": [x for x in c.steps if x],
1557:                         "step_index": c.step_index, "requests": list(c.requests[-6:])}
1558:                        for c in list(d.chains.values())[-12:]],
1559:             "next_lock": self.next_lock, "plan_version": d.plan_version,
1560:             "lambda_s": round(self.sched.lambda_estimate(), 2), "listening": d.listening,
1561:             "awaiting_decision": d.awaiting_decision, "erasure_gate_open": self._ready.is_set(),
1562:             "queued_segments": len(d.queue), "mode": d.mode.value,
1563:             "exercise": ({"concept": d.exercise.concept, "kind": d.exercise.kind,
1564:                           "question": d.exercise.question, "option_texts": list(d.exercise.options),
1565:                           "options": [o[:1] for o in d.exercise.options]} if d.exercise is not None else None),
1566:         }
1567: 
1568:     def open_chains(self) -> list[str]:
1569:         return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]

FILE live_agent/types.py
90: 
91: 
92: class TaskKind(str, enum.Enum):
93:     ACTION = "action"
94:     CONTENT = "content"
95:     MULTISTEP = "multistep"
96:     CORRECTION = "correction"
97:     MEMORY = "memory"
98:     CHAT = "chat"
99: 
100: 
101: @dataclass
102: class Utterance:
103:     uid: str
104:     speaker: str  # "user" | "persona" | "viewer:<id>"
105:     text: str
106:     t_end: float  # VAD endpoint on the shared timeline
107:     session_id: str = ""
108:     scope: str = "private"
109:     lesson_context: dict[str, Any] | None = None  # backend-validated catalogue selection, never profile edits
110: 
111: 
112: @dataclass

FILE live_agent/student.py
150:             except (TypeError, ValueError):
151:                 pass
152:         return changed
153: 
154:     # ------------------------------------------------------------ understanding
155:     def prior(self, concept: str, subject: str = "") -> float | None:
156:         """0.4 when the latest exam that tested the concept's subject lost points on it (an older loss that a
157:         later exam of that subject no longer lists does not count)."""
158:         latest: dict[str, Exam] = {}
159:         for e in sorted(self.exams, key=lambda e: e.date):
160:             latest[e.subject] = e
161:         return 0.4 if any(concept in e.weak for e in latest.values()) else None
162: 
163:     def source(self, concept: str) -> str | None:
164:         """Where the estimate comes from: "manual" (a teacher set it), "exercise" (graded answers), "exam" (a
165:         prior), None (unknown)."""
166:         c = self.concepts.get(concept)
167:         if c is not None and c.manual and c.mastery is not None:
168:             return "manual"
169:         if c is not None and c.attempts and c.mastery is not None:
170:             return "exercise"
171:         return "exam" if self.mastery(concept) is not None else None
172: 
173:     def mastery(self, concept: str) -> float | None:
174:         c = self.concepts.get(concept)
175:         if c is not None and c.mastery is not None:
176:             return c.mastery
177:         return self.prior(concept, c.subject if c else "")
178: 
179:     def level(self, concept: str) -> str:
180:         """"mastered" needs graded exercises (at least 3), never a prior alone."""
330:             s = f"考试：{e.subject}{e.name} {e.score:g}/{e.full:g}"
331:             if e.weak:
332:                 s += f"，失分点：{'、'.join(e.weak)}"
333:             parts.append(s)
334:         names = sorted(set(self.concepts) | {w for e in self.exams for w in e.weak},
335:                        key=lambda n: (self.mastery(n) is None, self.mastery(n) or 0.0))[:limit]
336:         if names:
337:             parts.append("概念掌握情况：" + "；".join(self._mastery_text(n) for n in names))
338:         return "\n".join(parts)
339: 
340:     def concept_notes(self, concepts: list[str]) -> str:
341:         """For one section: how well the student knows each of its concepts."""
342:         known = [self._mastery_text(n) for n in concepts if str(n).strip()]
343:         return "；".join(known) or "无记录"
344: 
345:     def view(self) -> dict[str, Any]:
346:         """For the page panel."""
347:         names = sorted(set(self.concepts) | {w for e in self.exams for w in e.weak},
348:                        key=lambda n: (self.mastery(n) is None, -(self.mastery(n) or 0.0)))
349:         return {"id": self.student_id, "name": self.name, "grade": self.grade, "version": self.version,
350:                 "exams": [{"subject": e.subject, "name": e.name, "score": e.score, "full": e.full, "date": e.date,
351:                            "weak": e.weak} for e in self.exams],
352:                 "concepts": [{"name": n, "mastery": self.mastery(n), "level": self.level(n), "source": self.source(n),
353:                               "subject": self.concepts[n].subject if n in self.concepts else "",
354:                               "notes": self.concepts[n].notes if n in self.concepts else [],
355:                               "attempts": self.concepts[n].attempts if n in self.concepts else 0,
356:                               "correct": self.concepts[n].correct if n in self.concepts else 0}
357:                              for n in names][:60],
358:                 "history": list(reversed(self.history[-30:]))}
359: 
360: 
361: def validate_page_edit(body: Any) -> dict:
362:     """The profile page's save request, checked field by field; returns it with the grade normalised."""
363:     from live_agent.curriculum import grade_name, parse_grade
364: 
365:     if not isinstance(body, dict):
366:         raise ValueError("body must be an object")
367:     out = dict(body)
368: 
369:     def text(v, n, what):
370:         if v is None:
371:             return ""
372:         if not isinstance(v, (str, int, float)) or len(str(v)) > n:
373:             raise ValueError(f"{what}: at most {n} characters")
374:         return str(v).strip()
375: 
376:     def number(v, what, lo=None, hi=None):
377:         if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
378:             raise ValueError(f"{what}: must be a number")
379:         if (lo is not None and v < lo) or (hi is not None and v > hi):
380:             raise ValueError(f"{what}: out of range")
381:         return float(v)
382: 
383:     if "name" in out:
384:         out["name"] = text(out["name"], 20, "name")
385:     if "grade" in out:
386:         g = text(out["grade"], 12, "grade")
387:         if g:
388:             n = parse_grade(g)
389:             if n is None:
390:                 raise ValueError("grade: not recognised (e.g. 小学三年级, 初二, 高一)")
391:             g = grade_name(n)
392:         out["grade"] = g
393:     if "exams" in out:
394:         if not isinstance(out["exams"], list) or len(out["exams"]) > 20:
395:             raise ValueError("exams: a list of at most 20")
396:         for e in out["exams"]:
397:             if not isinstance(e, dict):
398:                 raise ValueError("exams: each exam is an object")
399:             full = number(e.get("full", 100) or 100, "exam full score", 1, 1000)
400:             number(e.get("score"), "exam score", 0, full)
401:             text(e.get("subject"), 12, "exam subject"), text(e.get("name"), 20, "exam name")
402:             text(e.get("date"), 10, "exam date")

FILE live_agent/exercise.py
1: """Exercises the teacher gives: shown on the board, answered by voice or text, graded, fed back into the profile.
2: 
3: An exercise is either multiple choice (graded by rule: the letter, or the option's text) or a short answer
4: (exact match by rule, else graded by the LLM against the reference answer). A pending exercise pauses the
5: lesson: the next lesson line waits until the student answers (or says they do not know).
6: """
7: 
8: from __future__ import annotations
9: 
10: import re
11: from dataclasses import dataclass, field
12: from typing import Any
13: 
14: from live_agent.lesson import Board, LessonLine, spoken
15: from live_agent.llm import ChatLLM, parse_json
16: 
17: LETTERS = "ABCD"
18: SKIP = re.compile(r"^(我)?(不会|不知道|跳过|不懂|想不出来?|没思路|算了)(做|写)?(吧|啊|呢)?[。.!！]?$")
19: # not a plain answer: a negation, a question or a hedge goes to the LLM ("我不选B", "B是什么意思？", "不会是B吧")
20: NOT_PLAIN = re.compile(r"不|没|别|吗|什么|为什么|怎么|哪|[?？]|或者|还是|吧")
21: 
22: EXERCISE_PROMPT = """你是用中文教学的老师「{name}」。请给学生出一道关于「{topic}」的练习题。
23: 学生档案：
24: {profile}
25: 难度按学生情况定：这个知识点薄弱就出基础题（直接用定义或公式一步能做），基本理解出中等题，已掌握出稍有变化的题；按学生年级出题。
26: {craft}{exercise_spec}"""
27: 
28: EXERCISE_SPEC = """练习题格式（只输出 JSON）：
29: {{"exercise": {{"concept": 考查的概念（用档案里已有的概念名，没有就写一个不超过 8 字的名称）, "subject": 学科,
30:   "type": "choice" 或 "short", "question": 题目（不超过 {q_chars} 字，公式写在 $...$ 里）,
31:   "options": ["A. …", "B. …", "C. …", "D. …"]（选择题才有，每项不超过 20 字）,
32:   "answer": 选择题写字母（如 "B"），简答题写最简答案（一个数、一个词或一个式子）,
33:   "explanation": [讲解为什么，1-2 句，每句不超过 {chars} 个汉字，口语化，公式用中文读出来；不要只重复选哪个]}}}}
34: 选择题的错误选项要对应常见的错误想法。"""
35: 
36: GRADE_PROMPT = """你是老师，正在批改学生的口头回答。
37: 题目：{question}
38: {options}参考答案：{answer}
39: 讲解：{explanation}
40: 学生说：「{said}」
41: 先判断学生这句话是不是在回答这道题（是答案、写出了结果或说不会，都算回答；问别的问题、聊别的事不算）。
42: 是回答时判断对错（意思对、等价的式子或数值都算对）；错了用一句话指出学生的错误想法。
43: 只输出 JSON：{{"is_answer": true 或 false, "correct": true 或 false, "misconception": 错误想法（答对时为 null）,
44: "feedback": [老师回应，2-3 句，每句不超过 {chars} 个汉字，口语化：答对先肯定再点出关键；答错先鼓励，再讲正确思路和答案；公式用中文读出来]}}"""
45: 
46: 
47: @dataclass
48: class Exercise:
49:     concept: str
50:     question: str
51:     answer: str
52:     kind: str = "short"  # "choice" | "short"
53:     options: list[str] = field(default_factory=list)
54:     explanation: list[str] = field(default_factory=list)
55:     subject: str = ""
56:     key: str = "x"
57:     source: str = "lesson"  # "lesson" (pauses the lesson) | "asked" (the student asked for one)
58: 
59:     @classmethod
60:     def from_dict(cls, d: Any, key: str, source: str = "lesson") -> Exercise | None:
61:         if not isinstance(d, dict):
62:             return None
63:         q, ans = str(d.get("question") or "").strip(), str(d.get("answer") or "").strip()
64:         if not q or not ans:
65:             return None
66:         expl = d.get("explanation") or []
67:         expl = [str(x) for x in (expl if isinstance(expl, list) else [expl]) if str(x).strip()]
68:         ex = cls(concept=str(d.get("concept") or "").strip()[:20] or "练习", question=q[:120], answer=ans[:60],
69:                  explanation=expl[:3], subject=str(d.get("subject") or "")[:12], key=key, source=source)
70:         opts = [str(x).strip()[:40] for x in (d.get("options") or []) if str(x).strip()][:4]
71:         if str(d.get("type") or "") == "choice" or opts:
72:             letter = ans.upper()[:1]
73:             if len(opts) < 2 or letter not in LETTERS[: len(opts)]:
74:                 return None
75:             ex.kind, ex.answer = "choice", letter
76:             ex.options = [o if re.match(r"^[A-D][.．、:：]", o) else f"{LETTERS[i]}. {o}" for i, o in enumerate(opts)]
77:         return ex
78: 
79:     def board(self, reveal_answer: bool = False) -> Board:
80:         items = [self.question, *self.options]
81:         if reveal_answer:
82:             items.append(f"答案：{self.answer_text()}")
83:         return Board(key=self.key + ("a" if reveal_answer else ""), title=f"练习 · {self.concept}"[:24], items=items)
84: 
85:     def answer_text(self) -> str:
86:         if self.kind == "choice":
87:             i = LETTERS.index(self.answer)
88:             return self.options[i] if i < len(self.options) else self.answer
89:         return self.answer
90: 

===== FILE: tests/test_backend_api.py =====
"""The standalone backend owns data and media, without depending on browser assets."""

import json
import os

from fastapi.testclient import TestClient

from live_agent.backend.app import build_app
from live_agent.backend.config import parse_args


def backend(tmp_path, students="demo"):
    args = parse_args(["--generator", "mock", "--llm-url", "scripted", "--vlm-url", "mock", "--asr-url", "",
                       "--memory-db", "", "--student-store", str(tmp_path / "students"),
                       "--log-dir", str(tmp_path / "logs"), "--students", students, "--dev-allow-uncalibrated"])
    return build_app(args)


def test_backend_runs_without_browser_views_and_documents_its_api(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "generator": "mock", "protocol_version": 1}
        for path in ("/", "/profile", "/traces", "/assets/live.js", "/static/index.html"):
            assert client.get(path).status_code == 404
        paths = client.get("/openapi.json").json()["paths"]
        assert {"/api/health", "/api/traces", "/api/students", "/api/curriculum"} <= paths.keys()
        assert "/profile" not in paths and "/traces" not in paths
        assert client.get("/api/students").headers["cache-control"] == "no-store"


def test_trace_index_returns_data_and_only_its_own_media(tmp_path):
    directory = tmp_path / "logs"
    directory.mkdir()
    first = directory / "sess-a.jsonl"
    first.write_text('{"type":"lock"}\n')
    second = directory / "sess-ab.jsonl"
    second.write_text('{"type":"stop"}\n')
    os.utime(first, (100, 100))
    os.utime(second, (200, 200))
    names = ["sess-a.mp4", "sess-a-part2.mp4", "sess-a.generated.mp4", "sess-a.generated-part2.mp4", "sess-ab.mp4"]
    for name in names:
        (directory / name).write_bytes(b"media")
    (directory / "sess-<bad>.jsonl").write_text("untrusted filename")
    (directory / "secret.txt").write_text("private")
    with TestClient(backend(tmp_path)) as client:
        response = client.get("/api/traces")
        assert response.headers["cache-control"] == "no-store"
        sessions = response.json()["sessions"]
        assert [s["id"] for s in sessions] == ["sess-ab", "sess-a"]
        session = sessions[1]
        assert session["size_bytes"] == first.stat().st_size
        assert session["updated_at"].endswith("+00:00")
        assert session["trace_url"] == "/traces/file/sess-a.jsonl"
        assert {v["name"] for v in session["videos"]} == set(names[:-1])
        assert {v["label"] for v in session["videos"]} == {"presented", "presented part2", "generated", "generated-part2"}
        assert client.get(session["trace_url"]).content == first.read_bytes()
        media = client.get("/traces/file/sess-a.mp4", headers={"Range": "bytes=1-3"})
        assert media.status_code == 206 and media.content == b"edi"
        assert media.headers["cache-control"] == "no-store"
        for path in ("/traces/file/secret.txt", "/traces/file/sess-missing.mp4", "/board/img/secret.txt"):
            assert client.get(path).status_code == 404


def test_websocket_keeps_hello_clock_and_binary_media_contract(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "user_id": "test", "video_codecs": []})
            ws.send_json({"type": "ping", "t": 123.0})
            status = pong = chunk = None
            binary_frames = 0
            for _ in range(150):
                msg = ws.receive()
                if "bytes" in msg:
                    binary_frames += 1
                else:
                    data = json.loads(msg["text"])
                    if data["type"] == "status":
                        status = data
                    elif data["type"] == "pong":
                        pong = data
                    elif data["type"] == "chunk":
                        chunk = data
                if status and pong and chunk and binary_frames >= chunk["n_frames"] + 1:
                    break
            assert status["generator"] == "mock" and status["responder"] == "rules"
            assert pong["t"] == 123.0 and isinstance(pong["ts"], float)
            assert chunk["codec"] == "jpeg" and chunk["sample_rate"] > 0 and chunk["duration"] > 0
            assert binary_frames >= chunk["n_frames"] + 1


def test_old_server_module_is_a_compatibility_entrypoint():
    from live_agent.server.app import WSTransport, build_app as old_build_app
    from live_agent.backend.transport import WSTransport as transport

    assert old_build_app is build_app and WSTransport is transport


def test_presentation_timestamps_work_before_and_after_clock_sync():
    from live_agent.backend.transport import WSTransport
    from live_agent.types import now

    transport = WSTransport(None)
    start = now()
    assert start <= transport._to_server({}) <= now()
    assert start <= transport._to_server({"tp": 10.0}) <= now()
    transport.on_clock({"rtt": 20.0, "t_server": 100.0, "t_client": 1000.0})
    assert abs(transport._to_server({"tp": 1500.0}) - 100.49) < 1e-9


def test_curriculum_topics_come_from_real_school_entries(tmp_path):
    app = backend(tmp_path)
    curriculum = app.state.curriculum
    with TestClient(app) as client:
        response = client.get("/api/curriculum/topics")
        assert response.headers["cache-control"] == "no-store"
        topics = response.json()["topics"]
        assert topics
        assert client.get("/api/curriculum").json() == curriculum.summary()
        for item in topics:
            subject = next(s for s in curriculum.subjects if s["subject"] == item["subject"])
            entry = subject["grade_topics"][str(item["grade"])]
            assert item["topic"] in entry["topics"]
            assert subject["grades"][0] <= item["grade"] <= subject["grades"][1]
            assert item["basis"] == entry.get("basis", "")
        assert any(t["subject"] == "数学" and t["grade"] == 1 for t in topics)
        assert any(t["subject"] == "物理" and t["grade"] == 8 for t in topics)
        assert not any(t["subject"] == "科学" and t["grade"] > 6 for t in topics)


def test_curriculum_topics_empty_directory_and_invalid_entries(tmp_path, monkeypatch):
    import live_agent.backend.app as backend_module

    directory = tmp_path / "curriculum"
    directory.mkdir()
    monkeypatch.setattr(backend_module, "CURRICULUM", directory)
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/curriculum/topics").json() == {"topics": []}
    (directory / "subject.json").write_text(json.dumps({
        "subject": "数学", "grades": [1, 12], "grade_topics": {
            "1": {"topics": ["真实章节", "", {"topic": "not a title"}], "basis": "textbook", "source": "s1"},
            "13": {"topics": ["not a school grade"]},
            "adult": {"topics": ["not a school grade"]},
            "²": {"topics": ["not a grade integer"]},
        },
    }), encoding="utf-8")
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/curriculum/topics").json() == {"topics": [
            {"subject": "数学", "grade": 1, "topic": "真实章节", "basis": "textbook", "source": "s1"},
        ]}


def test_pending_exercise_snapshot_and_event_show_question_without_answer():
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.exercise import Exercise

    orch, _ = pipeline.build()
    exercise = Exercise(concept="加法", question="一加二等于几？", answer="B", kind="choice",
                        options=["A. 二", "B. 三"], explanation=["先数一，再数两次。"])
    orch.director.exercise = exercise
    orch._exercise_changed()
    expected = {"concept": "加法", "kind": "choice", "question": "一加二等于几？",
                "options": ["A", "B"], "option_texts": ["A. 二", "B. 三"]}
    assert orch.snapshot()["exercise"] == expected
    event = panel_event(orch.log.events[-1], 0)
    assert event["data"] == {"stage": "exercise_open", **expected}
    assert "answer" not in event["data"] and "explanation" not in event["data"]
    orch.director.exercise = None
    orch._exercise_changed()
    assert orch.snapshot()["exercise"] is None
    assert panel_event(orch.log.events[-1], 0)["data"] == {"stage": "exercise_closed"}


def saved_trace(directory, session_id, mode=None, student=None):
    from live_agent.timeline import EventLog
    from live_agent.types import EventType

    directory.mkdir(exist_ok=True)
    log = EventLog(directory / f"{session_id}.jsonl")
    if mode:
        log.emit(EventType.AUDIT, where="session_start", session_id=session_id, mode=mode, student_id=student)
    log.emit(EventType.UTTERANCE_END, speaker="user", uid="u1", text="给我讲加法。")
    log.emit(EventType.UTTERANCE_END, uid="u1", decision={"kind": "lesson"})
    log.emit(EventType.LOCK, request_index=0, transcript="一加一等于二。", prompt="internal generation prompt")
    log.emit(EventType.LOCK, request_index=1, transcript="没有播放的生成脚本。")
    log.emit(EventType.CHUNK_PRESENTED, request_index=0, chunk_index=0)
    log.emit(EventType.CHUNK_PRESENTED, request_index=0, chunk_index=1)
    log.close()
    for suffix in (".mp4", "-part2.mp4", ".generated.mp4"):
        (directory / f"{session_id}{suffix}").write_bytes(b"video")


def test_trace_filters_use_declared_learner_or_public_scope(tmp_path):
    directory = tmp_path / "logs"
    saved_trace(directory, "sess-alpha", "private", "alpha")
    saved_trace(directory, "sess-beta", "private", "beta")
    saved_trace(directory, "sess-public", "public")
    saved_trace(directory, "sess-legacy")
    saved_trace(directory, "sess-unknown", "private")
    with TestClient(backend(tmp_path, "alpha,beta")) as client:
        assert {s["id"] for s in client.get("/api/traces").json()["sessions"]} == {
            "sess-alpha", "sess-beta", "sess-public", "sess-legacy", "sess-unknown"}
        for query, expected in (("student=alpha", "sess-alpha"), ("student=beta", "sess-beta"), ("mode=public", "sess-public")):
            response = client.get("/api/traces?" + query)
            assert response.headers["cache-control"] == "no-store"
            sessions = response.json()["sessions"]
            assert len(sessions) == 1 and sessions[0]["id"] == expected
            session = sessions[0]
            assert session["transcript_url"] == f"/api/traces/{expected}/transcript?{query}"
            assert session["trace_url"].endswith("?" + query)
            assert all(video["url"].endswith("?" + query) for video in session["videos"])
            assert client.get(session["trace_url"]).status_code == 200
            assert all(client.get(video["url"]).status_code == 200 for video in session["videos"])
        assert client.get("/api/traces?student=outside").status_code == 404
        for query in ("student=alpha&mode=public", "mode=private", "mode=other"):
            assert client.get("/api/traces?" + query).status_code == 400
        assert client.get("/traces/file/sess-beta.mp4?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-legacy.jsonl?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-alpha.mp4?mode=public").status_code == 404


def test_transcript_is_readable_exact_script_and_input_with_scope_guard(tmp_path):
    directory = tmp_path / "logs"
    saved_trace(directory, "sess-alpha", "private", "alpha")
    saved_trace(directory, "sess-legacy")
    with (directory / "sess-alpha.jsonl").open("a") as trace:
        trace.write('{"unfinished":')
    with TestClient(backend(tmp_path, "alpha,beta")) as client:
        response = client.get("/api/traces/sess-alpha/transcript?student=alpha")
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"id": "sess-alpha", "mode": "private", "student_id": "alpha",
                                   "kind": "scripted", "verified_audio": False, "entries": [
                                       {"role": "user", "text": "给我讲加法。", "source": "utterance_end"},
                                       {"role": "teacher", "text": "一加一等于二。", "source": "lock", "request_index": 0, "presented": True},
                                   ]}
        assert client.get("/api/traces/sess-alpha/transcript?student=beta").status_code == 404
        assert client.get("/api/traces/sess-alpha/transcript?mode=public").status_code == 404
        assert client.get("/api/traces/sess-legacy/transcript?student=alpha").status_code == 404
        assert client.get("/api/traces/sess-missing/transcript").status_code == 404
        assert client.get("/api/traces/secret.txt/transcript").status_code == 404
        (directory / "sess-link.jsonl").symlink_to(directory / "sess-alpha.jsonl")
        assert client.get("/api/traces/sess-link/transcript").status_code == 404


def test_new_sessions_log_actual_profile_and_no_public_learner(tmp_path):
    app = backend(tmp_path, "alpha,beta")
    with TestClient(app) as client:
        ids = {}
        for mode, selected in (("private", "alpha"), ("private", "beta"), ("public", "alpha")):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "hello", "mode": mode, "student": selected, "user_id": "test"})
                while True:
                    message = ws.receive()
                    if "text" in message:
                        payload = json.loads(message["text"])
                        if payload.get("type") == "status":
                            ids[(mode, selected)] = payload["session"]
                            break
        for selected in ("alpha", "beta"):
            sessions = client.get("/api/traces?student=" + selected).json()["sessions"]
            assert [(s["id"], s["mode"], s["student_id"]) for s in sessions] == [
                (ids[("private", selected)], "private", selected)]
        app.state.profiles.allowed.clear()  # public browsing does not require private profiles
        sessions = client.get("/api/traces?mode=public").json()["sessions"]
        assert [(s["id"], s["mode"], s["student_id"]) for s in sessions] == [
            (ids[("public", "alpha")], "public", None)]


def test_websocket_catalogue_context_is_validated_and_carried_with_text(tmp_path, monkeypatch):
    from live_agent.orchestrator import Orchestrator

    received = []

    async def capture(self, utterance, **kwargs):
        received.append(utterance)
        await self.transport.send_json({"type": "received_for_test"})

    monkeypatch.setattr(Orchestrator, "on_user_utterance", capture)
    with TestClient(backend(tmp_path)) as client:
        item = client.get("/api/curriculum/topics").json()["topics"][0]
        selected = {key: item[key] for key in ("subject", "grade", "topic")}
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
            ws.send_json({"type": "text", "text": "请讲这一章。", "lesson_context": {**selected, "profile": "not trusted"}})
            while True:
                message = ws.receive()
                if "text" in message and json.loads(message["text"]).get("type") == "received_for_test":
                    break
            assert received[0].text == "请讲这一章。" and received[0].lesson_context == selected
            for invalid in ({**selected, "topic": "a fabricated course"}, {**selected, "grade": 13},
                            {**selected, "grade": True}, {**selected, "subject": "university"}):
                ws.send_json({"type": "text", "text": "不应该排队。", "lesson_context": invalid})
                while True:
                    message = ws.receive()
                    if "text" in message:
                        payload = json.loads(message["text"])
                        if payload.get("type") == "error":
                            assert payload["error"] == "invalid catalogue topic selection"
                            break
            assert len(received) == 1

===== FILE: frontend/tests/live.test.mjs =====
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/assets/live.js', import.meta.url), 'utf8');
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function page({ edition = 'primary', codec, bitmap } = {}) {
  const elements = new Map(), sockets = [], events = [], transitions = [], permissions = [];
  const timers = new Map();
  let nextTimer = 0;
  function element(id) {
    if (!elements.has(id)) {
      const node = { id, value: '', textContent: '', className: '', children: [], style: {}, dataset: {},
        hidden: false, disabled: false, width: 480, height: 864, clientWidth: 1000,
        clientHeight: 500, scrollHeight: 0, scrollTop: 0,
        appendChild(child) { child.parent = this; this.children.push(child); },
        contains(child) { return this.children.includes(child); },
        focus() { document.activeElement = this; },
        remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
        querySelector() { return null; }, querySelectorAll() { return []; },
        setAttribute(name, value) { this[name] = value; },
        getAttribute(name) { return this[name] ?? null; }, removeAttribute(name) { delete this[name]; },
        getContext() { return { drawImage() {}, clearRect() {} }; },
        setPointerCapture() {}, hasPointerCapture() { return false; },
        play() { return Promise.resolve(); }, scrollIntoView() {},
      };
      Object.defineProperty(node, 'innerHTML', { get() { return this.html || ''; }, set(value) { this.html = value; this.children = []; } });
      node.classList = {
        contains(name) { return node.className.split(' ').includes(name); },
        add(name) { if (!this.contains(name)) node.className = `${node.className} ${name}`.trim(); },
        remove(name) { node.className = node.className.split(' ').filter(value => value !== name).join(' '); },
        toggle(name, value) { if (value) this.add(name); else this.remove(name); },
      };
      elements.set(id, node);
    }
    return elements.get(id);
  }
  const document = {
    hidden: false,
    getElementById(id) { return id === 'student' ? null : element(id); },
    createElement(type) { return element(`created-${elements.size}-${type}`); },
    querySelector() { return element('stage'); },
    querySelectorAll(selector) { return selector.includes('chip') ? element('chips').children : []; },
  };
  class AudioContext {
    constructor() { this.state = 'running'; this.currentTime = 0; this.destination = {}; }
    resume() { return Promise.resolve(); }
    createGain() { return { connect() { return this; }, gain: { setTargetAtTime() {} } }; }
    createBuffer(_channels, size) { return { getChannelData: () => new Float32Array(size) }; }
    createBufferSource() { return { connect() {}, start() {}, stop() {} }; }
  }
  class WebSocket {
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; sockets.push(this); }
    send(value) { if (this.failSend || this.readyState !== 1) throw new Error('Socket unavailable'); this.sent.push(value); }
    close() { this.readyState = 3; }
  }
  class MediaRecorder {
    constructor(stream) { this.stream = stream; this.state = 'inactive'; }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      this.ondataavailable?.({ data: new Blob(['recorded audio']) });
      this.completed = this.onstop?.();
    }
  }
  const window = {
    AudioContext,
    location: { href: '/' },
    dispatchEvent(event) { events.push(event); },
    LiveAgentAPI: { websocketUrl() { return 'ws://frontend.test/ws'; } },
    LiveAgentProduct: {
      edition, t(_key, fallback) { return fallback; },
      examples() { return [{ label: 'Explain this step', text: '这一步我还没明白' }]; },
      sessionChanged(state, detail) { transitions.push({ state, detail }); },
    },
  };
  const context = vm.createContext({ document, window, WebSocket, MediaRecorder, Blob,
    AudioContext, CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    navigator: { mediaDevices: {
      addEventListener() {},
      getUserMedia(options) { const request = { ...deferred(), options }; permissions.push(request); return request.promise; },
    } },
    console: { warn() {}, error() {} }, performance: { now: () => 1000 },
    localStorage: { getItem() { return null; }, setItem() {} },
    innerHeight: 800, innerWidth: 1200, addEventListener() {}, requestAnimationFrame() {},
    setInterval(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearInterval(id) { timers.delete(id); },
    setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    createImageBitmap: bitmap || (() => Promise.resolve({ close() {} })),
    ...(codec ? { VideoDecoder: { isConfigSupported: codec } } : {}),
  });
  vm.runInContext(source, context);
  element('mode').value = 'private'; element('uid').value = 'actual-user'; element('sid').value = 'actual-student';
  const run = code => vm.runInContext(code, context);
  async function connect() { await element('connect').onclick(); return sockets.at(-1); }
  async function open(socket = sockets.at(-1)) { socket.readyState = 1; await socket.onopen(); }
  async function status(extra = {}, socket = sockets.at(-1)) {
    await socket.onmessage({ data: JSON.stringify({ type: 'status', session: 'actual-session',
      generator: 'mock', responder: 'rules', director: 'online', judge: 'mock',
      asr: false, attention: false, board: false, student: null, ...extra }) });
  }
  return { element, sockets, events, transitions, permissions, timers, run, connect, open, status };
}

function stream() {
  let stopped = 0;
  return { getTracks: () => [{ stop() { stopped++; } }], stopped: () => stopped };
}

test('rapid connect clicks produce one socket and input waits for backend status', async () => {
  const app = page();
  const first = app.element('connect').onclick();
  const second = app.element('connect').onclick();
  assert.equal(app.element('connect').disabled, true);
  await Promise.all([first, second]);
  assert.equal(app.sockets.length, 1);
  await app.open();
  assert.equal(app.element('text').disabled, true);
  assert.equal(app.element('talk').disabled, true);
  app.element('text').value = 'Keep this draft';
  assert.equal(app.run('sendText()'), false);
  assert.equal(app.element('text').value, 'Keep this draft');
  const hello = JSON.parse(app.sockets[0].sent[0]);
  assert.equal(hello.student, 'actual-student');
  assert.equal(hello.user_id, 'actual-user');
  await app.status();
  assert.equal(app.element('text').disabled, false);
  assert.equal(app.element('talk').disabled, true);
  assert.equal(app.run('sendText()'), true);
  assert.equal(app.element('text').value, '');
  assert.equal(JSON.parse(app.sockets[0].sent.at(-1)).text, 'Keep this draft');
  assert.equal(app.transitions.at(-1).detail.status.generator, 'mock');
  assert.equal(app.events.at(-1).type, 'live-agent:status');
});

test('public hello uses a public memory namespace and omits private learner identity', async () => {
  const app = page();
  app.element('mode').value = 'public';
  app.element('uid').value = 'learner:private-id';
  app.element('sid').value = 'private-id';
  await app.connect(); await app.open();
  const hello = JSON.parse(app.sockets[0].sent[0]);
  assert.equal(hello.mode, 'public');
  assert.equal(hello.user_id, 'public-preview');
  assert.equal(Object.hasOwn(hello, 'student'), false);
  assert.equal(app.sockets[0].sent[0].includes('private-id'), false);
});

test('failed connection resets controls and stale close cannot stop a reconnected session', async () => {
  const app = page({ edition: 'university' });
  const oldSocket = await app.connect();
  oldSocket.onerror();
  assert.equal(app.element('connect').disabled, false);
  assert.equal(app.element('text').disabled, true);
  assert.match(app.element('connectionError').textContent, /could not connect/);
  const socket = await app.connect();
  await app.open(socket); await app.status({}, socket);
  oldSocket.onclose();
  assert.equal(app.run('ready()'), true);
  assert.equal(app.element('connectionError').hidden, true);
  assert.equal(app.run('ws === null'), false);
});

test('connection failure preserves the retry button and writes only its message node', async () => {
  const app = page();
  const panel = app.element('connectionError'), message = app.element('connectionErrorText'), retry = app.element('connectionRetry');
  panel.children = [message, retry];
  panel.querySelector = selector => selector === '#connectionErrorText' ? message : null;
  const socket = await app.connect(); socket.onerror();
  assert.equal(panel.children.length, 2);
  assert.equal(panel.children[1], retry);
  assert.match(message.textContent, /连接不上/);
});

test('startup deadline releases an open socket without status and preserves the draft', async () => {
  const app = page();
  const socket = await app.connect(); await app.open(socket);
  app.element('text').value = 'Keep my question';
  app.timers.get(app.run('startupTimer'))();
  assert.equal(app.run('sessionState'), 'error');
  assert.equal(app.element('connect').disabled, false);
  assert.equal(app.element('text').value, 'Keep my question');
  assert.equal(socket.readyState, 3);
  assert.equal(app.timers.size, 0);
  await app.status({}, socket);
  assert.equal(app.run('sessionState'), 'error');
});

test('codec probe and late status from a disconnected socket cannot reach the next session', async () => {
  const supported = deferred();
  const app = page({ codec: () => supported.promise });
  const oldSocket = await app.connect();
  oldSocket.readyState = 1;
  const opening = oldSocket.onopen();
  app.element('disconnect').onclick();
  const socket = await app.connect();
  supported.resolve({ supported: true });
  await opening;
  assert.equal(oldSocket.sent.length, 0);
  await app.status({ persona: 'Stale tutor' }, oldSocket);
  assert.equal(app.run('sessionState'), 'connecting');
  await app.open(socket); await app.status({ persona: 'Current tutor' }, socket);
  assert.equal(app.element('title').textContent, 'Current tutor');
  assert.equal(app.timers.size, 3);
});

test('a failed send preserves the draft and IME composition does not submit', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.element('text').value = 'Unsent draft';
  app.sockets[0].failSend = true;
  assert.equal(app.run('sendText()'), false);
  assert.equal(app.element('text').value, 'Unsent draft');
  app.sockets[0].failSend = false;
  const before = app.sockets[0].sent.length;
  app.element('text').onkeydown({ key: 'Enter', isComposing: true, preventDefault() { throw new Error('Composition must not be handled'); } });
  assert.equal(app.sockets[0].sent.length, before);
});

test('lesson text forwards only explicit school context and ordinary messages keep their original shape', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.run('sendText("给我上一节数学分数的课", {subject: "数学", grade: 3, topic: "分数", basis: "textbook", student: "private-id", mastery: 0.1})');
  const lesson = JSON.parse(app.sockets[0].sent.at(-1));
  assert.deepEqual(lesson.lesson_context, { subject: '数学', grade: 3, topic: '分数' });
  assert.equal(lesson.text, '给我上一节数学分数的课');
  app.run('sendText("请再讲一遍")');
  assert.equal(Object.hasOwn(JSON.parse(app.sockets[0].sent.at(-1)), 'lesson_context'), false);
});

test('decoding from an ended session is discarded without acknowledging it on the new socket', async () => {
  const decoded = deferred();
  let closed = 0;
  const app = page({ bitmap: () => decoded.promise });
  const oldSocket = await app.connect(); await app.open(); await app.status();
  await oldSocket.onmessage({ data: JSON.stringify({ type: 'chunk', codec: 'jpeg', n_frames: 1, request: 1, chunk: 0 }) });
  await oldSocket.onmessage({ data: new ArrayBuffer(2) });
  const completing = oldSocket.onmessage({ data: new ArrayBuffer(2) });
  app.element('disconnect').onclick();
  const socket = await app.connect(); await app.open(socket); await app.status({}, socket);
  decoded.resolve({ close() { closed++; } });
  await completing;
  assert.equal(closed, 1);
  assert.equal(app.run('queue.length'), 0);
  assert.equal(socket.sent.some(value => JSON.parse(value).type === 'chunk_received'), false);
});

test('a fresh public session cannot inherit private board data when its first chunk has no board', async () => {
  const app = page();
  await app.connect(); await app.open(); await app.status();
  app.run(`lastBoard = {key: "private-board", title: "Private lesson", items: ["Private question"]};
    shownBoard = lastBoard; onScreen = {board: lastBoard};
    $("boardTitle").textContent = "Private lesson";
    $("boardItems").innerHTML = "Private question";
    $("board").classList.add("on");`);
  app.element('disconnect').onclick();
  app.element('mode').value = 'public';
  await app.connect();
  assert.equal(app.run('lastBoard'), null);
  assert.equal(app.run('onScreen'), null);
  assert.equal(app.element('boardTitle').textContent, '');
  assert.equal(app.element('boardItems').innerHTML, '');
  app.run(`schedule({meta: {request: 1, chunk: 0, width: 480, height: 864, sample_rate: 16000,
    duration: 1, n_frames: 1, fps: 24}, frames: [], pcm: new Int16Array([0, 0]), epoch});`);
  assert.equal(app.run('queue[0].board'), null);
});

test('ordinary playback interruption retains the current lesson board for following chunks', async () => {
  const app = page(); await app.connect();
  app.run('lastBoard = {key: "same-lesson"}; stopAll();');
  assert.equal(app.run('lastBoard.key'), 'same-lesson');
});

test('releasing while microphone permission is pending stops its stream and sends no speech', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ asr: true });
  const recording = app.element('talk').onpointerdown({ pointerId: 1 });
  app.element('talk').onpointerup();
  const granted = stream(); app.permissions[0].resolve(granted);
  await recording;
  assert.equal(granted.stopped(), 1);
  assert.equal(app.run('recorder'), null);
  assert.equal(app.sockets[0].sent.filter(value => JSON.parse(value).type === 'speech_start').length, 0);
  assert.equal(app.element('talk').classList.contains('recording'), false);
});

test('late camera permission after disconnect releases tracks and never activates preview', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ attention: true });
  const enabling = app.element('cam').onclick();
  app.element('disconnect').onclick();
  const granted = stream(); app.permissions[0].resolve(granted);
  await enabling;
  assert.equal(granted.stopped(), 1);
  assert.equal(app.element('camView').hidden, true);
  assert.equal(app.run('camStream'), null);
  assert.equal(app.timers.size, 0);
});

test('microphone denial restores controls with localized advice and no false speech start', async () => {
  const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status({ asr: true });
  const recording = app.element('talk').onpointerdown({ pointerId: 1 });
  app.permissions[0].reject(Object.assign(new Error('Permission denied detail'), { name: 'NotAllowedError' }));
  await recording;
  assert.equal(app.run('micPressed'), false);
  assert.equal(app.element('talk').textContent, 'Hold to speak');
  assert.match(app.element('chat').children.at(-1).textContent, /Microphone permission was declined/);
  assert.equal(app.sockets[0].sent.filter(value => JSON.parse(value).type === 'speech_start').length, 0);
});

test('repeated voice presses start one recording and release preserves audio metadata ordering', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ asr: true });
  const starting = app.element('talk').onpointerdown({ pointerId: 1 });
  app.permissions[0].resolve(stream()); await starting;
  app.run('window.activeRecording = recorder');
  await app.element('talk').onpointerdown({ pointerId: 2 });
  assert.equal(app.permissions.length, 1);
  app.element('talk').onpointerup();
  app.element('talk').onpointerleave({ pointerId: 1 });
  await app.run('window.activeRecording.completed');
  const sent = app.sockets[0].sent;
  assert.equal(JSON.parse(sent.at(-2)).type, 'audio_end');
  assert.equal(JSON.parse(sent.at(-2)).tp, 1000);
  assert.ok(sent.at(-1) instanceof ArrayBuffer);
  assert.equal(app.element('talk').disabled, false);
  assert.equal(app.run('micUploading'), false);
});

test('university chips keep localized labels and original backend answer values', async () => {
  const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status();
  app.run('showExercise({concept: "Fractions", options: ["A", "B"]})');
  assert.equal(app.element('chips').children[0].textContent, 'Choose A');
  app.element('chips').children[0].onclick();
  assert.equal(JSON.parse(app.sockets[0].sent.at(-1)).text, '选 A');
  app.run('showExercise(null)');
  app.element('profEdit').onclick();
  assert.match(app.run('window.location.href'), /student=actual-student&edition=university/);
});

test('new exercise choices announce through the product event while composer focus stays put', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.element('text').focus();
  app.run('onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Fractions", question: "Choose a fraction", options: ["A"], option_texts: ["A. One half"]}})');
  assert.equal(app.run('document.activeElement === $("text")'), true);
  const event = app.events.findLast(event => event.type === 'live-agent:event');
  assert.equal(event.detail.data.question, 'Choose a fraction');
  assert.equal(app.element('chips').children[0]['aria-label'], '选 A: A. One half');
});

test('replacing focused chips preserves a matching prompt and returns removed choices to the composer', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.run('setChips([{label: "Original label", text: "这一步我还没明白"}], true)');
  app.element('chips').children[0].focus();
  app.run('setChips([{label: "New label", text: "这一步我还没明白"}], true)');
  assert.equal(app.run('document.activeElement === $("chips").children[0]'), true);
  app.run('setChips(["Different prompt"], true)');
  assert.equal(app.run('document.activeElement === $("text")'), true);
});

test('classroom mastery evidence and capability labels are visible and localized in English', async () => {
  const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status();
  app.run(`showProfile({id: "actual-student", name: "Learner", grade: "Grade 8", exams: [],
    concepts: [{name: "Fractions", level: "partial", source: "exercise", mastery: 0.5, attempts: 3, correct: 2}]});`);
  const html = app.element('prof').innerHTML;
  assert.match(html, /tabindex="0" aria-describedby="concept-evidence-0"/);
  assert.match(html, /<p class="meta concept-evidence" id="concept-evidence-0">Partly understood · Uncalibrated estimate · Based on recorded practice · Recorded practice: 2\/3 correct<\/p>/);
  assert.doesNotMatch(html, /hover|据练习|无依据|已掌握|薄弱/);
  const badges = app.element('badges').children.map(node => node.textContent).join('\n');
  assert.match(badges, /Video: Mock video \(CPU preview\)/);
  assert.match(badges, /Responder: Rules \(preview\)/);
  assert.doesNotMatch(badges, /生成|质检|仅文字/);
});

===== FILE: frontend/tests/profile.test.mjs =====
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/profile.js", import.meta.url), "utf8");

function profile(version, name = "Saved name", id = "demo") {
  return {id, version, name, grade: "初二", saved: true,
    exams: [{subject: "数学", name: "期中", date: "2026-10-01", score: 60, full: 100, weak: []}],
    concepts: [], history: []};
}

function editor({edition, storedEdition, confirm = () => true} = {}) {
  const elements = new Map(), requests = [], historyUrls = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: "", textContent: "", innerHTML: "", checked: false,
      listeners: new Map(),
      addEventListener(event, listener) { this.listeners.set(event, listener); },
      setAttribute(name, value) { this[name] = value; },
    });
    return elements.get(id);
  }
  let poll;
  const controls = ["name", "grade", "addExam", "newName", "newSubject", "newMastery", "addConcept", "clearHist", "reset", "examScore", "examDelete", "conceptSlider", "conceptDelete"];
  const document = {hidden: false, getElementById: element,
    documentElement: {dataset: {}}, querySelectorAll: selector =>
      selector.includes("[data-profile-control]") ? controls.map(element) : []};
  const context = vm.createContext({document,
    window: {addEventListener() {}, LiveAgentAPI: {fetchJson(path, opts) {
      // Leave the initial student-list request pending; tests supply a loaded editor.
      if (path === "/api/students") return new Promise(() => {});
      return new Promise((resolve, reject) => { requests.push({path, opts, resolve, reject}); });
    }}},
    location: {search: "?student=demo" + (edition ? "&edition=" + edition : "")}, URLSearchParams,
    localStorage: {getItem: () => storedEdition, setItem() {}},
    history: {replaceState(_state, _unused, url) { historyUrls.push(url); }}, confirm,
    setInterval(callback) { poll = callback; },
  });
  function run(code) { return vm.runInContext(code, context); }
  vm.runInContext(source, context);
  run(`server = ${JSON.stringify(profile(1))}; exams = server.exams.map(e => ({...e, weak: ""})); render(); clean();`);
  // Bootstrap the controlled fixture as a completed load, including its controls.
  run(`if (typeof state !== "undefined") state = "ready"; setReady(true);`);
  return {document, element, requests, historyUrls, run, poll: () => poll(),
    editName(value) {
      element("name").value = value;
      element("name").listeners.get("input")();
    },
    editExam(score) {
      const row = {dataset: {i: "0"}, querySelector: () => ({textContent: ""})};
      element("exams").listeners.get("input")({target: {
        dataset: {k: "score"}, value: String(score), closest: () => row,
      }});
    },
  };
}

test("a pending refresh preserves unsaved name and exam drafts", async () => {
  const page = editor(), pending = page.poll();
  page.editName("Unsaved name");
  page.editExam(95);
  page.requests[0].resolve(profile(2, "External name"));
  await pending;
  assert.equal(page.element("name").value, "Unsaved name");
  assert.equal(page.run("exams[0].score"), 95);
  assert.equal(page.run("dirty"), true);
  assert.equal(page.run("server.version"), 1);
  assert.match(page.element("status").textContent, /有未保存的修改/);
});

test("a refresh started before a successful save cannot replace the saved profile", async () => {
  const page = editor(), pending = page.poll();
  page.editName("Just saved name");
  const saving = page.element("save").onclick();
  assert.equal(page.requests[1].opts.method, "PUT");
  assert.equal(JSON.parse(page.requests[1].opts.body).name, "Just saved name");
  page.requests[1].resolve(profile(3, "Just saved name"));
  await saving;
  page.requests[0].resolve(profile(2, "Earlier external name"));
  await pending;
  assert.equal(page.element("name").value, "Just saved name");
  assert.equal(page.run("server.version"), 3);
  assert.equal(page.run("dirty"), false);
});

test("a refresh started before a manual reload cannot replace the loaded profile", async () => {
  const page = editor(), pending = page.poll();
  const reloading = page.element("discard").onclick();
  page.requests[1].resolve(profile(3, "Reloaded name"));
  await reloading;
  page.requests[0].resolve(profile(2, "Earlier external name"));
  await pending;
  assert.equal(page.element("name").value, "Reloaded name");
  assert.equal(page.run("server.version"), 3);
});

test("a pending refresh for the previous student is discarded during student switching", async () => {
  const page = editor(), pending = page.poll();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  assert.equal(page.requests[0].path, "/api/students/demo");
  assert.equal(page.requests[1].path, "/api/students/other");
  // The old refresh returns before the selected student's load finishes.
  page.requests[0].resolve(profile(2, "Previous student"));
  await pending;
  assert.equal(page.element("name").value, "Saved name");
  page.requests[1].resolve(profile(1, "Other student", "other"));
  await switching;
  assert.equal(page.element("name").value, "Other student");
  assert.equal(page.run("server.id"), "other");
});

test("an older overlapping refresh cannot replace a newer refresh result", async () => {
  const page = editor(), first = page.poll(), second = page.poll();
  page.requests[1].resolve(profile(3, "Newer name"));
  await second;
  page.requests[0].resolve(profile(2, "Earlier name"));
  await first;
  assert.equal(page.element("name").value, "Newer name");
  assert.equal(page.run("server.version"), 3);
});

test("an unchanged, clean editor accepts a refresh with a newer version", async () => {
  const page = editor(), pending = page.poll();
  const updated = profile(2, "External name");
  updated.exams[0].score = 80;
  page.requests[0].resolve(updated);
  await pending;
  assert.equal(page.element("name").value, "External name");
  assert.equal(page.run("exams[0].score"), 80);
  assert.equal(page.run("server.version"), 2);
  assert.equal(page.run("dirty"), false);
  assert.match(page.element("status").textContent, /已自动更新/);
});

test("a pending refresh does not update an editor hidden before the response", async () => {
  const page = editor(), pending = page.poll();
  page.document.hidden = true;
  page.requests[0].resolve(profile(2, "External name"));
  await pending;
  assert.equal(page.element("name").value, "Saved name");
  assert.equal(page.run("server.version"), 1);
});

test("edition query overrides stored preference and localizes profile controls", () => {
  const page = editor({edition: "university", storedEdition: "primary"});
  assert.equal(page.document.documentElement.lang, "en");
  assert.equal(page.element("editionSelect").value, "university");
  assert.match(page.element("exams").innerHTML, /Assessment name/);
  assert.match(page.element("back").href, /edition=university/);
  assert.match(page.element("back").href, /student=demo/);
  assert.equal(page.element("demoBadge").hidden, false);
  assert.equal(page.element("profileName").textContent, "Saved name");
});

test("stored primary edition offers age-appropriate copy and grade suggestions", () => {
  const page = editor({storedEdition: "primary"});
  assert.equal(page.document.documentElement.lang, "zh-CN");
  assert.equal(page.run('t("title")'), "学习小档案，从这里开始。");
  assert.match(page.element("grades").innerHTML, /小学四年级/);
  assert.doesNotMatch(page.element("grades").innerHTML, /初二/);
  assert.equal(page.element("grade").value, "初二"); // Existing data survives an edition switch.
});

test("English grade suggestions submit canonical school values rather than unsupported adult stages", () => {
  const page = editor({edition: "university"});
  const values = [...page.element("grades").innerHTML.matchAll(/value="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(values, ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"]);
  assert.match(page.element("grades").innerHTML, /label="Grade 8 · 初二"/);
  assert.doesNotMatch(page.element("grades").innerHTML, /University|Postgrad|Adult|Professional/);
  assert.match(page.run('t("basicHelp")'), /Leave the grade blank/);
});

test("invalid editions fall back to the Chinese secondary edition", () => {
  const page = editor({edition: "unknown", storedEdition: "unknown"});
  assert.equal(page.element("editionSelect").value, "secondary");
  assert.match(page.element("grades").innerHTML, /初二/);
  assert.equal(page.document.documentElement.lang, "zh-CN");
});

test("profile reload retains edition and student in the URL", async () => {
  const page = editor({edition: "university"});
  const reloading = page.element("discard").onclick();
  page.requests[0].resolve(profile(2));
  await reloading;
  assert.equal(page.historyUrls[0], "/profile?edition=university&student=demo");
});

test("version conflicts keep the English draft and explain recovery", async () => {
  const page = editor({edition: "university"});
  page.editName("Keep my draft");
  const saving = page.element("save").onclick();
  page.requests[0].reject(Object.assign(new Error("profile changed"), {status: 409}));
  await saving;
  assert.equal(page.element("name").value, "Keep my draft");
  assert.equal(page.run("dirty"), true);
  assert.equal(page.element("save").disabled, false);
  assert.match(page.element("status").textContent, /Discard changes/);
});

test("a slow learner switch cannot save the previous learner's fields to the new learner", async () => {
  const page = editor();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.editName("Previous learner draft");
  const saving = page.element("save").onclick();
  const writes = page.requests.filter(request => request.opts?.method === "PUT");
  // Settle an unsafe request so the failure records the actual target and body.
  for (const request of writes) request.resolve(profile(2, "Previous learner draft", "other"));
  await saving;
  assert.equal(writes.length, 0, JSON.stringify(writes.map(({path, opts}) => ({path, body:JSON.parse(opts.body)}))));
  page.requests[0].resolve(profile(1, "Other learner", "other"));
  await switching;
  assert.equal(page.element("name").value, "Other learner");
});

test("loading a learner disables static and generated edits, reset and save", async () => {
  const page = editor();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  for (const id of ["name", "grade", "addExam", "newName", "clearHist", "examScore", "examDelete", "conceptSlider", "conceptDelete", "reset", "save", "discard"])
    assert.equal(page.element(id).disabled, true, id);
  page.editExam(95);
  assert.equal(page.run("exams[0].score"), 60);
  await page.element("reset").onclick();
  assert.equal(page.requests.length, 1);
  page.requests[0].resolve(profile(1, "Other learner", "other"));
  await switching;
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("reset").disabled, false);
  assert.equal(page.element("save").disabled, true);
});

test("a stale learner load cannot replace the latest selection", async () => {
  const page = editor();
  page.element("student").value = "other";
  const first = page.element("student").onchange();
  page.element("student").value = "third";
  const second = page.element("student").onchange();
  page.requests[1].resolve(profile(3, "Third learner", "third"));
  await second;
  page.requests[0].resolve(profile(1, "Other learner", "other"));
  await first;
  assert.equal(page.run("server.id"), "third");
  assert.equal(page.element("name").value, "Third learner");
  assert.equal(page.historyUrls.at(-1), "/profile?edition=secondary&student=third");
});

test("a stale failed load cannot disable the latest learner or replace its status", async () => {
  const page = editor();
  page.element("student").value = "other";
  const first = page.element("student").onchange();
  page.element("student").value = "third";
  const second = page.element("student").onchange();
  page.requests[1].resolve(profile(3, "Third learner", "third"));
  await second;
  const status = page.element("status").textContent;
  page.requests[0].reject(new Error("old learner unavailable"));
  await first;
  assert.equal(page.element("name").value, "Third learner");
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("retryLoad").hidden, true);
  assert.equal(page.element("status").textContent, status);
});

test("a save completing after a switch cannot replace the new learner or its controls", async () => {
  const page = editor();
  page.editName("Saved previous learner");
  const saving = page.element("save").onclick();
  assert.equal(page.requests[0].path, "/api/students/demo");
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await switching;
  const status = page.element("status").textContent;
  page.requests[0].resolve(profile(2, "Saved previous learner"));
  await saving;
  assert.equal(page.run("server.id"), "other");
  assert.equal(page.element("name").value, "Other learner");
  assert.equal(page.element("status").textContent, status);
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("save").disabled, true);
});

test("an old save conflict cannot enable saving or show recovery for a different learner", async () => {
  const page = editor();
  page.editName("Previous draft");
  const saving = page.element("save").onclick();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await switching;
  const status = page.element("status").textContent;
  page.requests[0].reject(Object.assign(new Error("previous profile changed"), {status:409}));
  await saving;
  assert.equal(page.element("status").textContent, status);
  assert.equal(page.element("save").disabled, true);
});

test("a reset completing after a switch cannot reload or replace the new learner", async () => {
  const page = editor();
  const resetting = page.element("reset").onclick();
  assert.equal(page.requests[0].path, "/api/students/demo/reset");
  assert.equal(JSON.parse(page.requests[0].opts.body).version, 1);
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await switching;
  const status = page.element("status").textContent;
  page.requests[0].resolve(profile(2, "Reset previous learner"));
  await new Promise(resolve => setImmediate(resolve));
  // The old implementation wrongly starts a GET for the current selection.
  if (page.requests[2]) page.requests[2].resolve(profile(2, "Unwanted reload", "other"));
  await resetting;
  assert.equal(page.requests.length, 2);
  assert.equal(page.run("server.id"), "other");
  assert.equal(page.element("name").value, "Other learner");
  assert.equal(page.element("status").textContent, status);
});

test("a failed learner switch leaves old fields disabled until the target loads", async () => {
  const page = editor();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[0].reject(new Error("temporarily offline"));
  await switching;
  assert.equal(page.element("name").disabled, true);
  assert.equal(page.element("save").disabled, true);
  assert.equal(page.element("reset").disabled, true);
  assert.equal(page.element("retryLoad").hidden, false);
  await page.element("save").onclick();
  assert.equal(page.requests.length, 1);
  const retrying = page.run("load()");
  assert.equal(page.requests[1].path, "/api/students/other");
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await retrying;
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("retryLoad").hidden, true);
});

test("declining to discard a draft keeps the current learner and sends no load", async () => {
  const page = editor({confirm: () => false});
  page.editName("Keep this draft");
  page.element("student").value = "other";
  await page.element("student").onchange();
  assert.equal(page.run("sid"), "demo");
  assert.equal(page.element("student").value, "demo");
  assert.equal(page.element("name").value, "Keep this draft");
  assert.equal(page.run("dirty"), true);
  assert.equal(page.requests.length, 0);
});

test("a pending save freezes edits and prevents a second write", async () => {
  const page = editor();
  page.editName("Saved name draft");
  const saving = page.element("save").onclick();
  for (const id of ["name", "grade", "examScore", "examDelete", "conceptSlider", "conceptDelete", "reset", "save", "discard"])
    assert.equal(page.element(id).disabled, true, id);
  page.editExam(95);
  assert.equal(page.run("exams[0].score"), 60);
  await page.element("save").onclick();
  assert.equal(page.requests.length, 1);
  page.requests[0].resolve(profile(2, "Saved name draft"));
  await saving;
  assert.equal(page.element("name").value, "Saved name draft");
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.run("dirty"), false);
});

test("resetting the active learner uses its version and restores the loaded profile", async () => {
  const page = editor();
  page.editName("Draft to discard");
  const resetting = page.element("reset").onclick();
  page.requests[0].resolve(profile(2, "Reset learner"));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.requests[1].path, "/api/students/demo");
  page.requests[1].resolve(profile(2, "Reset learner"));
  await resetting;
  assert.equal(page.element("name").value, "Reset learner");
  assert.equal(page.run("dirty"), false);
  assert.equal(page.element("save").disabled, true);
  assert.equal(page.element("reset").disabled, false);
  assert.match(page.element("status").textContent, /已恢复初始档案/);
});

===== FILE: frontend/tests/traces.test.mjs =====
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/traces.js", import.meta.url), "utf8");
class Element {
  constructor(tag = "div") { this.tagName = tag; this.children = []; this.hidden = false; this.dataset = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}
function library({edition = "secondary", storedEdition, student = "demo", mode} = {}) {
  const elements = new Map(), requests = [];
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  get("scopeNote").dataset.copy = "scope"; get("intro").dataset.copy = "intro";
  for (const link of ["classroom", "courses", "profile", "recordings"]) get(link + "Link").dataset.link = link;
  const document = {documentElement:{dataset:{}}, getElementById:get, querySelectorAll:selector=>
    selector === "[data-copy]" ? [get("scopeNote"), get("intro")] : selector === "[data-link]" ? ["classroom", "courses", "profile", "recordings"].map(link=>get(link + "Link")) : [], createElement:tag=>new Element(tag)};
  const query = new URLSearchParams({edition}); if (student) query.set("student",student); if (mode) query.set("mode",mode);
  const context = vm.createContext({document, URLSearchParams, Intl,
    location:{search:"?" + query.toString()},
    localStorage:{getItem:()=>storedEdition, setItem(){}},
    window:{LiveAgentAPI:{fetchJson(path) { return new Promise((resolve,reject)=>requests.push({path,resolve,reject})); }}},
  });
  vm.runInContext(source, context);
  return {get, document, requests, run:code=>vm.runInContext(code,context),
    async respond(sessions) { requests[0].resolve({sessions}); await new Promise(setImmediate); },
  };
}
function descendants(element) { return element.children.flatMap(child => typeof child === "string" ? [] : [child,...descendants(child)]); }
function session(videos = []) { return {id:"sess-test",mode:"private",student_id:"demo",updated_at:"2026-10-02T08:00:00+00:00",size_bytes:42,trace_url:"/traces/file/sess-test.jsonl",transcript_url:"/api/traces/sess-test/transcript?student=demo",videos}; }

test("empty recording library offers a classroom route without inventing sessions", async () => {
  const page = library({edition:"primary"});
  await page.respond([]);
  assert.equal(page.requests[0].path,"/api/traces?student=demo");
  assert.equal(page.get("emptyState").hidden,false);
  assert.equal(page.get("sessions").children.length,0);
  assert.equal(page.get("sessionCount").textContent,"已保存 0 段会话");
  assert.equal(page.run('pageLink("/")'),"/?edition=primary&student=demo");
});

test("saved video playback and downloads use actual media paths and part numbers", async () => {
  const page = library({edition:"university"});
  await page.respond([session([
    {name:"sess-test-part10.mp4",label:"presented part10",url:"/traces/file/sess-test-part10.mp4"},
    {name:"sess-test-part2.mp4",label:"presented part2",url:"/traces/file/sess-test-part2.mp4"},
    {name:"sess-test.mp4",label:"presented",url:"/traces/file/sess-test.mp4"},
    {name:"sess-test.generated.mp4",label:"generated",url:"/traces/file/sess-test.generated.mp4"},
  ])]);
  const nodes = descendants(page.get("sessions"));
  const video = nodes.find(node => node.tagName === "video");
  assert.equal(video.src,"/traces/file/sess-test.mp4");
  assert.equal(video.preload,"none");
  assert.equal(video.controls,true);
  const links = nodes.filter(node => node.tagName === "a");
  assert.equal(links.find(node => node.textContent === "Recording part 10").href,"/traces/file/sess-test-part10.mp4");
  assert.equal(links.find(node => node.textContent.includes("session record")).href,"/traces/file/sess-test.jsonl");
  assert.equal(links.find(node => node.textContent === "Generated material").href,"/traces/file/sess-test.generated.mp4");
  assert.equal(page.get("emptyState").hidden,true);
  assert.equal(page.document.documentElement.lang,"en");
});

test("generated-only files are not presented as a classroom replay", async () => {
  const page = library({edition:"university"});
  await page.respond([session([{name:"sess-test.generated.mp4",label:"generated",url:"/traces/file/sess-test.generated.mp4"}])]);
  const nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node => node.tagName === "video"),false);
  assert.equal(nodes.some(node => node.textContent === "No presented video was saved. The session record is still available below."),true);
  assert.equal(nodes.some(node => node.textContent === "Generated material may include content that was never shown in the session."),true);
});

test("failed fetch exposes an actionable error and re-enables refresh", async () => {
  const page = library({edition:"university"});
  page.requests[0].reject(new Error("offline"));
  await new Promise(setImmediate);
  assert.match(page.get("status").textContent,/Try refreshing/);
  assert.match(page.get("status").className,/error/);
  assert.equal(page.get("refresh").disabled,false);
  assert.equal(page.get("sessions").children.length,0);
});

test("private libraries exclude other learners, public sessions and legacy unknown scope", async () => {
  const page = library({edition:"university"});
  await page.respond([session(), {...session(),id:"other",student_id:"other"}, {...session(),id:"public",mode:"public",student_id:null}, {...session(),id:"legacy",mode:null,student_id:null}]);
  assert.equal(page.requests[0].path,"/api/traces?student=demo");
  assert.equal(page.get("sessions").children.length,1);
  assert.match(page.get("scopeNote").textContent,/learner demo/);
  assert.match(page.get("scopeNote").textContent,/no account authentication/);
  assert.equal(descendants(page.get("sessions")).some(node=>node.textContent === "other"),false);
  assert.doesNotMatch(page.get("intro").textContent,/videos and notes/);
});

test("public libraries omit learner identity from requests and crosslinks", async () => {
  const page = library({edition:"university",student:"private-id",mode:"public"});
  const publicSession = {...session(),id:"public",mode:"public",student_id:null};
  await page.respond([session(),publicSession,{...session(),id:"legacy",mode:null,student_id:null}]);
  assert.equal(page.requests[0].path,"/api/traces?mode=public");
  assert.equal(page.get("sessions").children.length,1);
  assert.equal(page.run('pageLink("/")'),"/?edition=university&mode=public");
  assert.equal(page.get("profileLink").hidden,true);
  assert.equal(page.get("profileLink").href,undefined);
  assert.match(page.get("scopeNote").textContent,/public sessions only/);
});

test("a direct private library without a learner never fetches an operator index or guesses demo", () => {
  const page = library({edition:"university",student:null});
  assert.equal(page.requests.length,0);
  assert.equal(page.get("refresh").disabled,true);
  assert.match(page.get("status").textContent,/Choose a learner/);
  assert.equal(page.run('pageLink("/")'),"/?edition=university");
});

test("session text shows scoped recorded input and presented scripts with honest provenance", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const nodes = descendants(page.get("sessions")), button = nodes.find(node=>node.textContent === "Read session text");
  const reading = button.onclick();
  assert.equal(button["aria-expanded"],"true");
  assert.equal(page.requests[1].path,"/api/traces/sess-test/transcript?student=demo");
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"scripted",verified_audio:false,entries:[
    {role:"user",text:"<img src=x onerror=alert(1)>",source:"utterance_end"},
    {role:"teacher",text:"A saved explanation.\nSecond line.",source:"lock",presented:true},
    {role:"teacher",text:"Never presented",source:"lock",presented:false},
  ]});
  await reading;
  const textNodes = descendants(page.get("sessions"));
  assert.equal(textNodes.some(node=>node.textContent === "<img src=x onerror=alert(1)>"),true);
  assert.equal(textNodes.some(node=>node.textContent === "A saved explanation.\nSecond line."),true);
  assert.equal(textNodes.some(node=>node.textContent === "Never presented"),false);
  assert.equal(textNodes.some(node=>node.textContent?.includes("not verified audio captions")),true);
  assert.equal(textNodes.filter(node=>node.tagName === "li").length,2);
  button.onclick(); await button.onclick();
  assert.equal(page.requests.length,2); // Already-read text is not fetched again.
});

test("an empty script is explicit rather than invented from the video", async () => {
  const page = library(); await page.respond([session()]);
  const button = descendants(page.get("sessions")).find(node=>node.tagName === "button" && node.textContent === "阅读会话文字");
  const reading = button.onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"scripted",verified_audio:false,entries:[]});
  await reading;
  assert.equal(descendants(page.get("sessions")).some(node=>node.textContent === "这次会话没有保存可读的文字。"),true);
});

test("transcript scope mismatches expose no content and allow retry", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const button = descendants(page.get("sessions")).find(node=>node.textContent === "Read session text");
  const reading = button.onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"other",entries:[{role:"user",text:"Other learner private text"}]});
  await reading;
  let nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "Other learner private text"),false);
  assert.equal(nodes.some(node=>node.textContent === "Session text couldn’t be loaded. Try again."),true);
  const retrying = nodes.find(node=>node.textContent === "Retry session text").onclick();
  page.requests[2].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"scripted",verified_audio:false,entries:[]});
  await retrying;
  nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "No readable text was saved for this session."),true);
});

===== FILE: scripts/student_frontend_check.py =====
"""Real-browser student UI checks against isolated CPU services, never the user's profiles.

Usage: python3 scripts/student_frontend_check.py [--shots DIRECTORY]
Mock sessions verify transport/UX. Explicit synthetic lesson events verify rendering only.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', type=Path)
    args = parser.parse_args()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='student-ui-') as directory:
        scratch = Path(directory)
        backend_port, front_port = port(), port()
        while backend_port == front_port:
            front_port = port()
        logs = [(scratch / name).open('w') for name in ('backend.log', 'frontend.log')]
        backend = subprocess.Popen(['python3', '-m', 'live_agent.backend.app', '--host', '127.0.0.1', '--port', str(backend_port), '--config', 'configs/persona_teacher', '--generator', 'mock', '--llm-url', 'scripted', '--vlm-url', 'mock', '--asr-url', '', '--memory-db', '', '--students', 'demo,learner', '--student-store', str(scratch / 'students'), '--log-dir', str(scratch / 'sessions'), '--dev-allow-uncalibrated'], cwd=ROOT, stdout=logs[0], stderr=subprocess.STDOUT)
        env = {**os.environ, 'HOST': '127.0.0.1', 'PORT': str(front_port), 'BACKEND_URL': f'http://127.0.0.1:{backend_port}'}
        frontend = subprocess.Popen(['node', 'frontend/server.mjs'], cwd=ROOT, env=env, stdout=logs[1], stderr=subprocess.STDOUT)
        origin = f'http://127.0.0.1:{front_port}'
        try:
            for _ in range(150):
                try:
                    with urlopen(origin + '/api/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError('isolated services did not start')
            with sync_playwright() as browser:
                chromium = browser.chromium.launch(headless=True)
                context = chromium.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                for edition in ('primary', 'secondary', 'university'):
                    for width in (1440, 390, 320):
                        page.set_viewport_size({'width': width, 'height': 1000 if width == 1440 else 844})
                        page.goto(origin + '/?edition=' + edition)
                        page.wait_for_function("!document.getElementById('connect').disabled")
                        page.wait_for_selector('.course-card')
                        assert page.locator('html').get_attribute('lang') == ('en' if edition == 'university' else 'zh-CN')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (edition, width, 'horizontal overflow')
                        assert page.locator('#diagnostics').get_attribute('open') is None
                        for nav in ('Live classroom', 'Explore topics', 'Learning profile', 'Session recordings') if edition == 'university' else ('我的小课堂','找点新知识','我的学习卡','看看课堂记录') if edition == 'primary' else ('私人课堂','探索课程','学习档案','课堂记录'):
                            assert page.get_by_role('navigation').get_by_role('link', name=nav, exact=True).count() == 1
                        assert page.locator('#helpOpen').is_visible()
                        assert page.locator('#profileDisclaimer').inner_text()
                        assert page.locator('#runtimeNotice').is_visible()
                        page.locator('.course-card').first.click()
                        assert page.locator('#lessonTopic').input_value()
                        assert page.locator('#startLesson').is_disabled()
                        page.locator('#helpOpen').evaluate('(button)=>button.click()')
                        assert page.locator('#helpDialog').is_visible()
                        page.keyboard.press('Escape')
                        assert not page.locator('#helpDialog').is_visible()
                        if args.shots:
                            page.evaluate('scrollTo(0,0)')
                            page.screenshot(path=str(args.shots / f'classroom-{edition}-{width}.png'), full_page=True)
                            if width == 1440:
                                page.screenshot(path=str(args.shots / f'classroom-{edition}-preview.png'))
                        results.append({'edition': edition, 'width': width, 'layout': 'passed'})
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.goto(origin + '/?edition=secondary')
                page.wait_for_function("!document.getElementById('connect').disabled")
                page.locator('#notes').fill('Student A private note')
                page.locator('#sid').select_option('learner')
                assert page.locator('#notes').input_value() == ''
                page.locator('#notes').fill('Student B private note')
                page.locator('#sid').select_option('demo')
                assert page.locator('#notes').input_value() == 'Student A private note'
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#notes').input_value() == 'Student A private note'
                with page.expect_download() as exported:
                    page.locator('#exportNotes').click()
                assert Path(exported.value.path()).read_text() == 'Student A private note'
                results.append({'notes': 'persist, isolate and export passed'})
                page.locator('#edition').select_option('university')
                assert 'Example profile' in page.locator('#sid').inner_text()
                assert page.locator('html').get_attribute('lang') == 'en'
                assert 'edition=university' in page.locator('#profLink').get_attribute('href')
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#edition').input_value() == 'university'
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'", timeout=15000)
                assert page.locator('#talk').is_disabled()
                assert page.locator('#startLesson').is_disabled()
                assert 'Video preview' in page.locator('#runtimeNotice').inner_text()
                assert 'cannot create lessons' in page.locator('#runtimeNotice').inner_text()
                page.locator('#text').fill('请讲慢一点')
                page.locator('#text').press('Enter')
                assert page.locator('#chat .msg.user').last.inner_text() == '请讲慢一点'
                page.wait_for_function('queue.length > 0', timeout=15000)
                dimensions = page.locator('#screen').bounding_box()
                ratio = page.evaluate('canvas.width/canvas.height')
                assert abs(dimensions['width']/dimensions['height'] - ratio) < .01
                # Synthetic capability fixtures verify UI gating and the actual outgoing text contract only.
                page.evaluate("""() => {window.__sentTexts=[];const original=ws.send.bind(ws);ws.send=data=>{try{const packet=JSON.parse(data);if(packet.type==='text')window.__sentTexts.push(packet.text);}catch{};original(data);};window.LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}""")
                assert 'cannot create lessons' not in page.locator('#runtimeNotice').inner_text()
                page.locator('#gradeFilter').select_option('3')
                page.locator('#subjectFilter').select_option('数学')
                page.locator('.course-card').first.click()
                page.locator('#startLesson').click()
                assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
                page.evaluate("LiveAgentProduct.sessionChanged('ready',{status:{generator:'taomate_h3',responder:'rules',board:true}})")
                assert 'Video preview' not in page.locator('#runtimeNotice').inner_text()
                assert page.locator('#startLesson').is_disabled()
                results.append({'capability fixtures':'video/responder independently gated; catalogue grade/subject preserved'})
                page.locator('#disconnect').click()
                page.wait_for_function("sessionState === 'disconnected'")
                results.append({'session': 'real CPU connect, text, media and disconnect passed'})
                # Synthetic events are deliberate rendering fixtures, not a generated teaching result.
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',concept:'Fixture',question:'Which value?',options:['A','B'],option_texts:['A. One','B. Two']}}}));window.__exerciseAnnounced=document.getElementById('exerciseAnnouncement').textContent;window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_graded',correct:false}}}));window.dispatchEvent(new CustomEvent('live-agent:state',{detail:{exercise:null}}));}""")
                assert page.locator('#exerciseCard').is_visible()
                assert 'A. One' in page.locator('#exerciseQuestion').inner_text()
                assert 'incorrect' in page.locator('#exerciseFeedback').inner_text()
                assert 'Which value?' in page.evaluate('window.__exerciseAnnounced')
                results.append({'exercise fixture': 'full question, choices and persistent feedback passed'})
                # Abort pre-session profile loads on connecting; public status must be authoritative.
                held_profiles = []
                page.route('**/api/students/learner', lambda route: held_profiles.append(route))
                page.evaluate("""() => {const original=LiveAgentAPI.fetchJson;window.LiveAgentAPI={...LiveAgentAPI,fetchJson:async(...args)=>{try{return await original(...args);}finally{if(args[0]==='/api/students/learner')window.__lateProfileCompleted=true;}}};}""")
                page.locator('#sid').select_option('learner')
                page.wait_for_function('true')
                for _ in range(100):
                    if held_profiles:
                        break
                    page.wait_for_timeout(10)
                assert held_profiles, 'late profile fixture did not intercept the request'
                page.locator('#text').evaluate("node=>node.value='PRIVATE DRAFT'")
                page.evaluate("""() => {document.getElementById('caption').textContent='PRIVATE CAPTION';document.getElementById('boardTitle').textContent='PRIVATE BOARD';document.getElementById('memory').textContent='PRIVATE MEMORY';document.getElementById('lessonTopic').value='PRIVATE TOPIC';}""")
                page.locator('#diagnostics').evaluate('(node)=>node.open=true')
                page.locator('#mode').select_option('public')
                assert not page.locator('#profCard').is_visible()
                assert not page.locator('.student-picker').is_visible()
                assert not page.locator('#chat .msg').count()
                assert page.locator('#text').input_value()==''
                assert page.locator('#caption').inner_text()==''
                assert page.locator('#memory').inner_text()==''
                assert page.locator('#lessonTopic').input_value()==''
                assert page.locator('#notes').input_value() == ''
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'", timeout=15000)
                held_profiles[0].fulfill(status=200, content_type='application/json', body=json.dumps({'id':'learner','name':'Delayed private name','grade':'初一','version':1,'exams':[],'concepts':[]}))
                page.wait_for_function('window.__lateProfileCompleted === true')
                page.wait_for_timeout(50)
                assert 'Delayed private name' not in page.locator('#prof').inner_text()
                assert page.evaluate('profile === null')
                assert page.locator('#uid').input_value()=='public-preview'
                assert 'student=' not in page.locator('#tracesNav').get_attribute('href')
                assert 'mode=public' in page.locator('#tracesNav').get_attribute('href')
                page.locator('#disconnect').click()
                results.append({'privacy': 'public classroom has no learner profile or private notes'})
                assert not errors, errors
                # Service errors and retry use real page logic with a controlled HTTP failure.
                page.unroute('**/api/students/learner')
                page.route('**/api/health',lambda route:route.fulfill(status=503,content_type='text/plain',body='Unavailable'))
                page.goto(origin+'/?edition=university')
                page.wait_for_selector('#connectionError:not([hidden])')
                assert page.locator('#connect').is_disabled()
                assert 'not available' in page.locator('#connectionErrorText').inner_text()
                page.unroute('**/api/health')
                page.locator('#connectionRetry').click()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert not page.locator('#connectionError').is_visible()
                results.append({'recovery':'HTTP service failure and retry passed'})
                page.route('**/api/students',lambda route:route.fulfill(status=200,content_type='application/json',body='{"students":[]}'))
                page.goto(origin+'/?edition=university')
                page.wait_for_selector('#connectionError:not([hidden])')
                page.locator('#diagnostics').evaluate('(node)=>node.open=true')
                page.locator('#mode').select_option('public')
                assert not page.locator('#connect').is_disabled()
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'")
                page.locator('#disconnect').click()
                results.append({'public without profiles':'healthy public mode remains usable'})
                context.close()
                chromium.close()
        finally:
            for process in (frontend, backend):
                process.terminate()
            for process in (frontend, backend):
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()
    print(json.dumps({'measured_locally': results, 'page_errors': errors}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
