Targeted independent read-only re-review of student5's two findings. All current evidence is inlined; sandbox shell cannot start. Number concrete remaining findings as blocking/major/minor with evidence. Do not equate tests or agreement with verification. Limit this checkpoint to the supplied interruption and catalogue-context repairs; preceding student UI, private/public scope, profile writes/navigation, recordings and frontend/backend split were independently reviewed. PROJECT.md controls the phase; no training/deployment/broadcast, GPU, teaching efficacy, English-teaching or university-curriculum qualification is claimed.

Repair 1: correlated decision events now include applied:false when input epoch supersedes their decision and true only after the decision/grading applied. Ordinary events preserve shape. Product checks applied:false before kind/context and shows a replaced-request outcome. A same-kind accepted activity stays tracked while preparing until an outline/question/failure arrives. A newer successful text submission emits a synchronous local submitted event, cancelling that pending activity before the new request ticket is stored. Later decisions for the old ticket cannot restore waiting. No event on failed send and no extra network packet. Backend held-decision/graded-supersession regressions and browser cases cover these causal paths.

Repair 2: the catalogue filters nonempty trimmed subject/title plus valid school-grade integers before exposing cards, ensuring its selected context satisfies live.sendText's context condition. Empty subject/title entries are not offered. Mixed valid/invalid catalogue fixture checks valid selection and excluded blanks. Catalogue title content itself remains Chinese and source-provenanced, not a fabricated university course.

Measured locally: combined frontend 90 passed; final affected backend 75 passed. Latest browser before the mixed-catalogue case passed nine layout cases and nine behavior scenarios, including accepted request -> newer ordinary text -> late matching decision and direct applied:false decision. Full final Python and refreshed browser tests are running. Previously full CPU Python 401 passed and one GPU-only skip after optional request-ID transport repair. All browser activity events are explicit synthetic fixtures following an actual isolated CPU connection/text/media test; no real teaching-model output is qualified. This review is source-only unless you independently execute supplied checks.

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

===== FILE: docs/reviews/student5_review.md =====
Read-only review of the inlined source; I did not run the reported tests.

1. **Major — An interrupted activity can remain “waiting.”** The WebSocket receive loop accepts a later chat message while an earlier lesson or practice decision is running ([app.py](/data/zhoutaichang/live-agent/live_agent/backend/app.py:352)). The [orchestrator](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1438) skips applying that earlier decision when its input epoch is superseded, but still emits the decision with its `request_id` at line 1485. In [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js), a matching, same-kind decision clears `pendingActivity` without changing `lessonSent` or `practiceWaiting`. No activity is started in the skipped branch. A delayed practice decision interrupted by ordinary chat would settle the visible result.

2. **Minor — The frontend can claim catalogue context that it did not send.** `loadCatalogue()` in [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) accepts an empty `subject`, and `sendActivity()` records the selected object as context. [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js:1015) omits `lesson_context` when that subject is empty. If the matching lesson decision has an empty topic, the [orchestrator](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1455) starts nothing, while the page leaves `lessonSent` displayed. A catalogue fixture with an empty subject reproduces the mismatch; the supplied material does not show whether the actual catalogue contains one.

The direct four reproductions appear addressed in the supplied code. The inlined browser fixtures test synthetic outcomes, and the endpoint tests check ID propagation; neither verifies the interrupted-decision path above.
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
  let visibleLearner = null, lessonMessage = {key:"lessonEmpty", suffix:""}, feedbackKey = null, sessionHintKey = "roomHint", noteStatusKey = "localOnly", pendingActivity = null, activitySequence = 0;
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
  const product = {get edition(){return edition;},t,examples,sessionChanged};
  window.LiveAgentProduct = product;
  function setLessonStatus(key,suffix=''){lessonMessage={key,suffix};el('lessonStatus').textContent=t(key,key==='lessonEmpty'?originals.get(el('lessonStatus')):'')+(suffix?' '+suffix:'');}
  function sendActivity(kind,text,context){const requestId=globalThis.crypto?.randomUUID?.()||'activity-'+Date.now().toString(36)+'-'+(++activitySequence);if(!window.sendText(text,context,requestId))return false;pendingActivity={requestId,kind,context:!!context};setLessonStatus(kind==='lesson'?'lessonSent':'practiceWaiting');return true;}
  function setNoteStatus(key){noteStatusKey=key;el('noteStatus').textContent=t(key,originals.get(el('noteStatus')));}
  function setFeedback(key){feedbackKey=key;el('exerciseFeedback').textContent=key?t(key):'';}
  function setTopicStatus(topic){lessonMessage=null;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+t(topic.basis.includes('estimate')?'estimate':topic.basis.includes('textbook')?'textbook':'reference');}
  function clearLearningScope(){pendingLesson=null;selectedTopic=null;resetLearningState();window.resetSessionView?.();el('text').value='';el('lessonTopic').value='';el('courseSearch').value='';setLessonStatus('lessonEmpty');renderCourses();updateLessonActions();}
  function resetLearningState(){pendingActivity=null;feedbackKey=null;recentExercise=null;el('exerciseAnnouncement').textContent='';el('exerciseQuestion').textContent='';el('exerciseFeedback').textContent='';el('exerciseCard').hidden=true;el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
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
  async function loadCatalogue(){catalogueFailed=false;el('catalogueRetry').hidden=true;try{const data=await requestJson('/api/curriculum/topics');topics=(data.topics||[]).filter(x=>typeof x.subject==='string'&&!!x.subject.trim()&&typeof x.topic==='string'&&!!x.topic.trim()&&Number.isInteger(x.grade)&&x.grade>=1&&x.grade<=12).map(x=>({...x,basis:String(x.basis||'')}));const order=['数学','英语','语文','物理','化学','生物','历史','地理'];topics.sort((a,b)=>(order.indexOf(a.subject)<0?99:order.indexOf(a.subject))-(order.indexOf(b.subject)<0?99:order.indexOf(b.subject))||a.grade-b.grade);}catch{catalogueFailed=true;topics=[];}renderSubjects();renderCourses();}
  function updateService(){el('serviceStatus').textContent=t(serviceReady?'ready':'unavailable');el('serviceDot').className=serviceReady?'ready':'error';}
  function updateRuntime(){const messages=[];if(edition==='university')messages.push(t('languageNotice'));if((status?.generator||healthInfo?.generator)==='mock')messages.push(edition==='university'?'Video preview: the teacher video is a placeholder. Teaching availability is shown after connecting.':'视频演示：当前为占位画面，教学功能会在连接后确认。');if(status?.responder==='rules')messages.push(t('rulesLesson'));if(status&&!status.board)messages.push(t('noTeacher'));el('runtimeNotice').textContent=messages.join(' ');el('runtimeNotice').hidden=!messages.length;}
  function updateLessonActions(){const allowed=serviceReady&&connection==='ready'&&status?.board&&status.responder!=='rules';el('startLesson').disabled=!allowed||!el('lessonTopic').value.trim();el('practice').disabled=connection!=='ready'||!status?.board||status?.responder==='rules'||!!recentExercise;}
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
    const chosen=selectedTopic&&selectedTopic.topic===topic?selectedTopic:null;const grade=chosen?(chosen.grade<=6?'小学'+'一二三四五六'[chosen.grade-1]+'年级':(chosen.grade<=9?'初':'高')+'一二三'[(chosen.grade-7)%3]):'';const prompt=chosen?'给我上一节'+grade+chosen.subject+'「'+topic+'」的课，请按照'+grade+'的课程要求讲解。':'给我上一节'+topic+'的课';
    if(connection==='ready'){if(sendActivity('lesson',prompt,chosen)){el('stepLearn').classList.add('current');}}
    else{pendingLesson={text:prompt,context:chosen};setLessonStatus('lessonWaiting');el('connect').click();}
  }
  function renderExercise(ex){const announcement=el('exerciseAnnouncement');const spoken=ex?[t('yourTurn','轮到你啦'),ex.question||ex.concept,...(ex.option_texts||[])].join(' '):'';if(announcement.textContent!==spoken)announcement.textContent=spoken;recentExercise=ex||null;el('exerciseCard').hidden=!ex&&!el('exerciseFeedback').textContent;if(ex){const question=ex.question||ex.concept;el('exerciseQuestion').textContent=[question,...(ex.option_texts||[])].join('\n');el('suggestionLabel').textContent=t('exercisePending');el('stepPractice').classList.add('current');}else el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));updateLessonActions();}
  function onLessonEvent(event){const message=event.detail;const data=message.data||{};if(message.event==='utterance_end'&&data.decision&&pendingActivity&&data.request_id===pendingActivity.requestId){const dec=data.decision;const starts=dec.kind===pendingActivity.kind&&(pendingActivity.kind!=='lesson'||pendingActivity.context||(typeof dec.topic==='string'&&dec.topic.trim()));if(data.applied===false){setLessonStatus('requestSuperseded');pendingActivity=null;}else if(!starts){setLessonStatus('requestNotStarted');pendingActivity=null;}else pendingActivity.accepted=true;}if(message.event==='error'&&['lessonSent','practiceWaiting'].includes(lessonMessage?.key))setLessonStatus('lessonFailed');if(message.event!=='lesson')return;
    if(data.stage==='outline'){pendingActivity=null;setLessonStatus('outlineReady',data.title||data.topic||'');el('stepLearn').classList.add('current');}
    if(data.stage==='section')setLessonStatus('sectionReady',data.title||'');
    if(data.stage==='planned')setLessonStatus('lessonPrepared');
    if(data.stage==='outline_failed')setLessonStatus('lessonFailed');
    if(data.stage==='exercise_failed'||data.stage==='exercise_dropped'){pendingActivity=null;setLessonStatus('exerciseFailed');}
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
  el('practice').onclick=()=>{const topic=el('lessonTopic').value.trim(),chosen=selectedTopic?.topic===topic?selectedTopic:null;const grade=chosen?(chosen.grade<=6?'小学'+'一二三四五六'[chosen.grade-1]+'年级':(chosen.grade<=9?'初':'高')+'一二三'[(chosen.grade-7)%3]):'';const text=chosen?'给我出道'+grade+chosen.subject+'「'+topic+'」的练习题。':'给我出道'+topic+'练习题';sendActivity('exercise',text,chosen);};
  ['subjectFilter','gradeFilter','courseSearch'].forEach(id=>el(id).addEventListener(id==='courseSearch'?'input':'change',()=>{limit=6;renderCourses();}));
  el('moreCourses').onclick=()=>{limit+=6;renderCourses();};el('catalogueRetry').onclick=loadCatalogue;
  el('connectionRetry').onclick=()=>{if(serviceReady&&(studentsReady||el('mode').value==='public'))el('connect').click();else bootstrap();};
  el('helpOpen').onclick=()=>el('helpDialog').showModal();el('helpClose').onclick=()=>el('helpDialog').close();
  el('notes').oninput=()=>setNoteStatus(storage.set(noteKey||'liveAgent.notes.unselected',el('notes').value)?'noteSaved':'noteFailed');
  el('exportNotes').onclick=()=>download(el('notes').value,'study-notes.txt');
  el('exportChat').onclick=()=>download([...el('chat').querySelectorAll('.msg')].map(n=>n.textContent).join('\n\n'),'classroom-conversation.txt');
  window.addEventListener('live-agent:submitted',event=>{if(pendingActivity&&event.detail.request_id!==pendingActivity.requestId){pendingActivity=null;setLessonStatus('requestSuperseded');}});
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');else sendActivity('lesson',queued.text,queued.context);}updateLessonActions();});
  window.addEventListener('live-agent:profile',event=>{if(loadingProfile&&!event.detail)return;selectedProfile=event.detail;profileDisclaimer(event.detail);});
  window.addEventListener('live-agent:state',event=>renderExercise(event.detail.exercise));
  window.addEventListener('live-agent:event',onLessonEvent);
  window.addEventListener('DOMContentLoaded',()=>{setEdition(edition,true);bootstrap();});
})();

===== FILE: .cache/student-review/contracts6.txt =====
===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1403-1505 =====
1403: 
1404:     @property
1405:     def input_epoch(self) -> int:
1406:         return self._input_epoch
1407: 
1408:     async def _on_user_utterance(self, utt: Utterance, epoch: int) -> dict[str, Any]:
1409:         correlation = {"request_id": utt.request_id} if utt.request_id is not None else {}
1410:         self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text, **correlation)
1411:         # A forget request must not recall the very fact it asks to erase into the responder.
1412:         memories, memory_ids, recall_id = None, [], None
1413:         if self.memory and not _FORGET.search(utt.text):
1414:             hits_fn = getattr(self.memory, "recall_hits", None)
1415:             if hits_fn is not None:
1416:                 hits = hits_fn(utt.text, mode=self.cfg.scope)
1417:                 memories, memory_ids = [h.rendered for h in hits], [h.id for h in hits]
1418:                 recall_id = getattr(hits, "recall_id", None)
1419:             else:
1420:                 memories, memory_ids = self.memory.recall(utt.text, mode=self.cfg.scope), None
1421:         elif self.memory and hasattr(self.memory, "no_recall"):
1422:             # nothing recalled for a forget request; the responder prompt then contains no memory
1423:             # (the director never injects memory notes), so the context is isolated
1424:             recall_id = self._no_recall()
1425:         if self.memory:
1426:             self.memory.on_user_utterance(utt)
1427:         if self.director.exercise is not None and not _FORGET.search(utt.text):
1428:             graded = await self._grade_answer(utt, epoch)
1429:             if graded is not None:
1430:                 self._drain_director_events(now())
1431:                 outcome = {**correlation, "applied": not bool(graded.get("superseded"))} if correlation else {}
1432:                 self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=graded,
1433:                               chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1434:                               recalled=[], **outcome)
1435:                 return graded
1436:         self.director.student_context = self._student_context()
1437:         decision = await self.director.decide(utt, memories)
1438:         term = (decision or {}).get("forget_term")
1439:         applied = False
1440:         if epoch != self._input_epoch:
1441:             # The user barged in again while this decision was computed: it must not change the plan
1442:             # (the newer utterance decides). An erasure request is still honoured.
1443:             self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
1444:         else:
1445:             if term:  # the confirmation is spoken only after the erasure is verified (below)
1446:                 decision = {**decision, "steps": []}
1447:             queued_before = {id(x) for x in self.director.queue}
1448:             self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
1449:             applied = True
1450:             self._decisions += 1  # only applied decisions end the post-interruption wait
1451:             if self.answer_boards and (decision or {}).get("kind") == "content" \
1452:                     and self.director.answer_board_missing(decision):
1453:                 segs = [x for x in self.director.queue if id(x) not in queued_before and x.board is None and x.line]
1454:                 if segs:  # the responder left it out: write one now and show it from the next unlocked line
1455:                     self._spawn(self._answer_board(utt.text, segs), "answer_board")
1456:             self._make_figures()
1457:             kind = (decision or {}).get("kind")
1458:             if kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
1459:                 topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
1460:                 self._start_lesson(topic, utt.lesson_context)
1461:             elif kind == "lesson_stop":
1462:                 self._stop_lesson()
1463:             elif kind == "exercise" and self.director.exercise is not None:
1464:                 self.director.remind_exercise()  # one exercise at a time: the open one first
1465:             elif kind == "exercise":
1466:                 topic = utt.lesson_context["topic"] if utt.lesson_context else \
1467:                     str((decision or {}).get("topic") or "").strip() or self.director.lesson_title or "刚才讲的内容"
1468:                 self._spawn(self._give_exercise(topic, utt.lesson_context, input_epoch=epoch,
1469:                                                 profile_epoch=self._profile_epoch, plan_version=self.director.plan_version), "exercise")
1470:             elif self.director.exercise is not None:
1471:                 self.director.remind_exercise()  # a question while an exercise waits: back to it afterwards
1472:             if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
1473:                 changed = self.student.apply_update(decision["profile_update"])
1474:                 if changed:
1475:                     self._save_profile()
1476:                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
1477:                     self._emit_profile()
1478:         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
1479:         if term and self.memory is not None and hasattr(self.memory, "forget"):
1480:             complete = await self._erase(term)
1481:             line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
1482:             self.director.say_verified(line)  # a verified statement: not subject to the narration guard
1483:         if term:  # the decision itself names erased terms
1484:             raw = json.dumps(decision, ensure_ascii=False)
1485:             for x in sorted(self.director.erased_terms, key=len, reverse=True):
1486:                 raw = raw.replace(x, "[已删除]")
1487:             decision = json.loads(raw)
1488:         outcome = {**correlation, "applied": applied} if correlation else {}
1489:         self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
1490:                       chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1491:                       recalled=list(memories or []), **outcome)
1492:         return decision
1493: 
1494:     async def _erase(self, term: str) -> bool:
1495:         async with self._erase_lock:  # erasures are serialized; each owns the erasure gate
1496:             return await self._erase_locked(term)
1497: 
1498:     async def _erase_locked(self, term: str) -> bool:
1499:         """Erasure (proposal §12): quiesce locking, memory cascade, purge controller state and
1500:         stored prompts, drop unpresented content, restart the generator from canon. Fails closed:
1501:         an incomplete memory erasure is logged as an ERROR."""
1502:         self._ready.clear()
1503:         ack = getattr(self.memory, "acknowledge_erasure", None)
1504:         report = None
1505: 

===== CURRENT SOURCE: live_agent/backend/transport.py, lines 69-94 =====
69: PANEL_EVENTS = {"lock", "verdict", "repair", "completion_claim", "refusal", "capacity_skip", "narration_guard",
70:                 "playback_stop", "speech_onset", "utterance_end", "audit", "error", "request_done", "continuity", "lesson", "attention"}
71: PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
72:                 "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
73:                 "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
74:                 "decision", "applied", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
75:                 "audibility", "revision", "speaker", "uid", "request_id", "counts", "expected", "wrong", "target", "gave_up", "anchor_removed", "stage",
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

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 1013-1034 =====
1013: $("talk").onblur = () => { if (micPressed) endSpeech(); };
1014: addEventListener("blur", () => { if (micPressed || recorder) endSpeech(); });
1015: function sendText(v, lessonContext, requestId) {
1016:   v = (v ?? $("text").value).trim(); if (!v || !ready()) return false;
1017:   const packet = {type: "text", text: v, tp: performance.now()};
1018:   if (typeof requestId === "string") packet.request_id = requestId;
1019:   if (lessonContext && typeof lessonContext.subject === "string" && lessonContext.subject.trim() &&
1020:       Number.isInteger(lessonContext.grade) && lessonContext.grade >= 1 && lessonContext.grade <= 12 &&
1021:       typeof lessonContext.topic === "string" && lessonContext.topic.trim()) {
1022:     packet.lesson_context = {subject: lessonContext.subject.trim(), grade: lessonContext.grade, topic: lessonContext.topic.trim()};
1023:   }
1024:   if (!send(packet)) {
1025:     notice("session.sendFailed", "消息还没有发出去，请重新连接后再试。"); return false;
1026:   }
1027:   productEvent("submitted", {request_id: requestId ?? null});
1028:   chat("user", v); $("text").value = ""; return true;
1029: }
1030: $("send").onclick = () => sendText();
1031: $("text").onkeydown = e => { if (e.key === "Enter" && !e.isComposing && !e.shiftKey) { e.preventDefault(); sendText(); } };
1032: addEventListener("pagehide", () => { $("disconnect").onclick(); cancelSpeech(); camOff(false); });
1033: window.LiveAgentMedia = {...window.LiveAgentMedia, refreshLanguage};
1034: refreshLanguage();
===== FILE: tests/test_exercise_generation.py =====
"""Exercise generation keeps profile grade guidance without a contradictory age role."""

import asyncio
import json

import pytest

from live_agent.exercise import make_exercise
from live_agent.llm import ScriptedLLM


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
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_failed'}}}))")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.__oldActivity=window.__requestIds.at(-1);window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))" )
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("sendText('Newer ordinary question')")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),applied:false,decision:{kind:'exercise'}}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.locator('#lessonTopic').fill('Custom empty-topic fixture')
                page.locator('#startLesson').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),decision:{kind:'lesson',topic:''}}}}))")
                assert 'did not start' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',question:'Successful practice fixture'}}}))")
                assert 'question is ready' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_closed'}}}))")
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
                page.route('**/api/curriculum/topics',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'topics':[{'subject':'','grade':3,'topic':'INVALID EMPTY SUBJECT'},{'subject':'数学','grade':3,'topic':''},{'subject':'   ','grade':3,'topic':'INVALID BLANK SUBJECT'},{'subject':'数学','grade':3,'topic':'Valid catalogue fixture','basis':'textbook'}]})))
                page.goto(origin+'/?edition=primary&mode=public')
                page.wait_for_selector('.course-card')
                assert page.locator('.course-card').count()==1
                page.locator('.course-card').click()
                assert page.locator('#lessonTopic').input_value()=='Valid catalogue fixture'
                results.append({'catalogue validation':'blank subjects/topics are excluded; valid chapter remains selectable'})
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
