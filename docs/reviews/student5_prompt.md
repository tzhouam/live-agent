Targeted independent read-only re-review of the four student4 findings, using the inlined current source and tests. Shell sandbox cannot start; do not mutate files. Number concrete remaining findings and mark blocking, major or minor, with evidence. Do not broaden to unrelated features, diagnose unsupported model performance or equate reported tests with verification. This is a student frontend engineering change; PROJECT.md is inlined. The prior frontend/backend and student scope/privacy/recording repairs were independently reviewed.

Repairs: successful practice events update actual status to prepared, ready-to-answer, closed or reviewed; no question/feedback state leaves practiceWaiting after completion. A custom lesson decision without a nonempty topic and without catalogue context produces the not-started explanation. Each lesson/practice button generates a unique request_id; optional bounded request_id passes through live.sendText, backend queue, Utterance, initial/decision/grading utterance_end and panel allow-list, distinct from unchanged server uid. Only its matching decision can resolve the current request; ordinary packets keep their original shape. Error-state edition switching leaves error state and refreshes the overlay/connection advice, preserving specific same-language error advice, without restart/events/profile replacement.

Browser checks use actual page scripts plus explicit CPU/synthetic fixtures: unrelated A chat decision while B practice waits must not change B; matching B chat resolves not-started; custom lesson with empty topic resolves not-started; successful question open and close resolve ready/closed; grading and language changes keep accurate feedback; actual finishSession error then edition switch keeps translated error. Synthetic request packets are intercepted after the actual CPU connection/text/media check; they qualify UI/packet behavior, not a teaching model. Endpoint regression independently verifies actual WebSocket request IDs, absent IDs, invalid/max-length IDs and grading echoes.

Measured locally before this final packet repair: full CPU Python 398 passed with one GPU-only skip. Current combined frontend suite 89 passed; owned live subset 29 passed. Final affected backend, full Python and browser checks are finishing after latest changes. No real model teaching, GPU, training, deployment/broadcast, English instruction, university curriculum or learning efficacy was qualified. Three audience editions are interface configurations. Recording text remains an explicitly limited planned-script aid, not verified captions or audio equivalence; scoped resources filter a trusted local operator service, not authenticated accounts.

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

===== FILE: docs/reviews/student4_review.md =====
Read-only re-review of the inlined source; I did not run the reported tests.

1. **Major — Successful practice still stays “waiting.”** In [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js), a matching `utterance_end` with `kind: "exercise"` leaves `practiceWaiting` in place. `exercise_open`, grading, and closure update the question and feedback but never `lessonStatus`. Check a successful practice request through question closure; the status still says it is waiting for a question.

2. **Major — A custom lesson can wait indefinitely without starting.** A typed goal has no `lesson_context`. The [orchestrator](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1454) starts a lesson only when the decision also supplies a nonempty `topic`, while `product.js` treats `kind: "lesson"` alone as a started request. A lesson decision with an empty topic produces no lesson start or failure event and leaves the status waiting. Force that decision for a typed goal to settle the path.

3. **Minor — An outcome can be assigned to the wrong request.** `onLessonEvent()` checks every `utterance_end` against one global `lessonMessage`. Send chat A, then request practice B before A’s decision returns: A’s `kind: "chat"` marks B as “did not start,” and B’s later matching decision does not clear that status.

4. **Minor — Switching editions misstates an error state.** After a connection error, `setEdition()` replaces the error overlay with a generic ready prompt. [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js) refreshes the badge but does not restore the overlay; `connectionErrorText` remains in the previous language. Check a Chinese-edition WebSocket error, then switch to university.

I found no remaining concrete defect in the supplied profile navigation, learner clearing, stale exercise suppression, active-choice translation, or recording ACK wording repairs.
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
    ready:'Classroom available',unavailable:'Classroom unavailable',checking:'Checking classroom…',idle:'Ready when you are',connecting:'Preparing your classroom…',ended:'Session ended. Start again whenever you’re ready.',readyHint:'Your tutor is ready. Ask your first question.',demoProfile:'Example profile · Sample records are not your assessment.',profileEvidence:'Understanding values are uncalibrated estimates from the stored profile.',profileLoadFailed:'Could not load this profile. Try selecting it again.',studentsFailed:'Could not load learner profiles. Check that the backend is running, then try again.',serviceFailed:'The classroom service is not available. Start the backend and try again.',mockNotice:'Preview mode: placeholder video. Simple conversation is available; lesson and exercise generation require a configured teaching model.',languageNotice:'English interface · The current teaching language and school catalogue are Chinese. University course coverage is not available.',rulesLesson:'This preview cannot create lessons or practice questions. Configure a teaching model to use these actions.',noTeacher:'This persona does not support classroom lessons. Start the service with PERSONA=teacher.',selectGoal:'Enter a topic first.',lessonWaiting:'Preparing your lesson request…',lessonSent:'Lesson requested. Waiting for the tutor’s plan…',lessonPrepared:'Lesson material is prepared. Follow the live explanation.',lessonFailed:'The lesson could not be prepared. Ask a smaller question or try again.',outlineReady:'Your lesson plan is ready:',sectionReady:'Prepared section:',practiceWaiting:'Practice requested. Waiting for the question…',practiceClosed:'This question is closed. Ask for another when you’re ready.',correct:'The tutor marked this answer correct.',incorrect:'The tutor marked this answer incorrect. Ask for a hint and try again.',skipped:'You chose to skip. Ask the tutor to explain the idea.',requestNotStarted:'The tutor did not start that learning activity. Ask again or rephrase the request.',practicePrepared:'The question is prepared. Follow the tutor’s explanation.',practiceReady:'A practice question is ready. Give your answer.',practiceReviewed:'Answer feedback is ready. Review it before continuing.',exerciseFailed:'The practice question could not be prepared. Try again or choose a smaller topic.',gradingFailed:'The answer could not be graded. Ask the tutor to try again.',exercisePending:'A practice question is waiting for your answer.',noTopics:'No matching topics. Try another grade or subject, or enter a custom goal.',catalogueError:'The topic catalogue could not be loaded.',allGrades:'All school grades',topicAction:'Choose topic ↗',textbook:'Textbook chapter',estimate:'Estimated placement',reference:'Catalogue reference',customTopic:'Custom topic request',emptyExport:'There is nothing to export yet.',noteSaved:'Saved on this device',noteFailed:'Could not save. Export your notes to keep a copy.',savedExample:'Example profile',noProfiles:'No learner profiles are available. Ask the operator to configure one.',publicMode:'Test livestream · No learner profile',localStorageHelp:'Notes could not be loaded from this browser. Export any new notes before leaving.'
  };
  const zh = {ready:'课堂服务可用',unavailable:'课堂服务不可用',checking:'正在检查课堂…',idle:'课堂准备好了',connecting:'正在准备课堂…',ended:'课堂已结束，随时可以重新开始。',readyHint:'老师准备好了，说说你的第一个问题吧。',demoProfile:'示例档案 · 这里的样例记录不是你的测评结果。',profileEvidence:'理解程度为档案中的估计值，尚未校准。',profileLoadFailed:'档案暂时加载失败，请重新选择。',studentsFailed:'学习档案加载失败，请确认后端运行后重试。',serviceFailed:'课堂服务暂时不可用，请启动后端后重试。',mockNotice:'演示模式：当前是占位视频，可体验简单对话；生成课程和练习需要配置教学模型。',rulesLesson:'当前演示不能生成课程和练习。启用教学模型后即可使用。',noTeacher:'当前人设不支持教学课程，请以 PERSONA=teacher 启动服务。',selectGoal:'先写下你想学的主题吧。',lessonWaiting:'正在准备你的课程请求…',lessonSent:'已请求课程，等待老师准备大纲…',lessonPrepared:'课程内容已备好，请跟随老师的实时讲解。',lessonFailed:'备课暂时失败了，可以换一个更具体的问题再试。',outlineReady:'课程大纲已准备：',sectionReady:'已备好：',practiceWaiting:'已请求练习，正在等待题目…',practiceClosed:'这道练习已结束，准备好后可以再来一道。',correct:'老师判定这次作答正确。',incorrect:'老师判定这次作答有误，可以请老师给你一个提示。',skipped:'这次先跳过，可以请老师再讲一遍思路。',requestNotStarted:'老师没有开始这项学习活动，可以重新提问或换一种说法。',practicePrepared:'题目已备好，请跟随老师的讲解。',practiceReady:'练习题已准备好，试着回答吧。',practiceReviewed:'作答反馈已收到，看看老师的建议吧。',exerciseFailed:'练习暂时生成失败，可以重试或换一个更具体的主题。',gradingFailed:'这次未能完成批改，可以请老师重试。',exercisePending:'有一道练习在等你作答。',noTopics:'没有找到匹配课程，试试其他年级、学科，或直接填写学习目标。',catalogueError:'课程目录暂时加载失败。',allGrades:'全部年级',topicAction:'选这个主题 ↗',textbook:'教材章节',estimate:'年级归属为估计',reference:'课程目录参考',customTopic:'自选主题请求',emptyExport:'还没有可以导出的内容。',noteSaved:'已保存到当前设备',noteFailed:'保存失败，请导出笔记以保留内容。',savedExample:'示例档案',noProfiles:'尚未配置学习档案，请联系服务维护者。',publicMode:'测试直播 · 不读取学习档案',localStorageHelp:'无法读取本浏览器中的笔记，离开前请导出新笔记。'};
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
  async function loadCatalogue(){catalogueFailed=false;el('catalogueRetry').hidden=true;try{const data=await requestJson('/api/curriculum/topics');topics=(data.topics||[]).filter(x=>typeof x.subject==='string'&&typeof x.topic==='string'&&Number.isInteger(x.grade)&&x.grade>=1&&x.grade<=12).map(x=>({...x,basis:String(x.basis||'')}));const order=['数学','英语','语文','物理','化学','生物','历史','地理'];topics.sort((a,b)=>(order.indexOf(a.subject)<0?99:order.indexOf(a.subject))-(order.indexOf(b.subject)<0?99:order.indexOf(b.subject))||a.grade-b.grade);}catch{catalogueFailed=true;topics=[];}renderSubjects();renderCourses();}
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
  function onLessonEvent(event){const message=event.detail;const data=message.data||{};if(message.event==='utterance_end'&&data.decision&&pendingActivity&&data.request_id===pendingActivity.requestId){const dec=data.decision;const starts=dec.kind===pendingActivity.kind&&(pendingActivity.kind!=='lesson'||pendingActivity.context||(typeof dec.topic==='string'&&dec.topic.trim()));if(!starts)setLessonStatus('requestNotStarted');pendingActivity=null;}if(message.event==='error'&&['lessonSent','practiceWaiting'].includes(lessonMessage?.key))setLessonStatus('lessonFailed');if(message.event!=='lesson')return;
    if(data.stage==='outline'){setLessonStatus('outlineReady',data.title||data.topic||'');el('stepLearn').classList.add('current');}
    if(data.stage==='section')setLessonStatus('sectionReady',data.title||'');
    if(data.stage==='planned')setLessonStatus('lessonPrepared');
    if(data.stage==='outline_failed')setLessonStatus('lessonFailed');
    if(data.stage==='exercise_failed'||data.stage==='exercise_dropped')setLessonStatus('exerciseFailed');
    if(data.stage==='exercise')setLessonStatus('practicePrepared');
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
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');else sendActivity('lesson',queued.text,queued.context);}updateLessonActions();});
  window.addEventListener('live-agent:profile',event=>{if(loadingProfile&&!event.detail)return;selectedProfile=event.detail;profileDisclaimer(event.detail);});
  window.addEventListener('live-agent:state',event=>renderExercise(event.detail.exercise));
  window.addEventListener('live-agent:event',onLessonEvent);
  window.addEventListener('DOMContentLoaded',()=>{setEdition(edition,true);bootstrap();});
})();

===== FILE: .cache/student-review/contracts5.txt =====
===== CURRENT SOURCE: live_agent/types.py, lines 98-112 =====
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
110:     request_id: str | None = None  # optional bounded browser correlation id, distinct from the server utterance uid
111: 
112: 

===== CURRENT SOURCE: live_agent/backend/app.py, lines 282-361 =====
282:                                            "asr": bool(args.asr_url), "persona": canon.get("display_name", ""),
283:                                            "examples": canon.get("examples", []),
284:                                            "attention": orch.attention is not None,
285:                                            "board": bool(canon.get("board")),
286:                                            "student": orch.student.view() if orch.student is not None else None},
287:                                           ensure_ascii=False))
288: 
289:             async def handle_inputs() -> None:
290:                 """Utterances are processed in order, off the receive loop, so presentation acks
291:                 and barge-in keep being read (and timestamped) while ASR / the LLM run."""
292:                 while True:
293:                     kind, payload, t_end, epoch, lesson_context, request_id = await inputs.get()  # epoch stamped at receipt
294:                     try:
295:                         if kind == "audio":
296:                             from live_agent.asr import decode_audio_bytes
297: 
298:                             audio = decode_audio_bytes(payload, 16000)
299:                             text = await asr.transcribe(audio, 16000)
300:                             await ws.send_text(json.dumps({"type": "transcript", "text": text}))
301:                         else:
302:                             text = payload
303:                         if text:
304:                             # t_end = when the user stopped speaking / sent (client clock, mapped), so
305:                             # ASR and queueing delay count toward the deadlines (proposal §7)
306:                             await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, t_end,
307:                                                                    session_id=session_id, scope=mode,
308:                                                                    lesson_context=lesson_context, request_id=request_id),
309:                                                          epoch=epoch)
310:                     except Exception:  # noqa: BLE001
311:                         log.exception("input handling failed")
312: 
313:             worker = asyncio.create_task(handle_inputs())
314:             audio_end = now()
315:             done = asyncio.create_task(orch.wait_done())
316:             while True:
317:                 recv = asyncio.create_task(ws.receive())
318:                 await asyncio.wait({recv, done}, return_when=asyncio.FIRST_COMPLETED)
319:                 if not recv.done():  # the orchestrator stopped (fatal error or bounded run)
320:                     recv.cancel()
321:                     err = f"{type(orch.error).__name__}: {orch.error}" if orch.error else "session ended"
322:                     try:
323:                         await ws.send_text(json.dumps({"type": "error", "error": err}))
324:                         await ws.close()
325:                     except Exception:  # noqa: BLE001
326:                         pass
327:                     break
328:                 msg = recv.result()
329:                 if msg.get("type") == "websocket.disconnect":
330:                     break
331:                 if msg.get("bytes") is not None:
332:                     if asr is not None:
333:                         inputs.put_nowait(("audio", msg["bytes"], audio_end, orch.input_epoch, None, None))
334:                     continue
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
357:                 elif t == "ping":
358:                     await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
359:                 elif t == "clock":
360:                     transport.on_clock(data)
361:                 elif t == "camera" and isinstance(data.get("jpeg"), str) and len(data["jpeg"]) <= 400_000:

===== CURRENT SOURCE: live_agent/backend/transport.py, lines 69-94 =====
69: PANEL_EVENTS = {"lock", "verdict", "repair", "completion_claim", "refusal", "capacity_skip", "narration_guard",
70:                 "playback_stop", "speech_onset", "utterance_end", "audit", "error", "request_done", "continuity", "lesson", "attention"}
71: PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
72:                 "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
73:                 "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
74:                 "decision", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
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

===== CURRENT SOURCE: live_agent/orchestrator.py, lines 1403-1495 =====
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
1431:                 self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=graded,
1432:                               chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1433:                               recalled=[], **correlation)
1434:                 return graded
1435:         self.director.student_context = self._student_context()
1436:         decision = await self.director.decide(utt, memories)
1437:         term = (decision or {}).get("forget_term")
1438:         if epoch != self._input_epoch:
1439:             # The user barged in again while this decision was computed: it must not change the plan
1440:             # (the newer utterance decides). An erasure request is still honoured.
1441:             self.log.emit(EventType.CAPACITY_SKIP, now(), uid=utt.uid, reason="superseded_before_decision")
1442:         else:
1443:             if term:  # the confirmation is spoken only after the erasure is verified (below)
1444:                 decision = {**decision, "steps": []}
1445:             queued_before = {id(x) for x in self.director.queue}
1446:             self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
1447:             self._decisions += 1  # only applied decisions end the post-interruption wait
1448:             if self.answer_boards and (decision or {}).get("kind") == "content" \
1449:                     and self.director.answer_board_missing(decision):
1450:                 segs = [x for x in self.director.queue if id(x) not in queued_before and x.board is None and x.line]
1451:                 if segs:  # the responder left it out: write one now and show it from the next unlocked line
1452:                     self._spawn(self._answer_board(utt.text, segs), "answer_board")
1453:             self._make_figures()
1454:             kind = (decision or {}).get("kind")
1455:             if kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
1456:                 topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
1457:                 self._start_lesson(topic, utt.lesson_context)
1458:             elif kind == "lesson_stop":
1459:                 self._stop_lesson()
1460:             elif kind == "exercise" and self.director.exercise is not None:
1461:                 self.director.remind_exercise()  # one exercise at a time: the open one first
1462:             elif kind == "exercise":
1463:                 topic = utt.lesson_context["topic"] if utt.lesson_context else \
1464:                     str((decision or {}).get("topic") or "").strip() or self.director.lesson_title or "刚才讲的内容"
1465:                 self._spawn(self._give_exercise(topic, utt.lesson_context, input_epoch=epoch,
1466:                                                 profile_epoch=self._profile_epoch, plan_version=self.director.plan_version), "exercise")
1467:             elif self.director.exercise is not None:
1468:                 self.director.remind_exercise()  # a question while an exercise waits: back to it afterwards
1469:             if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
1470:                 changed = self.student.apply_update(decision["profile_update"])
1471:                 if changed:
1472:                     self._save_profile()
1473:                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
1474:                     self._emit_profile()
1475:         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
1476:         if term and self.memory is not None and hasattr(self.memory, "forget"):
1477:             complete = await self._erase(term)
1478:             line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
1479:             self.director.say_verified(line)  # a verified statement: not subject to the narration guard
1480:         if term:  # the decision itself names erased terms
1481:             raw = json.dumps(decision, ensure_ascii=False)
1482:             for x in sorted(self.director.erased_terms, key=len, reverse=True):
1483:                 raw = raw.replace(x, "[已删除]")
1484:             decision = json.loads(raw)
1485:         self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
1486:                       chains={c.chain_id: c.status.value for c in self.director.chains.values()},
1487:                       recalled=list(memories or []), **correlation)
1488:         return decision
1489: 
1490:     async def _erase(self, term: str) -> bool:
1491:         async with self._erase_lock:  # erasures are serialized; each owns the erasure gate
1492:             return await self._erase_locked(term)
1493: 
1494:     async def _erase_locked(self, term: str) -> bool:
1495:         """Erasure (proposal §12): quiesce locking, memory cascade, purge controller state and

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 1-19 =====
1: const $ = (id) => document.getElementById(id);
2: const canvas = $("screen"), g = canvas.getContext("2d");
3: let ws = null, audioCtx = null, playhead = 0, queue = [], pending = null, recorder = null, epoch = 0, decoding = [];
4: let lastUtterT = null, verified = 0, repairs = 0, pingTimer = null;
5: let connectionAttempt = 0, sessionState = "disconnected", sessionStatus = null, pingTimeouts = [], startupTimer = null;
6: let latestAttention = null;
7: let errorLanguage = null;
8: const EXAMPLES = ["请给我讲一道例题", "这一步我还没明白", "给我一道练习题", "请讲慢一点"];
9: const ENGLISH = {
10:   "session.connecting": "Connecting…", "session.starting": "Preparing your tutor…",
11:   "session.ready": "Tutor ready", "session.ended": "Session ended. You can start again.",
12:   "session.closed": "Disconnected", "session.connectFailed": "We could not connect to your tutor. Please try again.",
13:   "session.failed": "Your session stopped. Please reconnect to continue.",
14:   "session.audioUnavailable": "Audio is unavailable in this browser. Please use a browser with audio support.",
15:   "session.protocolError": "The tutor connection could not be read. Please reconnect.",
16:   "session.started": "Your tutoring session has started.", "session.notReady": "Please wait until your tutor is ready.",
17:   "session.startTimeout": "Your tutor is taking longer than expected. Please try connecting again.",
18:   "session.sendFailed": "Your message was not sent. Please reconnect and try again.",
19:   "voice.hold": "Hold to speak", "voice.release": "Release to send", "voice.permission": "Waiting for microphone permission…",

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 96-122 =====
96: function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
97: function send(o, socket = ws) {
98:   if (!socket || socket !== ws || socket.readyState !== 1) return false;
99:   try { socket.send(JSON.stringify(o)); return true; }
100:   catch (e) { console.warn("WebSocket send failed", e); return false; }
101: }
102: function setConn(s, live) { const el = $("conn"); el.textContent = s; el.className = "badge" + (live ? " live" : ""); }
103: function sessionChanged(state, detail = {}) {
104:   sessionState = state;
105:   errorLanguage = state === "error" ? (window.LiveAgentProduct?.edition === "university" ? "en" : "zh") : null;
106:   const live = state === "ready", busy = state === "connecting" || live;
107:   $("connect").disabled = busy; $("disconnect").disabled = !busy;
108:   ["text", "send"].forEach(id => $(id).disabled = !live);
109:   $("talk").disabled = !live || !sessionStatus?.asr || micUploading;
110:   $("cam").disabled = !live || !sessionStatus?.attention || camPending;
111:   ["mode", "uid", "sid"].forEach(id => { if ($(id)) $(id).disabled = busy; });
112:   document.querySelectorAll("#chips .chip").forEach(button => button.disabled = !live);
113:   const failure = $("connectionError");
114:   if (failure) {
115:     failure.hidden = state !== "error";
116:     const message = failure.querySelector("#connectionErrorText") || failure;
117:     message.textContent = state === "error" ? detail.message || "" : "";
118:   }
119:   window.LiveAgentProduct?.sessionChanged?.(state, {...detail, status: sessionStatus});
120: }
121: function notice(key, fallback, error) {
122:   if (error) feed(null, "bad", "Browser", error.message || String(error));

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 374-411 =====
374: function refreshLanguage() {
375:   setConn(sessionState === "ready" ? tr("session.ready", "老师已就绪") : sessionState === "connecting"
376:     ? tr("session.connecting", "连接中…") : connectionAttempt ? tr("session.closed", "连接已关闭") : tr("idle", "待开始"), sessionState === "ready");
377:   const language = window.LiveAgentProduct?.edition === "university" ? "en" : "zh";
378:   if (sessionState === "error" && errorLanguage !== language) {
379:     const message = tr("session.failed", "会话暂时中断了，请重新连接后继续。");
380:     $("overlay").style.display = "flex"; $("overlay").textContent = message;
381:     const failure = $("connectionError");
382:     if (failure) {
383:       failure.hidden = false;
384:       (failure.querySelector("#connectionErrorText") || failure).textContent = message;
385:     }
386:     errorLanguage = language;
387:   }
388:   if (sessionStatus) renderBadges(sessionStatus);
389:   $("cam").textContent = camPending ? tr("camera.permission", "等待摄像头授权…") : camStream
390:     ? tr("camera.off", "关闭专注检测") : tr("camera.on", "开启专注检测");
391:   $("talk").textContent = recorder?.state === "recording" ? tr("voice.release", "松开发送") : micPressed
392:     ? tr("voice.permission", "等待麦克风授权…") : tr("voice.hold", "按住说话");
393:   $("talk").title = sessionStatus?.asr ? "" : tr("voice.disabled", "这次会话暂时不能识别语音，请用文字提问。");
394:   renderFocusLabel();
395:   if (currentExercise) renderExerciseChips(currentExercise);
396:   if (shownBoard?.key === "idle") {
397:     $("boardTitle").innerHTML = esc(tr("board.title", "学习黑板"));
398:     $("boardItems").innerHTML = [tr("board.ask", "可以提问题，老师会边讲边写。"), tr("board.lesson", "选一个学习主题，就可以开始上课。")]
399:       .map(text => `<li>${esc(text)}</li>`).join("");
400:   } else if (shownBoard) {
401:     $("boardTitle").innerHTML = shownBoard.title;
402:     const [k, n] = shownBoard.progress || [];
403:     if (k != null && n != null) for (const li of $("boardItems").children) li.querySelector(".dots")?.setAttribute("aria-label", boardSentenceLabel(k, n));
404:   }
405:   if (!$("avPanel").hidden) avInfo();
406: }
407: function onStatus(m) {
408:   clearStartupTimer();
409:   const firstReady = sessionState !== "ready";
410:   sessionStatus = m;
411:   setConn(tr("session.ready", "老师已就绪"), true);

===== CURRENT SOURCE: frontend/public/assets/live.js, lines 1014-1033 =====
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
1027:   chat("user", v); $("text").value = ""; return true;
1028: }
1029: $("send").onclick = () => sendText();
1030: $("text").onkeydown = e => { if (e.key === "Enter" && !e.isComposing && !e.shiftKey) { e.preventDefault(); sendText(); } };
1031: addEventListener("pagehide", () => { $("disconnect").onclick(); cancelSpeech(); camOff(false); });
1032: window.LiveAgentMedia = {...window.LiveAgentMedia, refreshLanguage};
1033: refreshLanguage();

===== CURRENT SOURCE: tests/test_backend_api.py, lines 363-437 =====
363: def test_text_request_ids_round_trip_in_initial_and_decision_panel_events(tmp_path):
364:     with TestClient(backend(tmp_path)) as client:
365:         with client.websocket_connect("/ws") as ws:
366:             ws.send_json({"type": "hello", "mode": "private", "student": "demo"})
367:             outcomes = []
368:             for request_id, text in (("chat-A", "你好"), ("practice-B", "再聊一句"), (None, "普通消息")):
369:                 packet = {"type": "text", "text": text}
370:                 if request_id is not None:
371:                     packet["request_id"] = request_id
372:                 ws.send_json(packet)
373:                 records = []
374:                 while True:
375:                     message = ws.receive()
376:                     if "text" not in message:
377:                         continue
378:                     event = json.loads(message["text"])
379:                     if event.get("event") == "utterance_end":
380:                         records.append(event["data"])
381:                         if "decision" in event["data"]:
382:                             break
383:                 assert len(records) == 2 and records[0]["text"] == text
384:                 assert records[0]["uid"] == records[1]["uid"]
385:                 if request_id is None:
386:                     assert all("request_id" not in record for record in records)
387:                 else:
388:                     assert all(record["request_id"] == request_id for record in records)
389:                 outcomes.append(records[1])
390:             assert outcomes[0]["request_id"] != outcomes[1]["request_id"]
391: 
392: 
393: def test_invalid_request_ids_are_not_queued_and_maximum_id_is_preserved(tmp_path, monkeypatch):
394:     from live_agent.orchestrator import Orchestrator
395: 
396:     received = []
397: 
398:     async def capture(self, utterance, **kwargs):
399:         received.append(utterance)
400:         await self.transport.send_json({"type": "received_for_test"})
401: 
402:     monkeypatch.setattr(Orchestrator, "on_user_utterance", capture)
403:     with TestClient(backend(tmp_path)) as client:
404:         with client.websocket_connect("/ws") as ws:
405:             ws.send_json({"type": "hello", "mode": "private"})
406:             for invalid in (None, True, 3, "", "   ", "r" * 65):
407:                 ws.send_json({"type": "text", "text": "不要排队", "request_id": invalid})
408:                 while True:
409:                     message = ws.receive()
410:                     if "text" in message:
411:                         payload = json.loads(message["text"])
412:                         if payload.get("type") == "error":
413:                             assert payload["error"] == "invalid request_id"
414:                             break
415:             valid = "r" * 64
416:             ws.send_json({"type": "text", "text": "有效消息", "request_id": valid})
417:             while True:
418:                 message = ws.receive()
419:                 if "text" in message and json.loads(message["text"]).get("type") == "received_for_test":
420:                     break
421:             assert len(received) == 1 and received[0].request_id == valid
422: 
423: 
424: def test_grading_result_keeps_the_answer_request_id_in_panel_events():
425:     import asyncio
426:     import test_pipeline as pipeline
427:     from live_agent.backend.transport import panel_event
428:     from live_agent.exercise import Exercise
429:     from live_agent.types import EventType, Utterance, now
430: 
431:     orch, _ = pipeline.build()
432:     orch.director.exercise = Exercise("加法", "一加一等于几？", "二")
433:     result = asyncio.run(orch.on_user_utterance(Utterance("server-uid", "user", "二", now(), request_id="answer-ticket")))
434:     assert result["exercise_result"]["correct"]
435:     events = [panel_event(event, 0)["data"] for event in orch.log.events if event.type == EventType.UTTERANCE_END]
436:     assert len(events) == 2 and all(event["request_id"] == "answer-ticket" for event in events)
437:     assert all(event["uid"] == "server-uid" for event in events)
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
