Independent read-only targeted re-review of the four student6 findings, using inlined current source. Sandbox shell cannot start; no mutations. Number remaining concrete findings as blocking/major/minor with evidence. Focus these repairs and their direct regressions; do not broaden to unrelated roadmap features, model quality or research claims. PROJECT.md is inlined. No training, deployment, broadcast, GPU, real teaching/ASR, university curriculum or efficacy qualification is claimed.

Current activity ownership contract: optional request_id is captured on the lesson/exercise job, propagated through outline/section/planned/failures/checks and exercise generated/open/closed/graded/timeout states. A resulting Exercise retains its creating request ID, including snapshots; generated model JSON cannot forge this ownership. An answer's utterance_end retains its own request ID. Legacy/manual null ownership is allowed when the product considers it current.

The product keeps currentActivityId through a lesson's preparation, question and feedback, retiring it on newer activity/text submission or scope reset. Its acceptsActivity guard filters status events, exercise snapshots and answer chips; old activity events cannot clear a newer ticket or restore a retired question. Ordinary text/voice while a current question is open preserves its creating owner so answer feedback/closure remain visible. Lesson/practice buttons wait until the open question closes, matching the existing single-exercise constraint. Accepted pending activity remains tracked while preparing; applied:false and new successful input cancel it. Failure clears its ticket; outline_failed is terminal. No network/AV scheduling change from the UI guards.

Padded catalogue titles are normalized to the trimmed canonical title used by backend validation, and comparisons preserve grade/subject context; blank title/subject entries are excluded. A mixed catalogue/browser packet fixture covers both lesson and practice. The actual WebSocket regression holds B's responder, sends C text plus ping without speech_start, observes pong before releasing B, then verifies B applied:false, C applied:true and no B lesson activity/generation.

Measured locally: 85 affected Python checks pass, including new ownership and real text-only supersession regressions. Combined frontend currently 94 pass. Browser pass: nine classroom edition/viewport cases plus ten behavior scenarios; delayed old decision/activity, newer-ticket protection, current-answer feedback, outline failure, public/profile privacy, and padded chapter packets pass without errors/overflow. Explicit synthetic fixtures qualify UI/packet behavior after a real isolated CPU connection/text/media test, not model teaching. Final full Python is running; previous full CPU 403 passed and one GPU-only skip before ownership plumbing. The underlying frontend/backend split and earlier scope/write/media repairs were independently reviewed already.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/PROJECT.md =====
# Live Agent — Project Specification (single source of truth)

Status: **v1.0** (2026-09-25). Updated after the research phase and all four Codex checkpoints (CP4 in rounds). v0.1 was the provisional
version; see `docs/codex_reviews.md` and the git history. **Precedence:** `goal.md` (the owner's brief) sets the
requirements. This file records our current interpretation of them and tracks
their status. If the two disagree, raise the conflict in `docs/decision_log.md`
for resolution; do not silently prefer either one. `CLAUDE.md`, `AGENTS.md` and
`AGENT.md` point here and must not restate the spec.

## Purpose

Research, then demo, a **real-time, personalized live agent**: a digital persona
that talks with users through live generated video (and speech where supported),
follows instructions during the interaction, reasons about it, and keeps useful
long-term memory across sessions.

Central research question: *How can we combine real-time video generation with
reasoning, instruction following, and persistent memory to create a coherent,
controllable, personalized live agent?*

Working hypothesis (to be tested, not asserted): real-time video generation
alone is insufficient for reliable, stateful agent behavior.

## Current phase and scope

- **Phase 1 (complete): research and proposal.** Deliverables are listed below.
- **Phase 2 (current, owner-authorised 2026-09-26, D-019): implementation** of the A2 system in
  `live_agent/`, the TaoMate-H3 runtime integration, serving and the evaluation harness. The owner-requested
  frontend/backend split (2026-10-02, D-045) puts browser assets and their independent server in `frontend/`,
  with the API and streaming backend in `live_agent/backend/`. The owner-requested student frontend
  (2026-10-02, D-046) adds primary-school and secondary-school interface configurations in Chinese and
  a university/adult interface configuration in English, using the actual school-topic catalogue,
  learner profiles and lesson/exercise transport. Teaching remains Chinese/Mandarin; university/adult
  curriculum coverage and English teaching are not established. Research references, current limits
  and CPU verification are in `docs/student_frontend.md`; formal independent review is pending.
  Status and how to run it: `docs/implementation.md`; generator measurements: `docs/m0_measurements.md`. Still no
  foundation-model training, paid deployments, public broadcasts, or unrelated repository changes.
- Initial use cases: **personalized 1:1 interaction** and **livestreaming**.
  We target one focused demo scenario (defined in the proposal), not a
  general-purpose assistant.
- Preferred video backbone: **LingBot-World 2.0 in vLLM-Omni**
  (<https://github.com/vllm-project/vllm-omni>). It may not be silently
  replaced. Any feasibility gap and any alternative must be justified in
  `docs/decision_log.md`.
- Reference experience: <https://www.twitch.tv/sylar_nv> (owner-provided, not
  verified: built by a friend, "based purely on MiniMax H3"). It is a qualitative
  reference unless a fair quantitative comparison is possible.

## Intended capabilities

1. Follow instructions during a live interaction, including corrections,
   interruptions, and changing goals.
2. Remember relevant user preferences, facts, and prior interactions across
   sessions, with correction, deletion, and provenance.
3. Keep the persona and its visual, conversational, and behavioral state
   consistent.
4. Turn decisions into controls that the generator can actually execute, and
   check that the output complies.
5. Stay responsive while reasoning, retrieving memories, and streaming output.

## Requirements, assumptions, open questions

| ID | Item | Status |
|----|------|--------|
| R1 | Produce the deliverables listed below | Confirmed (goal.md §8) |
| R2 | Mandatory GPT-6 Sol review through Codex at 4 checkpoints, with an auditable log | Confirmed (goal.md §7) |
| R3 | Label every number as cited / measured locally / estimate / proposed target | Confirmed (goal.md §6) |
| R4 | Keep private user memory separate from public livestream content; never store generated or inferred events as confirmed user facts | Confirmed (goal.md §5) |
| A1 | Hardware *inventory*: 8× NVIDIA L20X (≈140 GB each), shared and scheduled through `gpu` (canhazgpu). Inventory is not guaranteed capacity: schedulable access, memory per job, and LingBot throughput on L20X are **unverified**. Upstream validated H200/B200 only | Inventory observed 2026-09-25 (`nvidia-smi`); capacity open |
| A2 | The reference agent's implementation ("MiniMax H3") | **Still unverified.** Public evidence is consistent with clip-based H3 generation (24 fps, ~13 s segments) but does not prove it. H3 is an offline joint audio-video clip model (4–15 s) with no streaming mode. The reference agent is qualitative only (`docs/related_work.md` §3) |
| A3 | Speech, audio and lip sync need components outside LingBot-World | **Confirmed (code-read):** no audio in the pipeline. Native LingBot lip, face and audio conditioning is class D. An external TTS plus audio-driven avatar is engineering (D-005) |
| Q1 | Mid-session prompt changes in LingBot-World 2.0? | **Answered (code-read, not yet executed):** the public stepwise WS path registers only `camera` (`registry.py:25-27`). A prompt interaction → `interaction_failed`. Prompt switching exists only on the deprecated tick path (latents only). Extension C1 is needed. M0 runs one real WS test |
| Q2 | Does camera control express character behavior? | **Answered: no.** Camera control is viewpoint only. Character actions are prompt-conditioned (paper, class B) and depend on C1 and E1 calibration (D-012) |
| Q3 | Audience | 1:1 private user first; private test livestream second; no public broadcast this phase (D-001) |
| Q4 | Local "MiniMax H3" copy | Incomplete: 1 of 13 DiT shards, no text encoder. MiniMax H3 Community License excludes some territories. **Not part of the proposed stack** |
| Q5 | Is a simpler pipeline enough? | Carried as baseline A0, with the same LLM, memory and avatar as A2 (D-004, D-009). RQ4 tests this in both directions |
| Q6 | "Real-time" targets | Defined as [target] values in proposal §8, gated by M0 measurement |
| Q7 | Local GPU identity ("L20X": Ada/CC 8.9 per NVML vs H200-like 143,771 MiB/700 W) | **Open.** Resolved in M0 (D-008) |
| Q8 | Permission to use the shared `/data/models` LingBot weights | **Open. Owner to confirm** |

## Current direction (summary; current proposal: `docs/research_proposal_zh.md` v2.11, owner-directed per D-017; `docs/research_proposal.md` v1.0 is the previous LingBot-based version)

- **Base generator (D-017):** TaoMate-H3 (MiniMax H3 + 3-step streaming LoRA). The persona speaks with generated
  audio and video in 5 s requests. LingBot-World is optional (world shot / comparison). TaoMate-LTX is a
  system-level comparison.
- **Architecture:** an online version of Google's long-form agentic suite: layered director, state ledger,
  calibrated capability manifest, deadline-bounded VLM checks with forward-only corrections, and a frozen
  cross-session style bandit.
- **Central research claim:** online agentic director vs open-loop prompting (instruction-level success over
  effective intent chains, false-completion claims). Measured with a wall-clock TVC protocol on a single
  lock → teacher → student → presentation timeline, with just-in-time prompt locking.
- **Memory:** typed by provenance and separated by scope (private/public/canon). Deletion cascades to derived
  artifacts.
- **Phase 2 status:** M0 done (short-run TaoMate-H3 generator throughput is real time at 480p on 4+2 local Hopper GPUs, D-021). The next
  gates are M1 qualification, E1 calibration (needs human labels) and the E2 pilot (needs blinded adjudication).

## Requirement → deliverable checklist (from goal.md)

| goal.md § | Requirement | Where addressed |
|---|---|---|
| §1 | Research question, hypothesis tested rather than asserted, focused demo scenario, preferred backbone not silently replaced, reference agent treated as qualitative | proposal §1–2, decision_log |
| §2 | Instruction files kept consistent. Provisional understanding recorded first, then updated | this file, CLAUDE/AGENTS/AGENT.md |
| §3 | Six research areas. Matrix fields: approach, capabilities, memory, control interface, latency/hardware, availability, limitations, relevance, date/URL. Synthesis of solved, open, reusable, and contribution | related_work.md |
| §4 | Backbone integration surface. Each capability classed as available / reported / needs engineering / needs research, with the smallest resolving experiment | backbone_verification.md, proposal §6 |
| §5 | ≥3 candidate architectures. IR/interfaces/state/feedback, critical path, interruption, latency budget, memory taxonomy and lifecycle, private/public separation, feasibility, diagrams | proposal §5, figures/ |
| §6 | Ten proposal sections. Contribution separated from engineering. Evaluation with baselines, ablations, controls, sample sizes, uncertainty. Every number labeled | research_proposal.md |
| §7 | GPT-6 Sol review at 4 checkpoints, logged and re-reviewed | codex_reviews.md, docs/reviews/ |
| §8 | Final consistency check and closing summary | end of phase |

## Deliverables (Phase 1)

| File | Content |
|------|---------|
| `docs/research_proposal.md` | Complete, self-contained academic proposal |
| `docs/related_work.md` | Evidence-backed synthesis and comparison matrix |
| `docs/backbone_verification.md` | Verified vLLM-Omni / LingBot-World integration surface |
| `docs/decision_log.md` | Decisions, alternatives, evidence, assumptions, open questions |
| `tools/codex_review.sh` | Runs a Codex review checkpoint with inlined evidence and audit metadata |
| `docs/codex_reviews.md` | Actual Codex review records and resolutions |
| `docs/references.bib` | Verified bibliography |
| `docs/figures/` | Editable diagrams (Mermaid `.mmd` sources) |
| `docs/notes/` | Raw research notes (supporting material, not authoritative) |

## Research standards

- Use primary sources for technical claims. Record URLs and dates. For code,
  record the repo, commit, and `path:line` or symbol.
- Keep separate: what the inspected code does, what is reported upstream but
  not verified here, what needs engineering, and what needs new training or research.
- Do not fabricate experiments, measurements, user studies, or expected gains.
- Do not claim novelty just because components are combined. Agreement between
  models is not verification.
- Camera control does not imply character control. High generation FPS does
  not imply low latency from instruction to visible response.

## Codex review process (mandatory)

- Reviewer: **GPT-6 Sol**, invoked as
  `codex exec -m gpt-6-sol -s read-only --skip-git-repo-check -o <out> - < prompt`
  from the repo root. After each run, verify the model in the session rollout
  (`~/.codex/sessions/.../rollout-*.jsonl`, field `"model":"gpt-6-sol"`).
  Naming a model inside a prompt does not select it.
- Checkpoints: (1) understanding/requirements/assumptions; (2) literature and
  research gap; (3) architectures, integration, memory, latency; (4) experiments
  and final proposal.
- The Codex shell sandbox cannot start on this host (user namespaces are
  disabled), and running unsandboxed is not permitted. Reviews therefore run
  through `tools/codex_review.sh <tag> <instructions> <files...>`, which puts
  every piece of evidence (files and code excerpts) inline in the prompt.
- For each checkpoint, record in `docs/reviews/<tag>_*`: the exact prompt and
  evidence bundle (with sha256), the reviewer output, the event stream, and
  metadata (repo HEAD and dirty state, vLLM-Omni commit, CLI version, requested
  model, model reported by the rollout, thread ID, exit code).
  `docs/codex_reviews.md` summarizes every finding with its disposition
  (accepted / partially accepted / rejected with evidence / open) and the
  revision that resolved it. Re-review material changes.
- If Codex is unavailable, record the exact blocker and mark the review
  **pending**. Never simulate or substitute a reviewer.

===== FILE: docs/reviews/student6_review.md =====
Source-only re-review; I did not run the reported checks. The supplied code addresses the original late-decision and blank-subject reproductions, but these issues remain:

1. **Major — A late activity event can undo a replacement or clear a newer request.** In [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js), `onLessonEvent` handles `lesson` stages without checking which request produced them. After ordinary text replaces a pending practice request, a delayed `exercise_open` changes the status to “question ready” and displays the old question. If another activity is pending, that old event clears its ticket. The supplied `exercise_open` panel fixture has no `request_id`, and the browser cases cover late decisions rather than late activity events.

2. **Minor — A failed lesson remains pending internally.** `outline_failed` shows `lessonFailed` but leaves `pendingActivity` set. A later successful ordinary text submission therefore changes the displayed failure to “request replaced.” `exercise_failed` clears the ticket; a corresponding outline-failure fixture would expose this difference.

3. **Minor — A selectable padded title loses its catalogue context.** `loadCatalogue()` accepts a title such as `" 真实章节 "` but retains its spaces. After selection, `requestLesson()` and the practice handler trim the input and compare it with the untrimmed title, so `chosen` becomes `null` and no `lesson_context` is sent. The mixed-catalogue fixture covers blanks, not this case.

4. **Minor — Text-only supersession remains unverified across the WebSocket path.** The held-decision backend test explicitly calls `on_speech_start()` before the newer utterance; the browser activity fixtures intercept outgoing text and inject outcomes. Neither check establishes that an actual newer WebSocket text message supersedes a held earlier decision. An interleaved WebSocket text test would settle that path.
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
  let visibleLearner = null, lessonMessage = {key:"lessonEmpty", suffix:""}, feedbackKey = null, sessionHintKey = "roomHint", noteStatusKey = "localOnly", pendingActivity = null, activitySequence = 0, currentActivityId = null;
  const originals = new Map(), originalAttributes = new Map();
  document.querySelectorAll('[data-i18n-aria]').forEach(node=>originalAttributes.set(node,node.getAttribute('aria-label')));
  document.querySelectorAll('[data-i18n]').forEach(node => originals.set(node,node.textContent));
  const en = {
    skip:'Skip to classroom',navigation:'Main navigation',brand:'YāLearn',mySpace:'My learning space',classroom:'Live classroom',courses:'Explore topics',profile:'Learning profile',recordings:'Session recordings',help:'Quick guide',experience:'Experience',tagAsk:'Ask freely',tagPractice:'Learn & practice',tagPace:'Your own pace',retry:'Try again',liveRoom:'YOUR LIVE CLASSROOM',roomHint:'Choose a learner profile to get started',private:'Private session',video:'AI tutor video',board:'Lesson board',boardTitle:'A little space for a new idea',boardIntro:'Your tutor’s key points will appear here.',boardAsk:'Ask a question whenever you need.',boardPractice:'Try a practice question as you learn.',learner:'Learner',editProfile:'Edit profile',connect:'Enter classroom ↗',disconnect:'End session',inputLabel:'Ask your tutor',send:'Send',talk:'Hold to speak',avButton:'Audio / video sync',inputHint:'Enter to send · A new question interrupts playback',avOffset:'Video delay',avTest:'Test flash & sound',avReset:'Reset',avHelp:'If the sound is late, move right. If the picture is late, move left. This setting stays in this browser; test again after changing headphones.',tryAsk:'A starting point for your next question',suggestions:'Suggested questions',aiNotice:'AI explanations and grading can be wrong. Check important details against your course materials.',todayGoal:'Start with a learning goal',lessonHelp:'Enter your classroom, then request an explanation or practice.',topicLabel:'I want to understand',startLesson:'Start a lesson →',lessonEmpty:'Choose a topic below, or enter your own question.',stepChoose:'Choose a goal',stepChooseHelp:'Make your next learning task clear',stepLearn:'Explore the idea',stepLearnHelp:'Follow the board and ask questions',stepPractice:'Check your understanding',stepPracticeHelp:'Try a question and reflect on feedback',practice:'Request a practice question ↗',yourTurn:'YOUR TURN',exercise:'Practice question',exerciseHelp:'Use the choices below the classroom or type your answer.',profileGlance:'My learning profile',manage:'Edit ↗',profileEmpty:'Select a profile to see your learning records.',discover:'FOLLOW YOUR CURIOSITY',courseHeading:'Explore a topic worth understanding',catalogueNote:'Available catalogue: Chinese school subjects. Chapter titles and teaching are currently in Chinese; university courses are not included.',subject:'Subject',grade:'School grade',allSubjects:'All subjects',searchCourses:'Search topics',searchPlaceholder:'Search a chapter title…',coursesLoading:'Loading available topics…',moreCourses:'Show more topics ↓',conversation:'Classroom conversation',export:'Export',conversationEmpty:'Your questions and your tutor’s responses appear here.',notes:'My study notes',localOnly:'Stored in this browser only',notesPlaceholder:'An idea to remember. A question to revisit…',notesHelp:'Notes stay on this device, grouped by learner.',diagnostics:'Classroom settings & technical details',sessionSettings:'Session settings',sessionMode:'Mode',memoryIdentity:'Memory identifier',settingsHelp:'Test livestream mode does not use a student profile. The memory identifier connects session memories; it is not a login.',cameraHelp:'Focus check requires camera permission. Images are analyzed without being saved.',metrics:'Runtime diagnostics · measurements / estimates',metricsHelp:'Onset is measured from audio energy; it does not measure answer correctness. Simulated judging does not verify real actions.',intent:'Instruction state',timeline:'Event log',memory:'Session memory',footer:'YāLearn · Bring a question. Leave with understanding.',footerDetail:'AI classroom by Live Agent',close:'Close',helpOne:'Choose a learner profile, then enter the classroom.',helpTwo:'Choose a topic or enter a goal, then request a lesson. You can also type a question directly.',helpThree:'Interrupt to ask for clarification. Use the choices or text box to answer a practice question.',helpFour:'Edit or reset the profile and learning history. Notes are stored only in this browser.',helpLimit:'This edition translates the interface. The current curriculum covers Chinese school subjects and the teacher speaks Mandarin. Voice and video depend on service configuration.',privacyHelp:'This is a local classroom for trusted devices, without student authentication or account isolation. Recordings may include conversations; take care with personal information on shared devices.',
    ready:'Classroom available',unavailable:'Classroom unavailable',checking:'Checking classroom…',idle:'Ready when you are',connecting:'Preparing your classroom…',ended:'Session ended. Start again whenever you’re ready.',readyHint:'Your tutor is ready. Ask your first question.',demoProfile:'Example profile · Sample records are not your assessment.',profileEvidence:'Understanding values are uncalibrated estimates from the stored profile.',profileLoadFailed:'Could not load this profile. Try selecting it again.',studentsFailed:'Could not load learner profiles. Check that the backend is running, then try again.',serviceFailed:'The classroom service is not available. Start the backend and try again.',mockNotice:'Preview mode: placeholder video. Simple conversation is available; lesson and exercise generation require a configured teaching model.',languageNotice:'English interface · The current teaching language and school catalogue are Chinese. University course coverage is not available.',rulesLesson:'This preview cannot create lessons or practice questions. Configure a teaching model to use these actions.',noTeacher:'This persona does not support classroom lessons. Start the service with PERSONA=teacher.',selectGoal:'Enter a topic first.',lessonWaiting:'Preparing your lesson request…',lessonSent:'Lesson requested. Waiting for the tutor’s plan…',lessonPrepared:'Lesson material is prepared. Follow the live explanation.',lessonFailed:'The lesson could not be prepared. Ask a smaller question or try again.',outlineReady:'Your lesson plan is ready:',sectionReady:'Prepared section:',practiceWaiting:'Practice requested. Waiting for the question…',practiceClosed:'This question is closed. Ask for another when you’re ready.',correct:'The tutor marked this answer correct.',incorrect:'The tutor marked this answer incorrect. Ask for a hint and try again.',skipped:'You chose to skip. Ask the tutor to explain the idea.',requestSuperseded:'That activity request was replaced by a newer action. Ask again when ready.',requestNotStarted:'The tutor did not start that learning activity. Ask again or rephrase the request.',practicePrepared:'The question is prepared. Follow the tutor’s explanation.',practiceReady:'A practice question is ready. Give your answer.',practiceReviewed:'Answer feedback is ready. Review it before continuing.',exerciseFailed:'The practice question could not be prepared. Try again or choose a smaller topic.',gradingFailed:'The answer could not be graded. Ask the tutor to try again.',exercisePending:'A practice question is waiting for your answer.',noTopics:'No matching topics. Try another grade or subject, or enter a custom goal.',catalogueError:'The topic catalogue could not be loaded.',allGrades:'All school grades',topicAction:'Choose topic ↗',textbook:'Textbook chapter',estimate:'Estimated placement',reference:'Catalogue reference',customTopic:'Custom topic request',emptyExport:'There is nothing to export yet.',noteSaved:'Saved on this device',noteFailed:'Could not save. Export your notes to keep a copy.',savedExample:'Example profile',noProfiles:'No learner profiles are available. Ask the operator to configure one.',publicMode:'Test livestream · No learner profile',localStorageHelp:'Notes could not be loaded from this browser. Export any new notes before leaving.'
  };
  const zh = {ready:'课堂服务可用',unavailable:'课堂服务不可用',checking:'正在检查课堂…',idle:'课堂准备好了',connecting:'正在准备课堂…',ended:'课堂已结束，随时可以重新开始。',readyHint:'老师准备好了，说说你的第一个问题吧。',demoProfile:'示例档案 · 这里的样例记录不是你的测评结果。',profileEvidence:'理解程度为档案中的估计值，尚未校准。',profileLoadFailed:'档案暂时加载失败，请重新选择。',studentsFailed:'学习档案加载失败，请确认后端运行后重试。',serviceFailed:'课堂服务暂时不可用，请启动后端后重试。',mockNotice:'演示模式：当前是占位视频，可体验简单对话；生成课程和练习需要配置教学模型。',rulesLesson:'当前演示不能生成课程和练习。启用教学模型后即可使用。',noTeacher:'当前人设不支持教学课程，请以 PERSONA=teacher 启动服务。',selectGoal:'先写下你想学的主题吧。',lessonWaiting:'正在准备你的课程请求…',lessonSent:'已请求课程，等待老师准备大纲…',lessonPrepared:'课程内容已备好，请跟随老师的实时讲解。',lessonFailed:'备课暂时失败了，可以换一个更具体的问题再试。',outlineReady:'课程大纲已准备：',sectionReady:'已备好：',practiceWaiting:'已请求练习，正在等待题目…',practiceClosed:'这道练习已结束，准备好后可以再来一道。',correct:'老师判定这次作答正确。',incorrect:'老师判定这次作答有误，可以请老师给你一个提示。',skipped:'这次先跳过，可以请老师再讲一遍思路。',requestSuperseded:'这项学习请求已被新的操作取代，准备好后可以重新请求。',requestNotStarted:'老师没有开始这项学习活动，可以重新提问或换一种说法。',practicePrepared:'题目已备好，请跟随老师的讲解。',practiceReady:'练习题已准备好，试着回答吧。',practiceReviewed:'作答反馈已收到，看看老师的建议吧。',exerciseFailed:'练习暂时生成失败，可以重试或换一个更具体的主题。',gradingFailed:'这次未能完成批改，可以请老师重试。',exercisePending:'有一道练习在等你作答。',noTopics:'没有找到匹配课程，试试其他年级、学科，或直接填写学习目标。',catalogueError:'课程目录暂时加载失败。',allGrades:'全部年级',topicAction:'选这个主题 ↗',textbook:'教材章节',estimate:'年级归属为估计',reference:'课程目录参考',customTopic:'自选主题请求',emptyExport:'还没有可以导出的内容。',noteSaved:'已保存到当前设备',noteFailed:'保存失败，请导出笔记以保留内容。',savedExample:'示例档案',noProfiles:'尚未配置学习档案，请联系服务维护者。',publicMode:'测试直播 · 不读取学习档案',localStorageHelp:'无法读取本浏览器中的笔记，离开前请导出新笔记。'};
  const primary = {classroom:'我的小课堂',courses:'找点新知识',profile:'我的学习卡',recordings:'看看课堂记录',todayGoal:'今天想学什么呀？',lessonHelp:'先和老师见个面，再开始学一学。',topicLabel:'我想知道',startLesson:'和老师一起学 →',stepChoose:'选一个小目标',stepChooseHelp:'你想知道什么呀？',stepLearn:'一起找答案',stepLearnHelp:'看一看，听一听，不懂就问',stepPractice:'动手试一试',stepPracticeHelp:'答一道题，说说你的想法',practice:'老师，给我一道题 ↗',courseHeading:'下一个发现，等着你',tryAsk:'可以这样问老师',inputHint:'回车发送 · 想提问，随时打断老师'};
  function t(key, fallback='') { return (edition === 'university' ? en[key] : (edition === 'primary' ? primary[key] ?? zh[key] : zh[key])) ?? fallback; }
  function examples() {
    if (edition === 'university') return [{label:'Walk me through an example',text:'请给我讲一道例题'}, {label:'Explain that step again',text:'这一步我还没明白，请再解释一下'}, {label:'Let’s try a question',text:'给我出道练习题'}, {label:'A slower explanation',text:'请讲慢一点'}];
    return edition === 'primary' ? ['老师，可以举个例子吗？','这一步我还不懂','请讲慢一点','给我出道练习题'] : ['请给我讲一道例题','这一步我还没明白','给我出道练习题','请讲慢一点'];
  }
  if(query.get('mode')==='public'){el('mode').value='public';el('uid').value='public-preview';}
  const product = {get edition(){return edition;},t,examples,sessionChanged,acceptsActivity};
  window.LiveAgentProduct = product;
  function setLessonStatus(key,suffix=''){lessonMessage={key,suffix};el('lessonStatus').textContent=t(key,key==='lessonEmpty'?originals.get(el('lessonStatus')):'')+(suffix?' '+suffix:'');}
  function acceptsActivity(requestId){return (requestId??null)===currentActivityId;}
  function sendActivity(kind,text,context){const requestId=globalThis.crypto?.randomUUID?.()||'activity-'+Date.now().toString(36)+'-'+(++activitySequence);if(!window.sendText(text,context,requestId))return false;pendingActivity={requestId,kind,context:!!context};setLessonStatus(kind==='lesson'?'lessonSent':'practiceWaiting');return true;}
  function setNoteStatus(key){noteStatusKey=key;el('noteStatus').textContent=t(key,originals.get(el('noteStatus')));}
  function setFeedback(key){feedbackKey=key;el('exerciseFeedback').textContent=key?t(key):'';}
  function setTopicStatus(topic){lessonMessage=null;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+t(topic.basis.includes('estimate')?'estimate':topic.basis.includes('textbook')?'textbook':'reference');}
  function clearLearningScope(){pendingLesson=null;selectedTopic=null;resetLearningState();window.resetSessionView?.();el('text').value='';el('lessonTopic').value='';el('courseSearch').value='';setLessonStatus('lessonEmpty');renderCourses();updateLessonActions();}
  function resetLearningState(){currentActivityId=null;pendingActivity=null;feedbackKey=null;recentExercise=null;el('exerciseAnnouncement').textContent='';el('exerciseQuestion').textContent='';el('exerciseFeedback').textContent='';el('exerciseCard').hidden=true;el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
  function links() {
    const contextURL=new URL(location.href);contextURL.searchParams.set('edition',edition);if(el('mode').value==='public'){contextURL.searchParams.delete('student');contextURL.searchParams.set('mode','public');}else{contextURL.searchParams.delete('mode');if(el('sid').value)contextURL.searchParams.set('student',el('sid').value);}history.replaceState(null,'',contextURL);
    const parameters = new URLSearchParams({edition});if(el('mode').value!=='public')parameters.set('student',el('sid').value);
    ['profileNav','profLink'].forEach(id=>el(id).href='/profile?'+parameters);
    if(el('mode').value==='public')parameters.set('mode','public');el('tracesNav').href='/traces?'+parameters;
    document.querySelector('.brand').href='/?'+parameters;
  }
  function modePresentation(){const publicMode=el('mode').value==='public';document.querySelector('.private-label').textContent=publicMode?t('publicMode'):t('private','私人会话');document.querySelector('.student-picker').hidden=publicMode;el('profLink').hidden=publicMode;el('profCard').hidden=publicMode;el('profileNav').hidden=publicMode;}
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
    if(connection==='disconnected'){el('conn').textContent=t('idle','待开始');el('overlay').textContent=next==='university'?'Your classroom is ready.\nEnter to meet your AI tutor.':next==='primary'?'小课堂准备好啦！\n点「进入课堂」和老师见面吧。':'课堂准备好了\n点击「进入课堂」与老师见面';}
    if(!status)el('title').textContent=next==='university'?'AI learning companion':'AI 学习伙伴';
    populateGrades(!initial);renderSubjects();renderCourses();updateService();updateRuntime();modePresentation();links();for(const option of el('sid').options){const student=students.find(s=>s.id===option.value);if(student)option.textContent=(student.name||student.id)+(student.id==='demo'?' · '+t('savedExample'):'');}
    if(selectedProfile&&typeof window.showProfile==='function') window.showProfile(selectedProfile);
    if(lessonMessage)setLessonStatus(lessonMessage.key,lessonMessage.suffix);else if(selectedTopic)setTopicStatus(selectedTopic);setFeedback(feedbackKey);setNoteStatus(noteStatusKey);el('sessionHint').textContent=t(sessionHintKey,originals.get(el('sessionHint')));if(recentExercise)renderExercise(recentExercise);
    if(typeof window.setChips==='function'&&!recentExercise)window.setChips(examples(),connection==='ready');window.LiveAgentMedia?.refreshLanguage?.();
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
      card.onclick=()=>{selectedTopic=topic;el('lessonTopic').value=topic.topic;setTopicStatus(topic);updateLessonActions();el('classroom').scrollIntoView({behavior:'smooth',block:'start'});el('lessonTopic').focus({preventScroll:true});};list.append(card);
    }
    el('moreCourses').hidden=matches.length<=limit;
  }
  async function requestJson(path){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);try{return await window.LiveAgentAPI.fetchJson(path,{signal:controller.signal});}finally{clearTimeout(timer);}}
  async function loadCatalogue(){catalogueFailed=false;el('catalogueRetry').hidden=true;try{const data=await requestJson('/api/curriculum/topics');topics=(data.topics||[]).filter(x=>typeof x.subject==='string'&&!!x.subject.trim()&&typeof x.topic==='string'&&!!x.topic.trim()&&Number.isInteger(x.grade)&&x.grade>=1&&x.grade<=12).map(x=>({...x,topic:x.topic.trim(),basis:String(x.basis||'')}));const order=['数学','英语','语文','物理','化学','生物','历史','地理'];topics.sort((a,b)=>(order.indexOf(a.subject)<0?99:order.indexOf(a.subject))-(order.indexOf(b.subject)<0?99:order.indexOf(b.subject))||a.grade-b.grade);}catch{catalogueFailed=true;topics=[];}renderSubjects();renderCourses();}
  function updateService(){el('serviceStatus').textContent=t(serviceReady?'ready':'unavailable');el('serviceDot').className=serviceReady?'ready':'error';}
  function updateRuntime(){const messages=[];if(edition==='university')messages.push(t('languageNotice'));if((status?.generator||healthInfo?.generator)==='mock')messages.push(edition==='university'?'Video preview: the teacher video is a placeholder. Teaching availability is shown after connecting.':'视频演示：当前为占位画面，教学功能会在连接后确认。');if(status?.responder==='rules')messages.push(t('rulesLesson'));if(status&&!status.board)messages.push(t('noTeacher'));el('runtimeNotice').textContent=messages.join(' ');el('runtimeNotice').hidden=!messages.length;}
  function updateLessonActions(){const allowed=serviceReady&&connection==='ready'&&status?.board&&status.responder!=='rules';el('startLesson').disabled=!allowed||!el('lessonTopic').value.trim()||!!recentExercise;el('practice').disabled=connection!=='ready'||!status?.board||status?.responder==='rules'||!!recentExercise;}
  function sessionChanged(state,detail={}){
    connection=state;status=state==='ready'?detail.status:state==='connecting'?null:status;
    if(state==='connecting'){resetLearningState();profileRequest++;loadingProfile=false;selectedProfile=null;el('connectionError').hidden=true;recentExercise=null;el('exerciseCard').hidden=true;el('exerciseFeedback').textContent='';['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
    if(state==='error'){resetLearningState();setLessonStatus('serviceFailed');pendingLesson=null;el('connectionError').hidden=false;el('connectionErrorText').textContent=detail.message||t('serviceFailed');}
    if(state==='disconnected'){resetLearningState();pendingLesson=null;recentExercise=null;el('exerciseCard').hidden=true;setLessonStatus('ended');}
    sessionHintKey=state==='ready'?'readyHint':state==='connecting'?'connecting':state==='disconnected'?'ended':'serviceFailed';el('sessionHint').textContent=t(sessionHintKey);
    if(state!=='connecting'&&state!=='ready')el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);
    updateLessonActions();updateRuntime();
  }
  function profileDisclaimer(p){el('profileDisclaimer').textContent=!p?'':p.id==='demo'?t('demoProfile'):t('profileEvidence');}
  async function selectProfile(){
    const request=++profileRequest;const id=el('sid').value;const nextLearner=el('mode').value==='public'?null:id;if(visibleLearner!==null&&visibleLearner!==nextLearner)clearLearningScope();visibleLearner=nextLearner;selectedProfile=null;window.showProfile?.(null);profileDisclaimer(null);if(el('mode').value==='public'){selectedProfile=null;loadingProfile=false;window.showProfile?.(null);profileDisclaimer(null);loadNotes();return;}loadingProfile=true;el('prof').textContent=edition==='university'?'Loading this learner’s profile…':'正在加载这个学习档案…';links();storage.set('liveAgent.student',id);el('uid').value='learner:'+id;loadNotes();
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
    if(studentsReady){for(const student of students){const option=document.createElement('option');option.value=student.id;option.textContent=(student.name||student.id)+(student.id==='demo'?' · '+t('savedExample'):'');el('sid').append(option);}const preferred=new URLSearchParams(location.search).get('student')||storage.get('liveAgent.student');if([...el('sid').options].some(o=>o.value===preferred))el('sid').value=preferred;el('sid').disabled=connection==='ready'||connection==='connecting';await selectProfile();}
    else{const option=document.createElement('option');option.value='';option.textContent=t('noProfiles');el('sid').append(option);el('sid').disabled=true;}
    if(connection!=='ready'&&connection!=='connecting')el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);
    updateService();updateLessonActions();updateRuntime();
    if(!serviceReady||(el('mode').value!=='public'&&!studentsReady)){el('connectionError').hidden=false;el('connectionErrorText').textContent=t(!serviceReady?'serviceFailed':'studentsFailed');}
    else{el('connectionError').hidden=true;}
    if(el('mode').value==='public')loadNotes();loadCatalogue();
  }
  function requestLesson(){
    const topic=el('lessonTopic').value.trim();if(!topic){setLessonStatus('selectGoal');el('lessonTopic').focus();return;}
    if(status&&(status.responder==='rules'||!status.board)){setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');return;}
    const chosen=selectedTopic&&selectedTopic.topic.trim()===topic?selectedTopic:null;const grade=chosen?(chosen.grade<=6?'小学'+'一二三四五六'[chosen.grade-1]+'年级':(chosen.grade<=9?'初':'高')+'一二三'[(chosen.grade-7)%3]):'';const prompt=chosen?'给我上一节'+grade+chosen.subject+'「'+topic+'」的课，请按照'+grade+'的课程要求讲解。':'给我上一节'+topic+'的课';
    if(connection==='ready'){if(sendActivity('lesson',prompt,chosen)){el('stepLearn').classList.add('current');}}
    else{pendingLesson={text:prompt,context:chosen};setLessonStatus('lessonWaiting');el('connect').click();}
  }
  function renderExercise(ex){const announcement=el('exerciseAnnouncement');const spoken=ex?[t('yourTurn','轮到你啦'),ex.question||ex.concept,...(ex.option_texts||[])].join(' '):'';if(announcement.textContent!==spoken)announcement.textContent=spoken;recentExercise=ex||null;el('exerciseCard').hidden=!ex&&!el('exerciseFeedback').textContent;if(ex){const question=ex.question||ex.concept;el('exerciseQuestion').textContent=[question,...(ex.option_texts||[])].join('\n');el('suggestionLabel').textContent=t('exercisePending');el('stepPractice').classList.add('current');}else el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));updateLessonActions();}
  function onLessonEvent(event){const message=event.detail;const data=message.data||{};if(message.event==='utterance_end'&&data.decision&&pendingActivity&&data.request_id===pendingActivity.requestId){const dec=data.decision;const starts=dec.kind===pendingActivity.kind&&(pendingActivity.kind!=='lesson'||pendingActivity.context||(typeof dec.topic==='string'&&dec.topic.trim()));if(data.applied===false){setLessonStatus('requestSuperseded');pendingActivity=null;currentActivityId=null;}else if(!starts){setLessonStatus('requestNotStarted');pendingActivity=null;currentActivityId=null;}else pendingActivity.accepted=true;}if(message.event==='error'&&['lessonSent','practiceWaiting'].includes(lessonMessage?.key))setLessonStatus('lessonFailed');if(message.event!=='lesson'||!acceptsActivity(data.request_id))return;
    if(data.stage==='outline'){pendingActivity=null;setLessonStatus('outlineReady',data.title||data.topic||'');el('stepLearn').classList.add('current');}
    if(data.stage==='section')setLessonStatus('sectionReady',data.title||'');
    if(data.stage==='planned')setLessonStatus('lessonPrepared');
    if(data.stage==='outline_failed'){pendingActivity=null;currentActivityId=null;setLessonStatus('lessonFailed');}
    if(data.stage==='exercise_failed'||data.stage==='exercise_dropped'){if(pendingActivity?.kind==='exercise')currentActivityId=null;pendingActivity=null;setLessonStatus('exerciseFailed');}
    if(data.stage==='exercise'){pendingActivity=null;setLessonStatus('practicePrepared');}
    if(data.stage==='exercise_open'){pendingActivity=null;setLessonStatus('practiceReady');setFeedback(null);renderExercise(data);}
    if(data.stage==='exercise_closed'||data.stage==='exercise_timeout'){pendingActivity=null;setLessonStatus('practiceClosed');renderExercise(null);}
    if(data.stage==='exercise_graded'){setLessonStatus('practiceReviewed');el('exerciseCard').hidden=false;setFeedback(data.skipped?'skipped':data.correct?'correct':'incorrect');el('stepPractice').classList.add('current');}
    if(data.stage==='grading_failed')setFeedback('gradingFailed');
  }
  function loadNotes(){noteKey='liveAgent.notes.'+(el('mode').value==='public'?'public':encodeURIComponent(el('sid').value||'unselected'));el('notes').value=storage.get(noteKey)||'';setNoteStatus('localOnly');}
  function download(contents,name){if(!contents.trim()){setNoteStatus('emptyExport');return;}const url=URL.createObjectURL(new Blob([contents],{type:'text/plain;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  el('edition').onchange=()=>setEdition(el('edition').value);
  el('sid').onchange=selectProfile;el('mode').onchange=()=>{profileRequest++;selectedProfile=null;loadingProfile=false;clearLearningScope();el('uid').value=el('mode').value==='public'?'public-preview':'learner:'+el('sid').value;modePresentation();links();selectProfile();renderCourses();updateLessonActions();el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);el('connectionError').hidden=serviceReady&&(el('mode').value==='public'||studentsReady);if(el('mode').value!=='public'&&!studentsReady)bootstrap();window.layoutStage?.();};el('lessonTopic').oninput=()=>{selectedTopic=null;setLessonStatus('customTopic');updateLessonActions();};el('startLesson').onclick=requestLesson;
  el('practice').onclick=()=>{const topic=el('lessonTopic').value.trim(),chosen=selectedTopic?.topic.trim()===topic?selectedTopic:null;const grade=chosen?(chosen.grade<=6?'小学'+'一二三四五六'[chosen.grade-1]+'年级':(chosen.grade<=9?'初':'高')+'一二三'[(chosen.grade-7)%3]):'';const text=chosen?'给我出道'+grade+chosen.subject+'「'+topic+'」的练习题。':'给我出道'+topic+'练习题';sendActivity('exercise',text,chosen);};
  ['subjectFilter','gradeFilter','courseSearch'].forEach(id=>el(id).addEventListener(id==='courseSearch'?'input':'change',()=>{limit=6;renderCourses();}));
  el('moreCourses').onclick=()=>{limit+=6;renderCourses();};el('catalogueRetry').onclick=loadCatalogue;
  el('connectionRetry').onclick=()=>{if(serviceReady&&(studentsReady||el('mode').value==='public'))el('connect').click();else bootstrap();};
  el('helpOpen').onclick=()=>el('helpDialog').showModal();el('helpClose').onclick=()=>el('helpDialog').close();
  el('notes').oninput=()=>setNoteStatus(storage.set(noteKey||'liveAgent.notes.unselected',el('notes').value)?'noteSaved':'noteFailed');
  el('exportNotes').onclick=()=>download(el('notes').value,'study-notes.txt');
  el('exportChat').onclick=()=>download([...el('chat').querySelectorAll('.msg')].map(n=>n.textContent).join('\n\n'),'classroom-conversation.txt');
  window.addEventListener('live-agent:submitted',event=>{const incoming=event.detail.request_id??null;if(recentExercise&&incoming===null)return;currentActivityId=incoming;if(recentExercise&&!acceptsActivity(recentExercise.request_id)){setFeedback(null);renderExercise(null);window.LiveAgentMedia?.refreshLanguage?.();}if(pendingActivity&&incoming!==pendingActivity.requestId){pendingActivity=null;setLessonStatus('requestSuperseded');}});
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');else sendActivity('lesson',queued.text,queued.context);}updateLessonActions();});
  window.addEventListener('live-agent:profile',event=>{if(loadingProfile&&!event.detail)return;selectedProfile=event.detail;profileDisclaimer(event.detail);});
  window.addEventListener('live-agent:state',event=>{const ex=event.detail.exercise;if(ex&&!acceptsActivity(ex.request_id))return;renderExercise(ex);});
  window.addEventListener('live-agent:event',onLessonEvent);
  window.addEventListener('DOMContentLoaded',()=>{setEdition(edition,true);bootstrap();});
})();

===== FILE: .cache/student-review/contracts7.txt =====
===== CURRENT SOURCE: live_agent/orchestrator.py, lines 970-983 =====
970:         self._lesson_mistakes = []
971:         self.director.lesson_title = topic
972:         self._lesson_task = asyncio.create_task(self._guarded(self._lesson_loop(topic, lesson_context, request_id), "lesson", fatal=False))
973:         self._aux.add(self._lesson_task)
974:         self._lesson_task.add_done_callback(lambda t: (self._aux.discard(t), self._maybe_finish()))
975: 
976:     def _make_figures(self) -> None:
977:         """Generate the images boards asked for, in the background (a board shows its figure on requests locked
978:         after the image exists; without an image model the figure is simply left out)."""
979:         d = self.director
980:         figs, d.pending_figures = d.pending_figures, []
981:         for fig in figs:
982:             if fig.queued or fig.url:
983:                 continue

===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1046-1085 =====
1046:         self._make_figures()
1047: 
1048:     # ------------------------------------------------------------------ exercises
1049:     async def _grade_answer(self, utt: Utterance, epoch: int) -> dict | None:
1050:         """While an exercise waits: is this utterance its answer? If so grade it, speak the feedback, update the
1051:         student profile and return the decision for the log; None: not an answer (the responder handles it)."""
1052:         from live_agent.exercise import grade
1053: 
1054:         d = self.director
1055:         ex = d.exercise
1056:         correlation = {"request_id": ex.request_id} if ex.request_id is not None else {}
1057:         profile_epoch = self._profile_epoch
1058:         try:
1059:             r = await grade(d.llm, ex, utt.text)
1060:         except Exception as e:  # noqa: BLE001 - grading failed: the responder answers as usual
1061:             self.log.emit(EventType.LESSON, now(), stage="grading_failed", error=str(e)[:160], **correlation)
1062:             return None
1063:         if not r.get("is_answer"):
1064:             return None
1065:         decision = {"relation": "chat", "target_chain": None, "kind": "chat", "memory_note": None,
1066:                     "forget_term": None, "steps": [{"intent": "", "line": x} for x in r.get("feedback") or []],
1067:                     "exercise_result": {"correct": r["correct"], "concept": ex.concept}}
1068:         if epoch != self._input_epoch or d.exercise is not ex or profile_epoch != self._profile_epoch:
1069:             # a newer utterance (or an erasure) came first: nothing is applied or recorded
1070:             self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
1071:             return {"relation": "chat", "kind": "superseded", "steps": [], "superseded": True}
1072:         before = {id(x) for x in d.queue}
1073:         d.apply(utt, decision)
1074:         d.close_exercise(before)
1075:         self._decisions += 1
1076:         change = None
1077:         if self.student is not None:
1078:             change = self.student.record_exercise(ex.concept, r["correct"], question=ex.question, answer=utt.text,
1079:                                                   misconception=r.get("misconception") or "", subject=ex.subject)
1080:             self._save_profile()
1081:         if not r["correct"] and (ex.source == "lesson" or d.lesson_title):
1082:             self._lesson_mistakes.append(ex.concept + (f"（{r['misconception']}）" if r.get("misconception") else ""))
1083:         self.log.emit(EventType.LESSON, now(), stage="exercise_graded", concept=ex.concept, correct=r["correct"],
1084:                       skipped=bool(r.get("skipped")), misconception=r.get("misconception"), mastery=change, **correlation)
1085:         self._emit_profile()

===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1101-1189 =====
1101: 
1102:     async def _give_exercise(self, topic: str, lesson_context: dict | None = None, *,
1103:                              input_epoch: int | None = None, profile_epoch: int | None = None,
1104:                              plan_version: int | None = None, request_id: str | None = None) -> None:
1105:         """The student asked for an exercise: one on ``topic`` at the level the profile suggests."""
1106:         from live_agent.exercise import make_exercise
1107: 
1108:         d = self.director
1109:         correlation = {"request_id": request_id} if request_id is not None else {}
1110:         self._exercises += 1
1111:         input_epoch = self._input_epoch if input_epoch is None else input_epoch
1112:         profile_epoch = self._profile_epoch if profile_epoch is None else profile_epoch
1113:         plan = d.plan_version if plan_version is None else plan_version
1114: 
1115:         def superseded() -> bool:
1116:             return input_epoch != self._input_epoch or profile_epoch != self._profile_epoch or plan != d.plan_version
1117: 
1118:         def drop_superseded() -> None:
1119:             self.log.emit(EventType.AUDIT, now(), where="exercise_generation", topic=topic, reason="superseded", **correlation)
1120: 
1121:         if superseded():
1122:             drop_superseded()
1123:             return
1124:         from live_agent.curriculum import parse_grade
1125: 
1126:         exercise_profile, curriculum = self._catalogue_teaching_context(lesson_context)
1127:         g = parse_grade(exercise_profile.grade) if exercise_profile is not None else None
1128:         profile = exercise_profile.summary() if lesson_context else self._student_context()
1129:         profile = profile or "无（新学生，没有档案）"
1130:         if curriculum and exercise_profile is not None:
1131:             if lesson_context:
1132:                 profile += "\n" + curriculum.teaching_context(g, CHARS_PER_REQUEST, brief=True)
1133:             profile += "\n" + curriculum.topic_context(topic, g)
1134:             if curriculum.exercise_style(g):
1135:                 profile += f"\n这个年级的练习形式：{curriculum.exercise_style(g)}"
1136:         try:
1137:             craft = curriculum.practice_craft(g, curriculum.subject_of(topic, g)) \
1138:                 if curriculum and exercise_profile is not None else ""
1139:             ex = await make_exercise(d.llm, name=d.persona_name, topic=topic, profile=profile,
1140:                                      key=f"q{self._exercises}", craft=craft)
1141:         except Exception as e:  # noqa: BLE001
1142:             if superseded():
1143:                 drop_superseded()
1144:                 return
1145:             self.log.emit(EventType.LESSON, now(), stage="exercise_failed", topic=topic, error=str(e)[:160], **correlation)
1146:             d.say_verified("抱歉，这道题我没出好，你可以换个问法。")
1147:             return
1148:         if superseded():
1149:             drop_superseded()
1150:             return
1151:         if d.exercise is not None or any(
1152:                 t in ex.question or t in ex.concept for t in d.erased_terms):
1153:             self.log.emit(EventType.LESSON, now(), stage="exercise_dropped", concept=ex.concept,
1154:                           reason="another exercise is open" if d.exercise is not None else "erasure", **correlation)
1155:             return
1156:         ex.request_id = request_id
1157:         lines = ex.lines(22)
1158:         d.pose_exercise(lines[1:])  # the responder already said it will give one
1159:         self.log.emit(EventType.LESSON, now(), stage="exercise", concept=ex.concept, exercise=ex.question,
1160:                       options=ex.options, kind=ex.kind, **correlation)
1161: 
1162:     def _exercise_changed(self) -> None:
1163:         """Tell the page when an exercise opens or closes (its answer buttons); the 2 Hz state snapshot is only
1164:         sent in gaps between events, which a lesson rarely leaves."""
1165:         ex = self.director.exercise
1166:         if ex is self._shown_exercise:
1167:             return
1168:         previous = self._shown_exercise
1169:         self._shown_exercise = ex
1170:         if ex is None:
1171:             correlation = {"request_id": previous.request_id} if previous is not None and previous.request_id is not None else {}
1172:             self.log.emit(EventType.LESSON, now(), stage="exercise_closed", **correlation)
1173:         else:
1174:             correlation = {"request_id": ex.request_id} if ex.request_id is not None else {}
1175:             self.log.emit(EventType.LESSON, now(), stage="exercise_open", concept=ex.concept,
1176:                           kind=ex.kind, question=ex.question, option_texts=list(ex.options),
1177:                           options=[o[:1] for o in ex.options], **correlation)
1178: 
1179:     def _erase_learning(self, terms: list[str]) -> int:
1180:         """Erasure of teaching state: the student profile, a pending exercise that mentions a term (with its queued
1181:         lines and answer board), this lesson's mistakes; in-flight grading / exercise generation is invalidated."""
1182:         n = 0
1183:         self._profile_epoch += 1  # grading / exercise generation in flight must not write back erased data
1184:         ex = self.director.exercise
1185:         if ex is not None and any(x in json.dumps(ex.__dict__, ensure_ascii=False, default=str) for x in terms):
1186:             self.director.close_exercise(set(id(s) for s in self.director.queue))  # its lines go too
1187:             self.director.queue = type(self.director.queue)(s for s in self.director.queue
1188:                                                            if s.board is None or s.board.key not in (ex.key, ex.key + "a"))
1189:         if self.student is not None:

===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1260-1333 =====
1260:         self._lesson_task = None
1261:         self.director.stop_lesson()
1262: 
1263:     async def _lesson_loop(self, topic: str, lesson_context: dict | None = None, request_id: str | None = None) -> None:
1264:         """Outline first (its intro plays with the outline on the board), then one section at a time, each
1265:         generated while the previous one plays (a section is ~1 min of speech, ~10-20 s to generate)."""
1266:         from live_agent.lesson import LessonLine, LessonPlanner
1267: 
1268:         d = self.director
1269:         correlation = {"request_id": request_id} if request_id is not None else {}
1270:         lesson_profile, lesson_curriculum = self._catalogue_teaching_context(lesson_context)
1271:         planner = LessonPlanner(d.llm, name=d.persona_name, bio=d.persona_bio, curriculum=lesson_curriculum)
1272:         context = "；".join(t for r, t in d.dialogue if r == "user")[-300:]
1273:         try:
1274:             outline = await planner.outline(topic, context, profile=lesson_profile)
1275:         except Exception as e:  # noqa: BLE001
1276:             self.log.emit(EventType.LESSON, now(), stage="outline_failed", topic=topic, error=str(e)[:160], **correlation)
1277:             d.add_lesson_lines([LessonLine("抱歉，这节课我还没准备好，你可以先问我问题。", None, None)])
1278:             return
1279:         d.lesson_title = outline.title
1280:         d.add_lesson_lines(planner.intro_lines(outline))
1281:         self.log.emit(EventType.LESSON, now(), stage="outline", topic=topic, title=outline.title,
1282:                       sections=[s["title"] for s in outline.sections],
1283:                       plan=[{"title": s["title"], "concepts": s.get("concepts", []), "depth": s.get("depth"),
1284:                              "exercise": s.get("exercise", False)} for s in outline.sections],
1285:                       note=outline.note, adaptive=self.student is not None, subject=outline.subject,
1286:                       subject_source=getattr(planner, "last_subject", None), objectives=outline.objectives,
1287:                       key_point=outline.key_point, difficulty=outline.difficulty, hook=outline.hook_type, **correlation)
1288:         covered: list[str] = []
1289:         waiting_for = None  # the previous section's exercise: its result shapes the next section
1290:         for i in range(len(outline.sections)):
1291:             # a judged-and-rewritten section takes about twice as long to produce: start it earlier
1292:             lookahead = self.cfg.lesson_lookahead * (2 if self.cfg.lesson_self_check == "revise" and i > 0 else 1)
1293:             while not self._stop.is_set() and (
1294:                     len(d.lesson_backlog) >= lookahead
1295:                     or (waiting_for is not None and (d.exercise is waiting_for
1296:                                                      or any(x.exercise is waiting_for for x in d.lesson_backlog)))
1297:                     or (self.student is not None and d.exercise is not None)):
1298:                 await asyncio.sleep(0.5)
1299:             waiting_for = None
1300:             lines = None
1301:             for attempt in range(2):
1302:                 try:
1303:                     lines = await planner.section(outline, i, covered, profile=lesson_profile,
1304:                                                   mistakes=list(self._lesson_mistakes))
1305:                     break
1306:                 except Exception as e:  # noqa: BLE001 - retry once, then skip the section
1307:                     self.log.emit(EventType.LESSON, now(), stage="section_failed", section=i, attempt=attempt,
1308:                                   error=str(e)[:160], **correlation)
1309:             if lines and self.cfg.lesson_self_check == "revise" and i > 0:
1310:                 lines = await self._revise_section(planner, outline, i, covered, lines, profile=lesson_profile, request_id=request_id)
1311:             if lines:
1312:                 for line in lines:
1313:                     if getattr(line, "exercise", None) is not None:
1314:                         line.exercise.request_id = request_id
1315:                 if self.cfg.lesson_self_check == "log" or (self.cfg.lesson_self_check == "revise" and i == 0):
1316:                     self._spawn(self._check_section(planner, outline, i, lines, profile=lesson_profile, request_id=request_id), "lesson_check")
1317:                 self._lesson_mistakes.clear()  # addressed by this section
1318:                 d.add_lesson_lines(lines)
1319:                 if self.student is not None and outline.sections[i].get("concepts"):
1320:                     self.student.mark_taught(outline.sections[i]["concepts"])
1321:                     self._save_profile()
1322:                 self._make_figures()
1323:                 self._spawn(self._judge_figures(planner, lines, request_id), "figure_judgement")
1324:                 ex = next((ln.exercise for ln in lines if getattr(ln, "exercise", None) is not None), None)
1325:                 waiting_for = ex if self.student is not None else None  # adapt the next section to the answer
1326:                 self.log.emit(EventType.LESSON, now(), stage="section", section=i,
1327:                               title=outline.sections[i]["title"], lines=len(lines),
1328:                               points=len(lines[0].board.items), depth=outline.sections[i].get("depth"),
1329:                               exercise=(ex.question if ex is not None else None), **correlation)
1330:             covered.append(outline.sections[i]["title"])
1331:         self.log.emit(EventType.LESSON, now(), stage="planned", title=outline.title, **correlation)
1332: 
1333:     async def _check_section(self, planner, outline, i: int, lines, *, revised: bool = False, profile=None,

===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1461-1515 =====
1461:             self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
1462:         else:
1463:             if term:  # the confirmation is spoken only after the erasure is verified (below)
1464:                 decision = {**decision, "steps": []}
1465:             queued_before = {id(x) for x in self.director.queue}
1466:             self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
1467:             applied = True
1468:             self._decisions += 1  # only applied decisions end the post-interruption wait
1469:             if self.answer_boards and (decision or {}).get("kind") == "content" \
1470:                     and self.director.answer_board_missing(decision):
1471:                 segs = [x for x in self.director.queue if id(x) not in queued_before and x.board is None and x.line]
1472:                 if segs:  # the responder left it out: write one now and show it from the next unlocked line
1473:                     self._spawn(self._answer_board(utt.text, segs), "answer_board")
1474:             self._make_figures()
1475:             kind = (decision or {}).get("kind")
1476:             if kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
1477:                 topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
1478:                 self._start_lesson(topic, utt.lesson_context, utt.request_id)
1479:             elif kind == "lesson_stop":
1480:                 self._stop_lesson()
1481:             elif kind == "exercise" and self.director.exercise is not None:
1482:                 self.director.remind_exercise()  # one exercise at a time: the open one first
1483:             elif kind == "exercise":
1484:                 topic = utt.lesson_context["topic"] if utt.lesson_context else \
1485:                     str((decision or {}).get("topic") or "").strip() or self.director.lesson_title or "刚才讲的内容"
1486:                 self._spawn(self._give_exercise(topic, utt.lesson_context, input_epoch=epoch,
1487:                                                 profile_epoch=self._profile_epoch, plan_version=self.director.plan_version,
1488:                                                 request_id=utt.request_id), "exercise")
1489:             elif self.director.exercise is not None:
1490:                 self.director.remind_exercise()  # a question while an exercise waits: back to it afterwards
1491:             if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
1492:                 changed = self.student.apply_update(decision["profile_update"])
1493:                 if changed:
1494:                     self._save_profile()
1495:                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
1496:                     self._emit_profile()
1497:         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
1498:         if term and self.memory is not None and hasattr(self.memory, "forget"):
1499:             complete = await self._erase(term)
1500:             line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
1501:             self.director.say_verified(line)  # a verified statement: not subject to the narration guard
1502:         if term:  # the decision itself names erased terms
1503:             raw = json.dumps(decision, ensure_ascii=False)
1504:             for x in sorted(self.director.erased_terms, key=len, reverse=True):
1505:                 raw = raw.replace(x, "[已删除]")
1506:             decision = json.loads(raw)
1507:         outcome = {**correlation, "applied": applied} if correlation else {}
1508:         self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
1509:                       chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1510:                       recalled=list(memories or []), **outcome)
1511:         return decision
1512: 
1513:     async def _erase(self, term: str) -> bool:
1514:         async with self._erase_lock:  # erasures are serialized; each owns the erasure gate
1515:             return await self._erase_locked(term)

===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1600-1624 =====
1600:                           detail=str(getattr(report, "errors", "")), pending_targets=pending)
1601:         self._maybe_finish()
1602:         return complete
1603: 
1604:     def snapshot(self) -> dict[str, Any]:
1605:         """Compact live state for the web demo panel (no media, no prompts)."""
1606:         d = self.director
1607:         return {
1608:             "chains": [{"id": c.chain_id, "status": c.status.value, "kind": c.kind.value, "intent": c.final_intent,
1609:                         "revisions": len(c.revisions), "steps": [x for x in c.steps if x],
1610:                         "step_index": c.step_index, "requests": list(c.requests[-6:])}
1611:                        for c in list(d.chains.values())[-12:]],
1612:             "next_lock": self.next_lock, "plan_version": d.plan_version,
1613:             "lambda_s": round(self.sched.lambda_estimate(), 2), "listening": d.listening,
1614:             "awaiting_decision": d.awaiting_decision, "erasure_gate_open": self._ready.is_set(),
1615:             "queued_segments": len(d.queue), "mode": d.mode.value,
1616:             "exercise": ({"concept": d.exercise.concept, "kind": d.exercise.kind,
1617:                           "question": d.exercise.question, "option_texts": list(d.exercise.options),
1618:                           "options": [o[:1] for o in d.exercise.options],
1619:                           **({"request_id": d.exercise.request_id} if d.exercise.request_id is not None else {})}
1620:                          if d.exercise is not None else None),
1621:         }
1622: 
1623:     def open_chains(self) -> list[str]:
1624:         return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]

===== CURRENT SOURCE: live_agent/backend/app.py, lines 35-55 =====
35: def _validated_lesson_context(curriculum, value) -> dict | None:
36:     if not isinstance(value, dict) or type(value.get("grade")) is not int:
37:         return None
38:     subject, grade, topic = value.get("subject"), value["grade"], value.get("topic")
39:     if not isinstance(subject, str) or not isinstance(topic, str) or not 1 <= grade <= 12:
40:         return None
41:     for entry in curriculum.subjects:
42:         grades = entry.get("grade_topics")
43:         if entry.get("subject") != subject or not isinstance(grades, dict):
44:             continue
45:         chapter = grades.get(str(grade))
46:         if isinstance(chapter, dict) and isinstance(chapter.get("topics"), list) and any(
47:                 isinstance(title, str) and title.strip() == topic for title in chapter["topics"]):
48:             return {"subject": subject, "grade": grade, "topic": topic}
49:     return None
50: 
51: 
52: def build_app(args: argparse.Namespace) -> FastAPI:
53:     app = FastAPI(title="Live Agent Backend", version="1.0")
54: 
55:     @app.middleware("http")

===== CURRENT SOURCE: live_agent/backend/app.py, lines 335-356 =====
335:                 data = json.loads(msg["text"])
336:                 t = data.get("type")
337:                 if t in ("chunk_start", "chunk_end", "chunk_received"):
338:                     transport.on_client_message(data)
339:                 elif t == "speech_start":
340:                     await orch.on_speech_start()
341:                 elif t == "text" and data.get("text", "").strip():
342:                     request_id = data.get("request_id")
343:                     if "request_id" in data and (not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 64):
344:                         await ws.send_json({"type": "error", "error": "invalid request_id"})
345:                         continue
346:                     lesson_context = None
347:                     if "lesson_context" in data:
348:                         lesson_context = _validated_lesson_context(curriculum, data["lesson_context"])
349:                         if lesson_context is None:
350:                             await ws.send_json({"type": "error", "error": "invalid catalogue topic selection"})
351:                             continue
352:                     # a typed instruction interrupts like speech does (before its LLM work is queued)
353:                     await orch.on_speech_start()
354:                     inputs.put_nowait(("text", data["text"].strip(), transport._to_server(data), orch.input_epoch, lesson_context, request_id))
355:                 elif t == "audio_end":  # precedes the recorded audio bytes
356:                     audio_end = transport._to_server(data)

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 448-480 =====
448:       " · " + (SRC[c.source] || tr("profile.source.none", "无记录依据")) +
449:       (typeof c.attempts === "number" ? " · " + tr("profile.attempts", "记录练习：") + (c.correct ?? 0) + "/" + c.attempts + tr("profile.correct", " 次正确") : "");
450:     return `<div class="concept-record"><div class="cp ${esc(c.level)}${flash === c.name ? " flash" : ""}" tabindex="0" aria-describedby="concept-evidence-${index}" title="${esc(evidence)}">
451:       <span>${esc(c.name)}</span><span class="bar" aria-hidden="true"><i style="width:${Math.round((c.mastery ?? 0) * 100)}%"></i></span>
452:       <span class="v">${c.mastery == null ? "–" : (c.source === "exam" ? "≈" : "") + Math.round(c.mastery * 100) + "%"}</span></div>
453:       <p class="meta concept-evidence" id="concept-evidence-${index}">${esc(evidence)}</p></div>`;
454:   }).join("");
455:   el.innerHTML = `<div class="who">${esc(p.name || tr("profile.learner", "同学"))} · ${esc(p.grade || tr("profile.gradeMissing", "年级未填"))}</div>` +
456:     (exams ? `<ul class="exams">${exams}</ul>` : `<div class="meta">${esc(tr("profile.noExams", "还没有考试成绩"))}</div>`) +
457:     (cps ? `<div class="meta">${esc(tr("profile.mastery", "知识点掌握度（未校准的估计；每条记录下方列出依据）"))}</div>` + cps : `<div class="meta">${esc(tr("profile.noConcepts", "做练习后，这里会出现知识点记录。"))}</div>`);
458: }
459: $("profEdit").onclick = () => {
460:   const id = profile ? profile.id : $("sid").value;
461:   window.location.href = `/profile?student=${encodeURIComponent(id)}&edition=${encodeURIComponent(window.LiveAgentProduct?.edition || "primary")}`;
462: };
463: function showExercise(ex, requestId = ex?.request_id ?? null) {  // answer buttons while an exercise waits; the persona's examples otherwise
464:   if (!acceptsActivity(requestId)) {
465:     if (currentExercise && !acceptsActivity(currentExercise.request_id ?? null)) {
466:       currentExercise = null; exerciseKey = ""; renderExerciseChips(null);
467:     }
468:     return;
469:   }
470:   currentExercise = ex || null;
471:   const key = ex ? JSON.stringify([requestId, ex.concept, ex.question, ex.options || [], ex.option_texts || []]) : "";
472:   if (key === exerciseKey) return;
473:   exerciseKey = key;
474:   renderExerciseChips(currentExercise);
475: }
476: function renderExerciseChips(ex) {
477:   const live = ready();
478:   if (!ex) { setChips(sessionStatus?.board ? idleExamples() : personaChips, live); return; }
479:   setChips([...(ex.options || []).map((o, index) => ({label: tr("exercise.choose", "选 ") + o, text: "选 " + o,
480:               description: ex.option_texts?.[index] ? tr("exercise.choose", "选 ") + o + ": " + ex.option_texts[index] : undefined})),

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 995-1039 =====
995:     recording.start();
996:     if (!send({type: "speech_start"}, socket)) throw new Error("Unable to start voice input");
997:     productEvent("submitted", {request_id: null});
998:     duck(true); $("talk").classList.add("recording"); $("talk").textContent = tr("voice.release", "松开发送");
999:   } catch (error) {
1000:     stream?.getTracks().forEach(track => track.stop());
1001:     if (request === micRequest && activeSocket(socket, attempt)) {
1002:       cancelSpeech(); permissionNotice("voice", error);
1003:     }
1004:   }
1005: };
1006: function endSpeech(cancel = false) {
1007:   if (cancel) { cancelSpeech(); return; }
1008:   if (!micPressed) return;
1009:   micPressed = false;
1010:   duck(false);
1011:   if (recorder?.state === "recording") { recorder.endedAt = performance.now(); recorder.stop(); }
1012:   else micRequest++;  // releasing while permission is pending cancels that request
1013:   resetTalkButton();
1014: }
1015: $("talk").onpointerup = () => endSpeech();
1016: $("talk").onpointerleave = event => { if (!$("talk").hasPointerCapture?.(event?.pointerId)) endSpeech(); };
1017: $("talk").onpointercancel = () => endSpeech();
1018: $("talk").onkeydown = event => {
1019:   if ([" ", "Enter"].includes(event.key) && !event.repeat) { event.preventDefault(); $("talk").onpointerdown(); }
1020: };
1021: $("talk").onkeyup = event => {
1022:   if ([" ", "Enter"].includes(event.key)) { event.preventDefault(); endSpeech(); }
1023: };
1024: $("talk").onblur = () => { if (micPressed) endSpeech(); };
1025: addEventListener("blur", () => { if (micPressed || recorder) endSpeech(); });
1026: function sendText(v, lessonContext, requestId) {
1027:   v = (v ?? $("text").value).trim(); if (!v || !ready()) return false;
1028:   const packet = {type: "text", text: v, tp: performance.now()};
1029:   if (typeof requestId === "string") packet.request_id = requestId;
1030:   if (lessonContext && typeof lessonContext.subject === "string" && lessonContext.subject.trim() &&
1031:       Number.isInteger(lessonContext.grade) && lessonContext.grade >= 1 && lessonContext.grade <= 12 &&
1032:       typeof lessonContext.topic === "string" && lessonContext.topic.trim()) {
1033:     packet.lesson_context = {subject: lessonContext.subject.trim(), grade: lessonContext.grade, topic: lessonContext.topic.trim()};
1034:   }
1035:   if (!send(packet)) {
1036:     notice("session.sendFailed", "消息还没有发出去，请重新连接后再试。"); return false;
1037:   }
1038:   productEvent("submitted", {request_id: requestId ?? null});
1039:   chat("user", v); $("text").value = ""; return true;
===== FILE: live_agent/exercise.py =====
"""Exercises the teacher gives: shown on the board, answered by voice or text, graded, fed back into the profile.

An exercise is either multiple choice (graded by rule: the letter, or the option's text) or a short answer
(exact match by rule, else graded by the LLM against the reference answer). A pending exercise pauses the
lesson: the next lesson line waits until the student answers (or says they do not know).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from live_agent.lesson import Board, LessonLine, spoken
from live_agent.llm import ChatLLM, parse_json

LETTERS = "ABCD"
SKIP = re.compile(r"^(我)?(不会|不知道|跳过|不懂|想不出来?|没思路|算了)(做|写)?(吧|啊|呢)?[。.!！]?$")
# not a plain answer: a negation, a question or a hedge goes to the LLM ("我不选B", "B是什么意思？", "不会是B吧")
NOT_PLAIN = re.compile(r"不|没|别|吗|什么|为什么|怎么|哪|[?？]|或者|还是|吧")

EXERCISE_PROMPT = """你是用中文教学的老师「{name}」。请给学生出一道关于「{topic}」的练习题。
学生档案：
{profile}
难度按学生情况定：这个知识点薄弱就出基础题（直接用定义或公式一步能做），基本理解出中等题，已掌握出稍有变化的题；按学生年级出题。
{craft}{exercise_spec}"""

EXERCISE_SPEC = """练习题格式（只输出 JSON）：
{{"exercise": {{"concept": 考查的概念（用档案里已有的概念名，没有就写一个不超过 8 字的名称）, "subject": 学科,
  "type": "choice" 或 "short", "question": 题目（不超过 {q_chars} 字，公式写在 $...$ 里）,
  "options": ["A. …", "B. …", "C. …", "D. …"]（选择题才有，每项不超过 20 字）,
  "answer": 选择题写字母（如 "B"），简答题写最简答案（一个数、一个词或一个式子）,
  "explanation": [讲解为什么，1-2 句，每句不超过 {chars} 个汉字，口语化，公式用中文读出来；不要只重复选哪个]}}}}
选择题的错误选项要对应常见的错误想法。"""

GRADE_PROMPT = """你是老师，正在批改学生的口头回答。
题目：{question}
{options}参考答案：{answer}
讲解：{explanation}
学生说：「{said}」
先判断学生这句话是不是在回答这道题（是答案、写出了结果或说不会，都算回答；问别的问题、聊别的事不算）。
是回答时判断对错（意思对、等价的式子或数值都算对）；错了用一句话指出学生的错误想法。
只输出 JSON：{{"is_answer": true 或 false, "correct": true 或 false, "misconception": 错误想法（答对时为 null）,
"feedback": [老师回应，2-3 句，每句不超过 {chars} 个汉字，口语化：答对先肯定再点出关键；答错先鼓励，再讲正确思路和答案；公式用中文读出来]}}"""


@dataclass
class Exercise:
    concept: str
    question: str
    answer: str
    kind: str = "short"  # "choice" | "short"
    options: list[str] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    subject: str = ""
    key: str = "x"
    source: str = "lesson"  # "lesson" (pauses the lesson) | "asked" (the student asked for one)
    request_id: str | None = None  # activity owner assigned by the orchestrator, never by generated JSON

    @classmethod
    def from_dict(cls, d: Any, key: str, source: str = "lesson") -> Exercise | None:
        if not isinstance(d, dict):
            return None
        q, ans = str(d.get("question") or "").strip(), str(d.get("answer") or "").strip()
        if not q or not ans:
            return None
        expl = d.get("explanation") or []
        expl = [str(x) for x in (expl if isinstance(expl, list) else [expl]) if str(x).strip()]
        ex = cls(concept=str(d.get("concept") or "").strip()[:20] or "练习", question=q[:120], answer=ans[:60],
                 explanation=expl[:3], subject=str(d.get("subject") or "")[:12], key=key, source=source)
        opts = [str(x).strip()[:40] for x in (d.get("options") or []) if str(x).strip()][:4]
        if str(d.get("type") or "") == "choice" or opts:
            letter = ans.upper()[:1]
            if len(opts) < 2 or letter not in LETTERS[: len(opts)]:
                return None
            ex.kind, ex.answer = "choice", letter
            ex.options = [o if re.match(r"^[A-D][.．、:：]", o) else f"{LETTERS[i]}. {o}" for i, o in enumerate(opts)]
        return ex

    def board(self, reveal_answer: bool = False) -> Board:
        items = [self.question, *self.options]
        if reveal_answer:
            items.append(f"答案：{self.answer_text()}")
        return Board(key=self.key + ("a" if reveal_answer else ""), title=f"练习 · {self.concept}"[:24], items=items)

    def answer_text(self) -> str:
        if self.kind == "choice":
            i = LETTERS.index(self.answer)
            return self.options[i] if i < len(self.options) else self.answer
        return self.answer

    def lines(self, chars: int) -> list[LessonLine]:
        """The teacher poses it: the board shows the question (and options)."""
        b = self.board()
        out = [LessonLine("我们来做一道练习。", b, None, gesture=True)]
        out += [LessonLine(p, b, None) for p in spoken(self.question, chars)]  # question and options all shown
        out.append(LessonLine("选项在黑板上，选好了告诉我。" if self.kind == "choice" else "想好了把答案告诉我。", b, None))
        for ln in out:  # any of them opens the exercise: an answer given while it is still being read out counts
            ln.exercise = self
        return out


def _norm(s: str) -> str:
    s = re.sub(r"^(我觉得|我选|选|答案是|答案|应该是|是)", "", s.strip())
    s = re.sub(r"^\s*[a-zA-Z]\s*[=＝]", "", s)  # "x = 3" -> "3"
    return re.sub(r"[\s，。,.!！?？$:：=＝]", "", s).lower()


def quick_grade(ex: Exercise, said: str) -> dict | None:
    """Rule grading when it is unambiguous; None when the LLM must judge."""
    text = said.strip()
    if SKIP.match(text):
        return {"is_answer": True, "correct": False, "skipped": True, "misconception": None}
    if NOT_PLAIN.search(text):
        return None
    if ex.kind == "choice":
        letters = set(re.findall(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", text))
        if len(letters) == 1 and len(text) <= 16:
            got = letters.pop().upper()
            return {"is_answer": True, "correct": got == ex.answer, "given": got, "misconception": None}
        for i, o in enumerate(ex.options):  # the option's own text ("选相等的那个" is left to the LLM)
            body = re.sub(r"^[A-D][.．、:：]\s*", "", o)
            if body and _norm(body) == _norm(text):
                return {"is_answer": True, "correct": LETTERS[i] == ex.answer, "given": LETTERS[i],
                        "misconception": None}
        return None
    if _norm(text) and _norm(text) == _norm(ex.answer):
        return {"is_answer": True, "correct": True, "misconception": None}
    return None


async def grade(llm: ChatLLM, ex: Exercise, said: str, chars: int = 22) -> dict:
    """Grade the student's reply: rules first, then the LLM. Always returns is_answer / correct / feedback."""
    r = quick_grade(ex, said)
    if r is not None:
        r["feedback"] = feedback_lines(ex, r, chars)
        return r
    opts = ("选项：" + " ".join(ex.options) + "\n") if ex.options else ""
    raw = await llm.chat([{"role": "user", "content": GRADE_PROMPT.format(
        question=ex.question, options=opts, answer=ex.answer_text(), explanation="".join(ex.explanation) or "无",
        said=said[:200], chars=chars)}], max_tokens=400, temperature=0.0, json_mode=True)
    d = parse_json(raw)
    if not isinstance(d, dict) or not isinstance(d.get("is_answer"), bool):
        raise ValueError("grader reply without a boolean is_answer")
    if not d["is_answer"]:
        return {"is_answer": False, "correct": False, "misconception": None}
    if not isinstance(d.get("correct"), bool):
        raise ValueError("grader reply without a boolean correct")
    mis = d.get("misconception")
    r = {"is_answer": True, "correct": d["correct"],
         "misconception": str(mis)[:40] if isinstance(mis, str) and mis.strip() and not d["correct"] else None}
    fb = d.get("feedback")
    fb = [fb] if isinstance(fb, str) else fb if isinstance(fb, list) else []
    said_fb = [p for x in fb if isinstance(x, str) for p in spoken(x, chars)][:4]
    r["feedback"] = feedback_lines(ex, r, chars, said_fb)
    return r


def feedback_lines(ex: Exercise, r: dict, chars: int, llm_lines: list[str] | None = None) -> list[str]:
    """What the teacher says after grading: praise or the correct answer, then the explanation."""
    if llm_lines:
        lines = list(llm_lines)
        stated = re.compile(rf"(答案|应该)(是|选)\s*{ex.answer}|选\s*{ex.answer}(?![A-Za-z])")
        if not r["correct"] and ex.kind == "choice" and not any(stated.search(x) for x in lines):
            lines.insert(1 if len(lines) > 1 else 0, f"正确答案是 {ex.answer}。")
        return lines
    expl = [p for x in ex.explanation for p in spoken(x, chars)][:3]
    if r.get("skipped"):
        head = ["没关系，我们一起来看。"]
        head += [f"答案是 {ex.answer}。"] if ex.kind == "choice" else spoken(f"答案是{ex.answer}。", chars)
        return head + expl
    if r["correct"]:
        return ["答对了，很好！"] + expl[:2]
    head = [f"不太对哦，正确答案是 {ex.answer}。"] if ex.kind == "choice" else \
        ["不太对哦，我们看一下。"] + spoken(f"答案是{ex.answer}。", chars)
    return head + expl


async def make_exercise(llm: ChatLLM, *, name: str, topic: str, profile: str, key: str, chars: int = 22,
                        source: str = "asked", craft: str = "") -> Exercise:
    """``craft``: the curriculum's practice-design rules for the student's grade ("" without craft data)."""
    raw = await llm.chat([{"role": "user", "content": EXERCISE_PROMPT.format(
        name=name, topic=topic, profile=profile, craft=(craft + "\n") if craft else "",
        exercise_spec=EXERCISE_SPEC.format(chars=chars, q_chars=60))}],
        max_tokens=600, temperature=0.5, json_mode=True)
    d = parse_json(raw)
    ex = Exercise.from_dict(d.get("exercise", d), key=key, source=source)
    if ex is None:
        raise ValueError("no usable exercise in the reply")
    return ex


__all__ = ["EXERCISE_SPEC", "Exercise", "feedback_lines", "grade", "make_exercise", "quick_grade"]

===== FILE: tests/test_activity_requests.py =====
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
    for chunk in range(4):
        log.emit(EventType.CHUNK_PRESENTED, request_index=0, chunk_index=chunk, chunks_per_request=4,
                 request_complete=chunk == 3)
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
                                   "kind": "script_aid", "verified_audio": False, "omitted_partial_requests": [], "entries": [
                                       {"role": "user", "text": "给我讲加法。", "source": "utterance_end"},
                                       {"role": "teacher", "text": "一加一等于二。", "source": "lock", "request_index": 0,
                                        "presented": True, "kind": "planned_script", "may_include_unplayed_words": True,
                                        "presentation": {"status": "complete", "chunks_acknowledged": [0, 1, 2, 3], "chunks_expected": 4}},
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


def test_declared_media_base_owns_ambiguous_part_names_in_index_and_files(tmp_path):
    directory = tmp_path / "logs"
    saved_trace(directory, "sess-a", "private", "alpha")
    saved_trace(directory, "sess-a-part2", "private", "beta")
    (directory / "sess-a-part3.mp4").write_bytes(b"alpha part 3")
    (directory / "sess-a-part2.mp4").write_bytes(b"beta base")
    with TestClient(backend(tmp_path, "alpha,beta")) as client:
        a = client.get("/api/traces?student=alpha").json()["sessions"][0]
        b = client.get("/api/traces?student=beta").json()["sessions"][0]
        assert {v["name"] for v in a["videos"]} == {"sess-a.mp4", "sess-a.generated.mp4", "sess-a-part3.mp4"}
        assert {v["name"] for v in b["videos"]} == {"sess-a-part2.mp4", "sess-a-part2.generated.mp4", "sess-a-part2-part2.mp4"}
        operator = client.get("/api/traces").json()["sessions"]
        names = [video["name"] for session in operator for video in session["videos"]]
        assert len(names) == len(set(names))
        assert client.get("/traces/file/sess-a-part2.mp4?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-a-part2.mp4?student=beta").content == b"beta base"
        assert client.get("/traces/file/sess-a-part3.mp4?student=alpha").content == b"alpha part 3"
        assert client.get("/traces/file/sess-a-part2-part2.mp4?student=alpha").status_code == 404
        assert client.get("/traces/file/sess-a-part2.generated.mp4?student=beta").status_code == 200


def test_script_aid_omits_known_partial_requests_and_labels_legacy_uncertainty(tmp_path):
    from live_agent.timeline import EventLog
    from live_agent.types import EventType

    directory = tmp_path / "logs"
    saved_trace(directory, "sess-alpha", "private", "alpha")
    log = EventLog(directory / "sess-alpha.jsonl")
    log.emit(EventType.LOCK, request_index=2, transcript="前半句可能播放了，后半句没有。")
    log.emit(EventType.CHUNK_PRESENTED, request_index=2, chunk_index=0, chunks_per_request=4, request_complete=False)
    log.emit(EventType.LOCK, request_index=3, transcript="旧日志没有完整播放信息。")
    log.emit(EventType.CHUNK_PRESENTED, request_index=3, chunk_index=0)
    log.close()
    with TestClient(backend(tmp_path, "alpha")) as client:
        result = client.get("/api/traces/sess-alpha/transcript?student=alpha").json()
        assert result["kind"] == "script_aid" and result["verified_audio"] is False
        assert result["omitted_partial_requests"] == [2]
        teacher = [entry for entry in result["entries"] if entry["role"] == "teacher"]
        assert [entry["request_index"] for entry in teacher] == [0, 3]
        assert all(entry["kind"] == "planned_script" and entry["may_include_unplayed_words"] for entry in teacher)
        assert teacher[0]["presentation"]["status"] == "complete"
        assert teacher[1]["presentation"] == {"status": "unknown", "chunks_acknowledged": [0], "chunks_expected": None}


def test_presentation_events_record_expected_chunks_and_full_request_end():
    import test_pipeline as pipeline
    from live_agent.types import EventType

    orch, _ = pipeline.build()
    orch.cfg.qc_enabled = False
    for chunk in range(orch.n_chunks):
        orch.on_presented(0, chunk, float(chunk), float(chunk + 1))
    events = [event for event in orch.log.events if event.type == EventType.CHUNK_PRESENTED]
    assert len(events) == orch.n_chunks
    assert all(event.data["chunks_per_request"] == orch.n_chunks for event in events)
    assert [event.data["request_complete"] for event in events] == [False] * (orch.n_chunks - 1) + [True]


def test_text_request_ids_round_trip_in_initial_and_decision_panel_events(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
            outcomes = []
            for request_id, text in (("chat-A", "你好"), ("practice-B", "再聊一句"), (None, "普通消息")):
                packet = {"type": "text", "text": text}
                if request_id is not None:
                    packet["request_id"] = request_id
                ws.send_json(packet)
                records = []
                while True:
                    message = ws.receive()
                    if "text" not in message:
                        continue
                    event = json.loads(message["text"])
                    if event.get("event") == "utterance_end":
                        records.append(event["data"])
                        if "decision" in event["data"]:
                            break
                assert len(records) == 2 and records[0]["text"] == text
                assert records[0]["uid"] == records[1]["uid"]
                if request_id is None:
                    assert all("request_id" not in record and "applied" not in record for record in records)
                else:
                    assert all(record["request_id"] == request_id for record in records)
                    assert "applied" not in records[0] and records[1]["applied"] is True
                outcomes.append(records[1])
            assert outcomes[0]["request_id"] != outcomes[1]["request_id"]


def test_invalid_request_ids_are_not_queued_and_maximum_id_is_preserved(tmp_path, monkeypatch):
    from live_agent.orchestrator import Orchestrator

    received = []

    async def capture(self, utterance, **kwargs):
        received.append(utterance)
        await self.transport.send_json({"type": "received_for_test"})

    monkeypatch.setattr(Orchestrator, "on_user_utterance", capture)
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private"})
            for invalid in (None, True, 3, "", "   ", "r" * 65):
                ws.send_json({"type": "text", "text": "不要排队", "request_id": invalid})
                while True:
                    message = ws.receive()
                    if "text" in message:
                        payload = json.loads(message["text"])
                        if payload.get("type") == "error":
                            assert payload["error"] == "invalid request_id"
                            break
            valid = "r" * 64
            ws.send_json({"type": "text", "text": "有效消息", "request_id": valid})
            while True:
                message = ws.receive()
                if "text" in message and json.loads(message["text"]).get("type") == "received_for_test":
                    break
            assert len(received) == 1 and received[0].request_id == valid


def test_grading_result_keeps_the_answer_request_id_in_panel_events():
    import asyncio
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.exercise import Exercise
    from live_agent.types import EventType, Utterance, now

    orch, _ = pipeline.build()
    orch.director.exercise = Exercise("加法", "一加一等于几？", "二")
    result = asyncio.run(orch.on_user_utterance(Utterance("server-uid", "user", "二", now(), request_id="answer-ticket")))
    assert result["exercise_result"]["correct"]
    events = [panel_event(event, 0)["data"] for event in orch.log.events if event.type == EventType.UTTERANCE_END]
    assert len(events) == 2 and all(event["request_id"] == "answer-ticket" for event in events)
    assert all(event["uid"] == "server-uid" for event in events)
    assert events[1]["decision"]["exercise_result"]["correct"]
    assert "applied" not in events[0] and events[1]["applied"] is True


def test_correlated_decision_reports_not_applied_after_a_newer_input():
    import asyncio
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.types import EventType, Utterance, now

    async def scenario():
        orch, _ = pipeline.build()
        entered, release = asyncio.Event(), asyncio.Event()

        class HeldDecision:
            async def chat(self, messages, **kwargs):
                assert messages[0]["role"] == "system"  # skipped request must never begin exercise generation
                if "考考我" in messages[-1]["content"]:
                    entered.set()
                    await release.wait()
                    return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
                return json.dumps({"kind": "chat", "steps": []})

        orch.director.llm = HeldDecision()
        await orch.on_speech_start()
        old = asyncio.create_task(orch.on_user_utterance(Utterance("B", "user", "考考我", now(), request_id="B-ticket")))
        await asyncio.wait_for(entered.wait(), timeout=2)
        await orch.on_speech_start()
        await orch.on_user_utterance(Utterance("C", "user", "换个话题", now(), request_id="C-ticket"))
        release.set()
        returned = await old
        assert returned["kind"] == "exercise"  # existing server return semantics stay compatible
        assert not orch._aux and orch.director.exercise is None
        outcomes = {event.data["request_id"]: panel_event(event, 0)["data"] for event in orch.log.events
                    if event.type == EventType.UTTERANCE_END and "decision" in event.data}
        assert outcomes["B-ticket"]["applied"] is False and outcomes["B-ticket"]["decision"]["kind"] == "exercise"
        assert outcomes["C-ticket"]["applied"] is True
        assert any(event.type == EventType.CAPACITY_SKIP and event.data.get("uid") == "B" for event in orch.log.events)

    asyncio.run(scenario())


def test_correlated_grading_supersession_reports_not_applied():
    import asyncio
    import test_pipeline as pipeline
    from live_agent.backend.transport import panel_event
    from live_agent.exercise import Exercise
    from live_agent.types import EventType, Utterance, now

    async def scenario():
        orch, _ = pipeline.build()
        entered, release = asyncio.Event(), asyncio.Event()
        orch.director.exercise = Exercise("加法", "一加一等于几？", "二")

        class HeldGrade:
            async def chat(self, messages, **kwargs):
                entered.set()
                await release.wait()
                return json.dumps({"is_answer": True, "correct": True, "feedback": ["答对了。"]}, ensure_ascii=False)

        orch.director.llm = HeldGrade()
        old = asyncio.create_task(orch.on_user_utterance(Utterance("answer", "user", "可能是二", now(), request_id="answer-ticket")))
        await asyncio.wait_for(entered.wait(), timeout=2)
        await orch.on_speech_start()
        release.set()
        returned = await old
        assert returned["superseded"] is True
        outcome = next(panel_event(event, 0)["data"] for event in orch.log.events
                       if event.type == EventType.UTTERANCE_END and "decision" in event.data)
        assert outcome["request_id"] == "answer-ticket" and outcome["applied"] is False
        assert not any(event.type == EventType.LESSON and event.data.get("stage") == "exercise_graded" for event in orch.log.events)

    asyncio.run(scenario())


def test_newer_websocket_text_supersedes_a_held_decision_without_speech_start(tmp_path, monkeypatch):
    import asyncio
    import threading
    from live_agent.llm import RuleResponder

    entered, release = threading.Event(), threading.Event()
    calls = []

    async def held_chat(self, messages, **kwargs):
        # This is the actual responder path. Exercise generation must never begin for B.
        assert messages[0]["role"] == "system"
        text = messages[-1]["content"]
        calls.append(text)
        if text == "考考我":
            entered.set()
            assert await asyncio.to_thread(release.wait, 5), "test did not release held decision"
            return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
        return json.dumps({"kind": "chat", "steps": []})

    monkeypatch.setattr(RuleResponder, "chat", held_chat)
    messages = []
    try:
        with TestClient(backend(tmp_path)) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
                ws.send_json({"type": "text", "text": "考考我", "request_id": "B-ticket"})
                assert entered.wait(3), "B did not reach the held responder"
                ws.send_json({"type": "text", "text": "换个话题", "request_id": "C-ticket"})
                ws.send_json({"type": "ping", "t": "C-received"})
                while True:
                    packet = ws.receive()
                    if "text" not in packet:
                        continue
                    message = json.loads(packet["text"])
                    messages.append(message)
                    if message.get("type") == "pong" and message.get("t") == "C-received":
                        break  # the receive loop has queued C and stamped its newer epoch
                release.set()
                outcomes = {}
                while len(outcomes) < 2:
                    packet = ws.receive()
                    if "text" not in packet:
                        continue
                    message = json.loads(packet["text"])
                    messages.append(message)
                    if message.get("event") == "utterance_end" and "decision" in message["data"]:
                        outcomes[message["data"]["request_id"]] = message["data"]
                assert outcomes["B-ticket"]["decision"]["kind"] == "exercise"
                assert outcomes["B-ticket"]["applied"] is False
                assert outcomes["C-ticket"]["applied"] is True
    finally:
        release.set()
    assert calls == ["考考我", "换个话题"]
    assert not any(message.get("event") == "lesson" and message["data"].get("request_id") == "B-ticket"
                   for message in messages)
    logged = [json.loads(line) for path in (tmp_path / "logs").glob("*.jsonl") for line in path.read_text().splitlines()]
    assert not any(event["type"] == "lesson" and event["data"].get("request_id") == "B-ticket" for event in logged)

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
                page.evaluate("""() => {window.__originalStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('controlled storage failure');};}""")
                page.locator('#notes').fill('Unsaved fixture note')
                assert '失败' in page.locator('#noteStatus').inner_text()
                page.locator('#edition').select_option('university')
                assert 'Could not save' in page.locator('#noteStatus').inner_text()
                page.locator('#edition').select_option('secondary')
                assert '失败' in page.locator('#noteStatus').inner_text()
                page.evaluate('() => {Storage.prototype.setItem=window.__originalStorageSet;}')
                page.locator('#notes').fill('Student A private note')
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
                page.evaluate("""() => {window.__sentTexts=[];window.__lessonContexts=[];window.__requestIds=[];const original=ws.send.bind(ws);ws.send=data=>{try{const packet=JSON.parse(data);if(packet.type==='text'){window.__sentTexts.push(packet.text);window.__requestIds.push(packet.request_id);if(packet.lesson_context)window.__lessonContexts.push(packet.lesson_context);return;}}catch{};original(data);};window.LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}""")
                assert 'cannot create lessons' not in page.locator('#runtimeNotice').inner_text()
                page.locator('#gradeFilter').select_option('3')
                page.locator('#subjectFilter').select_option('数学')
                page.locator('.course-card').first.click()
                page.locator('#startLesson').click()
                assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
                assert page.evaluate('window.__lessonContexts.at(-1).grade')==3
                assert page.evaluate('window.__lessonContexts.at(-1).subject')=='数学'
                assert page.evaluate('window.__lessonContexts.at(-1).topic')==page.locator('#lessonTopic').input_value()
                page.locator('#practice').click()
                assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
                assert page.evaluate('window.__lessonContexts.at(-1).grade')==3
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:'UNRELATED-OLD-TURN',decision:{kind:'chat'}}}}))")
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),decision:{kind:'chat'}}}}))")
                assert 'did not start' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'exercise_failed'}}}))")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.__oldActivity=window.__requestIds.at(-1);window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))" )
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("sendText('Newer ordinary question')")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__oldActivity,stage:'exercise_open',question:'LATE OLD QUESTION'}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                assert 'LATE OLD QUESTION' not in page.locator('#exerciseQuestion').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__oldActivity,stage:'outline',title:'LATE OLD OUTLINE'}}}))")
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),applied:false,decision:{kind:'exercise'}}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.locator('#lessonTopic').fill('Custom empty-topic fixture')
                page.locator('#startLesson').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),decision:{kind:'lesson',topic:''}}}}))")
                assert 'did not start' in page.locator('#lessonStatus').inner_text()
                page.locator('#startLesson').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'outline_failed'}}}))")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                page.evaluate("sendText('Ordinary text after failed outline')")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'exercise_open',question:'Successful practice fixture'}}}))")
                assert 'question is ready' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.__answerOwner=window.__requestIds.at(-1);sendText('An ordinary answer to the current exercise')")
                assert page.locator('#exerciseCard').is_visible()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__answerOwner,stage:'exercise_graded',correct:true}}}))")
                assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__answerOwner,stage:'exercise_closed'}}}))")
                assert 'question is closed' in page.locator('#lessonStatus').inner_text()
                results.append({'activity outcomes':'correlated decisions, empty-topic lesson, successful practice and failures resolve status'})
                page.evaluate("LiveAgentProduct.sessionChanged('ready',{status:{generator:'taomate_h3',responder:'rules',board:true}})")
                assert 'Video preview' not in page.locator('#runtimeNotice').inner_text()
                assert page.locator('#startLesson').is_disabled()
                results.append({'capability fixtures':'video/responder independently gated; catalogue grade/subject preserved'})
                page.locator('#disconnect').click()
                page.wait_for_function("sessionState === 'disconnected'")
                results.append({'session': 'real CPU connect, text, media and disconnect passed'})
                # A changed learner must not inherit the previous classroom before connecting.
                assert page.locator('#chat .msg').count()
                page.evaluate("""() => {document.getElementById('boardTitle').textContent='LEARNER A BOARD';document.getElementById('memory').textContent='LEARNER A MEMORY';document.getElementById('feed').textContent='LEARNER A EVENTS';}""")
                page.locator('#sid').select_option('learner')
                assert not page.locator('#chat .msg').count()
                assert page.locator('#boardTitle').inner_text()==''
                assert page.locator('#memory').inner_text()==''
                assert page.locator('#feed').inner_text()==''
                assert page.locator('#lessonTopic').input_value()==''
                assert page.evaluate('lastBoard===null && onScreen===null')
                page.locator('#sid').select_option('demo')
                results.append({'learner boundary':'previous chat, media, board, memory and goal clear before reconnect'})
                # Synthetic events are deliberate rendering fixtures, not a generated teaching result.
                page.locator('#edition').select_option('secondary')
                page.evaluate("""() => {showExercise({concept:'Language fixture',kind:'mcq',question:'Which value?',options:['A','B'],option_texts:['A. One','B. Two']});window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'planned'}}}));}""")
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',concept:'Fixture',question:'Which value?',options:['A','B'],option_texts:['A. One','B. Two']}}}));window.__exerciseAnnounced=document.getElementById('exerciseAnnouncement').textContent;window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_graded',correct:false}}}));window.dispatchEvent(new CustomEvent('live-agent:state',{detail:{exercise:null}}));}""")
                assert '有误' in page.locator('#exerciseFeedback').inner_text()
                page.locator('#edition').select_option('university')
                assert page.locator('#exerciseCard').is_visible()
                assert 'A. One' in page.locator('#exerciseQuestion').inner_text()
                assert 'incorrect' in page.locator('#exerciseFeedback').inner_text()
                assert 'feedback is ready' in page.locator('#lessonStatus').inner_text()
                assert 'Choose A' in page.locator('#chips').inner_text()
                page.evaluate('showExercise(null)')
                assert 'Which value?' in page.evaluate('window.__exerciseAnnounced')
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',question:'STALE AFTER ERROR'}}}));finishSession(ws,connectionAttempt,'error','连接发生错误，请重试。');}""")
                assert not page.locator('#exerciseCard').is_visible()
                assert page.locator('#exerciseAnnouncement').text_content()==''
                page.locator('#edition').select_option('secondary')
                page.locator('#edition').select_option('university')
                assert 'session stopped' in page.locator('#overlay').inner_text()
                assert 'session stopped' in page.locator('#connectionErrorText').inner_text()
                results.append({'exercise fixture': 'full question, choices, persistent feedback and active language switch passed'})
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
                page.evaluate("""() => {document.getElementById('caption').textContent='PRIVATE CAPTION';document.getElementById('boardTitle').textContent='PRIVATE BOARD';document.getElementById('memory').textContent='PRIVATE MEMORY';document.getElementById('lessonTopic').value='PRIVATE TOPIC';document.getElementById('exerciseAnnouncement').textContent='PRIVATE QUESTION';document.getElementById('stepPractice').classList.add('current');}""")
                page.locator('#diagnostics').evaluate('(node)=>node.open=true')
                page.locator('#mode').select_option('public')
                assert not page.locator('#profCard').is_visible()
                assert not page.locator('.student-picker').is_visible()
                assert not page.locator('#chat .msg').count()
                assert page.locator('#text').input_value()==''
                assert page.locator('#caption').inner_text()==''
                assert page.locator('#memory').inner_text()==''
                assert page.locator('#lessonTopic').input_value()==''
                assert page.locator('#exerciseAnnouncement').text_content()==''
                assert 'student=' not in page.url and 'mode=public' in page.url
                assert not page.locator('#profileNav').is_visible()
                assert page.locator('#stepPractice').get_attribute('class')!='current'
                assert 'A starting point' in page.locator('#suggestionLabel').inner_text()
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
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#mode').input_value()=='public'
                assert not page.locator('#profCard').is_visible()
                results.append({'privacy': 'public classroom clears private data, identity, screen-reader question and survives reload'})
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
                page.route('**/api/curriculum/topics',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'topics':[{'subject':'','grade':3,'topic':'INVALID EMPTY SUBJECT'},{'subject':'数学','grade':3,'topic':''},{'subject':'   ','grade':3,'topic':'INVALID BLANK SUBJECT'},{'subject':'数学','grade':3,'topic':'  Valid catalogue fixture  ','basis':'textbook'}]})))
                page.goto(origin+'/?edition=primary&mode=public')
                page.wait_for_selector('.course-card')
                assert page.locator('.course-card').count()==1
                page.locator('.course-card').click()
                assert page.locator('#lessonTopic').input_value()=='Valid catalogue fixture'
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'")
                page.evaluate("() => {window.__paddedPackets=[];const original=ws.send.bind(ws);ws.send=data=>{const packet=JSON.parse(data);if(packet.type==='text'){window.__paddedPackets.push(packet);return;}original(data);};LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}")
                page.locator('#startLesson').click()
                assert page.evaluate('window.__paddedPackets.at(-1).lesson_context.topic')=='Valid catalogue fixture'
                page.locator('#practice').click()
                assert page.evaluate('window.__paddedPackets.at(-1).lesson_context.topic')=='Valid catalogue fixture'
                page.locator('#disconnect').click()
                results.append({'catalogue validation':'blank subjects/topics excluded; padded chapter keeps canonical lesson/practice context'})
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
