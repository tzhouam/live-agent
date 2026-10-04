Independent read-only TARGETED re-review of the TWO student8 major findings and their direct regressions only. Inspect actual inlined current source, not agreement with contributor claims. Number remaining concrete findings blocking/major/minor with evidence. No shell or mutations. PROJECT.md applies. Previous reviewer supported the underlying student7 existing-question recovery, submission IDs and bounded WebSocket collector; those source paths are unchanged.

Fix1: product remembers latestSubmissionId separately from currentActivityId. Ordinary input while a question is shown preserves its creating owner for grading/closure but records the distinct new input as a candidate. Only an actual matching non-null outline/exercise/open/failure/existing event or actual nonnull exercise snapshot adopts and consumes that candidate. Newer D supersedes candidate C; terminal applied:false/nonactivity outcomes and terminal failures retire only matching candidates. Creator-owned answer feedback remains on B. Existing-question recovery keyed to latest C is also accepted even while B is still shown, then adopts the authoritative known/null B creator and consumes C. No new backend semantics or media scheduling changes. The actual backend source=lesson replacement remains allowed.

Fix2: panel error can terminate a pending activity only with the matching request ID. Old A/missing/null error IDs do not change B waiting; matching B error retires B and leaves late B activity rejected. Actual WebSocket/session failures retain the existing live.js session lifecycle and clear via sessionChanged, separate from panel errors. Error behavior does not depend on a displayed status string.

Measured locally AFTER these frontend-only repairs: full isolated browser check exit0, 9 edition/viewport layouts +24 behavior rows, zero page errors; twelve added regression rows cover actual backend-observed replacement event order, answer creator feedback, existing known/null creator, newer/terminal candidate and both practice/lesson correlated errors with retry. Source is stable. FullPython423passed/1GPUskip, frontend97passed and affectedbackend95passed remain valid; no backend/live/proxy changes in this round. Fixtures validate UI/state/packet behavior, not teaching. The cached pre-repair backend-trace.json is actual Orchestrator/Director/LessonPlanner event output under controlled model replies, demonstrating that C legitimately replaces a source=lesson B question. No real teaching/ASR model, GPU, physical AV, English teaching, learning efficacy, training, deployment or broadcast is claimed.

Please decide whether the two named fixes hold in the supplied source and direct regression paths. A source-only reviewer has not independently run the measured checks.

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

===== FILE: docs/reviews/student8_review.md =====
The inlined source leaves two **major** findings:

1. **Major — A replacement lesson can lose its UI events.** When question B is visible, [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) returns early for every ordinary text or voice submission, retaining B as `currentActivityId`. The backend permits a new lesson C to replace B when B has `source="lesson"` ([orchestrator.py](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1485)). C’s outline and later events carry C’s ID, so `acceptsActivity()` rejects them. A null exercise snapshot may clear B’s controls but does not adopt C. Check with B visible, submit a non-answer lesson request C, then deliver C’s outline.

2. **Major — An unrelated error can retire a pending activity.** In [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js), the `error` branch of `onLessonEvent` clears the pending request and its owner based only on the displayed status; it does not match `data.request_id`. If an old or unrelated error arrives while B is waiting, B’s later `exercise_open` is rejected and the activity buttons are enabled despite the server question. A delayed-error fixture with A’s error followed by B’s open event would settle the UI path.

The correlated `exercise_existing` recovery, fresh request IDs and bounded WebSocket test loops otherwise look consistent in the supplied code. I did not run the reported tests.
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
  let visibleLearner = null, lessonMessage = {key:"lessonEmpty", suffix:""}, feedbackKey = null, sessionHintKey = "roomHint", noteStatusKey = "localOnly", pendingActivity = null, activitySequence = 0, currentActivityId = null, latestSubmissionId = null, allowUnownedActivity = true;
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
  function adoptActivity(requestId,consume=false){currentActivityId=requestId;allowUnownedActivity=false;if(consume&&latestSubmissionId===requestId)latestSubmissionId=null;if(recentExercise&&!acceptsActivity(recentExercise.request_id)){setFeedback(null);renderExercise(null);window.LiveAgentMedia?.refreshLanguage?.();}}
  function sendActivity(kind,text,context){if(pendingActivity||recentExercise)return false;const requestId=globalThis.crypto?.randomUUID?.()||'activity-'+Date.now().toString(36)+'-'+(++activitySequence);if(!window.sendText(text,context,requestId))return false;pendingActivity={requestId,kind,context:!!context};setLessonStatus(kind==='lesson'?'lessonSent':'practiceWaiting');updateLessonActions();return true;}
  function setNoteStatus(key){noteStatusKey=key;el('noteStatus').textContent=t(key,originals.get(el('noteStatus')));}
  function setFeedback(key){feedbackKey=key;el('exerciseFeedback').textContent=key?t(key):'';}
  function setTopicStatus(topic){lessonMessage=null;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+t(topic.basis.includes('estimate')?'estimate':topic.basis.includes('textbook')?'textbook':'reference');}
  function clearLearningScope(){pendingLesson=null;selectedTopic=null;resetLearningState();window.resetSessionView?.();el('text').value='';el('lessonTopic').value='';el('courseSearch').value='';setLessonStatus('lessonEmpty');renderCourses();updateLessonActions();}
  function resetLearningState(){currentActivityId=null;latestSubmissionId=null;allowUnownedActivity=true;pendingActivity=null;feedbackKey=null;recentExercise=null;el('exerciseAnnouncement').textContent='';el('exerciseQuestion').textContent='';el('exerciseFeedback').textContent='';el('exerciseCard').hidden=true;el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
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
  function onLessonEvent(event) {
    const message = event.detail, data = message.data || {};
    if (message.event === 'utterance_end' && data.decision) {
      if (pendingActivity && data.request_id === pendingActivity.requestId) {
        const dec = data.decision;
        const starts = dec.kind === pendingActivity.kind && (pendingActivity.kind !== 'lesson' ||
          pendingActivity.context || (typeof dec.topic === 'string' && dec.topic.trim()));
        if (data.applied === false || !starts) {
          setLessonStatus(data.applied === false ? 'requestSuperseded' : 'requestNotStarted');
          pendingActivity = null; currentActivityId = null; latestSubmissionId = null; allowUnownedActivity = false;
        } else pendingActivity.accepted = true;
        updateLessonActions();
      }
      if (data.request_id != null && data.request_id === latestSubmissionId &&
          (data.applied === false || !['lesson','exercise'].includes(data.decision.kind))) {
        latestSubmissionId = null;
        if (currentActivityId === data.request_id && !data.decision.exercise_result) {
          currentActivityId = null; allowUnownedActivity = false;
        }
      }
    }
    if (message.event === 'error' && pendingActivity && data.request_id === pendingActivity.requestId) {
      pendingActivity = null; currentActivityId = null; latestSubmissionId = null; allowUnownedActivity = false;
      setLessonStatus('lessonFailed'); updateLessonActions();
    }
    if (message.event !== 'lesson') return;
    // A visible question keeps its owner while an answer is graded. Only an actual
    // activity from the latest input can transfer ownership to a replacement lesson.
    const adoptsLatest = data.request_id != null && data.request_id === latestSubmissionId &&
      ['outline','outline_failed','exercise','exercise_open','exercise_failed','exercise_dropped','exercise_existing'].includes(data.stage);
    if (adoptsLatest) adoptActivity(data.request_id, true);
    if (!acceptsActivity(data.request_id)) return;
    if (data.stage === 'outline') {
      pendingActivity = null; setLessonStatus('outlineReady', data.title || data.topic || '');
      el('stepLearn').classList.add('current');
    }
    if (data.stage === 'section') setLessonStatus('sectionReady', data.title || '');
    if (data.stage === 'planned') setLessonStatus('lessonPrepared');
    if (data.stage === 'outline_failed') {
      pendingActivity = null; currentActivityId = null; latestSubmissionId = null; allowUnownedActivity = false;
      setLessonStatus('lessonFailed');
    }
    if (data.stage === 'exercise_failed' || data.stage === 'exercise_dropped') {
      if (pendingActivity?.kind === 'exercise' || adoptsLatest) { currentActivityId = null; allowUnownedActivity = false; }
      if (latestSubmissionId === data.request_id) latestSubmissionId = null;
      pendingActivity = null; setLessonStatus('exerciseFailed');
    }
    if (data.stage === 'exercise') {
      if (!pendingActivity) pendingActivity = {requestId:data.request_id,kind:'exercise',accepted:true};
      setLessonStatus('practicePrepared');
    }
    if (data.stage === 'exercise_existing') {
      pendingActivity = null; latestSubmissionId = null; currentActivityId = data.exercise_request_id ?? null;
      allowUnownedActivity = currentActivityId === null;
      const ex = {...data,request_id:currentActivityId};
      setLessonStatus('exercisePending'); setFeedback(null); renderExercise(ex);
      window.LiveAgentMedia?.restoreExercise?.(ex);
    }
    if (data.stage === 'exercise_open') {
      pendingActivity = null; setLessonStatus('practiceReady'); setFeedback(null); renderExercise(data);
    }
    if (data.stage === 'exercise_closed' || data.stage === 'exercise_timeout') {
      pendingActivity = null; setLessonStatus('practiceClosed'); renderExercise(null);
    }
    if (data.stage === 'exercise_graded') {
      setLessonStatus('practiceReviewed'); el('exerciseCard').hidden = false;
      setFeedback(data.skipped ? 'skipped' : data.correct ? 'correct' : 'incorrect');
      el('stepPractice').classList.add('current');
    }
    if (data.stage === 'grading_failed') setFeedback('gradingFailed');
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
  window.addEventListener('live-agent:submitted',event=>{const incoming=event.detail.request_id??null;latestSubmissionId=incoming;if(recentExercise&&event.detail.activity!==true)return;adoptActivity(incoming);if(pendingActivity&&incoming!==pendingActivity.requestId){pendingActivity=null;setLessonStatus('requestSuperseded');}updateLessonActions();});
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');else sendActivity('lesson',queued.text,queued.context);}updateLessonActions();});
  window.addEventListener('live-agent:profile',event=>{if(loadingProfile&&!event.detail)return;selectedProfile=event.detail;profileDisclaimer(event.detail);});
  window.addEventListener('live-agent:state',event=>{const ex=event.detail.exercise;if(ex?.request_id!=null&&ex.request_id===latestSubmissionId)adoptActivity(ex.request_id,true);if(ex&&!acceptsActivity(ex.request_id))return;renderExercise(ex);});
  window.addEventListener('live-agent:event',onLessonEvent);
  window.addEventListener('DOMContentLoaded',()=>{setEdition(edition,true);bootstrap();});
})();

===== FILE: .cache/student-review/contracts9.txt =====
Exact current source excerpts for targeted student8 findings; original source line numbers are retained.

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

### frontend/public/assets/live.js:282–330
```
282:     socket.close();
283:   } else if (sessionState === "connecting") {
284:     connectionAttempt++; clearStartupTimer(); sessionChanged("disconnected");
285:     setConn(tr("session.closed", "连接已关闭")); $("overlay").textContent = tr("session.ended", "会话已结束，可以重新开始。");
286:   }
287: };
288: 
289: async function onMessage(ev, socket = ws, attempt = connectionAttempt) {
290:   if (!activeSocket(socket, attempt)) return;
291:   if (typeof ev.data === "string") {
292:     let m;
293:     try {
294:       m = JSON.parse(ev.data);
295:       if (!m || typeof m !== "object" || Array.isArray(m) || typeof m.type !== "string") throw new Error("Invalid message envelope");
296:     }
297:     catch (error) {
298:       feed(null, "bad", "Protocol", error.message);
299:       finishSession(socket, attempt, "error", tr("session.protocolError", "暂时无法读取老师的回应，请重新连接。")); socket.close(); return;
300:     }
301:     if (m.type === "chunk") { pending = {meta: m, frames: [], pcm: null, epoch}; }
302:     else if (m.type === "stop") { stopAll(); }
303:     else if (m.type === "event") { onEvent(m); }
304:     else if (m.type === "state") { onState(m); }
305:     else if (m.type === "transcript") { if (m.text) chat("user", "🎙 " + m.text); }
306:     else if (m.type === "status") { onStatus(m); }
307:     else if (m.type === "profile") { showProfile(m.profile, lastGraded); }
308:     else if (m.type === "error") {
309:       feed(null, "bad", "错误", m.error);
310:       finishSession(socket, attempt, "error", tr("session.failed", "会话暂时中断了，请重新连接后继续。")); socket.close();
311:     }
312:     else if (m.type === "pong") {
313:       const rtt = performance.now() - m.t;
314:       send({type: "clock", t_client: m.t, t_server: m.ts, rtt});
315:       $("sRtt").textContent = rtt.toFixed(0);
316:     }
317:     return;
318:   }
319:   if (!pending) return;
320:   const h264 = pending.meta.codec === "h264";
321:   if (h264 && !pending.video) {
322:     pending.video = decodeH264(ev.data, pending.meta);  // one Annex-B segment: all of the chunk's frames
323:     pending.video.catch(() => {});  // handled when the chunk completes (below)
324:   } else if (!h264 && pending.frames.length < pending.meta.n_frames) {
325:     pending.frames.push(createImageBitmap(new Blob([ev.data], {type: "image/jpeg"})));
326:   } else {
327:     pending.pcm = new Int16Array(ev.data);
328:     const c = pending; pending = null;
329:     decoding.push(c);  // arrival order = presentation order; decodes may finish out of order
330:     try {
```

### frontend/public/assets/live.js:398–409
```
398:   renderFocusLabel();
399:   if (currentExercise) {
400:     if (acceptsActivity(currentExercise.request_id ?? null)) renderExerciseChips(currentExercise);
401:     else { currentExercise = null; exerciseKey = ""; renderExerciseChips(null); }
402:   }
403:   if (shownBoard?.key === "idle") {
404:     $("boardTitle").innerHTML = esc(tr("board.title", "学习黑板"));
405:     $("boardItems").innerHTML = [tr("board.ask", "可以提问题，老师会边讲边写。"), tr("board.lesson", "选一个学习主题，就可以开始上课。")]
406:       .map(text => `<li>${esc(text)}</li>`).join("");
407:   } else if (shownBoard) {
408:     $("boardTitle").innerHTML = shownBoard.title;
409:     const [k, n] = shownBoard.progress || [];
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

### frontend/public/assets/live.js:1028–1050
```
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

### live_agent/orchestrator.py:968–975
```
968:     def _start_lesson(self, topic: str, lesson_context: dict | None = None, request_id: str | None = None) -> None:
969:         self._stop_lesson()
970:         self._lesson_mistakes = []
971:         self.director.lesson_title = topic
972:         self._lesson_task = asyncio.create_task(self._guarded(self._lesson_loop(topic, lesson_context, request_id), "lesson", fatal=False))
973:         self._aux.add(self._lesson_task)
974:         self._lesson_task.add_done_callback(lambda t: (self._aux.discard(t), self._maybe_finish()))
975: 
```

### live_agent/orchestrator.py:1047–1094
```
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
1086:         self._exercise_changed()
1087:         return decision
1088: 
1089:     def _catalogue_teaching_context(self, selected: dict | None):
1090:         if selected is None:
1091:             return self.student, self.curriculum
1092:         from live_agent.curriculum import Curriculum
1093:         from live_agent.student import StudentProfile
1094: 
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

### live_agent/orchestrator.py:1468–1522
```
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

### live_agent/director/director.py:779–785
```
779:     def stop_lesson(self) -> None:
780:         if self.exercise is not None and getattr(self.exercise, "source", "") == "lesson":
781:             self.exercise = None
782:         self.lesson_backlog.clear()
783:         self._lesson_locked.clear()
784:         self._lesson_resume = False
785:         self.lesson_title = ""
```

### tests/test_activity_requests.py:195–211
```
195: def test_new_lesson_can_still_replace_an_exercise_from_the_current_lesson():
196:     async def scenario():
197:         orch, _ = pipeline.build()
198:         orch.director.exercise = Exercise("加法", "一加一等于几？", "二", source="lesson", request_id="lesson-B")
199:         started = []
200: 
201:         def classify(messages):
202:             return json.dumps({"is_answer": False, "correct": False}) if messages[0]["role"] != "system" else \
203:                 json.dumps({"kind": "lesson", "topic": "减法", "steps": []})
204: 
205:         orch.director.llm = ScriptedLLM(classify)
206:         orch._start_lesson = lambda topic, context, owner: started.append((topic, owner))
207:         await orch.on_user_utterance(Utterance("C", "user", "请改讲减法", now(), request_id="lesson-C"))
208:         assert started == [("减法", "lesson-C")]
209:         assert not any(event["stage"] == "exercise_existing" for event in lesson_events(orch))
210: 
211:     asyncio.run(scenario())
```

### scripts/student_frontend_check.py:1–235
```
1: """Real-browser student UI checks against isolated CPU services, never the user's profiles.
2: 
3: Usage: python3 scripts/student_frontend_check.py [--shots DIRECTORY]
4: Mock sessions verify transport/UX. Explicit synthetic lesson events verify rendering only.
5: """
6: from __future__ import annotations
7: import argparse
8: import json
9: import os
10: from pathlib import Path
11: import socket
12: import subprocess
13: import tempfile
14: import time
15: from urllib.request import urlopen
16: from playwright.sync_api import sync_playwright
17: 
18: ROOT = Path(__file__).resolve().parents[1]
19: 
20: 
21: def port():
22:     with socket.socket() as sock:
23:         sock.bind(('127.0.0.1', 0))
24:         return sock.getsockname()[1]
25: 
26: 
27: def event_fixture(page, event, **data):
28:     """Deliver a synthetic wire event through both real browser event handlers."""
29:     page.evaluate("packet=>onMessage({data:JSON.stringify({type:'event',t:0,request:0,...packet})})", {'event': event, 'data': data})
30: 
31: 
32: def lesson_fixture(page, **data):
33:     event_fixture(page, 'lesson', **data)
34: 
35: 
36: def exercise_snapshot_fixture(page, exercise):
37:     page.evaluate("exercise=>onMessage({data:JSON.stringify({type:'state',exercise,erasure_gate_open:true,chains:[]})})", exercise)
38: 
39: 
40: def question_fixture(owner, label):
41:     return {'request_id': owner, 'concept': label, 'kind': 'choice', 'question': label + ' question',
42:             'options': ['A', 'B'], 'option_texts': ['A. ' + label + ' first', 'B. ' + label + ' second']}
43: 
44: 
45: def assert_question(page, owner, label):
46:     assert page.locator('#exerciseCard').is_visible()
47:     assert label + ' question' in page.locator('#exerciseQuestion').inner_text()
48:     assert label + ' second' in page.locator('#exerciseAnnouncement').text_content()
49:     assert page.locator('#chips .answer').count() == 3
50:     assert page.evaluate('currentExercise?.request_id ?? null') == owner
51:     assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', owner)
52: 
53: 
54: def open_question_fixture(page, owner, label):
55:     assert page.evaluate('owner=>sendText("Controlled lesson activity", undefined, owner)', owner)
56:     assert page.evaluate('window.__requestIds.at(-1)') == owner
57:     assert page.evaluate('window.__submissions.at(-1).activity') is True
58:     lesson_fixture(page, stage='exercise_open', **question_fixture(owner, label))
59:     assert_question(page, owner, label)
60: 
61: 
62: def ordinary_fixture(page, text):
63:     previous = page.evaluate('window.__requestIds.at(-1)')
64:     page.locator('#text').fill(text)
65:     page.locator('#text').press('Enter')
66:     owner = page.evaluate('window.__requestIds.at(-1)')
67:     assert isinstance(owner, str) and owner and owner != previous
68:     assert page.evaluate('window.__submissions.at(-1).activity') is False
69:     return owner
70: 
71: 
72: def activity_owner_checks(page, results):
73:     """Controlled wire outcomes: real input IDs, rendering and ownership; no model qualification."""
74:     old_owner = 'fixture-replacement-B'
75:     open_question_fixture(page, old_owner, 'Old lesson B')
76:     new_owner = ordinary_fixture(page, '给我上一节新主题的课')
77:     assert_question(page, old_owner, 'Old lesson B')
78:     assert not page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', new_owner)
79:     # Ordering captured from actual Orchestrator/Director and LessonPlanner with
80:     # controlled is_answer:false and kind:lesson replies: applied C decision,
81:     # C outline/section/planned, late B close, then C's newly posed question.
82:     event_fixture(page, 'utterance_end', request_id=new_owner, speaker='user', text='给我上一节新主题的课')
83:     event_fixture(page, 'utterance_end', request_id=new_owner, applied=True,
84:                   decision={'kind': 'lesson', 'topic': 'Replacement C'})
85:     assert_question(page, old_owner, 'Old lesson B')
86:     lesson_fixture(page, request_id=new_owner, stage='outline', title='Replacement C outline',
87:                    sections=['Replacement C section'])
88:     assert 'Replacement C outline' in page.locator('#lessonStatus').inner_text()
89:     assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', new_owner)
90:     assert not page.locator('#exerciseCard').is_visible()
91:     assert not page.locator('#chips .answer').count()
92:     lesson_fixture(page, request_id=new_owner, stage='section', title='Replacement C section', section=0)
93:     lesson_fixture(page, request_id=new_owner, stage='planned', title='Replacement C outline')
94:     prepared = page.locator('#lessonStatus').inner_text()
95:     lesson_fixture(page, request_id=old_owner, stage='exercise_closed')
96:     assert page.locator('#lessonStatus').inner_text() == prepared
97:     lesson_fixture(page, stage='exercise_open', **question_fixture(new_owner, 'Replacement C'))
98:     assert_question(page, new_owner, 'Replacement C')
99:     lesson_fixture(page, stage='exercise_open', **question_fixture(old_owner, 'Stale old B'))
100:     exercise_snapshot_fixture(page, question_fixture(old_owner, 'Stale old B'))
101:     assert_question(page, new_owner, 'Replacement C')
102:     results.append({'manual lesson replacement': 'actual backend ordering adopts ordinary C plan and question; late B close/open/state cannot overwrite C'})
103: 
104:     answer_owner = ordinary_fixture(page, 'B')
105:     assert_question(page, new_owner, 'Replacement C')
106:     lesson_fixture(page, request_id=new_owner, stage='exercise_graded', correct=True)
107:     lesson_fixture(page, request_id=new_owner, stage='exercise_closed')
108:     event_fixture(page, 'utterance_end', request_id=answer_owner, applied=True,
109:                   decision={'kind': 'chat', 'exercise_result': {'correct': True}})
110:     assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
111:     assert page.locator('#exerciseCard').is_visible()
112:     assert not page.locator('#chips .answer').count()
113:     assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', new_owner)
114:     answer_status = page.locator('#lessonStatus').inner_text()
115:     lesson_fixture(page, request_id=answer_owner, stage='outline', title='Retired answer outline')
116:     lesson_fixture(page, stage='exercise_open', **question_fixture(answer_owner, 'Retired answer'))
117:     exercise_snapshot_fixture(page, question_fixture(answer_owner, 'Retired answer'))
118:     assert page.locator('#lessonStatus').inner_text() == answer_status
119:     assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
120:     assert not page.locator('#chips .answer').count()
121:     results.append({'answer creator': 'ordinary answer ID retains creator grading/closure and feedback; its terminal decision cannot revive an activity'})
122: 
123:     old_owner = 'fixture-newer-candidate-B'
124:     open_question_fixture(page, old_owner, 'Shown B')
125:     retired_owner = ordinary_fixture(page, 'Older ordinary C')
126:     newest_owner = ordinary_fixture(page, 'Newer ordinary D')
127:     assert retired_owner != newest_owner
128:     event_fixture(page, 'utterance_end', request_id=retired_owner, applied=False, decision={'kind': 'lesson', 'topic': 'Old C'})
129:     event_fixture(page, 'utterance_end', request_id=retired_owner, applied=True, decision={'kind': 'chat'})
130:     lesson_fixture(page, request_id=retired_owner, stage='outline', title='Old C outline')
131:     lesson_fixture(page, stage='exercise_open', **question_fixture(retired_owner, 'Old C'))
132:     exercise_snapshot_fixture(page, question_fixture(retired_owner, 'Old C'))
133:     assert_question(page, old_owner, 'Shown B')
134:     lesson_fixture(page, request_id=newest_owner, stage='outline', title='Current D outline')
135:     assert 'Current D outline' in page.locator('#lessonStatus').inner_text()
136:     lesson_fixture(page, stage='exercise_open', **question_fixture(newest_owner, 'Current D'))
137:     assert_question(page, newest_owner, 'Current D')
138:     results.append({'newer candidate': 'newer ordinary D survives old C terminal outcomes and rejects old C activity events/snapshot'})
139: 
140:     for terminal in ('not_applied', 'nonactivity', 'outline_failed', 'exercise_failed'):
141:         old_owner = 'fixture-terminal-B-' + terminal
142:         open_question_fixture(page, old_owner, 'Terminal B ' + terminal)
143:         failed_owner = ordinary_fixture(page, 'Candidate C ' + terminal)
144:         if terminal in ('not_applied', 'nonactivity'):
145:             event_fixture(page, 'utterance_end', request_id=failed_owner, applied=terminal != 'not_applied',
146:                           decision={'kind': 'lesson', 'topic': 'Superseded C'} if terminal == 'not_applied' else {'kind': 'chat'})
147:             assert_question(page, old_owner, 'Terminal B ' + terminal)
148:         else:
149:             lesson_fixture(page, request_id=failed_owner, stage=terminal, error='Controlled activity failure')
150:             assert not page.locator('#exerciseCard').is_visible()
151:             assert not page.locator('#chips .answer').count()
152:             assert page.evaluate('currentExercise===null')
153:         terminal_status = page.locator('#lessonStatus').inner_text()
154:         terminal_question = page.locator('#exerciseQuestion').inner_text()
155:         lesson_fixture(page, request_id=failed_owner, stage='outline', title='Terminal C revival')
156:         lesson_fixture(page, stage='exercise_open', **question_fixture(failed_owner, 'Terminal C revival'))
157:         exercise_snapshot_fixture(page, question_fixture(failed_owner, 'Terminal C revival'))
158:         assert page.locator('#lessonStatus').inner_text() == terminal_status
159:         assert page.locator('#exerciseQuestion').inner_text() == terminal_question
160:         assert not page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', failed_owner)
161:         results.append({'terminal candidate': terminal, 'outcome': 'late correlated outline/open/snapshot cannot revive the retired C'})
162: 
163:     for creator_kind in ('known', 'legacy_null'):
164:         old_owner = 'fixture-existing-B-' + creator_kind
165:         open_question_fixture(page, old_owner, 'Visible B ' + creator_kind)
166:         input_owner = ordinary_fixture(page, 'New lesson while B waits ' + creator_kind)
167:         creator = old_owner if creator_kind == 'known' else None
168:         existing = question_fixture(input_owner, 'Authoritative B ' + creator_kind)
169:         lesson_fixture(page, stage='exercise_existing', exercise_request_id=creator, **existing)
170:         assert_question(page, creator, 'Authoritative B ' + creator_kind)
171:         # Existing-question resolution arrives before the final decision on the
172:         # backend path that blocks a new lesson with a standalone question.
173:         event_fixture(page, 'utterance_end', request_id=input_owner, applied=True,
174:                       decision={'kind': 'lesson', 'topic': 'Blocked new lesson'})
175:         lesson_fixture(page, stage='exercise_existing', exercise_request_id=creator,
176:                        **question_fixture(input_owner, 'Consumed C recovery'))
177:         lesson_fixture(page, request_id=input_owner, stage='outline', title='Consumed C outline')
178:         exercise_snapshot_fixture(page, question_fixture(input_owner, 'Consumed C snapshot'))
179:         assert_question(page, creator, 'Authoritative B ' + creator_kind)
180:         answer_owner = ordinary_fixture(page, 'B')
181:         assert_question(page, creator, 'Authoritative B ' + creator_kind)
182:         lesson_fixture(page, request_id=creator, stage='exercise_graded', correct=True)
183:         lesson_fixture(page, request_id=creator, stage='exercise_closed')
184:         event_fixture(page, 'utterance_end', request_id=answer_owner, applied=True,
185:                       decision={'kind': 'chat', 'exercise_result': {'correct': True}})
186:         assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
187:         assert not page.locator('#chips .answer').count()
188:         results.append({'visible question recovery': creator_kind, 'outcome': 'latest ordinary C recovers existing creator before its decision; candidate is consumed and creator-owned answer feedback persists'})
189: 
190:     old_owner = 'fixture-snapshot-B'
191:     open_question_fixture(page, old_owner, 'Snapshot old B')
192:     snapshot_owner = ordinary_fixture(page, 'New activity C with only a state snapshot')
193:     exercise_snapshot_fixture(page, question_fixture(snapshot_owner, 'Snapshot C'))
194:     assert_question(page, snapshot_owner, 'Snapshot C')
195:     lesson_fixture(page, request_id=old_owner, stage='exercise_closed')
196:     assert_question(page, snapshot_owner, 'Snapshot C')
197:     lesson_fixture(page, request_id=snapshot_owner, stage='exercise_closed')
198:     results.append({'actual snapshot adoption': 'nonnull latest ordinary C question is adopted; old B closure cannot clear it'})
199: 
200:     for action in ('practice', 'startLesson'):
201:         page.locator('#' + action).click()
202:         owner = page.evaluate('window.__requestIds.at(-1)')
203:         waiting_status = page.locator('#lessonStatus').inner_text()
204:         assert page.locator('#startLesson').is_disabled()
205:         assert page.locator('#practice').is_disabled()
206:         for correlation in ({'request_id': 'UNRELATED-OLD-ERROR'}, {'request_id': None}, {}):
207:             event_fixture(page, 'error', where='lesson', error='Delayed unrelated failure', **correlation)
208:             assert page.locator('#lessonStatus').inner_text() == waiting_status
209:             assert page.locator('#startLesson').is_disabled()
210:             assert page.locator('#practice').is_disabled()
211:             assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', owner)
212:         event_fixture(page, 'error', request_id=owner, where='lesson', error='Matching activity failure')
213:         assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
214:         assert not page.locator('#startLesson').is_disabled()
215:         assert not page.locator('#practice').is_disabled()
216:         failed_status = page.locator('#lessonStatus').inner_text()
217:         event_fixture(page, 'utterance_end', request_id=owner, applied=True,
218:                       decision={'kind': 'exercise' if action == 'practice' else 'lesson', 'topic': 'Late failed activity'})
219:         lesson_fixture(page, request_id=owner, stage='outline', title='Failed activity revival')
220:         lesson_fixture(page, stage='exercise_open', **question_fixture(owner, 'Failed activity revival'))
221:         exercise_snapshot_fixture(page, question_fixture(owner, 'Failed activity revival'))
222:         assert page.locator('#lessonStatus').inner_text() == failed_status
223:         assert not page.locator('#exerciseCard').is_visible()
224:         assert not page.locator('#chips .answer').count()
225:         page.locator('#practice').click()
226:         next_owner = page.evaluate('window.__requestIds.at(-1)')
227:         assert next_owner != owner
228:         next_status = page.locator('#lessonStatus').inner_text()
229:         event_fixture(page, 'error', request_id=owner, where='lesson', error='Delayed failed activity error')
230:         assert page.locator('#lessonStatus').inner_text() == next_status
231:         lesson_fixture(page, stage='exercise_open', **question_fixture(next_owner, 'Retry after ' + action))
232:         assert_question(page, next_owner, 'Retry after ' + action)
233:         lesson_fixture(page, request_id=next_owner, stage='exercise_closed')
234:         results.append({'correlated activity error': action, 'outcome': 'unrelated/null/missing IDs leave B waiting; matching error resolves B, rejects late B activity, and permits a successful retry'})
235: 
```

===== FILE: .cache/manual-lesson-owner/backend-trace.json =====
{
  "b_open": {
    "type": "event",
    "event": "lesson",
    "t": 4922269.08,
    "request": null,
    "data": {
      "kind": "choice",
      "request_id": "B",
      "stage": "exercise_open",
      "concept": "Old B concept",
      "options": [
        "A",
        "B"
      ],
      "question": "OLD B QUESTION",
      "option_texts": [
        "A. Old first",
        "B. Old second"
      ]
    }
  },
  "events": [
    {
      "type": "event",
      "event": "utterance_end",
      "t": 4922269.08,
      "request": null,
      "data": {
        "text": "给我上一节新主题的课",
        "speaker": "user",
        "uid": "manual-C",
        "request_id": "C"
      }
    },
    {
      "type": "event",
      "event": "utterance_end",
      "t": 4922269.08,
      "request": null,
      "data": {
        "decision": {
          "relation": "new",
          "kind": "lesson",
          "topic": "New C topic",
          "steps": [
            {
              "line": "好，我们换一节课。"
            }
          ]
        },
        "applied": true,
        "chains": {},
        "recalled": [],
        "uid": "manual-C",
        "request_id": "C"
      }
    },
    {
      "type": "event",
      "event": "lesson",
      "t": 4922269.09,
      "request": null,
      "data": {
        "request_id": "C",
        "stage": "outline",
        "title": "NEW C OUTLINE",
        "sections": [
          "NEW C SECTION"
        ],
        "plan": [
          {
            "title": "NEW C SECTION",
            "concepts": [
              "新知识"
            ],
            "depth": "new",
            "exercise": true
          }
        ],
        "note": "",
        "adaptive": false,
        "topic": "New C topic"
      }
    },
    {
      "type": "event",
      "event": "lesson",
      "t": 4922269.09,
      "request": null,
      "data": {
        "request_id": "C",
        "stage": "section",
        "title": "NEW C SECTION",
        "section": 0,
        "lines": 4,
        "points": 1,
        "depth": "new",
        "exercise": "NEW C QUESTION"
      }
    },
    {
      "type": "event",
      "event": "lesson",
      "t": 4922269.09,
      "request": null,
      "data": {
        "request_id": "C",
        "stage": "planned",
        "title": "NEW C OUTLINE"
      }
    },
    {
      "type": "event",
      "event": "lesson",
      "t": 4922269.09,
      "request": null,
      "data": {
        "request_id": "C",
        "stage": "figure_judgement",
        "title": "NEW C SECTION",
        "board": "s0",
        "judgements": []
      }
    },
    {
      "type": "event",
      "event": "lesson",
      "t": 4922269.09,
      "request": null,
      "data": {
        "request_id": "B",
        "stage": "exercise_closed"
      }
    },
    {
      "type": "event",
      "event": "lesson",
      "t": 4922269.09,
      "request": null,
      "data": {
        "kind": "choice",
        "request_id": "C",
        "stage": "exercise_open",
        "concept": "新知识",
        "options": [
          "A",
          "B"
        ],
        "question": "NEW C QUESTION",
        "option_texts": [
          "A. First",
          "B. Second"
        ]
      }
    }
  ]
}