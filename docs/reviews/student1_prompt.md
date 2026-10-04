Act as the independent reviewer for the owner-authorized student frontend refinement. Work read-only, no shell mutations. Challenge concrete bugs, unsupported claims, interface mismatches, privacy across private/public profile scope, stale async results, accessibility, and misleading teaching/assessment capabilities. Give findings as a numbered list, each marked blocking, major, or minor, with direct evidence or a check that would settle it. Do not equate agreement with verification. Focus this change, not an unrelated architecture redesign. The preceding frontend/backend split was separately reviewed.

Owner asks for a ready-to-use student frontend and web design research, then chooses all three audience versions: primary Chinese, secondary Chinese, and university/adult English. This change implements three interface editions, while explicitly disclosing that teacher language and school catalogue remain Chinese and no university curriculum is present. Current phase permits local implementation/test, no training/deployment/broadcast. All numbers in research/reporting must distinguish measured, cited, estimate, target. Runtime diagnostic counters are measurements; persisted mastery is uncalibrated estimate; demo profile must not masquerade as the learner's assessment.

Inputs include source and focused backend contract excerpts. The browser test uses isolated CPU mock services and explicit synthetic exercise events; it cannot qualify a real teaching model or GPU generation. Measured validation so far: frontend unit50passed; focusedPython65passed; actualbrowser six classroom edition/viewport combinations + notes/session/exercise/privacy scenarios passed with zeroJSerrors/overflow; profile/recordings twelve edition/viewport combinations passed; existing twelve audio/video alignment checks passed with real mock JPEG/PCM transport. Browser screenshots were visually inspected by contributor. Source is authoritative, test outcomes are not substitutes for reasoning.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/student_frontend.md =====
# Student frontend: research and implementation notes

Owner request, 2026-10-02: make the frontend a student product with primary-school and secondary-school
editions in Chinese, and a university/adult edition in English. This document records the inspected
contracts and the design references. Student-page implementation and verification are in progress;
the edition names and grade ranges below are product configuration categories, not efficacy claims.

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
| `/ws` `text` | `{type: "text", text, tp}` goes through the responder; receipt interrupts playback before queuing the request. A topic-selection action requests a lesson through this text contract |
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
lessons or exercises, so lesson-start controls must reflect that limitation.

## Runtime and verification scope

The launcher now defaults to `PERSONA=teacher`; `PERSONA=hanfu` still selects the existing reading-host
persona. The frontend/backend separation, port configuration and GPU reservation rules are unchanged.
`scripts/run_live.sh demo` remains a CPU transport and interface demo. Real teaching needs a configured
responder model; GPU generation needs its existing model runtime and scheduler allocation.

The focused resource tests verify that topic titles come from stored data, obey their school-grade
coverage, and do not appear for an empty curriculum directory. Exercise tests verify that the real
question and full options reach snapshots and events without the reference answer. Launcher tests
verify the teacher default and explicit reading-host override through a stub backend. Final page and
cross-edition validation will be recorded when the student interface is complete. These checks do not
establish learning efficacy, university curriculum coverage, English speech quality or GPU performance.

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
<nav class="navigation"><a class="nav-item active" href="#classroom" aria-current="page"><svg><use href="#i-book"/></svg><span data-i18n="classroom">私人课堂</span></a><a class="nav-item" href="#courses"><svg><use href="#i-grid"/></svg><span data-i18n="courses">探索课程</span></a><a class="nav-item" id="profileNav" href="/profile"><svg><use href="#i-user"/></svg><span data-i18n="profile">学习档案</span></a><a class="nav-item" id="tracesNav" href="/traces"><svg><use href="#i-play"/></svg><span data-i18n="recordings">课堂记录</span></a></nav>
<div class="sidebar-note"><span>✦</span><p id="sidebarNote">每一个好问题，<br>都是进步的开始。</p></div>
<button class="nav-item help-button" id="helpOpen"><svg><use href="#i-help"/></svg><span data-i18n="help">使用指南</span></button><div class="service-indicator"><i id="serviceDot"></i><span id="serviceStatus" role="status">正在检查课堂…</span></div>
</aside>
<div class="workspace">
<header class="topbar"><div class="breadcrumb"><span data-i18n="mySpace">我的学习空间</span><span aria-hidden="true">/</span><strong data-i18n="classroom">私人课堂</strong></div><label class="edition-control"><span data-i18n="experience">学习体验</span><select id="edition" aria-label="学习体验"><option value="primary">小学 · 中文</option><option value="secondary" selected>初高中 · 中文</option><option value="university">University & adult · English</option></select></label></header>
<main>
<section class="welcome" aria-labelledby="welcomeTitle"><div class="welcome-copy"><span class="eyebrow" id="welcomeEyebrow">给好奇心一点空间</span><h1 id="welcomeTitle">今天，想弄懂什么？</h1><p id="welcomeDescription">从一个问题开始。和 AI 老师一起，把复杂的知识慢慢理清。</p><div class="welcome-tags"><span><svg><use href="#i-check"/></svg><span data-i18n="tagAsk">随时提问</span></span><span><svg><use href="#i-check"/></svg><span data-i18n="tagPractice">边学边练</span></span><span><svg><use href="#i-check"/></svg><span data-i18n="tagPace">按你的节奏</span></span></div></div><svg class="welcome-art" viewBox="0 0 300 180" aria-hidden="true"><circle cx="158" cy="91" r="79" fill="#e5edce"/><circle cx="242" cy="43" r="8" fill="#eac87c"/><path d="m61 33 3 9 9 3-9 3-3 9-3-9-9-3 9-3Z" fill="#276653"/><path d="M93 58c22-8 44-4 62 8 18-12 40-16 62-8v86c-25-8-45-6-62 6-17-12-37-14-62-6V58Z" fill="#fffdf8" stroke="#276653" stroke-width="3" stroke-linejoin="round"/><path d="M155 66v84m-44-70c11-1 19 1 28 5m-28 11c11-1 19 1 28 5m-28 11c11-1 19 1 28 5m31-34c11-5 20-6 30-5m-30 21c11-5 20-6 30-5m-30 21c11-5 20-6 30-5" fill="none" stroke="#b4c7b1" stroke-width="3" stroke-linecap="round"/><path d="m208 133 20-59 12 4-20 59-12 11Z" fill="#eac87c" stroke="#276653" stroke-width="2"/><path d="m244 112 4 12 12 4-12 4-4 12-4-12-12-4 12-4Z" fill="#276653"/><ellipse cx="151" cy="164" rx="92" ry="5" fill="#276653" opacity=".08"/></svg></section>
<div class="connection-error" id="connectionError" role="alert" hidden><span id="connectionErrorText"></span><button id="connectionRetry" data-i18n="retry">重试</button></div><div class="notice" id="runtimeNotice" role="status" hidden></div>
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
<section class="card lesson-card" aria-labelledby="lessonHeading"><div class="card-heading"><h2 id="lessonHeading" data-i18n="todayGoal">从一个目标开始</h2><svg class="small-icon"><use href="#i-book"/></svg></div><p class="meta" id="lessonHelp" data-i18n="lessonHelp">想复习、预习，还是解决一道难题？</p><label for="lessonTopic" data-i18n="topicLabel">今天想学</label><input id="lessonTopic" type="text" maxlength="80" placeholder="例如：一次函数" aria-describedby="lessonHelp"><button class="primary wide" id="startLesson" disabled data-i18n="startLesson">开始这节课 →</button><p class="meta" id="lessonStatus" role="status" data-i18n="lessonEmpty">也可以从下方课程中选一个知识点。</p><ol class="learning-steps"><li id="stepChoose" class="current"><span>✓</span><div><strong data-i18n="stepChoose">选个目标</strong><small data-i18n="stepChooseHelp">告诉老师，你想弄懂什么</small></div></li><li id="stepLearn"><span>○</span><div><strong data-i18n="stepLearn">一起学懂</strong><small data-i18n="stepLearnHelp">看板书，听讲解，随时问</small></div></li><li id="stepPractice"><span>○</span><div><strong data-i18n="stepPractice">试一试</strong><small data-i18n="stepPracticeHelp">做一道题，看看理解得怎样</small></div></li></ol><button class="text-button" id="practice" disabled data-i18n="practice">给我一道练习题 ↗</button></section>
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
  let topics = [], catalogueFailed = false, limit = 6, pendingLesson = null, profileRequest = 0, selectedProfile = null;
  let noteKey = null, loadingProfile = false, recentExercise = null, healthInfo = null, bootstrapAttempt = 0;
  const originals = new Map(), originalAttributes = new Map();
  document.querySelectorAll('[data-i18n-aria]').forEach(node=>originalAttributes.set(node,node.getAttribute('aria-label')));
  document.querySelectorAll('[data-i18n]').forEach(node => originals.set(node,node.textContent));
  const en = {
    skip:'Skip to classroom',navigation:'Main navigation',brand:'YāLearn',mySpace:'My learning space',classroom:'Live classroom',courses:'Explore topics',profile:'Learning profile',recordings:'Session recordings',help:'Quick guide',experience:'Experience',tagAsk:'Ask freely',tagPractice:'Learn & practice',tagPace:'Your own pace',retry:'Try again',liveRoom:'YOUR LIVE CLASSROOM',roomHint:'Choose a learner profile to get started',private:'Private session',video:'AI tutor video',board:'Lesson board',boardTitle:'A little space for a new idea',boardIntro:'Your tutor’s key points will appear here.',boardAsk:'Ask a question whenever you need.',boardPractice:'Try a practice question as you learn.',learner:'Learner',editProfile:'Edit profile',connect:'Enter classroom ↗',disconnect:'End session',inputLabel:'Ask your tutor',send:'Send',talk:'Hold to speak',avButton:'Audio / video sync',inputHint:'Enter to send · A new question interrupts playback',avOffset:'Video delay',avTest:'Test flash & sound',avReset:'Reset',avHelp:'If the sound is late, move right. If the picture is late, move left. This setting stays in this browser; test again after changing headphones.',tryAsk:'A starting point for your next question',suggestions:'Suggested questions',aiNotice:'AI explanations and grading can be wrong. Check important details against your course materials.',todayGoal:'Start with a learning goal',lessonHelp:'Review a foundation, explore an idea, or work through a question.',topicLabel:'I want to understand',startLesson:'Start a lesson →',lessonEmpty:'Choose a topic below, or enter your own question.',stepChoose:'Choose a goal',stepChooseHelp:'Make your next learning task clear',stepLearn:'Explore the idea',stepLearnHelp:'Follow the board and ask questions',stepPractice:'Check your understanding',stepPracticeHelp:'Try a question and reflect on feedback',practice:'Request a practice question ↗',yourTurn:'YOUR TURN',exercise:'Practice question',exerciseHelp:'Use the choices below the classroom or type your answer.',profileGlance:'My learning profile',manage:'Edit ↗',profileEmpty:'Select a profile to see your learning records.',discover:'FOLLOW YOUR CURIOSITY',courseHeading:'Explore a topic worth understanding',catalogueNote:'Available catalogue: Chinese school subjects. Chapter titles and teaching are currently in Chinese; university courses are not included.',subject:'Subject',grade:'School grade',allSubjects:'All subjects',searchCourses:'Search topics',searchPlaceholder:'Search a chapter title…',coursesLoading:'Loading available topics…',moreCourses:'Show more topics ↓',conversation:'Classroom conversation',export:'Export',conversationEmpty:'Your questions and your tutor’s responses appear here.',notes:'My study notes',localOnly:'Stored in this browser only',notesPlaceholder:'An idea to remember. A question to revisit…',notesHelp:'Notes stay on this device, grouped by learner.',diagnostics:'Classroom settings & technical details',sessionSettings:'Session settings',sessionMode:'Mode',memoryIdentity:'Memory identifier',settingsHelp:'Test livestream mode does not use a student profile. The memory identifier connects session memories; it is not a login.',cameraHelp:'Focus check requires camera permission. Images are analyzed without being saved.',metrics:'Runtime diagnostics · measurements / estimates',metricsHelp:'Onset is measured from audio energy; it does not measure answer correctness. Simulated judging does not verify real actions.',intent:'Instruction state',timeline:'Event log',memory:'Session memory',footer:'YāLearn · Bring a question. Leave with understanding.',footerDetail:'AI classroom by Live Agent',close:'Close',helpOne:'Choose a learner profile, then enter the classroom.',helpTwo:'Choose a topic or enter a goal, then request a lesson. You can also type a question directly.',helpThree:'Interrupt to ask for clarification. Use the choices or text box to answer a practice question.',helpFour:'Edit or reset the profile and learning history. Notes are stored only in this browser.',helpLimit:'This edition translates the interface. The current curriculum covers Chinese school subjects and the teacher speaks Mandarin. Voice and video depend on service configuration.',privacyHelp:'This is a local classroom for trusted devices, without student authentication or account isolation. Recordings may include conversations; take care with personal information on shared devices.',
    ready:'Classroom available',unavailable:'Classroom unavailable',checking:'Checking classroom…',idle:'Ready when you are',connecting:'Preparing your classroom…',ended:'Session ended. Start again whenever you’re ready.',readyHint:'Your tutor is ready. Ask your first question.',demoProfile:'Example profile · Sample records are not your assessment.',profileEvidence:'Understanding values are uncalibrated estimates from the stored profile.',profileLoadFailed:'Could not load this profile. Try selecting it again.',studentsFailed:'Could not load learner profiles. Check that the backend is running, then try again.',serviceFailed:'The classroom service is not available. Start the backend and try again.',mockNotice:'Preview mode: placeholder video. Simple conversation is available; lesson and exercise generation require a configured teaching model.',languageNotice:'English interface · The current teaching language and school catalogue are Chinese. University course coverage is not available.',rulesLesson:'This preview cannot create lessons or practice questions. Configure a teaching model to use these actions.',noTeacher:'This persona does not support classroom lessons. Start the service with PERSONA=teacher.',selectGoal:'Enter a topic first.',lessonWaiting:'Preparing your lesson request…',lessonSent:'Lesson requested. Waiting for the tutor’s plan…',lessonPrepared:'Lesson material is prepared. Follow the live explanation.',lessonFailed:'The lesson could not be prepared. Ask a smaller question or try again.',outlineReady:'Your lesson plan is ready:',sectionReady:'Prepared section:',practiceWaiting:'Practice requested. Waiting for the question…',practiceClosed:'This question is closed. Ask for another when you’re ready.',correct:'The tutor marked this answer correct.',incorrect:'The tutor marked this answer incorrect. Ask for a hint and try again.',skipped:'You chose to skip. Ask the tutor to explain the idea.',gradingFailed:'The answer could not be graded. Ask the tutor to try again.',exercisePending:'A practice question is waiting for your answer.',noTopics:'No matching topics. Try another grade or subject, or enter a custom goal.',catalogueError:'The topic catalogue could not be loaded.',allGrades:'All school grades',topicAction:'Choose topic ↗',textbook:'Textbook chapter',estimate:'Estimated placement',reference:'Catalogue reference',customTopic:'Custom topic request',emptyExport:'There is nothing to export yet.',noteSaved:'Saved on this device',noteFailed:'Could not save. Export your notes to keep a copy.',savedExample:'Example profile',noProfiles:'No learner profiles are available. Ask the operator to configure one.',publicMode:'Test livestream · No learner profile',localStorageHelp:'Notes could not be loaded from this browser. Export any new notes before leaving.'
  };
  const zh = {ready:'课堂服务可用',unavailable:'课堂服务不可用',checking:'正在检查课堂…',idle:'课堂准备好了',connecting:'正在准备课堂…',ended:'课堂已结束，随时可以重新开始。',readyHint:'老师准备好了，说说你的第一个问题吧。',demoProfile:'示例档案 · 这里的样例记录不是你的测评结果。',profileEvidence:'理解程度为档案中的估计值，尚未校准。',profileLoadFailed:'档案暂时加载失败，请重新选择。',studentsFailed:'学习档案加载失败，请确认后端运行后重试。',serviceFailed:'课堂服务暂时不可用，请启动后端后重试。',mockNotice:'演示模式：当前是占位视频，可体验简单对话；生成课程和练习需要配置教学模型。',rulesLesson:'当前演示不能生成课程和练习。启用教学模型后即可使用。',noTeacher:'当前人设不支持教学课程，请以 PERSONA=teacher 启动服务。',selectGoal:'先写下你想学的主题吧。',lessonWaiting:'正在准备你的课程请求…',lessonSent:'已请求课程，等待老师准备大纲…',lessonPrepared:'课程内容已备好，请跟随老师的实时讲解。',lessonFailed:'备课暂时失败了，可以换一个更具体的问题再试。',outlineReady:'课程大纲已准备：',sectionReady:'已备好：',practiceWaiting:'已请求练习，正在等待题目…',practiceClosed:'这道练习已结束，准备好后可以再来一道。',correct:'老师判定这次作答正确。',incorrect:'老师判定这次作答有误，可以请老师给你一个提示。',skipped:'这次先跳过，可以请老师再讲一遍思路。',gradingFailed:'这次未能完成批改，可以请老师重试。',exercisePending:'有一道练习在等你作答。',noTopics:'没有找到匹配课程，试试其他年级、学科，或直接填写学习目标。',catalogueError:'课程目录暂时加载失败。',allGrades:'全部年级',topicAction:'选这个主题 ↗',textbook:'教材章节',estimate:'年级归属为估计',reference:'课程目录参考',customTopic:'自选主题请求',emptyExport:'还没有可以导出的内容。',noteSaved:'已保存到当前设备',noteFailed:'保存失败，请导出笔记以保留内容。',savedExample:'示例档案',noProfiles:'尚未配置学习档案，请联系服务维护者。',publicMode:'测试直播 · 不读取学习档案',localStorageHelp:'无法读取本浏览器中的笔记，离开前请导出新笔记。'};
  const primary = {classroom:'我的小课堂',courses:'找点新知识',profile:'我的学习卡',recordings:'看看课堂记录',todayGoal:'今天想学什么呀？',lessonHelp:'找一个小问题，我们一起想一想。',topicLabel:'我想知道',startLesson:'和老师一起学 →',stepChoose:'选一个小目标',stepChooseHelp:'你想知道什么呀？',stepLearn:'一起找答案',stepLearnHelp:'看一看，听一听，不懂就问',stepPractice:'动手试一试',stepPracticeHelp:'答一道题，说说你的想法',practice:'老师，给我一道题 ↗',courseHeading:'下一个发现，等着你',tryAsk:'可以这样问老师',inputHint:'回车发送 · 想提问，随时打断老师'};
  function t(key, fallback='') { return (edition === 'university' ? en[key] : (edition === 'primary' ? primary[key] ?? zh[key] : zh[key])) ?? fallback; }
  function examples() {
    if (edition === 'university') return [{label:'Walk me through an example',text:'请给我讲一道例题'}, {label:'Explain that step again',text:'这一步我还没明白，请再解释一下'}, {label:'Let’s try a question',text:'给我出道练习题'}, {label:'A slower explanation',text:'请讲慢一点'}];
    return edition === 'primary' ? ['老师，可以举个例子吗？','这一步我还不懂','请讲慢一点','给我出道练习题'] : ['请给我讲一道例题','这一步我还没明白','给我出道练习题','请讲慢一点'];
  }
  const product = {get edition(){return edition;},t,examples,sessionChanged};
  window.LiveAgentProduct = product;
  function links() {
    const parameters = new URLSearchParams({edition,student:el('sid').value});
    ['profileNav','profLink'].forEach(id=>el(id).href='/profile?'+parameters);
    el('tracesNav').href='/traces?'+parameters;
    document.querySelector('.brand').href='/?'+parameters;
  }
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
    populateGrades(!initial);renderSubjects();renderCourses();updateService();updateRuntime();links();
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
      card.onclick=()=>{el('lessonTopic').value=topic.topic;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+basis.textContent;updateLessonActions();el('classroom').scrollIntoView({behavior:'smooth',block:'start'});el('lessonTopic').focus({preventScroll:true});};list.append(card);
    }
    el('moreCourses').hidden=matches.length<=limit;
  }
  async function requestJson(path){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);try{return await window.LiveAgentAPI.fetchJson(path,{signal:controller.signal});}finally{clearTimeout(timer);}}
  async function loadCatalogue(){catalogueFailed=false;el('catalogueRetry').hidden=true;try{const data=await requestJson('/api/curriculum/topics');topics=(data.topics||[]).filter(x=>typeof x.subject==='string'&&typeof x.topic==='string'&&Number.isInteger(x.grade)&&x.grade>=1&&x.grade<=12).map(x=>({...x,basis:String(x.basis||'')}));const order=['数学','英语','语文','物理','化学','生物','历史','地理'];topics.sort((a,b)=>(order.indexOf(a.subject)<0?99:order.indexOf(a.subject))-(order.indexOf(b.subject)<0?99:order.indexOf(b.subject))||a.grade-b.grade);}catch{catalogueFailed=true;topics=[];}renderSubjects();renderCourses();}
  function updateService(){el('serviceStatus').textContent=t(serviceReady?'ready':'unavailable');el('serviceDot').className=serviceReady?'ready':'error';}
  function updateRuntime(){const messages=[];if(edition==='university')messages.push(t('languageNotice'));if((status?.generator||healthInfo?.generator)==='mock'||status?.responder==='rules')messages.push(t('mockNotice'));if(status&&!status.board)messages.push(t('noTeacher'));el('runtimeNotice').textContent=messages.join(' ');el('runtimeNotice').hidden=!messages.length;}
  function updateLessonActions(){const allowed=studentsReady&&serviceReady&&connection!=='connecting'&&(!status||(status.board&&status.responder!=='rules'));el('startLesson').disabled=!allowed||!el('lessonTopic').value.trim();el('practice').disabled=connection!=='ready'||!status?.board||status?.responder==='rules'||!!recentExercise;}
  function sessionChanged(state,detail={}){
    connection=state;status=state==='ready'?detail.status:state==='connecting'?null:status;
    if(state==='connecting'){profileRequest++;loadingProfile=false;selectedProfile=null;el('connectionError').hidden=true;recentExercise=null;el('exerciseCard').hidden=true;el('exerciseFeedback').textContent='';['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
    if(state==='error'){pendingLesson=null;el('connectionError').hidden=false;el('connectionErrorText').textContent=detail.message||t('serviceFailed');}
    if(state==='disconnected'){pendingLesson=null;recentExercise=null;el('exerciseCard').hidden=true;el('lessonStatus').textContent=t('ended');}
    el('sessionHint').textContent=t(state==='ready'?'readyHint':state==='connecting'?'connecting':state==='disconnected'?'ended':'serviceFailed');
    if(state!=='connecting'&&state!=='ready')el('connect').disabled=!studentsReady||!serviceReady;
    updateLessonActions();updateRuntime();
  }
  function profileDisclaimer(p){el('profileDisclaimer').textContent=!p?'':p.id==='demo'?t('demoProfile'):t('profileEvidence');}
  async function selectProfile(){
    const request=++profileRequest;const id=el('sid').value;if(el('mode').value==='public'){selectedProfile=null;loadingProfile=false;window.showProfile?.(null);profileDisclaimer(null);loadNotes();return;}loadingProfile=true;links();storage.set('liveAgent.student',id);el('uid').value='learner:'+id;loadNotes();
    try{const p=await requestJson('/api/students/'+encodeURIComponent(id));if(request!==profileRequest)return;selectedProfile=p;window.showProfile?.(p);profileDisclaimer(p);}
    catch{if(request!==profileRequest)return;selectedProfile=null;el('prof').textContent=t('profileLoadFailed');el('profileDisclaimer').textContent='';}
    finally{if(request===profileRequest)loadingProfile=false;}
  }
  async function bootstrap(){
    const attempt=++bootstrapAttempt;el('connectionRetry').disabled=true;
    const results=await Promise.allSettled([requestJson('/api/health'),requestJson('/api/students')]);
    if(attempt!==bootstrapAttempt)return;el('connectionRetry').disabled=false;
    serviceReady=results[0].status==='fulfilled';healthInfo=serviceReady?results[0].value:null;studentsReady=results[1].status==='fulfilled'&&Array.isArray(results[1].value.students)&&results[1].value.students.length>0;
    el('sid').replaceChildren();
    if(studentsReady){for(const student of results[1].value.students){const option=document.createElement('option');option.value=student.id;option.textContent=(student.name||student.id)+(student.id==='demo'?' · '+t('savedExample'):'');el('sid').append(option);}const preferred=query.get('student')||storage.get('liveAgent.student');if([...el('sid').options].some(o=>o.value===preferred))el('sid').value=preferred;el('sid').disabled=connection==='ready'||connection==='connecting';await selectProfile();}
    else{const option=document.createElement('option');option.value='';option.textContent=t('noProfiles');el('sid').append(option);el('sid').disabled=true;}
    if(connection!=='ready'&&connection!=='connecting')el('connect').disabled=!studentsReady||!serviceReady;
    updateService();updateLessonActions();updateRuntime();
    if(!serviceReady||!studentsReady){el('connectionError').hidden=false;el('connectionErrorText').textContent=t(!serviceReady?'serviceFailed':'studentsFailed');}
    else{el('connectionError').hidden=true;}
    loadCatalogue();
  }
  function requestLesson(){
    const topic=el('lessonTopic').value.trim();if(!topic){el('lessonStatus').textContent=t('selectGoal');el('lessonTopic').focus();return;}
    if(status&&(status.responder==='rules'||!status.board)){el('lessonStatus').textContent=t(status.responder==='rules'?'rulesLesson':'noTeacher');return;}
    const prompt='给我上一节'+topic+'的课';
    if(connection==='ready'){if(window.sendText(prompt)){el('lessonStatus').textContent=t('lessonSent');el('stepLearn').classList.add('current');}}
    else{pendingLesson=prompt;el('lessonStatus').textContent=t('lessonWaiting');el('connect').click();}
  }
  function renderExercise(ex){recentExercise=ex||null;el('exerciseCard').hidden=!ex&&!el('exerciseFeedback').textContent;if(ex){const question=ex.question||ex.concept;el('exerciseQuestion').textContent=[question,...(ex.option_texts||[])].join('\n');el('suggestionLabel').textContent=t('exercisePending');el('stepPractice').classList.add('current');}else el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));updateLessonActions();}
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
  el('sid').onchange=selectProfile;el('mode').onchange=()=>{profileRequest++;selectedProfile=null;loadingProfile=false;selectProfile();const label=document.querySelector('.private-label');label.textContent=el('mode').value==='public'?t('publicMode'):t('private','私人会话');};el('lessonTopic').oninput=updateLessonActions;el('startLesson').onclick=requestLesson;
  el('practice').onclick=()=>{if(window.sendText('给我出道'+el('lessonTopic').value.trim()+'练习题'))el('lessonStatus').textContent=t('practiceWaiting');};
  ['subjectFilter','gradeFilter','courseSearch'].forEach(id=>el(id).addEventListener(id==='courseSearch'?'input':'change',()=>{limit=6;renderCourses();}));
  el('moreCourses').onclick=()=>{limit+=6;renderCourses();};el('catalogueRetry').onclick=loadCatalogue;
  el('connectionRetry').onclick=()=>{if(serviceReady&&studentsReady)el('connect').click();else bootstrap();};
  el('helpOpen').onclick=()=>el('helpDialog').showModal();el('helpClose').onclick=()=>el('helpDialog').close();
  el('notes').oninput=()=>el('noteStatus').textContent=t(storage.set(noteKey||'liveAgent.notes.unselected',el('notes').value)?'noteSaved':'noteFailed');
  el('exportNotes').onclick=()=>download(el('notes').value,'study-notes.txt');
  el('exportChat').onclick=()=>download([...el('chat').querySelectorAll('.msg')].map(n=>n.textContent).join('\n\n'),'classroom-conversation.txt');
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const prompt=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)el('lessonStatus').textContent=t(status.responder==='rules'?'rulesLesson':'noTeacher');else if(window.sendText(prompt))el('lessonStatus').textContent=t('lessonSent');}updateLessonActions();});
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
  "profile.mastery": "Concept mastery (uncalibrated estimates; hover for evidence)",
  "profile.noConcepts": "Concept records appear after practice.", "exercise.unsure": "I’m not sure",
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
  $("chips").innerHTML = "";
  list.forEach(x => {
    const b = document.createElement("button"); b.className = "chip";
    b.textContent = typeof x === "object" ? x.label : x; b.disabled = !enabled;
    if (typeof x === "object" && x.description) b.setAttribute("aria-label", x.description);
    b.onclick = () => sendText(typeof x === "object" ? x.text : x); $("chips").appendChild(b);
  });
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
  shownBoard = null; $("board").classList.remove("on"); $("boardItems").innerHTML = "";
  $("boardImg").removeAttribute("src"); $("boardCap").textContent = "";
  delete $("board").dataset.key;
}
$("connect").onclick = async () => {
  if (sessionState === "connecting" || sessionState === "ready") return;
  const attempt = ++connectionAttempt;
  const student = $("student") || $("sid");
  const hello = {type: "hello", mode: $("mode").value, user_id: $("uid").value, student: student.value.trim()};
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
    ["生成", m.generator === "mock" ? "mock（CPU 演示）" : m.generator],
    ["导演", m.director === "open_loop" ? "A1 开环" : "A2 在线导演"],
    ["应答", m.responder === "rules" ? "规则（演示）" : m.responder],
    ["质检", {mock: "模拟判定（演示）", vlm: "Qwen3-VL", none: "无"}[m.judge] || m.judge],
    ["语音", m.asr ? "Qwen3-ASR" : "仅文字"],
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
  const exams = (p.exams || []).slice(-4).map(e => `<li>${esc(e.date || "")} ${esc(e.subject)}${esc(e.name)} <b>${e.score}</b>/${e.full}` +
    (e.weak && e.weak.length ? ` · 失分：${esc(e.weak.join("、"))}` : "") + "</li>").join("");
  const SRC = {exercise: "据练习", exam: "据考试失分推断"};
  const cps = (p.concepts || []).map(c => `<div class="cp ${esc(c.level)}${flash === c.name ? " flash" : ""}" title="${esc(LEVEL[c.level] || c.level)}（估计，${SRC[c.source] || "无依据"}）${c.attempts ? `，练习 ${c.correct}/${c.attempts} 对` : ""}">
      <span>${esc(c.name)}</span><span class="bar"><i style="width:${Math.round((c.mastery ?? 0) * 100)}%"></i></span>
      <span class="v">${c.mastery == null ? "–" : (c.source === "exam" ? "≈" : "") + Math.round(c.mastery * 100) + "%"}</span></div>`).join("");
  el.innerHTML = `<div class="who">${esc(p.name || tr("profile.learner", "同学"))} · ${esc(p.grade || tr("profile.gradeMissing", "年级未填"))}</div>` +
    (exams ? `<ul class="exams">${exams}</ul>` : `<div class="meta">${esc(tr("profile.noExams", "还没有考试成绩"))}</div>`) +
    (cps ? `<div class="meta">${esc(tr("profile.mastery", "知识点掌握度（估计值，未校准；悬停看依据）"))}</div>` + cps : `<div class="meta">${esc(tr("profile.noConcepts", "做练习后，这里会出现知识点记录。"))}</div>`);
}
$("profEdit").onclick = () => {
  const id = profile ? profile.id : $("sid").value;
  window.location.href = `/profile?student=${encodeURIComponent(id)}&edition=${encodeURIComponent(window.LiveAgentProduct?.edition || "primary")}`;
};
function showExercise(ex) {  // answer buttons while an exercise waits; the persona's examples otherwise
  const key = ex ? ex.concept + (ex.options || []).join("") : "";
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
  if (s.listening) flags.push("聆听中");
  if (s.awaiting_decision) flags.push("等待应答决策");
  if (!s.erasure_gate_open) flags.push("删除进行中（已暂停生成）");
  $("flags").textContent = flags.join(" · ");
  const el = $("chains");
  if (!s.chains || !s.chains.length) return;
  el.innerHTML = "";
  for (const c of s.chains.slice().reverse()) {
    const steps = c.steps && c.steps.length > 1 ? ` · 步骤 ${Math.min(c.step_index, c.steps.length)}/${c.steps.length}` : "";
    const d = document.createElement("div"); d.className = "chain";
    d.innerHTML = `<div class="top"><span class="intent">${esc(c.intent)}</span><span class="pill ${esc(c.status)}">${esc(STATUS[c.status] || c.status)}</span></div>
      <div class="meta">${esc(KIND[c.kind] || c.kind)}${steps}${c.revisions ? ` · 改口 ${c.revisions} 次` : ""}${c.requests.length ? ` · 请求 ${c.requests.join(", ")}` : ""}</div>`;
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
        (d.recalled || []).forEach(x => memo("召回：" + x));
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
          chat("sys", "已按删除请求清除本页的对话与记忆记录");
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
      el.textContent = d.state === "off" ? "专注检测：未开启" :
        `专注检测：${name[st] || st}` + (d.reason ? `（${d.reason}）` : "");
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
  queue = []; playhead = audioCtx ? audioCtx.currentTime : 0; onScreen = null; lastBoard = null;
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
  $("avInfo").textContent = `声卡报告的输出延迟 ≈ ${Math.round(out * 1000)} ms，屏幕刷新 ≈ ${Math.round(refreshS * 1000)} ms（均已自动补偿）`;
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
function sendText(v) {
  v = (v ?? $("text").value).trim(); if (!v || !ready()) return false;
  if (!send({type: "text", text: v, tp: performance.now()})) {
    notice("session.sendFailed", "消息还没有发出去，请重新连接后再试。"); return false;
  }
  chat("user", v); $("text").value = ""; return true;
}
$("send").onclick = () => sendText();
$("text").onkeydown = e => { if (e.key === "Enter" && !e.isComposing && !e.shiftKey) { e.preventDefault(); sendText(); } };
addEventListener("pagehide", () => { $("disconnect").onclick(); cancelSpeech(); camOff(false); });

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
  <a class="brand" href="/" data-link="classroom"><span class="brand-mark" aria-hidden="true">L<span>·</span>A</span><span>Live Agent<small data-copy="brandSub">陪你把知识学明白</small></span></a>
  <div class="nav-label" data-copy="space">我的学习空间</div>
  <nav aria-label="主导航" id="mainNav">
    <a data-link="classroom" href="/"><span aria-hidden="true">↗</span><span data-copy="classroom">学习课堂</span></a>
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
  skip:"跳到主要内容", brandSub:"陪你把知识学明白", space:"我的学习空间", classroom:"学习课堂", profile:"学习档案", recordings:"课堂回顾",
  sideTitle:"每个人，都有自己的节奏。", sideText:"告诉老师你学到了哪里，从这里继续向前。", editionLabel:"学习阶段", privateSpace:"一对一学习 · 本地演示", back:"返回课堂 ↗", eyebrow:"A LITTLE ABOUT YOU", title:"让学习更适合你。", intro:"补充你的年级和学习情况，老师会用更合适的例子、节奏和练习陪你学习。", demo:"演示档案", studentLabel:"当前学生", privacy:"档案只用于一对一学习。掌握度是未经校准的估计，可以手动修正。",
  basicKicker:"先认识一下", basic:"基本信息", nameLabel:"怎么称呼你", gradeLabel:"年级 / 学习阶段", namePlaceholder:"如 小明", gradePlaceholder:"如 初二", basicHelp:"只填写你愿意分享的信息。不确定的内容可以留空。", examKicker:"找到下一步", exams:"考试与测验", addExam:"＋ 添加成绩", examHelp:"写下最近的测验成绩。需要再练习的知识点，用逗号或顿号分开。", conceptKicker:"看看学习进展", concepts:"知识点掌握度", estimate:"估计值", conceptHelp:"这些估计来自测验、练习或手动调整，不是正式评定。滑块可以用方向键调整。",
  weak:"值得再练习", partial:"正在理解", mastered:"比较熟悉", unknown:"还未评估", newConcept:"添加知识点", subject:"学科", masteryInput:"估计掌握度 %", conceptPlaceholder:"如 因式分解", subjectPlaceholder:"如 数学", masteryPlaceholder:"可留空", addConcept:"＋ 添加", newConceptHelp:"留空表示还未评估；填写后作为手动估计保存。", historyKicker:"一步一步的积累", history:"最近练习", time:"时间", concept:"知识点", result:"结果", question:"题目", answer:"你的回答", dataOptions:"管理练习记录", clearHistory:"保存时清空练习记录、练习次数、错因和练习得出的掌握度",
  guideTitle:"从你现在的位置出发。", guideText:"成绩是线索，不是标签。告诉老师哪里有点难，让下一次练习更有帮助。", guideTipTitle:"小提示", guideTip:"课堂中的练习结果会自动更新这里。手动改动后，记得点击「保存档案」。", guideLink:"去课堂试一试 ↗", retry:"重新载入", reset:"恢复初始档案", discard:"放弃修改", save:"保存档案", loading:"载入中…", dirty:"有未保存的修改", noStudents:"暂时没有可用的学习档案。请联系这台服务的管理者。", loaded:"已载入 · 版本 {version}", initial:" · 初始演示内容，尚未保存", meta:"档案 {id} · 版本 {version}", gradeEmpty:"还没有填写学习阶段", noExams:"还没有测验成绩。需要时再添加就好。", examName:"测验名称", examPlaceholder:"如 期中考试", date:"日期", score:"分数（必填）", full:"满分（必填）", subjectRequired:"学科（必填）", weakConcepts:"需要再练习的知识点", weakPlaceholder:"如 因式分解、浮力", removeExam:"删除这次测验", remove:"删除", manual:"手动设定", exerciseSource:"练习 {correct}/{attempts} 对", examSource:"据测验失分推断", clearing:"保存时清除估计", manualUnsaved:"手动估计（未保存）", noConcepts:"还没有知识点记录。做一次练习，或者添加你想学的内容。", masteryLabel:"{name}的估计掌握度", sliderTitle:"方向键可调整估计掌握度", latestError:"最近的错因：", clear:"清除", clearTitle:"清除手动估计；若有相关测验，将使用测验推断的估计", undo:"撤销", correct:"正确", tryAgain:"需要再练习", noHistory:"还没有练习记录。你的课堂练习会出现在这里。", badExam:"请为每次测验填写学科、分数和满分。", saving:"正在保存…", saved:"已保存 · 版本 {version} · 课堂会同步更新", conflict:"档案在你编辑时更新了。请点击「放弃修改」载入最新内容，再重新编辑。", saveFailed:"保存失败：{message}", loadFailed:"暂时无法载入档案：{message}", resetConfirm:"恢复「{name}」的初始档案？保存的成绩、估计掌握度和练习记录都会删除。", resetDone:"已恢复初始档案", resetFailed:"恢复失败：{message}", switchConfirm:"有未保存的修改。继续会放弃这些修改。", refreshed:"已自动更新课堂练习 · 版本 {version}", navLabel:"主导航"
};
const en = {
  skip:"Skip to content", brandSub:"A little clearer, every day", space:"My learning space", classroom:"Study room", profile:"Learning profile", recordings:"Session library", sideTitle:"Your pace. Your next step.", sideText:"Help your tutor understand where you are, and where you want to go.", editionLabel:"Learning edition", privateSpace:"One-to-one learning · Local demo", back:"Back to study room ↗", eyebrow:"A LITTLE ABOUT YOU", title:"Make this space yours.", intro:"Share your study stage and recent work so your tutor can adapt the examples, pace and practice.", demo:"Demo profile", studentLabel:"Active learner", privacy:"Profiles are used only in private sessions. Mastery values are uncalibrated estimates that you can adjust.",
  basicKicker:"Start with the essentials", basic:"About you", nameLabel:"Preferred name", gradeLabel:"School grade (optional)", namePlaceholder:"Your name", gradePlaceholder:"Choose a school grade, or leave blank", basicHelp:"Only Chinese school grades are supported in profiles. Leave the grade blank if none applies. This edition changes the interface language; teaching and the current catalogue remain Chinese school subjects.", examKicker:"Find your next step", exams:"Assessments & results", addExam:"＋ Add result", examHelp:"Add a recent assessment. Separate topics that need practice with commas.", conceptKicker:"A view of your progress", concepts:"Topic understanding", estimate:"Estimated", conceptHelp:"These estimates come from assessments, practice or manual adjustments. They are not formal evaluations. Use arrow keys to adjust sliders.",
  weak:"Needs practice", partial:"Developing", mastered:"More comfortable", unknown:"Not assessed", newConcept:"New topic", subject:"Subject", masteryInput:"Estimated mastery %", conceptPlaceholder:"e.g. Derivatives", subjectPlaceholder:"e.g. Maths", masteryPlaceholder:"Optional", addConcept:"＋ Add", newConceptHelp:"Leave blank for not assessed. A value is saved as a manual estimate.", historyKicker:"Build on your practice", history:"Recent practice", time:"When", concept:"Topic", result:"Result", question:"Question", answer:"Your answer", dataOptions:"Manage practice data", clearHistory:"Clear practice history, attempt counts, error notes and practice-derived mastery when saving",
  guideTitle:"Start where you are.", guideText:"A result is a clue, not a label. Let your tutor know what feels difficult so the next practice can help.", guideTipTitle:"Good to know", guideTip:"Classroom practice updates this profile automatically. Save your profile after making manual changes.", guideLink:"Return to your study room ↗", retry:"Try again", reset:"Restore initial profile", discard:"Discard changes", save:"Save profile", loading:"Loading profile…", dirty:"You have unsaved changes", noStudents:"No learning profiles are available. Ask the operator of this service to enable one.", loaded:"Profile loaded · Version {version}", initial:" · Initial demo content, not saved yet", meta:"Profile {id} · Version {version}", gradeEmpty:"Study stage not set", noExams:"No assessments yet. Add a result whenever it helps.", examName:"Assessment name", examPlaceholder:"e.g. Midterm", date:"Date", score:"Score (required)", full:"Maximum (required)", subjectRequired:"Subject (required)", weakConcepts:"Topics to revisit", weakPlaceholder:"e.g. Derivatives, vectors", removeExam:"Remove this assessment", remove:"Remove", manual:"Manual estimate", exerciseSource:"Practice: {correct}/{attempts} correct", examSource:"Inferred from assessment gaps", clearing:"Estimate clears when saved", manualUnsaved:"Manual estimate (unsaved)", noConcepts:"No topics yet. Try a practice question or add something you want to study.", masteryLabel:"Estimated mastery of {name}", sliderTitle:"Use arrow keys to adjust estimated mastery", latestError:"Recent error: ", clear:"Clear", clearTitle:"Clear the manual estimate; a relevant assessment estimate may still apply", undo:"Undo", correct:"Correct", tryAgain:"Try again", noHistory:"No practice yet. Your classroom answers will appear here.", badExam:"Enter a subject, score and maximum for every assessment.", saving:"Saving your profile…", saved:"Saved · Version {version} · Your session will update", conflict:"Your profile changed while you were editing. Select “Discard changes” to load the latest version, then edit again.", saveFailed:"Could not save: {message}", loadFailed:"Could not load your profile: {message}", resetConfirm:"Restore the initial profile for “{name}”? Saved results, mastery estimates and practice history will be deleted.", resetDone:"Initial profile restored", resetFailed:"Could not restore: {message}", switchConfirm:"You have unsaved changes. Continuing will discard them.", refreshed:"Classroom practice updated · Version {version}", navLabel:"Main navigation"
};
const copy = english ? en : {...zh, ...(edition === "primary" ? {
  title:"学习小档案，从这里开始。", eyebrow:"我的学习小档案", intro:"让老师知道你读几年级、哪些地方还想练一练。遇到不会填的，可以请爸爸妈妈帮忙。", sideTitle:"一点点，也会变成大进步。", sideText:"不着急，我们从你会的地方一起出发。", nameLabel:"老师怎么称呼你", gradePlaceholder:"如 小学四年级", basicKicker:"让老师认识你", conceptPlaceholder:"如 分数加减法", weakPlaceholder:"如 分数加减法、面积", guideTitle:"不会也没关系。", guideText:"告诉老师你哪里卡住了，一起换个办法，再试一次。", guideTip:"可以和家长一起填写。课堂练习后，老师会自动更新档案；自己改动后记得保存。"
} : {})};
function t(key, values = {}) { return String(copy[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? "")); }
const LEVEL = {mastered:t("mastered"), partial:t("partial"), weak:t("weak"), unknown:t("unknown")};
const SCHOOL_GRADES = ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"];
const GRADES = english ? SCHOOL_GRADES : edition === "primary" ? SCHOOL_GRADES.slice(0,6) : SCHOOL_GRADES.slice(6);
document.documentElement.lang = english ? "en" : "zh-CN";
document.documentElement.dataset.edition = edition;
document.title = t("profile") + " · Live Agent";
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

function setStatus(text, cls) { const el = $("status"); el.textContent = text; el.className = "status " + (cls || ""); }
function markDirty() {
  dirty = true; $("save").disabled = false; $("discard").disabled = false;
  setStatus(t("dirty"), "dirty");
}
function clean() { dirty = false; $("save").disabled = true; $("discard").disabled = true; }

const api = window.LiveAgentAPI.fetchJson;

function pageLink(path, selectedEdition = edition) {
  const query = new URLSearchParams({edition:selectedEdition});
  if (sid) query.set("student", sid);
  return path + "?" + query.toString();
}
function updateLinks() {
  const paths = {classroom:"/", profile:"/profile", recordings:"/traces"};
  document.querySelectorAll("[data-link]").forEach(el => { el.href = pageLink(paths[el.dataset.link]); });
  $("back").href = pageLink("/");
}
function setReady(ready) {
  document.querySelectorAll("[data-profile-control]").forEach(el => { el.disabled = !ready; });
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
  const {students} = await api("/api/students");
  if (!students.length) { setStatus(t("noStudents"), "err"); return; }
  if (!students.some(s => s.id === sid)) sid = students[0].id;
  $("student").innerHTML = students.map(s =>
    `<option value="${esc(s.id)}"${s.id === sid ? " selected" : ""}>${esc(s.name || s.id)}${s.grade ? " · " + esc(s.grade) : ""} (${esc(s.id)})</option>`).join("");
  await load();
}

async function load() {
  server = await api(`/api/students/${encodeURIComponent(sid)}`);
  exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
  edits = new Map(); $("clearHist").checked = false;
  history.replaceState(null, "", pageLink("/profile"));
  updateLinks();
  render(); clean(); setReady(true);
  $("retryLoad").hidden = true;
  setStatus(t("loaded", {version:server.version}) + (server.saved ? "" : t("initial")), "ok");
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
  const row = ev.target.closest(".exam"), k = ev.target.dataset.k;
  if (!row || !k) return;
  const e = exams[+row.dataset.i];
  e[k] = (k === "score" || k === "full") ? (ev.target.value === "" ? "" : +ev.target.value) : ev.target.value;
  if (k === "score" || k === "full") row.querySelector(".pct").textContent = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
  markDirty();
});
$("exams").addEventListener("click", (ev) => {
  const i = ev.target.dataset.del;
  if (i === undefined) return;
  exams.splice(+i, 1); renderExams(); markDirty();
});
$("addExam").onclick = () => {
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
  if (ev.target.type !== "range") return;
  const name = ev.target.closest(".concept").dataset.name;
  edits.set(name, {...(edits.get(name) || {}), mastery: +ev.target.value / 100, delete: false});
  const row = ev.target.closest(".concept");
  row.querySelector(".v").textContent = ev.target.value + "%";
  markDirty();
});
$("concepts").addEventListener("change", (ev) => { if (ev.target.type === "range") renderConcepts(); });
$("concepts").addEventListener("click", (ev) => {
  const act = ev.target.dataset.act; if (!act) return;
  const name = ev.target.closest(".concept").dataset.name, e = edits.get(name) || {};
  if (act === "clear") edits.set(name, {...e, mastery: null, delete: false});
  if (act === "delete") edits.set(name, {...e, delete: true});
  if (act === "undo") { const {delete: _, ...rest} = e; Object.keys(rest).length ? edits.set(name, rest) : edits.delete(name); }
  renderConcepts(); markDirty();
});
$("addConcept").onclick = () => {
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
  $("save").disabled = true; setStatus(t("saving"));
  try {
    server = await api(`/api/students/${encodeURIComponent(sid)}`, {method: "PUT", body: JSON.stringify(body)});
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false; render(); clean();
    setStatus(t("saved", {version:server.version}), "ok");
  } catch (err) {
    $("save").disabled = false;
    if (err.status === 409) setStatus(t("conflict"), "err");
    else setStatus(t("saveFailed", {message:err.message}), "err");
  }
};
$("discard").onclick = () => load().catch(e => setStatus(t("loadFailed", {message:e.message}), "err"));
$("reset").onclick = async () => {
  if (!confirm(t("resetConfirm", {name:server.name || sid}))) return;
  try { server = await api(`/api/students/${encodeURIComponent(sid)}/reset`, {method: "POST", body: JSON.stringify({version: server.version})}); await load(); setStatus(t("resetDone"), "ok"); }
  catch (err) { setStatus(t("resetFailed", {message:err.message}), "err"); }
};
$("student").onchange = async () => {
  if (dirty && !confirm(t("switchConfirm"))) { $("student").value = sid; return; }
  sid = $("student").value; await load();
};
window.addEventListener("beforeunload", (ev) => { if (dirty) { ev.preventDefault(); ev.returnValue = ""; } });

// while nothing is being edited, follow changes made by a running lesson (graded exercises)
setInterval(async () => {
  if (dirty || !server || document.hidden) return;
  const refreshSid = sid, refreshProfile = server;
  try {
    const now = await api(`/api/students/${encodeURIComponent(refreshSid)}`);
    // Fetching can overlap edits, saves, student changes or another refresh.
    if (dirty || sid !== refreshSid || server !== refreshProfile || document.hidden) return;
    if (now.version !== server.version) { server = now; exams = now.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
      render(); setStatus(t("refreshed", {version:now.version}), "ok"); }
  } catch (_) { /* offline for a moment: try again next time */ }
}, 5000);

function loadError(e) { setStatus(t("loadFailed", {message:e.message}), "err"); $("retryLoad").hidden = false; }
$("retryLoad").onclick = () => loadList().catch(loadError);
loadList().catch(loadError);

===== FILE: frontend/public/traces.html =====
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><title>课堂回顾 · Live Agent</title><link rel="stylesheet" href="/assets/profile.css"><link rel="stylesheet" href="/assets/traces.css"></head>
<body class="recordings-page">
<a class="skip-link" href="#main" data-copy="skip">跳到主要内容</a>
<aside class="sidebar">
  <a class="brand" href="/" data-link="classroom"><span class="brand-mark" aria-hidden="true">L<span>·</span>A</span><span>Live Agent<small data-copy="brandSub">陪你把知识学明白</small></span></a>
  <div class="nav-label" data-copy="space">我的学习空间</div>
  <nav aria-label="主导航" id="mainNav"><a data-link="classroom" href="/"><span aria-hidden="true">↗</span><span data-copy="classroom">学习课堂</span></a><a data-link="profile" href="/profile"><span aria-hidden="true">◎</span><span data-copy="profile">学习档案</span></a><a class="active" aria-current="page" data-link="recordings" href="/traces"><span aria-hidden="true">▷</span><span data-copy="recordings">课堂回顾</span></a></nav>
  <div class="sidebar-note"><span class="note-orbit" aria-hidden="true">✳</span><strong data-copy="sideTitle">学过的，还可以再看看。</strong><p data-copy="sideText">回到当时的讲解，把一个小疑问再想明白。</p></div>
  <label class="edition-control"><span data-copy="editionLabel">学习阶段</span><select id="editionSelect" aria-label="学习阶段"><option value="primary">小学 · 中文</option><option value="secondary">中学 · 中文</option><option value="university">University & adult · English</option></select></label><div class="sidebar-footer" data-copy="privateSpace">一对一学习 · 本地演示</div>
</aside>
<div class="workspace">
  <header class="topbar"><div><span data-copy="space">我的学习空间</span><span class="crumb-divider">/</span><strong data-copy="recordings">课堂回顾</strong></div><a class="back-link" data-link="classroom" href="/" data-copy="back">返回课堂 ↗</a></header>
  <main id="main" tabindex="-1">
    <div class="page-heading"><div><span class="eyebrow" data-copy="eyebrow">LEARNING, WORTH REVISITING</span><h1 data-copy="title">好好学过，慢慢回顾。</h1><p data-copy="intro">重看一段讲解，整理一次思路。这里收好已保存的课堂视频和会话记录。</p></div><span class="edition-pill" id="editionBadge">中学版</span></div>
    <div class="library-toolbar"><div><h2 data-copy="savedSessions">已保存的课堂</h2><p id="sessionCount" aria-live="polite"></p></div><button id="refresh" class="secondary-button" data-copy="refresh">↻ 刷新列表</button></div>
    <p class="scope-note" data-copy="scope">这里显示当前服务保存的会话，暂不按学生分组。</p>
    <div class="load-message" id="status" role="status" aria-live="polite">正在寻找已保存的课堂…</div>
    <div class="recording-grid" id="sessions"></div>
    <section class="empty-library" id="emptyState" hidden><div class="empty-illustration" aria-hidden="true"><span>▷</span></div><span class="eyebrow" data-copy="emptyEyebrow">YOUR NEXT CHAPTER</span><h2 data-copy="emptyTitle">第一节课，还在前面等你。</h2><p data-copy="emptyText">现在还没有保存的会话。先去课堂聊一个想学的问题；开启录制的会话结束后会出现在这里。</p><a class="button-link" data-link="classroom" href="/" data-copy="emptyLink">开始学习 ↗</a></section>
    <div class="library-note"><span aria-hidden="true">◇</span><p data-copy="libraryNote">回放是实际保存的课堂内容，不代表知识点已经掌握。可以把看完后仍有疑问的地方，带回下一次课堂。</p></div>
  </main>
</div>
<script src="/assets/api.js"></script><script src="/assets/traces.js"></script>
</body>
</html>

===== FILE: frontend/public/assets/traces.js =====
const params = new URLSearchParams(location.search), editions = ["primary", "secondary", "university"];
let preferredEdition = "secondary";
try { preferredEdition = localStorage.getItem("liveAgent.edition") || preferredEdition; } catch (_) {}
const requestedEdition = params.get("edition");
const edition = editions.includes(requestedEdition) ? requestedEdition : editions.includes(preferredEdition) ? preferredEdition : "secondary";
const student = params.get("student") || "demo", english = edition === "university";
try { localStorage.setItem("liveAgent.edition", edition); } catch (_) {}
const copy = english ? {
  skip:"Skip to content", brandSub:"A little clearer, every day", space:"My learning space", classroom:"Study room", profile:"Learning profile", recordings:"Session library", sideTitle:"Keep a good explanation close.", sideText:"Return to an idea and see what makes more sense the second time.", editionLabel:"Learning edition", privateSpace:"One-to-one learning · Local demo", back:"Back to study room ↗", eyebrow:"LEARNING, WORTH REVISITING", title:"A little reflection goes a long way.", intro:"Replay an explanation and collect your thoughts. Find the videos and notes actually saved from your sessions.", savedSessions:"Saved sessions", refresh:"↻ Refresh library", scope:"This library shows sessions saved by this service. It is not filtered by learner.", loading:"Looking for saved sessions…", emptyEyebrow:"YOUR NEXT CHAPTER", emptyTitle:"Your first session is still ahead.", emptyText:"There are no saved sessions yet. Bring a question to the study room. Sessions recorded by the service will appear here after they finish.", emptyLink:"Go to your study room ↗", libraryNote:"Recordings show what was saved, not proof of topic mastery. Bring any remaining questions to your next session.", count:"{count} saved sessions", session:"Study session", noVideo:"No presented video was saved. The session record is still available below.", download:"Download recording", part:"Recording part {part}", details:"Session files", trace:"Download session record", generatedNote:"Generated material may include content that was never shown in the session.", generated:"Generated material", generatedPart:"Generated material · Part {part}", error:"We couldn’t load the library. Try refreshing the list.", navLabel:"Main navigation", videoLabel:"Recorded session from {date}"
} : {
  skip:"跳到主要内容", brandSub:"陪你把知识学明白", space:"我的学习空间", classroom:"学习课堂", profile:"学习档案", recordings:"课堂回顾", sideTitle:"学过的，还可以再看看。", sideText:"回到当时的讲解，把一个小疑问再想明白。", editionLabel:"学习阶段", privateSpace:"一对一学习 · 本地演示", back:"返回课堂 ↗", eyebrow:"LEARNING, WORTH REVISITING", title:edition === "primary" ? "再看一遍，又懂一点。" : "好好学过，慢慢回顾。", intro:edition === "primary" ? "想再听一次老师的讲解？保存好的课堂可以在这里重新看看。" : "重看一段讲解，整理一次思路。这里收好已保存的课堂视频和会话记录。", savedSessions:"已保存的课堂", refresh:"↻ 刷新列表", scope:"这里显示当前服务保存的会话，暂不按学生分组。", loading:"正在寻找已保存的课堂…", emptyEyebrow:"YOUR NEXT CHAPTER", emptyTitle:edition === "primary" ? "第一节课，还在等你呢。" : "第一节课，还在前面等你。", emptyText:"现在还没有保存的会话。先去课堂聊一个想学的问题；开启录制的会话结束后会出现在这里。", emptyLink:"开始学习 ↗", libraryNote:"回放是实际保存的课堂内容，不代表知识点已经掌握。可以把看完后仍有疑问的地方，带回下一次课堂。", count:"已保存 {count} 段会话", session:"学习课堂", noVideo:"这次会话没有保存已播放的视频，会话记录仍可下载。", download:"下载课堂回放", part:"课堂回放 · 第 {part} 部分", details:"会话文件", trace:"下载会话记录", generatedNote:"生成素材可能包含课堂中没有播放的内容。", generated:"生成素材", generatedPart:"生成素材 · 第 {part} 部分", error:"暂时无法载入课堂记录。请刷新列表重试。", navLabel:"主导航", videoLabel:"{date}的课堂录像"
};
function t(key, values = {}) { return String(copy[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? "")); }
function pageLink(path, selectedEdition = edition) { return path + "?" + new URLSearchParams({edition:selectedEdition, student}).toString(); }
document.documentElement.lang = english ? "en" : "zh-CN";
document.documentElement.dataset.edition = edition;
document.title = t("recordings") + " · Live Agent";
document.querySelectorAll("[data-copy]").forEach(el => { el.textContent = t(el.dataset.copy); });
const paths = {classroom:"/", profile:"/profile", recordings:"/traces"};
document.querySelectorAll("[data-link]").forEach(el => { el.href = pageLink(paths[el.dataset.link]); });
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
  content.append(details); card.append(content); return card;
}
async function loadTraces() {
  const status = document.getElementById("status"), refresh = document.getElementById("refresh");
  refresh.disabled = true; status.hidden = false; status.className = "load-message"; status.textContent = t("loading");
  try {
    const {sessions} = await window.LiveAgentAPI.fetchJson("/api/traces");
    const body = document.getElementById("sessions"); body.replaceChildren(...sessions.map(recordingCard));
    document.getElementById("sessionCount").textContent = t("count", {count:sessions.length});
    document.getElementById("emptyState").hidden = sessions.length > 0;
    status.hidden = true;
  } catch (_) { status.textContent = t("error"); status.className = "load-message error"; }
  finally { refresh.disabled = false; }
}
document.getElementById("refresh").onclick = loadTraces;
loadTraces();

===== FILE: .cache/student-review/contracts.txt =====

FILE live_agent/backend/app.py
86:                     if isinstance(entry.get("source"), str):
87:                         item["source"] = entry["source"]
88:                     topics.append(item)
89:         return {"topics": topics}
90: 
91:     @app.on_event("startup")
92:     async def _startup() -> None:
133:             if app.state.session_lock.locked():
134:                 await ws.send_text(json.dumps({"type": "error", "error": "generator busy (one live session at a time)"}))
135:                 await ws.close()
136:                 return
137:             await app.state.session_lock.acquire()
138:         orch = None
139:         inputs: asyncio.Queue = asyncio.Queue()
140:         worker = None
141:         try:
142:             from live_agent.llm import OpenAICompatLLM, make_chat_llm
143: 
144:             manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
145:             if args.llm_url == "scripted":  # CPU-only demo: rule-based responder, no model server
146:                 from live_agent.llm import RuleResponder
147: 
148:                 llm = RuleResponder(manifest)
149:             else:
150:                 llm = make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args))
151:             if args.dev_allow_uncalibrated:
152:                 manifest.min_status = Status.DOCUMENTED
153:             ledger = StateLedger.from_config(cfg_dir / "canon.json")
154:             intents = canon.get("intents", {})  # persona filler gestures (idle / listen / while speaking)
155:             director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
156:                                 persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode),
157:                                 idle_intent=intents.get("idle", "idle_read"),
158:                                 listen_intent=intents.get("listen", "listen"),
159:                                 speak_intent=intents.get("speak"),
160:                                 responder_style=canon.get("responder_style", ""),
161:                                 responder_examples=canon.get("responder_examples"))
162:             director.present_intent = intents.get("present")  # gesture toward the page's board
163:             generator = SessionView(app.state.shared_gen) if shared else make_generator(args)
164:             sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
165:                                                   lambda_prior_s=args.lambda_prior))
166:             judge = speech = None
167:             if args.vlm_url == "mock":  # demo only: simulated verdicts (p=0.8), never a measurement
168:                 from live_agent.qc.judge import MockJudge
169: 
170:                 # the placeholder video always "performs" the locked action, so by default the simulated
171:                 # judge agrees (p=1); a lower --mock-judge-p demonstrates the repair loop
172:                 judge = MockJudge(p_default=args.mock_judge_p)
173:             elif args.vlm_url:
174:                 from live_agent.qc.judge import VLMJudge
175: 
176:                 hosted = not args.vlm_url.startswith(("http://127.", "http://localhost"))
177:                 judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model,
178:                                                  api_key=llm_api_key(args) if hosted else "EMPTY", timeout_s=60.0),
179:                                  k=8, contrast=True)
180:             asr = None
181:             if args.asr_url.startswith("wss://"):  # hosted realtime audio model: user speech only (no per-request
182:                 from live_agent.asr import HostedRealtimeASR  # speech QC: an API call per 5 s line, ~6 s each)
183: 
184:                 asr = HostedRealtimeASR(args.asr_url, args.asr_model, llm_api_key(args))
185:             elif args.asr_url:
186:                 from live_agent.asr import OpenAIASR
187:                 from live_agent.qc.judge import SpeechCheck
188: 
189:                 asr = OpenAIASR(args.asr_url, args.asr_model)
190:                 speech = SpeechCheck(asr.transcribe_sync)
191:             from live_agent.qc.judge import ForwardCorrector
192: 
193:             log_dir = Path(args.log_dir)
194:             log_dir.mkdir(parents=True, exist_ok=True)
195:             orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=ForwardCorrector(None if args.llm_url == "scripted" else llm),
196:                                 speech_check=speech, memory=make_memory(args, hello, session_id, mode),
197:                                 log=EventLog(log_dir / f"{session_id}.jsonl"),
198:                                 cfg=OrchestratorConfig(session_id=session_id, scope=mode,

FILE live_agent/backend/transport.py
1: """WebSocket media encoding, presentation acknowledgements and panel events.
2: 
3: The binary protocol is preserved across the frontend proxy; the browser's audio
4: output clock is mapped to server monotonic time using ping samples.
5: """
6: 
7: from __future__ import annotations
8: 
9: import asyncio
10: import io
11: from fractions import Fraction
12: import json
13: import logging
14: from pathlib import Path
15: 
16: import numpy as np
17: from fastapi import WebSocket
18: 
19: from live_agent.orchestrator import Orchestrator
20: from live_agent.types import BlockScript, Chunk, now
21: 
22: log = logging.getLogger("live_agent.backend.transport")
23: 
24: 
25: def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
26:     from PIL import Image
27: 
28:     buf = io.BytesIO()
29:     Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
30:     return buf.getvalue()
31: 
32: 
33: def encode_h264(frames: np.ndarray, crf: int = 26) -> tuple[bytes, list[int]]:
34:     """One self-contained H.264 segment per chunk (baseline, IDR first, no B-frames: decodable on its own,
35:     so a barge-in can drop any chunk). Returns the Annex-B bytes and the size of each frame's access unit.
36:     About 5x smaller than per-frame JPEG q80 at 480x864 [measured locally], which the remote bridge needs."""
37:     import av
38: 
39:     n, h, w = frames.shape[:3]
40:     enc = av.CodecContext.create("libx264", "w")
41:     enc.width, enc.height, enc.pix_fmt = w, h, "yuv420p"
42:     enc.time_base = Fraction(1, 24)
43:     enc.framerate = Fraction(24, 1)
44:     enc.options = {"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline", "crf": str(crf),
45:                    "g": str(max(n, 1) + 1), "bf": "0", "threads": "4"}
46:     out, sizes = [], []
47: 
48:     def keep(packets):
49:         for pkt in packets:
50:             b = bytes(pkt)
51:             out.append(b)
52:             sizes.append(len(b))
53: 
54:     for i, f in enumerate(frames):
55:         vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24").reformat(format="yuv420p")
56:         vf.pts = i
57:         keep(enc.encode(vf))
58:     keep(enc.encode(None))
59:     return b"".join(out), sizes
60: 
61: 
62: def to_pcm16(audio: np.ndarray | None, n_samples: int) -> bytes:
63:     if audio is None or len(audio) == 0:
64:         return np.zeros(n_samples, dtype=np.int16).tobytes()
65:     a = audio.mean(axis=1) if audio.ndim == 2 else audio
66:     return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()
67: 
68: 
69: PANEL_EVENTS = {"lock", "verdict", "repair", "completion_claim", "refusal", "capacity_skip", "narration_guard",
70:                 "playback_stop", "speech_onset", "utterance_end", "audit", "error", "request_done", "continuity", "lesson", "attention"}
71: PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
72:                 "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
73:                 "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
74:                 "decision", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
75:                 "audibility", "revision", "speaker", "uid", "counts", "expected", "wrong", "target", "gave_up", "anchor_removed", "stage",
76:                 "title", "sections", "section", "lines", "points", "board", "seconds",
77:                 "attempt", "labels",
78:                 "point", "judgements", "state", "stable", "nudge",
79:                 "plan", "note", "adaptive", "depth", "exercise", "concept", "correct", "skipped", "misconception",
80:                 "mastery", "profile", "changed", "options", "question", "option_texts", "topic")
81: 
82: 
83: def panel_event(ev, t0: float) -> dict | None:
84:     """Compact, display-only form of a timeline event (the full log stays on disk)."""
85:     if ev.type.value not in PANEL_EVENTS:
86:         return None
87:     if ev.type.value == "error" and ev.data.get("where") in ("event_loop_stack",):
88:         return None
89:     data = {k: ev.data[k] for k in PANEL_FIELDS if k in ev.data}
90:     if isinstance(data.get("rationale"), str):
91:         data["rationale"] = data["rationale"][:160]
92:     return {"type": "event", "event": ev.type.value, "t": round(ev.t - t0, 2), "request": ev.request_index,
93:             "data": data}
94: 
95: 
96: class WSTransport:
97:     """Orchestrator transport over one WebSocket connection.
98: 
99:     Presentation times: the client reports, for each chunk, when its audio starts / ends at the
100:     audio *output* (AudioContext.getOutputTimestamp -> performance clock, ``tp`` in ms). The

FILE live_agent/orchestrator.py
1117:                       options=ex.options, kind=ex.kind)
1118: 
1119:     def _exercise_changed(self) -> None:
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


FILE live_agent/student.py
270:     def mark_taught(self, concepts: list[str], subject: str = "") -> None:
271:         for name in concepts:
272:             if str(name).strip():
273:                 self._concept(name, subject).taught += 1
274: 
275:     def purge(self, term: str) -> int:
276:         """Erasure: drop concepts, notes, exam entries and history rows that mention ``term``."""
277:         n = 0
278:         for name in [k for k in self.concepts if term in k]:
279:             del self.concepts[name]
280:             n += 1
281:         for c in self.concepts.values():
282:             keep = [x for x in c.notes if term not in x]
283:             n += len(c.notes) - len(keep)
284:             c.notes = keep
285:         keep_h = [h for h in self.history if term not in json.dumps(h, ensure_ascii=False)]
286:         n += len(self.history) - len(keep_h)
287:         self.history = keep_h
288:         keep_e = [e for e in self.exams if term not in e.name and term not in e.subject]
289:         n += len(self.exams) - len(keep_e)
290:         self.exams = keep_e
291:         for e in self.exams:
292:             if term in "".join(e.weak):
293:                 e.weak = [w for w in e.weak if term not in w]
294:                 n += 1
295:         for c in self.concepts.values():
296:             if term in c.subject:
297:                 c.subject, n = "", n + 1
298:         if term and term in self.name:
299:             self.name, n = "", n + 1
300:         if term and term in self.grade:
301:             self.grade, n = "", n + 1
302:         keep_e = [e for e in self.exams if term not in json.dumps(asdict(e), ensure_ascii=False)]
303:         n += len(self.exams) - len(keep_e)
304:         self.exams = keep_e
305:         return n
306: 
307:     # ------------------------------------------------------------ prompts and page
308:     def _mastery_text(self, name: str) -> str:
309:         m, c = self.mastery(name), self.concepts.get(name)
310:         s = f"{name}：{LEVELS_CN[self.level(name)]}"
311:         if m is not None:
312:             s += f"（估计掌握度 {m:.2f}" + ("，仅据考试失分" if self.source(name) == "exam" else "")
313:             if c is not None and c.attempts:
314:                 s += f"，练习 {c.correct}/{c.attempts} 对"
315:             s += "）"
316:         if c is not None and c.notes:
317:             s += f"，最近的错误：{c.notes[-1]}"
318:         return s
319: 
320:     def summary(self, limit: int = 16) -> str:
321:         """Planning context: grade, recent exams, understanding per concept (weakest first)."""
322:         if not (self.grade or self.exams or self.concepts):
323:             return "无（新学生，没有档案）"
324:         parts = []
325:         # minimal: what the plan needs (grade, recent results, understanding); no dates; the name only as a form of
326:         # address
327:         if self.name or self.grade:
328:             parts.append(f"学生：{self.name or '同学'}，{self.grade or '年级未知'}")
329:         for e in sorted(self.exams, key=lambda e: e.date)[-4:]:
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
22: EXERCISE_PROMPT = """你是中学老师「{name}」。请给学生出一道关于「{topic}」的练习题。
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
                    for width in (1440, 390):
                        page.set_viewport_size({'width': width, 'height': 1000 if width == 1440 else 844})
                        page.goto(origin + '/?edition=' + edition)
                        page.wait_for_function("!document.getElementById('connect').disabled")
                        page.wait_for_selector('.course-card')
                        assert page.locator('html').get_attribute('lang') == ('en' if edition == 'university' else 'zh-CN')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (edition, width, 'horizontal overflow')
                        assert page.locator('#diagnostics').get_attribute('open') is None
                        assert page.locator('#profileDisclaimer').inner_text()
                        assert page.locator('#runtimeNotice').is_visible()
                        page.locator('.course-card').first.click()
                        assert page.locator('#lessonTopic').input_value()
                        assert not page.locator('#startLesson').is_disabled()
                        page.locator('#helpOpen').evaluate('(button)=>button.click()')
                        assert page.locator('#helpDialog').is_visible()
                        page.keyboard.press('Escape')
                        assert not page.locator('#helpDialog').is_visible()
                        if args.shots:
                            page.evaluate('scrollTo(0,0)')
                            page.screenshot(path=str(args.shots / f'classroom-{edition}-{width}.png'), full_page=True)
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
                assert page.locator('html').get_attribute('lang') == 'en'
                assert 'edition=university' in page.locator('#profLink').get_attribute('href')
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#edition').input_value() == 'university'
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'", timeout=15000)
                assert page.locator('#talk').is_disabled()
                assert page.locator('#startLesson').is_disabled()
                assert 'Preview mode' in page.locator('#runtimeNotice').inner_text()
                page.locator('#text').fill('请讲慢一点')
                page.locator('#text').press('Enter')
                assert page.locator('#chat .msg.user').last.inner_text() == '请讲慢一点'
                page.wait_for_function('queue.length > 0', timeout=15000)
                dimensions = page.locator('#screen').bounding_box()
                ratio = page.evaluate('canvas.width/canvas.height')
                assert abs(dimensions['width']/dimensions['height'] - ratio) < .01
                page.locator('#disconnect').click()
                page.wait_for_function("sessionState === 'disconnected'")
                results.append({'session': 'real CPU connect, text, media and disconnect passed'})
                # Synthetic events are deliberate rendering fixtures, not a generated teaching result.
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',concept:'Fixture',question:'Which value?',options:['A','B'],option_texts:['A. One','B. Two']}}}));window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_graded',correct:false}}}));window.dispatchEvent(new CustomEvent('live-agent:state',{detail:{exercise:null}}));}""")
                assert page.locator('#exerciseCard').is_visible()
                assert 'A. One' in page.locator('#exerciseQuestion').inner_text()
                assert 'incorrect' in page.locator('#exerciseFeedback').inner_text()
                results.append({'exercise fixture': 'full question, choices and persistent feedback passed'})
                # Abort pre-session profile loads on connecting; public status must be authoritative.
                page.route('**/api/students/learner', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps({'id':'learner','name':'Delayed private name','grade':'初一','version':1,'exams':[],'concepts':[]})))
                page.locator('#diagnostics').evaluate('(node)=>node.open=true')
                page.locator('#mode').select_option('public')
                assert page.locator('#notes').input_value() == ''
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'", timeout=15000)
                assert 'Delayed private name' not in page.locator('#prof').inner_text()
                assert page.evaluate('profile === null')
                page.locator('#disconnect').click()
                results.append({'privacy': 'public classroom has no learner profile or private notes'})
                assert not errors, errors
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

function editor({edition, storedEdition} = {}) {
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
  const document = {hidden: false, getElementById: element,
    documentElement: {dataset: {}}, querySelectorAll: () => []};
  const context = vm.createContext({document,
    window: {addEventListener() {}, LiveAgentAPI: {fetchJson(path, opts) {
      // Leave the initial student-list request pending; tests supply a loaded editor.
      if (path === "/api/students") return new Promise(() => {});
      return new Promise((resolve, reject) => { requests.push({path, opts, resolve, reject}); });
    }}},
    location: {search: "?student=demo" + (edition ? "&edition=" + edition : "")}, URLSearchParams,
    localStorage: {getItem: () => storedEdition, setItem() {}},
    history: {replaceState(_state, _unused, url) { historyUrls.push(url); }}, confirm: () => true,
    setInterval(callback) { poll = callback; },
  });
  function run(code) { return vm.runInContext(code, context); }
  vm.runInContext(source, context);
  run(`server = ${JSON.stringify(profile(1))}; exams = server.exams.map(e => ({...e, weak: ""})); render(); clean();`);
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

===== FILE: frontend/tests/traces.test.mjs =====
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/traces.js", import.meta.url), "utf8");
class Element {
  constructor(tag = "div") { this.tagName = tag; this.children = []; this.hidden = false; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
}
function library({edition = "secondary", storedEdition} = {}) {
  const elements = new Map(), requests = [];
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const document = {documentElement:{dataset:{}}, getElementById:get, querySelectorAll:()=>[], createElement:tag=>new Element(tag)};
  const context = vm.createContext({document, URLSearchParams, Intl,
    location:{search:`?edition=${edition}&student=demo`},
    localStorage:{getItem:()=>storedEdition, setItem(){}},
    window:{LiveAgentAPI:{fetchJson(path) { return new Promise((resolve,reject)=>requests.push({path,resolve,reject})); }}},
  });
  vm.runInContext(source, context);
  return {get, document, requests, run:code=>vm.runInContext(code,context),
    async respond(sessions) { requests[0].resolve({sessions}); await new Promise(setImmediate); },
  };
}
function descendants(element) { return element.children.flatMap(child => typeof child === "string" ? [] : [child,...descendants(child)]); }
function session(videos = []) { return {id:"sess-test",updated_at:"2026-10-02T08:00:00+00:00",size_bytes:42,trace_url:"/traces/file/sess-test.jsonl",videos}; }

test("empty recording library offers a classroom route without inventing sessions", async () => {
  const page = library({edition:"primary"});
  await page.respond([]);
  assert.equal(page.requests[0].path,"/api/traces");
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
