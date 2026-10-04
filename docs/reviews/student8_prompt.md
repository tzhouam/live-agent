Independent read-only targeted re-review of the three student7 findings and direct regressions in their fixes. Review the actual inlined code, not the contributor summary. Number any remaining concrete findings blocking/major/minor with evidence. Do not broaden to unrelated product roadmap, models, authentication, university curriculum, research or training. No shell execution is possible, evidence is inline, no mutations. PROJECT.md applies.

Fix1: Both activity buttons stay locked throughout a pending button request including question-generated until exercise-open or failure. If a manual/newer request races an already-open server exercise, a correlated exercise_existing event contains the current request ID and authoritative existing question/creator ID. Product accepts only the current response, adopts that creator, clears its pending request, renders that actual question and restores guarded answer chips. Backend creator is never rewritten; exercise/content reminder requests and new-lesson requests while a standalone question is open return this existing question. Replacing a current source=lesson exercise with a new lesson retains prior behavior. Ordinary answers while a shown question is open preserve its creator despite a new answer request ID.

Fix2: Every successful UI text and speech_start has a distinct bounded request_id; provided button activity IDs remain exact. Product retires unowned-event acceptance after modern successful input or terminal failure, while fresh-scope compatibility and an explicitly recovered legacy existing question remain supported. Failures/permission denial do not emit submission. Voice start ID/epoch survives ASR and late recorded bytes so intervening newer text supersedes it. The audio_end/binary and AV clocks/framing stay unchanged. Invalid optional supplied IDs are rejected before interruption/queueing; legacy no-ID packets remain accepted on the backend. Missing non-null exercise snapshots cannot restore stale questions, and null current state clears shown answer controls.

Fix3: Actual WS test accumulates decisions in both pong-wait and completion loops, using a deadline/cancelled bounded receive instead of indefinitely blocking. Existing held-decision guard still applies.

Measured locally so far: final frontend97 passed, affected Python95 passed including six known/legacy existing-question cases, source=lesson replacement compatibility, real ASR/WS ID/epoch validation and text-only supersession. Full CPU suite and extended real-browser/synthetic delayed-event check are running. These checks qualify implementation/transport only; no real teaching model, GPU, physical audiovisual timing, English teaching or learning-efficacy experiment is claimed. Source is stable. Please assess the three named repairs and direct compatibility paths without presuming tests were independently run.

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

===== FILE: docs/reviews/student7_review.md =====
Source-only re-review found **no blocking issue**. Three concrete findings remain:

1. **Major — A second practice request can hide the question already open on the server.** [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) keeps the practice button enabled until `recentExercise` is set by an event received in the browser. If exercise B opens on the server but its `exercise_open` event is delayed, the learner can submit C. The browser then rejects B’s event as old, while the [orchestrator](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1481) only reminds the learner about B and creates no C-owned question. The UI remains waiting for C. Hold B’s open event, submit C after B is open server-side, then release the event to check this race.

2. **Major — A newer ordinary text submission cannot retire a no-ID activity.** In [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js), a missing event ID passes `acceptsActivity()` whenever `currentActivityId` is `null`. Ordinary [text submissions](/data/zhoutaichang/live-agent/frontend/public/assets/live.js:1026) have no ID, so a newer text leaves that value `null`; a delayed `outline` or `exercise_open` from an earlier manual or voice lesson is accepted. The supported null-owner path therefore cannot distinguish a current activity from a retired one. A delayed unowned-event browser fixture after newer text would demonstrate it.

3. **Minor — The new WebSocket regression can hang despite correct server behavior.** In [test_backend_api.py](/data/zhoutaichang/live-agent/tests/test_backend_api.py), the loop waiting for pong consumes C’s decision if it arrives first, but outcome collection starts only *after* pong. The following loop then waits indefinitely for two decisions. Collect outcomes in both loops and bound the receive wait.

The padded-title and `outline_failed` repairs appear sound in the supplied source. I could not run the reported checks.
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
  let visibleLearner = null, lessonMessage = {key:"lessonEmpty", suffix:""}, feedbackKey = null, sessionHintKey = "roomHint", noteStatusKey = "localOnly", pendingActivity = null, activitySequence = 0, currentActivityId = null, allowUnownedActivity = true;
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
  function acceptsActivity(requestId){return requestId==null ? allowUnownedActivity&&currentActivityId===null : requestId===currentActivityId;}
  function sendActivity(kind,text,context){if(pendingActivity||recentExercise)return false;const requestId=globalThis.crypto?.randomUUID?.()||'activity-'+Date.now().toString(36)+'-'+(++activitySequence);if(!window.sendText(text,context,requestId))return false;pendingActivity={requestId,kind,context:!!context};setLessonStatus(kind==='lesson'?'lessonSent':'practiceWaiting');updateLessonActions();return true;}
  function setNoteStatus(key){noteStatusKey=key;el('noteStatus').textContent=t(key,originals.get(el('noteStatus')));}
  function setFeedback(key){feedbackKey=key;el('exerciseFeedback').textContent=key?t(key):'';}
  function setTopicStatus(topic){lessonMessage=null;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+t(topic.basis.includes('estimate')?'estimate':topic.basis.includes('textbook')?'textbook':'reference');}
  function clearLearningScope(){pendingLesson=null;selectedTopic=null;resetLearningState();window.resetSessionView?.();el('text').value='';el('lessonTopic').value='';el('courseSearch').value='';setLessonStatus('lessonEmpty');renderCourses();updateLessonActions();}
  function resetLearningState(){currentActivityId=null;allowUnownedActivity=true;pendingActivity=null;feedbackKey=null;recentExercise=null;el('exerciseAnnouncement').textContent='';el('exerciseQuestion').textContent='';el('exerciseFeedback').textContent='';el('exerciseCard').hidden=true;el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
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
  function updateLessonActions(){const allowed=serviceReady&&connection==='ready'&&status?.board&&status.responder!=='rules',busy=!!recentExercise||!!pendingActivity;el('startLesson').disabled=!allowed||!el('lessonTopic').value.trim()||busy;el('practice').disabled=connection!=='ready'||!status?.board||status?.responder==='rules'||busy;}
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
  function onLessonEvent(event){const message=event.detail;const data=message.data||{};if(message.event==='utterance_end'&&data.decision&&pendingActivity&&data.request_id===pendingActivity.requestId){const dec=data.decision;const starts=dec.kind===pendingActivity.kind&&(pendingActivity.kind!=='lesson'||pendingActivity.context||(typeof dec.topic==='string'&&dec.topic.trim()));if(data.applied===false){setLessonStatus('requestSuperseded');pendingActivity=null;currentActivityId=null;allowUnownedActivity=false;}else if(!starts){setLessonStatus('requestNotStarted');pendingActivity=null;currentActivityId=null;allowUnownedActivity=false;}else pendingActivity.accepted=true;updateLessonActions();}if(message.event==='error'&&['lessonSent','practiceWaiting'].includes(lessonMessage?.key)){pendingActivity=null;currentActivityId=null;allowUnownedActivity=false;setLessonStatus('lessonFailed');updateLessonActions();}if(message.event!=='lesson'||!acceptsActivity(data.request_id))return;
    if(data.stage==='outline'){pendingActivity=null;setLessonStatus('outlineReady',data.title||data.topic||'');el('stepLearn').classList.add('current');}
    if(data.stage==='section')setLessonStatus('sectionReady',data.title||'');
    if(data.stage==='planned')setLessonStatus('lessonPrepared');
    if(data.stage==='outline_failed'){pendingActivity=null;currentActivityId=null;allowUnownedActivity=false;setLessonStatus('lessonFailed');}
    if(data.stage==='exercise_failed'||data.stage==='exercise_dropped'){if(pendingActivity?.kind==='exercise'){currentActivityId=null;allowUnownedActivity=false;}pendingActivity=null;setLessonStatus('exerciseFailed');}
    if(data.stage==='exercise'){setLessonStatus('practicePrepared');}
    if(data.stage==='exercise_existing'){pendingActivity=null;currentActivityId=data.exercise_request_id??null;allowUnownedActivity=currentActivityId===null;const ex={...data,request_id:currentActivityId};setLessonStatus('exercisePending');setFeedback(null);renderExercise(ex);window.LiveAgentMedia?.restoreExercise?.(ex);}
    if(data.stage==='exercise_open'){pendingActivity=null;setLessonStatus('practiceReady');setFeedback(null);renderExercise(data);}
    if(data.stage==='exercise_closed'||data.stage==='exercise_timeout'){pendingActivity=null;setLessonStatus('practiceClosed');renderExercise(null);}
    if(data.stage==='exercise_graded'){setLessonStatus('practiceReviewed');el('exerciseCard').hidden=false;setFeedback(data.skipped?'skipped':data.correct?'correct':'incorrect');el('stepPractice').classList.add('current');}
    if(data.stage==='grading_failed')setFeedback('gradingFailed');
    updateLessonActions();
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
  window.addEventListener('live-agent:submitted',event=>{const incoming=event.detail.request_id??null;if(recentExercise&&event.detail.activity!==true)return;currentActivityId=incoming;allowUnownedActivity=false;if(recentExercise&&!acceptsActivity(recentExercise.request_id)){setFeedback(null);renderExercise(null);window.LiveAgentMedia?.refreshLanguage?.();}if(pendingActivity&&incoming!==pendingActivity.requestId){pendingActivity=null;setLessonStatus('requestSuperseded');}updateLessonActions();});
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');else sendActivity('lesson',queued.text,queued.context);}updateLessonActions();});
  window.addEventListener('live-agent:profile',event=>{if(loadingProfile&&!event.detail)return;selectedProfile=event.detail;profileDisclaimer(event.detail);});
  window.addEventListener('live-agent:state',event=>{const ex=event.detail.exercise;if(ex&&!acceptsActivity(ex.request_id))return;renderExercise(ex);});
  window.addEventListener('live-agent:event',onLessonEvent);
  window.addEventListener('DOMContentLoaded',()=>{setEdition(edition,true);bootstrap();});
})();

===== FILE: .cache/student-review/contracts8.txt =====
Current exact source excerpts for the targeted student7 re-review. Line numbers refer to the source files at evidence capture.

### frontend/public/assets/live.js:1–12
```
1: const $ = (id) => document.getElementById(id);
2: const canvas = $("screen"), g = canvas.getContext("2d");
3: let ws = null, audioCtx = null, playhead = 0, queue = [], pending = null, recorder = null, epoch = 0, decoding = [];
4: let lastUtterT = null, verified = 0, repairs = 0, pingTimer = null;
5: let connectionAttempt = 0, sessionState = "disconnected", sessionStatus = null, pingTimeouts = [], startupTimer = null;
6: let latestAttention = null;
7: let errorLanguage = null;
8: const submissionNamespace = window.crypto?.randomUUID?.() || Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
9: let submissionSequence = 0;
10: const EXAMPLES = ["请给我讲一道例题", "这一步我还没明白", "给我一道练习题", "请讲慢一点"];
11: const ENGLISH = {
12:   "session.connecting": "Connecting…", "session.starting": "Preparing your tutor…",
```

### frontend/public/assets/live.js:86–97
```
86: }
87: function diagnostic(key, fallback, values = {}) {
88:   return tr(`event.${key}`, fallback).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
89: }
90: function productEvent(name, detail) { window.dispatchEvent(new CustomEvent(`live-agent:${name}`, {detail})); }
91: function nextSubmissionId() { return `client:${submissionNamespace}:${(++submissionSequence).toString(36)}`; }
92: function acceptsActivity(requestId) { return window.LiveAgentProduct?.acceptsActivity?.(requestId) !== false; }
93: function activeSocket(socket, attempt) { return socket === ws && attempt === connectionAttempt; }
94: function ready() { return sessionState === "ready" && ws?.readyState === 1; }
95: function idleExamples() { return window.LiveAgentProduct?.examples?.() || personaChips || EXAMPLES; }
96: const STATUS = {open: "进行中", complied: "已验证完成", failed: "失败", refused: "拒绝/降级", withdrawn: "已撤回",
97:                 capacity_skipped: "容量跳过", presented: "已呈现（未判定）"};
```

### frontend/public/assets/live.js:463–515
```
463:   const id = profile ? profile.id : $("sid").value;
464:   window.location.href = `/profile?student=${encodeURIComponent(id)}&edition=${encodeURIComponent(window.LiveAgentProduct?.edition || "primary")}`;
465: };
466: function showExercise(ex, requestId = ex?.request_id ?? null) {  // answer buttons while an exercise waits; the persona's examples otherwise
467:   if (!acceptsActivity(requestId)) {
468:     if (currentExercise && !acceptsActivity(currentExercise.request_id ?? null)) {
469:       currentExercise = null; exerciseKey = ""; renderExerciseChips(null);
470:     }
471:     return;
472:   }
473:   currentExercise = ex || null;
474:   const key = ex ? JSON.stringify([requestId, ex.concept, ex.question, ex.options || [], ex.option_texts || []]) : "";
475:   if (key === exerciseKey) return;
476:   exerciseKey = key;
477:   renderExerciseChips(currentExercise);
478: }
479: function renderExerciseChips(ex) {
480:   const live = ready();
481:   if (!ex) { setChips(sessionStatus?.board ? idleExamples() : personaChips, live); return; }
482:   setChips([...(ex.options || []).map((o, index) => ({label: tr("exercise.choose", "选 ") + o, text: "选 " + o,
483:               description: ex.option_texts?.[index] ? tr("exercise.choose", "选 ") + o + ": " + ex.option_texts[index] : undefined})),
484:             {label: tr("exercise.unsure", "我不会"), text: "我不会"}], live);
485:   document.querySelectorAll("#chips .chip").forEach(b => b.classList.add("answer"));
486: }
487: 
488: function onState(s) {
489:   productEvent("state", s);
490:   showExercise(s.exercise, s.exercise ? s.exercise.request_id ?? null : currentExercise?.request_id ?? null);
491:   $("sLambda").textContent = typeof s.lambda_s === "number" ? s.lambda_s.toFixed(1) : "–";
492:   $("sReq").textContent = s.next_lock ?? "–";
493:   const flags = [];
494:   if (s.listening) flags.push(tr("state.listening", "聆听中"));
495:   if (s.awaiting_decision) flags.push(tr("state.deciding", "等待应答决策"));
496:   if (!s.erasure_gate_open) flags.push(tr("state.erasure", "删除进行中（已暂停生成）"));
497:   $("flags").textContent = flags.join(" · ");
498:   const el = $("chains");
499:   if (!s.chains || !s.chains.length) return;
500:   el.innerHTML = "";
501:   for (const c of s.chains.slice().reverse()) {
502:     const steps = c.steps && c.steps.length > 1 ? ` · ${tr("state.steps", "步骤 ")}${Math.min(c.step_index, c.steps.length)}/${c.steps.length}` : "";
503:     const d = document.createElement("div"); d.className = "chain";
504:     d.innerHTML = `<div class="top"><span class="intent">${esc(c.intent)}</span><span class="pill ${esc(c.status)}">${esc(tr(`status.${c.status}`, STATUS[c.status] || c.status))}</span></div>
505:       <div class="meta">${esc(tr(`kind.${c.kind}`, KIND[c.kind] || c.kind))}${steps}${c.revisions ? ` · ${tr("state.revisions", "改口 ")}${c.revisions}` : ""}${c.requests.length ? ` · ${tr("state.requests", "请求 ")}${c.requests.join(", ")}` : ""}</div>`;
506:     el.appendChild(d);
507:   }
508: }
509: 
510: function onEvent(m) {
511:   productEvent("event", m);
512:   const d = m.data || {}, t = m.t, k = m.request;
513:   switch (m.event) {
514:     case "utterance_end":
515:       if (d.text) { lastUtterT = t; }
```

### frontend/public/assets/live.js:589–605
```
589:           `${i + 1}.${x.title}[${dep[x.depth] || x.depth}${x.exercise ? diagnostic("withPractice", "+练习") : ""}]`).join(" "));
590:       }
591:       if (d.stage === "section" && d.exercise) feed(t, "", "练习", diagnostic("sectionPractice", "本节后出题：{text}", {text: d.exercise}));
592:       if (d.stage === "exercise_graded") {
593:         const m = d.mastery;
594:         feed(t, d.correct ? "ok" : "bad", "批改", `${d.concept}：${d.skipped ? diagnostic("unsure", "不会") : d.correct ? diagnostic("correct", "答对") : diagnostic("incorrect", "答错")}` +
595:              (d.misconception ? `（${d.misconception}）` : "") +
596:              (m && m.after != null ? diagnostic("mastery", " · 掌握度 {before} → {after}", {before: m.before == null ? "–" : Math.round(m.before * 100) + "%", after: Math.round(m.after * 100) + "%"}) : ""));
597:       }
598:       if (d.stage === "exercise_graded") lastGraded = d.concept;
599:       if (d.stage === "exercise_open") showExercise(d);
600:       if (d.stage === "exercise_closed") showExercise(null, d.request_id ?? null);
601:       break;
602:     }
603:     case "attention": {
604:       latestAttention = d;
605:       renderFocusLabel();
```

### frontend/public/assets/live.js:930–1050
```
930: // A comment does not cut the video here: the server keeps it playing and sends "stop" when the reply is ready.
931: // While the user holds push-to-talk the persona's audio is muted (not the video) so the mic hears only the user.
932: let master = null;  // output gain: every chunk's audio goes through it
933: function outGain() {
934:   if (!master) { master = audioCtx.createGain(); master.connect(audioCtx.destination); }
935:   return master;
936: }
937: function duck(on) { if (audioCtx) outGain().gain.setTargetAtTime(on ? 0 : 1, audioCtx.currentTime, 0.03); }
938: let micPressed = false, micRequest = 0, micStream = null, micUploading = false;
939: function permissionNotice(device, error) {
940:   const kind = {NotAllowedError: "denied", SecurityError: "denied", NotFoundError: "missing", NotReadableError: "busy"}[error.name] || "failed";
941:   const messages = {
942:     voice: {denied: "麦克风未获授权，可以在浏览器里允许，或者用文字提问。", missing: "没有找到麦克风，可以接上麦克风，或者用文字提问。", busy: "麦克风正在被别的程序使用，可以先用文字提问。", failed: "暂时无法录音，可以用文字提问。"},
943:     camera: {denied: "摄像头未获授权，不开摄像头也可以继续学习。", missing: "没有找到摄像头，不开摄像头也可以继续学习。", busy: "摄像头正在被别的程序使用，不开摄像头也可以继续学习。", failed: "暂时无法使用摄像头，不开摄像头也可以继续学习。"},
944:   };
945:   notice(`${device}.${kind}`, messages[device][kind], error);
946: }
947: function resetTalkButton() {
948:   $("talk").classList.remove("recording"); $("talk").textContent = tr("voice.hold", "按住说话");
949: }
950: function cancelSpeech() {
951:   micPressed = false; micUploading = false; micRequest++;
952:   if (recorder) {
953:     recorder.onstop = null; recorder.ondataavailable = null;
954:     if (recorder.state !== "inactive") { try { recorder.stop(); } catch (e) {} }
955:   }
956:   micStream?.getTracks().forEach(track => track.stop()); micStream = null; recorder = null;
957:   duck(false); resetTalkButton();
958: }
959: $("talk").onpointerdown = async event => {
960:   if (!ready() || !sessionStatus?.asr || micPressed || micUploading || recorder?.state === "recording") return;
961:   if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
962:     notice("voice.unavailable", "这个浏览器暂时不能录音，可以用文字提问。"); return;
963:   }
964:   micPressed = true;
965:   const request = ++micRequest, socket = ws, attempt = connectionAttempt;
966:   $("talk").textContent = tr("voice.permission", "等待麦克风授权…");
967:   try { if (event?.pointerId != null) $("talk").setPointerCapture(event.pointerId); } catch (e) {}
968:   let stream;
969:   try {
970:     stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
971:     if (!micPressed || request !== micRequest || !activeSocket(socket, attempt) || !ready()) {
972:       stream.getTracks().forEach(track => track.stop()); return;
973:     }
974:     const parts = [];
975:     const recording = new MediaRecorder(stream); recorder = recording; micStream = stream;
976:     recording.ondataavailable = e => { if (e.data.size) parts.push(e.data); };
977:     recording.onstop = async () => {
978:       stream.getTracks().forEach(t => t.stop());
979:       if (recorder === recording) { recorder = null; micStream = null; }
980:       if (!parts.length || !activeSocket(socket, attempt) || request !== micRequest) return;
981:       micUploading = true; $("talk").disabled = true;
982:       try {
983:         const bytes = await new Blob(parts).arrayBuffer();
984:         if (!activeSocket(socket, attempt) || request !== micRequest || !ready()) return;
985:         if (send({type: "audio_end", tp: recording.endedAt ?? performance.now()}, socket)) socket.send(bytes);
986:       } catch (error) { if (activeSocket(socket, attempt)) permissionNotice("voice", error); }
987:       finally {
988:         if (request === micRequest && activeSocket(socket, attempt)) {
989:           micUploading = false; $("talk").disabled = !ready() || !sessionStatus?.asr;
990:         }
991:       }
992:     };
993:     recording.onerror = error => {
994:       if (request === micRequest && activeSocket(socket, attempt)) {
995:         cancelSpeech(); permissionNotice("voice", error.error || error);
996:       }
997:     };
998:     recording.start();
999:     const requestId = nextSubmissionId();
1000:     if (!send({type: "speech_start", request_id: requestId}, socket)) throw new Error("Unable to start voice input");
1001:     productEvent("submitted", {request_id: requestId, activity: false});
1002:     duck(true); $("talk").classList.add("recording"); $("talk").textContent = tr("voice.release", "松开发送");
1003:   } catch (error) {
1004:     stream?.getTracks().forEach(track => track.stop());
1005:     if (request === micRequest && activeSocket(socket, attempt)) {
1006:       cancelSpeech(); permissionNotice("voice", error);
1007:     }
1008:   }
1009: };
1010: function endSpeech(cancel = false) {
1011:   if (cancel) { cancelSpeech(); return; }
1012:   if (!micPressed) return;
1013:   micPressed = false;
1014:   duck(false);
1015:   if (recorder?.state === "recording") { recorder.endedAt = performance.now(); recorder.stop(); }
1016:   else micRequest++;  // releasing while permission is pending cancels that request
1017:   resetTalkButton();
1018: }
1019: $("talk").onpointerup = () => endSpeech();
1020: $("talk").onpointerleave = event => { if (!$("talk").hasPointerCapture?.(event?.pointerId)) endSpeech(); };
1021: $("talk").onpointercancel = () => endSpeech();
1022: $("talk").onkeydown = event => {
1023:   if ([" ", "Enter"].includes(event.key) && !event.repeat) { event.preventDefault(); $("talk").onpointerdown(); }
1024: };
1025: $("talk").onkeyup = event => {
1026:   if ([" ", "Enter"].includes(event.key)) { event.preventDefault(); endSpeech(); }
1027: };
1028: $("talk").onblur = () => { if (micPressed) endSpeech(); };
1029: addEventListener("blur", () => { if (micPressed || recorder) endSpeech(); });
1030: function sendText(v, lessonContext, requestId) {
1031:   v = (v ?? $("text").value).trim(); if (!v || !ready()) return false;
1032:   const activity = requestId != null;
1033:   if (activity && (typeof requestId !== "string" || !requestId.trim() || requestId.length > 64)) return false;
1034:   const packet = {type: "text", text: v, tp: performance.now(), request_id: activity ? requestId : nextSubmissionId()};
1035:   if (lessonContext && typeof lessonContext.subject === "string" && lessonContext.subject.trim() &&
1036:       Number.isInteger(lessonContext.grade) && lessonContext.grade >= 1 && lessonContext.grade <= 12 &&
1037:       typeof lessonContext.topic === "string" && lessonContext.topic.trim()) {
1038:     packet.lesson_context = {subject: lessonContext.subject.trim(), grade: lessonContext.grade, topic: lessonContext.topic.trim()};
1039:   }
1040:   if (!send(packet)) {
1041:     notice("session.sendFailed", "消息还没有发出去，请重新连接后再试。"); return false;
1042:   }
1043:   productEvent("submitted", {request_id: packet.request_id, activity});
1044:   chat("user", v); $("text").value = ""; return true;
1045: }
1046: $("send").onclick = () => sendText();
1047: $("text").onkeydown = e => { if (e.key === "Enter" && !e.isComposing && !e.shiftKey) { e.preventDefault(); sendText(); } };
1048: addEventListener("pagehide", () => { $("disconnect").onclick(); cancelSpeech(); camOff(false); });
1049: window.LiveAgentMedia = {...window.LiveAgentMedia, refreshLanguage, restoreExercise: showExercise};
1050: refreshLanguage();
```

### live_agent/backend/app.py:44–61
```
44:         return None
45:     for entry in curriculum.subjects:
46:         grades = entry.get("grade_topics")
47:         if entry.get("subject") != subject or not isinstance(grades, dict):
48:             continue
49:         chapter = grades.get(str(grade))
50:         if isinstance(chapter, dict) and isinstance(chapter.get("topics"), list) and any(
51:                 isinstance(title, str) and title.strip() == topic for title in chapter["topics"]):
52:             return {"subject": subject, "grade": grade, "topic": topic}
53:     return None
54: 
55: 
56: def build_app(args: argparse.Namespace) -> FastAPI:
57:     app = FastAPI(title="Live Agent Backend", version="1.0")
58: 
59:     @app.middleware("http")
60:     async def private_responses(request, call_next):
61:         response = await call_next(request)
```

### live_agent/backend/app.py:289–377
```
289:                                            "board": bool(canon.get("board")),
290:                                            "student": orch.student.view() if orch.student is not None else None},
291:                                           ensure_ascii=False))
292: 
293:             async def handle_inputs() -> None:
294:                 """Utterances are processed in order, off the receive loop, so presentation acks
295:                 and barge-in keep being read (and timestamped) while ASR / the LLM run."""
296:                 while True:
297:                     kind, payload, t_end, epoch, lesson_context, request_id = await inputs.get()  # epoch stamped at receipt
298:                     try:
299:                         if kind == "audio":
300:                             from live_agent.asr import decode_audio_bytes
301: 
302:                             audio = decode_audio_bytes(payload, 16000)
303:                             text = await asr.transcribe(audio, 16000)
304:                             correlation = {"request_id": request_id} if request_id is not None else {}
305:                             await ws.send_text(json.dumps({"type": "transcript", "text": text, **correlation}))
306:                         else:
307:                             text = payload
308:                         if text:
309:                             # t_end = when the user stopped speaking / sent (client clock, mapped), so
310:                             # ASR and queueing delay count toward the deadlines (proposal §7)
311:                             await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, t_end,
312:                                                                    session_id=session_id, scope=mode,
313:                                                                    lesson_context=lesson_context, request_id=request_id),
314:                                                          epoch=epoch)
315:                     except Exception:  # noqa: BLE001
316:                         log.exception("input handling failed")
317: 
318:             worker = asyncio.create_task(handle_inputs())
319:             audio_end = now()
320:             audio_request_id, audio_epoch, audio_rejected = None, None, False
321:             done = asyncio.create_task(orch.wait_done())
322:             while True:
323:                 recv = asyncio.create_task(ws.receive())
324:                 await asyncio.wait({recv, done}, return_when=asyncio.FIRST_COMPLETED)
325:                 if not recv.done():  # the orchestrator stopped (fatal error or bounded run)
326:                     recv.cancel()
327:                     err = f"{type(orch.error).__name__}: {orch.error}" if orch.error else "session ended"
328:                     try:
329:                         await ws.send_text(json.dumps({"type": "error", "error": err}))
330:                         await ws.close()
331:                     except Exception:  # noqa: BLE001
332:                         pass
333:                     break
334:                 msg = recv.result()
335:                 if msg.get("type") == "websocket.disconnect":
336:                     break
337:                 if msg.get("bytes") is not None:
338:                     if audio_rejected:
339:                         audio_rejected = False  # discard the recording whose start packet was rejected
340:                         continue
341:                     request_id, epoch = audio_request_id, audio_epoch
342:                     audio_request_id, audio_epoch = None, None  # one complete recording per binary message
343:                     if asr is not None:
344:                         inputs.put_nowait(("audio", msg["bytes"], audio_end,
345:                                           orch.input_epoch if epoch is None else epoch, None, request_id))
346:                     continue
347:                 data = json.loads(msg["text"])
348:                 t = data.get("type")
349:                 if t in ("chunk_start", "chunk_end", "chunk_received"):
350:                     transport.on_client_message(data)
351:                 elif t == "speech_start":
352:                     request_id = data.get("request_id")
353:                     if "request_id" in data and not _valid_request_id(request_id):
354:                         audio_request_id, audio_epoch, audio_rejected = None, None, True
355:                         await ws.send_json({"type": "error", "error": "invalid request_id"})
356:                         continue
357:                     await orch.on_speech_start()
358:                     audio_request_id, audio_epoch, audio_rejected = request_id, orch.input_epoch, False
359:                 elif t == "text" and data.get("text", "").strip():
360:                     request_id = data.get("request_id")
361:                     if "request_id" in data and not _valid_request_id(request_id):
362:                         await ws.send_json({"type": "error", "error": "invalid request_id"})
363:                         continue
364:                     lesson_context = None
365:                     if "lesson_context" in data:
366:                         lesson_context = _validated_lesson_context(curriculum, data["lesson_context"])
367:                         if lesson_context is None:
368:                             await ws.send_json({"type": "error", "error": "invalid catalogue topic selection"})
369:                             continue
370:                     # a typed instruction interrupts like speech does (before its LLM work is queued)
371:                     await orch.on_speech_start()
372:                     inputs.put_nowait(("text", data["text"].strip(), transport._to_server(data), orch.input_epoch, lesson_context, request_id))
373:                 elif t == "audio_end":  # precedes the recorded audio bytes
374:                     audio_end = transport._to_server(data)
375:                 elif t == "ping":
376:                     await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
377:                 elif t == "clock":
```

### live_agent/backend/transport.py:71–90
```
71: PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
72:                 "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
73:                 "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
74:                 "decision", "applied", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
75:                 "audibility", "revision", "speaker", "uid", "request_id", "exercise_request_id", "counts", "expected", "wrong", "target", "gave_up", "anchor_removed", "stage",
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
```

### live_agent/orchestrator.py:1179–1187
```
1179:     def _remind_existing_exercise(self, request_id: str | None) -> None:
1180:         """Tell the current input owner which authoritative question must be answered first."""
1181:         self.director.remind_exercise()
1182:         ex = self.director.exercise
1183:         correlation = {"request_id": request_id} if request_id is not None else {}
1184:         self.log.emit(EventType.LESSON, now(), stage="exercise_existing", concept=ex.concept,
1185:                       kind=ex.kind, question=ex.question, options=[o[:1] for o in ex.options],
1186:                       option_texts=list(ex.options), exercise_request_id=ex.request_id, **correlation)
1187: 
```

### live_agent/orchestrator.py:1434–1522
```
1434: 
1435:     async def _on_user_utterance(self, utt: Utterance, epoch: int) -> dict[str, Any]:
1436:         correlation = {"request_id": utt.request_id} if utt.request_id is not None else {}
1437:         self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text, **correlation)
1438:         # A forget request must not recall the very fact it asks to erase into the responder.
1439:         memories, memory_ids, recall_id = None, [], None
1440:         if self.memory and not _FORGET.search(utt.text):
1441:             hits_fn = getattr(self.memory, "recall_hits", None)
1442:             if hits_fn is not None:
1443:                 hits = hits_fn(utt.text, mode=self.cfg.scope)
1444:                 memories, memory_ids = [h.rendered for h in hits], [h.id for h in hits]
1445:                 recall_id = getattr(hits, "recall_id", None)
1446:             else:
1447:                 memories, memory_ids = self.memory.recall(utt.text, mode=self.cfg.scope), None
1448:         elif self.memory and hasattr(self.memory, "no_recall"):
1449:             # nothing recalled for a forget request; the responder prompt then contains no memory
1450:             # (the director never injects memory notes), so the context is isolated
1451:             recall_id = self._no_recall()
1452:         if self.memory:
1453:             self.memory.on_user_utterance(utt)
1454:         if self.director.exercise is not None and not _FORGET.search(utt.text):
1455:             graded = await self._grade_answer(utt, epoch)
1456:             if graded is not None:
1457:                 self._drain_director_events(now())
1458:                 outcome = {**correlation, "applied": not bool(graded.get("superseded"))} if correlation else {}
1459:                 self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=graded,
1460:                               chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1461:                               recalled=[], **outcome)
1462:                 return graded
1463:         self.director.student_context = self._student_context()
1464:         decision = await self.director.decide(utt, memories)
1465:         term = (decision or {}).get("forget_term")
1466:         applied = False
1467:         if epoch != self._input_epoch:
1468:             # The user barged in again while this decision was computed: it must not change the plan
1469:             # (the newer utterance decides). An erasure request is still honoured.
1470:             self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
1471:         else:
1472:             if term:  # the confirmation is spoken only after the erasure is verified (below)
1473:                 decision = {**decision, "steps": []}
1474:             queued_before = {id(x) for x in self.director.queue}
1475:             self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
1476:             applied = True
1477:             self._decisions += 1  # only applied decisions end the post-interruption wait
1478:             if self.answer_boards and (decision or {}).get("kind") == "content" \
1479:                     and self.director.answer_board_missing(decision):
1480:                 segs = [x for x in self.director.queue if id(x) not in queued_before and x.board is None and x.line]
1481:                 if segs:  # the responder left it out: write one now and show it from the next unlocked line
1482:                     self._spawn(self._answer_board(utt.text, segs), "answer_board")
1483:             self._make_figures()
1484:             kind = (decision or {}).get("kind")
1485:             if kind == "lesson" and self.director.exercise is not None and self.director.exercise.source != "lesson":
1486:                 self._remind_existing_exercise(utt.request_id)  # finish the standalone question before a new lesson
1487:             elif kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
1488:                 topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
1489:                 self._start_lesson(topic, utt.lesson_context, utt.request_id)
1490:             elif kind == "lesson_stop":
1491:                 self._stop_lesson()
1492:             elif kind == "exercise" and self.director.exercise is not None:
1493:                 self._remind_existing_exercise(utt.request_id)  # one exercise at a time: the open one first
1494:             elif kind == "exercise":
1495:                 topic = utt.lesson_context["topic"] if utt.lesson_context else \
1496:                     str((decision or {}).get("topic") or "").strip() or self.director.lesson_title or "刚才讲的内容"
1497:                 self._spawn(self._give_exercise(topic, utt.lesson_context, input_epoch=epoch,
1498:                                                 profile_epoch=self._profile_epoch, plan_version=self.director.plan_version,
1499:                                                 request_id=utt.request_id), "exercise")
1500:             elif self.director.exercise is not None:
1501:                 self._remind_existing_exercise(utt.request_id)  # a question while an exercise waits: back to it afterwards
1502:             if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
1503:                 changed = self.student.apply_update(decision["profile_update"])
1504:                 if changed:
1505:                     self._save_profile()
1506:                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
1507:                     self._emit_profile()
1508:         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
1509:         if term and self.memory is not None and hasattr(self.memory, "forget"):
1510:             complete = await self._erase(term)
1511:             line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
1512:             self.director.say_verified(line)  # a verified statement: not subject to the narration guard
1513:         if term:  # the decision itself names erased terms
1514:             raw = json.dumps(decision, ensure_ascii=False)
1515:             for x in sorted(self.director.erased_terms, key=len, reverse=True):
1516:                 raw = raw.replace(x, "[已删除]")
1517:             decision = json.loads(raw)
1518:         outcome = {**correlation, "applied": applied} if correlation else {}
1519:         self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
1520:                       chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1521:                       recalled=list(memories or []), **outcome)
1522:         return decision
```

### tests/test_backend_api.py:19–48
```
19: def receive_ws_bounded(ws, timeout=5):
20:     """Await the test channel with a deadline, without leaving a blocked receiver thread behind."""
21:     import asyncio
22: 
23:     message = ws.portal.call(asyncio.wait_for, ws._send_rx.receive(), timeout)
24:     ws._raise_on_close(message)
25:     return message
26: 
27: 
28: def receive_utterance(ws, request_id):
29:     import time
30: 
31:     records, transcripts = [], []
32:     deadline = time.monotonic() + 5
33:     while True:
34:         remaining = deadline - time.monotonic()
35:         assert remaining > 0, "utterance outcome did not arrive"
36:         packet = receive_ws_bounded(ws, remaining)
37:         if "text" not in packet:
38:             continue
39:         message = json.loads(packet["text"])
40:         if message.get("type") == "transcript":
41:             transcripts.append(message)
42:         if message.get("event") == "utterance_end" and message["data"].get("request_id") == request_id:
43:             records.append(message["data"])
44:             if "decision" in message["data"]:
45:                 assert len(records) == 2
46:                 return records, transcripts
47: 
48: 
```

### tests/test_backend_api.py:567–739
```
567: def test_newer_websocket_text_supersedes_a_held_decision_without_speech_start(tmp_path, monkeypatch):
568:     import asyncio
569:     import threading
570:     import time
571:     from live_agent.llm import RuleResponder
572: 
573:     entered, release = threading.Event(), threading.Event()
574:     calls = []
575: 
576:     async def held_chat(self, messages, **kwargs):
577:         # This is the actual responder path. Exercise generation must never begin for B.
578:         assert messages[0]["role"] == "system"
579:         text = messages[-1]["content"]
580:         calls.append(text)
581:         if text == "考考我":
582:             entered.set()
583:             assert await asyncio.to_thread(release.wait, 5), "test did not release held decision"
584:             return json.dumps({"kind": "exercise", "topic": "加法", "steps": []})
585:         return json.dumps({"kind": "chat", "steps": []})
586: 
587:     monkeypatch.setattr(RuleResponder, "chat", held_chat)
588:     messages = []
589:     outcomes = {}
590: 
591:     def collect(packet):
592:         if "text" not in packet:
593:             return {}
594:         message = json.loads(packet["text"])
595:         messages.append(message)
596:         if message.get("event") == "utterance_end" and "decision" in message["data"]:
597:             outcomes[message["data"]["request_id"]] = message["data"]
598:         return message
599: 
600:     def receive_until(ws, condition):
601:         deadline = time.monotonic() + 5
602:         while not condition():
603:             remaining = deadline - time.monotonic()
604:             assert remaining > 0, "expected WebSocket outcome did not arrive"
605:             message = collect(receive_ws_bounded(ws, remaining))
606:             if message.get("type") == "pong" and message.get("t") == "C-received":
607:                 return
608: 
609:     try:
610:         with TestClient(backend(tmp_path)) as client:
611:             with client.websocket_connect("/ws") as ws:
612:                 ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
613:                 ws.send_json({"type": "text", "text": "考考我", "request_id": "B-ticket"})
614:                 assert entered.wait(3), "B did not reach the held responder"
615:                 ws.send_json({"type": "text", "text": "换个话题", "request_id": "C-ticket"})
616:                 ws.send_json({"type": "ping", "t": "C-received"})
617:                 receive_until(ws, lambda: False)  # pong proves C was queued with its newer epoch
618:                 release.set()
619:                 receive_until(ws, lambda: len(outcomes) == 2)
620:                 assert outcomes["B-ticket"]["decision"]["kind"] == "exercise"
621:                 assert outcomes["B-ticket"]["applied"] is False
622:                 assert outcomes["C-ticket"]["applied"] is True
623:     finally:
624:         release.set()
625:     assert calls == ["考考我", "换个话题"]
626:     assert not any(message.get("event") == "lesson" and message["data"].get("request_id") == "B-ticket"
627:                    for message in messages)
628:     logged = [json.loads(line) for path in (tmp_path / "logs").glob("*.jsonl") for line in path.read_text().splitlines()]
629:     assert not any(event["type"] == "lesson" and event["data"].get("request_id") == "B-ticket" for event in logged)
630: 
631: 
632: def test_manual_and_voice_requests_keep_distinct_ids_and_legacy_audio_stays_unowned(tmp_path, monkeypatch):
633:     from live_agent.llm import RuleResponder
634:     from live_agent.orchestrator import Orchestrator
635: 
636:     audio, asr_calls = mock_voice_asr(monkeypatch, ["请讲加法", "普通语音", "旧版语音", "没有开始包的旧版语音"])
637:     started = []
638: 
639:     async def classify(self, messages, **kwargs):
640:         return json.dumps({"kind": "lesson", "topic": "加法", "steps": []}) if messages[-1]["content"] == "请讲加法" else \
641:             json.dumps({"kind": "chat", "steps": []})
642: 
643:     def capture_lesson(self, topic, context=None, request_id=None):
644:         started.append((topic, request_id))
645: 
646:     monkeypatch.setattr(RuleResponder, "chat", classify)
647:     monkeypatch.setattr(Orchestrator, "_start_lesson", capture_lesson)
648:     with TestClient(backend(tmp_path, asr_url="http://unused.test/v1")) as client:
649:         with client.websocket_connect("/ws") as ws:
650:             ws.send_json({"type": "hello", "mode": "private"})
651:             ws.send_json({"type": "text", "text": "请讲加法", "request_id": "manual-A"})
652:             records, _ = receive_utterance(ws, "manual-A")
653:             assert records[1]["applied"] is True
654:             for owner in ("voice-B", "voice-C", None):
655:                 start = {"type": "speech_start"}
656:                 if owner is not None:
657:                     start["request_id"] = owner
658:                 ws.send_json(start)
659:                 ws.send_json({"type": "audio_end"})
660:                 ws.send_bytes(audio)
661:                 records, transcripts = receive_utterance(ws, owner)
662:                 assert records[1]["decision"]["kind"] == ("lesson" if owner == "voice-B" else "chat")
663:                 assert len(transcripts) == 1 and transcripts[0].get("request_id") == owner
664:                 if owner is None:
665:                     assert all("request_id" not in event and "applied" not in event for event in records)
666:                     assert "request_id" not in transcripts[0]
667:                 else:
668:                     assert all(event["request_id"] == owner for event in records) and records[1]["applied"] is True
669:             ws.send_json({"type": "audio_end"})
670:             ws.send_bytes(audio)  # older clients can still send complete audio without a start packet
671:             records, transcripts = receive_utterance(ws, None)
672:             assert all("request_id" not in event for event in records) and "request_id" not in transcripts[0]
673:     assert started == [("加法", "manual-A"), ("加法", "voice-B")]
674:     assert len(asr_calls) == 4
675: 
676: 
677: def test_invalid_speech_ids_do_not_interrupt_or_transcribe_and_boundary_id_is_preserved(tmp_path, monkeypatch):
678:     from live_agent.orchestrator import Orchestrator
679: 
680:     audio, asr_calls = mock_voice_asr(monkeypatch, ["有效语音"])
681:     interrupts = []
682:     original = Orchestrator.on_speech_start
683: 
684:     async def capture_start(self, *args, **kwargs):
685:         await original(self, *args, **kwargs)
686:         interrupts.append(self.input_epoch)
687: 
688:     monkeypatch.setattr(Orchestrator, "on_speech_start", capture_start)
689:     with TestClient(backend(tmp_path, asr_url="http://unused.test/v1")) as client:
690:         with client.websocket_connect("/ws") as ws:
691:             ws.send_json({"type": "hello", "mode": "private"})
692:             for invalid in (None, True, 3, "", "   ", "r" * 65):
693:                 ws.send_json({"type": "speech_start", "request_id": invalid})
694:                 while True:
695:                     packet = receive_ws_bounded(ws)
696:                     if "text" in packet:
697:                         message = json.loads(packet["text"])
698:                         if message.get("type") == "error":
699:                             assert message["error"] == "invalid request_id"
700:                             break
701:                 ws.send_json({"type": "audio_end"})
702:                 ws.send_bytes(audio)  # a rejected recording is not treated as legacy unowned audio
703:             valid = "r" * 64
704:             ws.send_json({"type": "speech_start", "request_id": valid})
705:             ws.send_json({"type": "audio_end"})
706:             ws.send_bytes(audio)
707:             records, transcripts = receive_utterance(ws, valid)
708:             assert all(event["request_id"] == valid for event in records) and records[1]["applied"] is True
709:             assert transcripts[0]["request_id"] == valid
710:     assert len(interrupts) == 1 and len(asr_calls) == 1
711: 
712: 
713: def test_voice_recording_started_before_newer_text_keeps_its_older_epoch(tmp_path, monkeypatch):
714:     from live_agent.llm import RuleResponder
715: 
716:     audio, asr_calls = mock_voice_asr(monkeypatch, ["考考我"])
717:     calls = []
718: 
719:     async def classify(self, messages, **kwargs):
720:         assert messages[0]["role"] == "system"  # superseded voice must never generate an exercise
721:         calls.append(messages[-1]["content"])
722:         return json.dumps({"kind": "exercise", "topic": "加法", "steps": []}) if messages[-1]["content"] == "考考我" else \
723:             json.dumps({"kind": "chat", "steps": []})
724: 
725:     monkeypatch.setattr(RuleResponder, "chat", classify)
726:     with TestClient(backend(tmp_path, asr_url="http://unused.test/v1")) as client:
727:         with client.websocket_connect("/ws") as ws:
728:             ws.send_json({"type": "hello", "mode": "private"})
729:             ws.send_json({"type": "speech_start", "request_id": "voice-A"})
730:             ws.send_json({"type": "text", "text": "换个话题", "request_id": "manual-B"})
731:             newer, _ = receive_utterance(ws, "manual-B")
732:             assert newer[1]["applied"] is True
733:             ws.send_json({"type": "audio_end"})
734:             ws.send_bytes(audio)
735:             older, _ = receive_utterance(ws, "voice-A")
736:             assert older[1]["decision"]["kind"] == "exercise" and older[1]["applied"] is False
737:     assert len(asr_calls) == 1 and calls == ["换个话题", "考考我"]
738:     logged = [json.loads(line) for path in (tmp_path / "logs").glob("*.jsonl") for line in path.read_text().splitlines()]
739:     assert not any(event["type"] == "lesson" and event["data"].get("request_id") == "voice-A" for event in logged)
```

### frontend/tests/live.test.mjs:463–620
```
463: 
464: test('new exercise choices announce through the product event while composer focus stays put', async () => {
465:   const app = page(); await app.connect(); await app.open(); await app.status();
466:   app.element('text').focus();
467:   app.run('onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Fractions", question: "Choose a fraction", options: ["A"], option_texts: ["A. One half"]}})');
468:   assert.equal(app.run('document.activeElement === $("text")'), true);
469:   const event = app.events.findLast(event => event.type === 'live-agent:event');
470:   assert.equal(event.detail.data.question, 'Choose a fraction');
471:   assert.equal(app.element('chips').children[0]['aria-label'], '选 A: A. One half');
472: });
473: 
474: test('stale scoped exercise states and events leave current choices intact while ordinary state and profile still render', async () => {
475:   const app = page(); await app.connect(); await app.open(); await app.status({board: true});
476:   app.run(`window.LiveAgentProduct.acceptsActivity = requestId => requestId === "current-ticket";
477:     showExercise({request_id: "current-ticket", concept: "Current concept", options: ["B"], option_texts: ["Current choice"]});`);
478:   const currentChoice = app.element('chips').children[0]; currentChoice.focus();
479:   const profileEvents = app.events.filter(event => event.type === 'live-agent:profile').length;
480:   app.run(`onState({exercise: {request_id: "retired-ticket", concept: "Old concept", options: ["A"], option_texts: ["Old choice"]},
481:       lambda_s: 1.5, next_lock: 7, listening: true, erasure_gate_open: true, chains: []});
482:     onEvent({event: "lesson", data: {stage: "exercise_open", request_id: "retired-ticket", concept: "Old concept", options: ["A"]}});
483:     onEvent({event: "lesson", data: {stage: "exercise_closed", request_id: "retired-ticket"}});
484:     onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Unscoped old concept", options: ["A"]}});`);
485:   assert.equal(app.element('chips').children[0], currentChoice);
486:   assert.equal(app.run('document.activeElement === $("chips").children[0]'), true);
487:   assert.equal(app.run('currentExercise.request_id'), 'current-ticket');
488:   assert.equal(app.element('sLambda').textContent, '1.5');
489:   assert.equal(app.element('sReq').textContent, 7);
490:   assert.equal(app.element('flags').textContent, '聆听中');
491:   assert.equal(app.events.filter(event => event.type === 'live-agent:profile').length, profileEvents);
492:   assert.equal(app.events.findLast(event => event.type === 'live-agent:state').detail.exercise.request_id, 'retired-ticket');
493:   app.run('showProfile({id: "actual-student", name: "Current learner", concepts: [], exams: []});');
494:   assert.match(app.element('prof').innerHTML, /Current learner/);
495:   assert.equal(app.events.filter(event => event.type === 'live-agent:profile').length, profileEvents + 1);
496:   app.run('onEvent({event: "lesson", data: {stage: "exercise_closed", request_id: "current-ticket"}});');
497:   assert.equal(app.run('currentExercise'), null);
498:   assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
499: });
500: 
501: test('retired exercise snapshots cannot retain or resurrect chips through state or language refresh', async () => {
502:   const app = page(); await app.connect(); await app.open(); await app.status({board: true});
503:   app.run(`window.activityTicket = "old-ticket";
504:     window.LiveAgentProduct.acceptsActivity = requestId => requestId === window.activityTicket;
505:     showExercise({request_id: "old-ticket", concept: "Old concept", options: ["A"], option_texts: ["Old choice"]});
506:     window.activityTicket = "new-ticket";
507:     onState({exercise: {request_id: "old-ticket", concept: "Old concept", options: ["A"]}, erasure_gate_open: true, chains: []});`);
508:   assert.equal(app.run('currentExercise'), null);
509:   assert.equal(app.run('exerciseKey'), '');
510:   assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
511:   app.run(`window.activityTicket = "new-ticket";
512:     showExercise({request_id: "new-ticket", concept: "New concept", options: ["B"]});
513:     window.activityTicket = null; window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();`);
514:   assert.equal(app.run('currentExercise'), null);
515:   assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
516:   app.run('showExercise({concept: "Manual exercise", options: ["C"]});');
517:   assert.equal(app.element('chips').children[0].textContent, 'Choose C');
518:   app.run('showExercise(null);');
519:   assert.equal(app.run('currentExercise'), null);
520: });
521: 
522: test('the public restoreExercise method accepts the adopted owner and rejects a stale conflict', async () => {
523:   const app = page(); await app.connect(); await app.open(); await app.status({board: true});
524:   app.run(`window.currentOwner = "request-C";
525:     window.LiveAgentProduct.acceptsActivity = requestId => requestId === window.currentOwner;
526:     profile = {id: "actual-profile"};
527:     window.LiveAgentMedia.restoreExercise({request_id: "request-B", concept: "Existing question", options: ["B"]});`);
528:   assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
529:   const events = app.events.length, packets = app.sockets[0].sent.length, timers = app.timers.size, hooks = app.transitions.length;
530:   app.run(`window.currentOwner = "request-B";
531:     window.LiveAgentMedia.restoreExercise({request_id: "request-B", concept: "Existing question", options: ["B"], option_texts: ["Recovered B choice"]});`);
532:   assert.equal(app.element('chips').children[0].textContent, '选 B');
533:   assert.equal(app.element('chips').children[0]['aria-label'], '选 B: Recovered B choice');
534:   app.run(`window.currentOwner = "request-D";
535:     window.LiveAgentMedia.restoreExercise({request_id: "request-D", concept: "New question", options: ["D"]});
536:     window.LiveAgentMedia.restoreExercise({request_id: "request-B", concept: "Stale conflict", options: ["B"]});`);
537:   assert.equal(app.element('chips').children[0].textContent, '选 D');
538:   assert.equal(app.run('currentExercise.request_id'), 'request-D');
539:   assert.equal(app.events.length, events);
540:   assert.equal(app.sockets[0].sent.length, packets);
541:   assert.equal(app.timers.size, timers);
542:   assert.equal(app.transitions.length, hooks);
543:   assert.equal(app.run('profile.id'), 'actual-profile');
544:   app.run('onState({exercise: null, erasure_gate_open: true, chains: []});');
545:   assert.equal(app.run('currentExercise'), null);
546:   assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
547: });
548: 
549: test('modern ordinary submissions retire legacy unowned exercises without rejecting fresh-scope compatibility', async () => {
550:   const app = page(); await app.connect(); await app.open(); await app.status({board: true});
551:   app.run(`window.currentOwner = null;
552:     window.LiveAgentProduct.acceptsActivity = requestId => (requestId ?? null) === window.currentOwner;
553:     window.originalDispatch = window.dispatchEvent;
554:     window.dispatchEvent = event => {window.originalDispatch(event); if(event.type === "live-agent:submitted") window.currentOwner = event.detail.request_id;};
555:     window.LiveAgentMedia.restoreExercise({concept: "Legacy manual question", options: ["A"]});`);
556:   assert.equal(app.element('chips').children[0].textContent, '选 A');
557:   app.run('showExercise(null); sendText("A newer ordinary question");');
558:   const owner = app.events.at(-1).detail.request_id; assertRequestId(owner);
559:   app.run(`onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Late legacy question", options: ["L"]}});
560:     onState({exercise: {concept: "Late legacy state", options: ["L"]}, erasure_gate_open: true, chains: []});`);
561:   assert.equal(app.run('currentExercise'), null);
562:   assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
563:   app.run(`window.LiveAgentMedia.restoreExercise({request_id: ${JSON.stringify(owner)}, concept: "Current question", options: ["B"]});
564:     onState({exercise: {concept: "Late unscoped state", options: ["L"]}, erasure_gate_open: true, chains: []});`);
565:   assert.equal(app.element('chips').children[0].textContent, '选 B');
566:   assert.equal(app.run('currentExercise.request_id'), owner);
567:   app.run('onState({exercise: null, erasure_gate_open: true, chains: []});');
568:   assert.equal(app.run('currentExercise'), null);
569: });
570: 
571: test('replacing focused chips preserves a matching prompt and returns removed choices to the composer', async () => {
572:   const app = page(); await app.connect(); await app.open(); await app.status();
573:   app.run('setChips([{label: "Original label", text: "这一步我还没明白"}], true)');
574:   app.element('chips').children[0].focus();
575:   app.run('setChips([{label: "New label", text: "这一步我还没明白"}], true)');
576:   assert.equal(app.run('document.activeElement === $("chips").children[0]'), true);
577:   app.run('setChips(["Different prompt"], true)');
578:   assert.equal(app.run('document.activeElement === $("text")'), true);
579: });
580: 
581: test('classroom mastery evidence and capability labels are visible and localized in English', async () => {
582:   const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status();
583:   app.run(`showProfile({id: "actual-student", name: "Learner", grade: "Grade 8", exams: [],
584:     concepts: [{name: "Fractions", level: "partial", source: "exercise", mastery: 0.5, attempts: 3, correct: 2}]});`);
585:   const html = app.element('prof').innerHTML;
586:   assert.match(html, /tabindex="0" aria-describedby="concept-evidence-0"/);
587:   assert.match(html, /<p class="meta concept-evidence" id="concept-evidence-0">Partly understood · Uncalibrated estimate · Based on recorded practice · Recorded practice: 2\/3 correct<\/p>/);
588:   assert.doesNotMatch(html, /hover|据练习|无依据|已掌握|薄弱/);
589:   const badges = app.element('badges').children.map(node => node.textContent).join('\n');
590:   assert.match(badges, /Video: Mock video \(CPU preview\)/);
591:   assert.match(badges, /Responder: Rules \(preview\)/);
592:   assert.doesNotMatch(badges, /生成|质检|仅文字/);
593: });
594: 
595: test('English camera controls are localized on load and board progress labels use the current language', () => {
596:   const app = page({ edition: 'university' });
597:   assert.equal(app.element('cam').textContent, 'Enable focus check');
598:   assert.equal(app.element('focus').textContent, 'Focus check is off');
599:   assert.equal(app.run('boardSentenceLabel(2, 3)'), 'Sentence 2/3');
600:   const dot = app.element('progress-dot'), item = app.element('board-item');
601:   item.querySelector = selector => selector === '.dots' ? dot : null;
602:   app.element('boardItems').children = [item];
603:   app.run('shownBoard = {key: "actual-lesson", title: "原始课程标题", progress: [2, 3]}; window.LiveAgentMedia.refreshLanguage();');
604:   assert.equal(dot['aria-label'], 'Sentence 2/3');
605:   assert.equal(app.element('boardTitle').innerHTML, '原始课程标题');
606: });
607: 
608: test('language refresh translates a connected session without replaying hooks or overwriting profile data', async () => {
609:   const app = page(); await app.connect(); await app.open(); await app.status({ asr: true, attention: true });
610:   app.run('onEvent({event: "attention", data: {state: "focused", stable: "distracted", reason: "raw source reason"}}); profile = {id: "actual-profile"};');
611:   const hooks = app.transitions.length, events = app.events.length, packets = app.sockets[0].sent.length, timers = app.timers.size;
612:   app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
613:   assert.equal(app.element('conn').textContent, 'Tutor ready');
614:   const badges = app.element('badges').children.map(node => node.textContent).join('\n');
615:   assert.match(badges, /Video: Mock video/);
616:   assert.doesNotMatch(badges, /生成|质检|仅文字/);
617:   assert.equal(app.element('focus').textContent, 'Focus check: Distracted (raw source reason)');
618:   assert.equal(app.element('cam').textContent, 'Enable focus check');
619:   assert.equal(app.run('profile.id'), 'actual-profile');
620:   assert.equal(app.transitions.length, hooks);
```

### scripts/student_frontend_check.py:105–270
```
105:                 page.reload()
106:                 page.wait_for_function("!document.getElementById('connect').disabled")
107:                 assert page.locator('#notes').input_value() == 'Student A private note'
108:                 with page.expect_download() as exported:
109:                     page.locator('#exportNotes').click()
110:                 assert Path(exported.value.path()).read_text() == 'Student A private note'
111:                 page.evaluate("""() => {window.__originalStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('controlled storage failure');};}""")
112:                 page.locator('#notes').fill('Unsaved fixture note')
113:                 assert '失败' in page.locator('#noteStatus').inner_text()
114:                 page.locator('#edition').select_option('university')
115:                 assert 'Could not save' in page.locator('#noteStatus').inner_text()
116:                 page.locator('#edition').select_option('secondary')
117:                 assert '失败' in page.locator('#noteStatus').inner_text()
118:                 page.evaluate('() => {Storage.prototype.setItem=window.__originalStorageSet;}')
119:                 page.locator('#notes').fill('Student A private note')
120:                 results.append({'notes': 'persist, isolate and export passed'})
121:                 page.locator('#edition').select_option('university')
122:                 assert 'Example profile' in page.locator('#sid').inner_text()
123:                 assert page.locator('html').get_attribute('lang') == 'en'
124:                 assert 'edition=university' in page.locator('#profLink').get_attribute('href')
125:                 page.reload()
126:                 page.wait_for_function("!document.getElementById('connect').disabled")
127:                 assert page.locator('#edition').input_value() == 'university'
128:                 page.locator('#connect').click()
129:                 page.wait_for_function("sessionState === 'ready'", timeout=15000)
130:                 assert page.locator('#talk').is_disabled()
131:                 assert page.locator('#startLesson').is_disabled()
132:                 assert 'Video preview' in page.locator('#runtimeNotice').inner_text()
133:                 assert 'cannot create lessons' in page.locator('#runtimeNotice').inner_text()
134:                 page.locator('#text').fill('请讲慢一点')
135:                 page.locator('#text').press('Enter')
136:                 assert page.locator('#chat .msg.user').last.inner_text() == '请讲慢一点'
137:                 page.wait_for_function('queue.length > 0', timeout=15000)
138:                 dimensions = page.locator('#screen').bounding_box()
139:                 ratio = page.evaluate('canvas.width/canvas.height')
140:                 assert abs(dimensions['width']/dimensions['height'] - ratio) < .01
141:                 # Synthetic capability fixtures verify UI gating and the actual outgoing text contract only.
142:                 # Real CPU transport was checked above. Keep unrelated preview snapshots
143:                 # from replacing the controlled activity fixtures below.
144:                 page.evaluate("""() => {ws.onmessage=null;window.__sentTexts=[];window.__lessonContexts=[];window.__requestIds=[];window.__submissions=[];window.addEventListener('live-agent:submitted',event=>window.__submissions.push(event.detail));const original=ws.send.bind(ws);ws.send=data=>{try{const packet=JSON.parse(data);if(packet.type==='text'){window.__sentTexts.push(packet.text);window.__requestIds.push(packet.request_id);if(packet.lesson_context)window.__lessonContexts.push(packet.lesson_context);return;}}catch{};original(data);};window.LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}""")
145:                 assert 'cannot create lessons' not in page.locator('#runtimeNotice').inner_text()
146:                 page.locator('#gradeFilter').select_option('3')
147:                 page.locator('#subjectFilter').select_option('数学')
148:                 page.locator('.course-card').first.click()
149:                 page.locator('#startLesson').click()
150:                 assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
151:                 assert page.evaluate('window.__lessonContexts.at(-1).grade')==3
152:                 assert page.evaluate('window.__lessonContexts.at(-1).subject')=='数学'
153:                 assert page.evaluate('window.__lessonContexts.at(-1).topic')==page.locator('#lessonTopic').input_value()
154:                 assert page.locator('#startLesson').is_disabled()
155:                 assert page.locator('#practice').is_disabled()
156:                 lesson_fixture(page, request_id=page.evaluate('window.__requestIds.at(-1)'), stage='outline', title='Catalogue lesson fixture')
157:                 page.locator('#practice').click()
158:                 assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
159:                 assert page.evaluate('window.__lessonContexts.at(-1).grade')==3
160:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:'UNRELATED-OLD-TURN',decision:{kind:'chat'}}}}))")
161:                 assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
162:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),decision:{kind:'chat'}}}}))")
163:                 assert 'did not start' in page.locator('#lessonStatus').inner_text()
164:                 # A rejected activity clears its owner. Legacy no-ID events must
165:                 # remain retired even when the current owner becomes null again.
166:                 legacy_status = page.locator('#lessonStatus').inner_text()
167:                 lesson_fixture(page, stage='outline', title='LEGACY AFTER REJECTED INPUT')
168:                 lesson_fixture(page, stage='exercise_open', question='LEGACY AFTER REJECTED INPUT', options=['A'], option_texts=['A. Stale answer'])
169:                 exercise_snapshot_fixture(page, {'question':'LEGACY AFTER REJECTED INPUT','options':['A'],'option_texts':['A. Stale answer']})
170:                 assert page.locator('#lessonStatus').inner_text() == legacy_status
171:                 assert not page.locator('#exerciseCard').is_visible()
172:                 assert not page.locator('#chips .answer').count()
173:                 page.locator('#practice').click()
174:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'exercise_failed'}}}))")
175:                 assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
176:                 # B is being prepared, with its open packet deliberately held.
177:                 # A generated question alone must not unlock another activity C.
178:                 page.locator('#practice').click()
179:                 held_owner = page.evaluate('window.__requestIds.at(-1)')
180:                 assert isinstance(held_owner, str) and held_owner
181:                 assert page.evaluate('window.__submissions.at(-1).activity') is True
182:                 assert page.locator('#startLesson').is_disabled()
183:                 assert page.locator('#practice').is_disabled()
184:                 page.evaluate("owner=>window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:owner,applied:true,decision:{kind:'exercise'}}}}))", held_owner)
185:                 held_question = {'request_id':held_owner, 'stage':'exercise_open', 'concept':'Held practice B', 'kind':'choice', 'question':'Held B question', 'options':['A','B'], 'option_texts':['A. Held first answer','B. Held second answer']}
186:                 sent_before_open = page.evaluate('window.__sentTexts.length')
187:                 lesson_fixture(page, request_id=held_owner, stage='exercise', concept='Held practice B', exercise='Held B question')
188:                 assert 'question is prepared' in page.locator('#lessonStatus').inner_text()
189:                 assert not page.locator('#exerciseCard').is_visible()
190:                 assert page.locator('#startLesson').is_disabled()
191:                 assert page.locator('#practice').is_disabled()
192:                 for button in ('#practice', '#startLesson'):
193:                     page.locator(button).evaluate('(button)=>{button.click();button.onclick?.();}')
194:                 assert page.evaluate('window.__sentTexts.length') == sent_before_open
195:                 lesson_fixture(page, **held_question)
196:                 assert 'Held B question' in page.locator('#exerciseQuestion').inner_text()
197:                 assert 'Held second answer' in page.locator('#exerciseAnnouncement').text_content()
198:                 assert page.locator('#chips .answer').count() == 3
199:                 assert page.locator('#startLesson').is_disabled()
200:                 assert page.locator('#practice').is_disabled()
201:                 lesson_fixture(page, request_id=held_owner, stage='exercise_closed')
202:                 assert not page.locator('#practice').is_disabled()
203:                 results.append({'activity preparation':'waiting and generated B keep both buttons locked until the held open packet arrives'})
204: 
205:                 # A newer ordinary request C retires pending B; neither owned nor
206:                 # legacy delayed packets may restore its question, choices or status.
207:                 page.locator('#practice').click()
208:                 retired_owner = page.evaluate('window.__requestIds.at(-1)')
209:                 lesson_fixture(page, request_id=retired_owner, stage='exercise', concept='Retired B', exercise='Retired B question')
210:                 page.locator('#text').fill('Newer ordinary C while B is pending')
211:                 page.locator('#text').press('Enter')
212:                 newer_owner = page.evaluate('window.__requestIds.at(-1)')
213:                 assert isinstance(newer_owner, str) and newer_owner and newer_owner != retired_owner
214:                 assert page.evaluate('window.__submissions.at(-1).activity') is False
215:                 retired_status = page.locator('#lessonStatus').inner_text()
216:                 assert 'replaced by a newer action' in retired_status
217:                 for owner in (retired_owner, None):
218:                     late_question = {'stage':'exercise_open','question':'DELAYED RETIRED QUESTION','options':['A'],'option_texts':['A. DELAYED RETIRED CHOICE']}
219:                     if owner is not None:
220:                         late_question['request_id'] = owner
221:                     lesson_fixture(page, **({'request_id':owner} if owner is not None else {}), stage='outline', title='DELAYED RETIRED OUTLINE')
222:                     lesson_fixture(page, **late_question)
223:                     exercise_snapshot_fixture(page, late_question)
224:                     assert page.locator('#lessonStatus').inner_text() == retired_status
225:                     assert not page.locator('#exerciseCard').is_visible()
226:                     assert 'DELAYED' not in page.locator('#exerciseAnnouncement').text_content()
227:                     assert not page.locator('#chips .answer').count()
228: 
229:                 # The server may already have opened B while its packet was held.
230:                 # Only the correlated C recovery may restore B's creator identity.
231:                 recovery = {'stage':'exercise_existing','exercise_request_id':retired_owner,'concept':'Recovered B','kind':'choice','question':'Server-owned B question','options':['A','B'],'option_texts':['A. Existing first answer','B. Existing second answer']}
232:                 lesson_fixture(page, **{**recovery,'request_id':'UNRELATED-OLD-C'})
233:                 assert not page.locator('#exerciseCard').is_visible()
234:                 lesson_fixture(page, **{**recovery,'request_id':newer_owner})
235:                 assert 'Server-owned B question' in page.locator('#exerciseQuestion').inner_text()
236:                 assert page.locator('#chips .answer').count() == 3
237:                 assert page.evaluate('currentExercise.request_id') == retired_owner
238:                 assert page.locator('#practice').is_disabled()
239:                 recovered_status = page.locator('#lessonStatus').inner_text()
240:                 lesson_fixture(page, **{**recovery,'request_id':newer_owner,'question':'STALE SECOND C RECOVERY'})
241:                 assert page.locator('#lessonStatus').inner_text() == recovered_status
242:                 assert 'Server-owned B question' in page.locator('#exerciseQuestion').inner_text()
243:                 assert 'STALE SECOND' not in page.locator('#exerciseAnnouncement').text_content()
244:                 page.locator('#text').fill('An ordinary answer to restored B')
245:                 page.locator('#text').press('Enter')
246:                 answer_id = page.evaluate('window.__requestIds.at(-1)')
247:                 assert isinstance(answer_id, str) and answer_id not in (retired_owner, newer_owner)
248:                 assert page.evaluate('window.__submissions.at(-1).activity') is False
249:                 assert page.evaluate('currentExercise.request_id') == retired_owner
250:                 lesson_fixture(page, request_id=retired_owner, stage='exercise_graded', correct=True)
251:                 assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
252:                 lesson_fixture(page, request_id=retired_owner, stage='exercise_closed')
253:                 assert 'question is closed' in page.locator('#lessonStatus').inner_text()
254:                 assert not page.locator('#chips .answer').count()
255:                 results.append({'activity retirement and recovery':'new ordinary IDs reject delayed owned/legacy events; correlated existing question restores creator-owned answers'})
256:                 page.locator('#practice').click()
257:                 page.evaluate("window.__oldActivity=window.__requestIds.at(-1);window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))" )
258:                 assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
259:                 page.evaluate("sendText('Newer ordinary question')")
260:                 assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
261:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))")
262:                 assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
263:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__oldActivity,stage:'exercise_open',question:'LATE OLD QUESTION'}}}))")
264:                 assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
265:                 assert 'LATE OLD QUESTION' not in page.locator('#exerciseQuestion').inner_text()
266:                 page.locator('#practice').click()
267:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__oldActivity,stage:'outline',title:'LATE OLD OUTLINE'}}}))")
268:                 assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
269:                 page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),applied:false,decision:{kind:'exercise'}}}}))")
270:                 assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
```

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


@pytest.mark.parametrize("creator", [None, "practice-B"])
@pytest.mark.parametrize("kind", ["exercise", "content", "lesson"])
def test_new_input_reports_the_existing_standalone_question_without_reassigning_owner(creator, kind):
    async def scenario():
        orch, _ = pipeline.build()
        existing = Exercise("加法", "一加一等于几？", "B", kind="choice", options=["A. 一", "B. 二"],
                            source="asked", request_id=creator)
        orch.director.exercise = existing
        calls = []

        def classify(messages):
            calls.append(messages[0]["role"])
            if messages[0]["role"] != "system":
                return json.dumps({"is_answer": False, "correct": False})  # request is not an answer to B
            return json.dumps({"kind": kind, "topic": "减法", "steps": []})

        def unexpected_lesson(*args):
            raise AssertionError("an open standalone question must be recovered before a new lesson starts")

        orch.director.llm = ScriptedLLM(classify)
        orch._start_lesson = unexpected_lesson
        decision = await orch.on_user_utterance(Utterance("C", "user", "给我出一道别的练习", now(), request_id="practice-C"))
        assert decision["kind"] == kind and calls == ["user", "system"]
        assert not orch._aux and orch.director.exercise is existing and existing.request_id == creator
        event = next(event for event in lesson_events(orch) if event["stage"] == "exercise_existing")
        assert event == {"stage": "exercise_existing", "concept": "加法", "kind": "choice", "question": "一加一等于几？",
                         "options": ["A", "B"], "option_texts": ["A. 一", "B. 二"],
                         "request_id": "practice-C", "exercise_request_id": creator}
        assert all(segment.exercise is existing for segment in orch.director.queue if segment.exercise is not None)

    asyncio.run(scenario())


def test_new_lesson_can_still_replace_an_exercise_from_the_current_lesson():
    async def scenario():
        orch, _ = pipeline.build()
        orch.director.exercise = Exercise("加法", "一加一等于几？", "二", source="lesson", request_id="lesson-B")
        started = []

        def classify(messages):
            return json.dumps({"is_answer": False, "correct": False}) if messages[0]["role"] != "system" else \
                json.dumps({"kind": "lesson", "topic": "减法", "steps": []})

        orch.director.llm = ScriptedLLM(classify)
        orch._start_lesson = lambda topic, context, owner: started.append((topic, owner))
        await orch.on_user_utterance(Utterance("C", "user", "请改讲减法", now(), request_id="lesson-C"))
        assert started == [("减法", "lesson-C")]
        assert not any(event["stage"] == "exercise_existing" for event in lesson_events(orch))

    asyncio.run(scenario())
