Perform a targeted read-only material re-review of student3 findings. Evidence is inlined; the shell sandbox cannot start. Do not run shell mutations or infer that reported tests prove the code. Give any remaining concrete findings as a numbered list marked blocking, major or minor, with evidence or a decisive check. If no remaining material defect in these repairs, state that plainly. Focus the supplied repairs, not unrelated feature or model-quality work.

The owner requested a student frontend with all three editions (primary/secondary Chinese, university/adult English). PROJECT.md governs phase scope. Chinese/Mandarin teacher and school catalogue remain; no university curriculum, verified captions, English teaching, GPU or efficacy qualification is claimed. The frontend/backend split and earlier student findings are recorded separately. This review follows student3, not an initial implementation review.

Current repairs: profile URL/classroom/recording links synchronize to the chosen learner before its GET settles, after draft-discard refusal handling. Delayed exercise tasks capture input/profile epochs and plan version at scheduling; before/after await and on failure, superseded output emits only an audit record without a stale question, failure event or spoken apology. Product waiting statuses consume actual utterance_end decision kinds and explicit generation failures, explaining when no learning activity started. End/error clear exercise chips and all accessible choice text; product error clears question/card/live-region. Edition switching re-renders actual session/lesson/grading status and preserves a failed note-save warning; active exercise chips refresh without events/profile replay. Authored diagnostic templates translate into English while raw backend/user/curriculum values retain their original language. Recording omission warnings describe missing complete ACKs without inferring stopped playback.

Additional contributor audit repairs: selecting another learner after End clears the previous chat, board/canvas, memory/feed and lesson goal immediately before reconnect; ordinary edition switches preserve that session content. A matching profile request guard remains. The browser check verifies this and note-save warning persistence, activity failure/unclassified outcomes, and language changes with real page code.

Measured locally: latest affected Python suites 70 passed. Latest browser run passed nine edition/viewport layout cases and nine behavior scenarios without page errors/overflow; isolated CPU transport plus explicit synthetic capability/lesson/exercise decisions, no real teaching model. Owned subsets measured 39 profile/recordings and 27 live tests passed. Full Python and combined frontend suites are running after these final changes. Prior full CPU run was 393 passed and one GPU-only skip. Reported tests were not independently run by you.

Recording text remains an explicitly limited planned-script aid, not verified audio transcription/captions or a reliable spoken equivalent. The student3 review supports that disclosure and exact scoped media ownership. The trusted local service still has no account authentication; scoped navigation is not secure learner account isolation. Do not characterize those disclosed unimplemented qualifications as claims made by this work.

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

===== FILE: docs/reviews/student3_review.md =====
This was a read-only review of the inlined source. I did not run the reported tests.

1. **Major — Profile navigation can still target the previous learner.** In [profile.js](/data/zhoutaichang/live-agent/frontend/public/assets/profile.js), selecting B clears A’s visible fields immediately, but `load()` updates the URL and navigation links only after B’s GET succeeds. If it stalls or fails, the selector says B while the classroom and recordings links still point to A. Check `/profile?student=A`, select B, fail B’s GET, then inspect the address and links.

2. **Major — An old practice request can open after a newer turn.** [Orchestrator._give_exercise](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1103) captures `plan_version` before awaiting generation, but rejects a changed plan only while `d.listening` is true. Once a newer decision finishes, the old question can pass that guard. Hold generation for request A, finish a newer request B, then release A and check for `exercise_open`.

3. **Major — Lesson and practice controls can remain stuck waiting.** [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) marks a successful send as “waiting,” while [the orchestrator](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1435) starts the action only if the responder classifies it as `lesson` or `exercise`. A different classification produces no terminal action event; `exercise_failed` is also unhandled by the student status. The supplied tests force the desired classifications. Check a valid chapter request classified as `chat`, and a practice request emitting `exercise_failed`.

4. **Minor — Ending a session leaves exercise choices in the page.** The product clears the question card and live region, but [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js) only disables the answer chips; their accessible labels can still contain the old choices. An error transition also leaves the card and live region intact. Check `exercise_open` followed by End and by an unclean close.

5. **Minor — Changing editions overwrites live status.** `setEdition()` in [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js) resets dynamic session, lesson, suggestion, and note status text to initial translations. It can tell a connected learner to choose a profile and can erase a failed note-save warning while the note is still unsaved. Check both states before and after changing editions.

6. **Minor — English runtime controls remain partly untranslated.** An open exercise keeps its old-language answer chips after an edition change. [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js) also translates event headings but leaves its own Chinese diagnostic detail strings intact. This concerns interface text, not the intentionally Chinese teacher or catalogue.

7. **Minor — The recording omission notice overstates playback evidence.** [traces.js](/data/zhoutaichang/live-agent/frontend/public/assets/traces.js) says omitted requests were “incompletely played.” [resources.py](/data/zhoutaichang/live-agent/live_agent/backend/resources.py) establishes incomplete *chunk acknowledgements*; a lost ACK does not prove playback stopped. The notice should describe missing complete ACKs.

The inlined source does support the core public-mode clearing, immediate profile-field clearing, exact media ownership in scoped listings and files, and catalogue context for requests classified as lessons or exercises. The recording panel correctly presents its text as a limited script aid, with known partial ACK requests omitted and full or legacy evidence labelled; the absence of verified captions is disclosed rather than claimed away.
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
  let visibleLearner = null, lessonMessage = {key:"lessonEmpty", suffix:""}, feedbackKey = null, sessionHintKey = "roomHint", noteStatusKey = "localOnly";
  const originals = new Map(), originalAttributes = new Map();
  document.querySelectorAll('[data-i18n-aria]').forEach(node=>originalAttributes.set(node,node.getAttribute('aria-label')));
  document.querySelectorAll('[data-i18n]').forEach(node => originals.set(node,node.textContent));
  const en = {
    skip:'Skip to classroom',navigation:'Main navigation',brand:'YāLearn',mySpace:'My learning space',classroom:'Live classroom',courses:'Explore topics',profile:'Learning profile',recordings:'Session recordings',help:'Quick guide',experience:'Experience',tagAsk:'Ask freely',tagPractice:'Learn & practice',tagPace:'Your own pace',retry:'Try again',liveRoom:'YOUR LIVE CLASSROOM',roomHint:'Choose a learner profile to get started',private:'Private session',video:'AI tutor video',board:'Lesson board',boardTitle:'A little space for a new idea',boardIntro:'Your tutor’s key points will appear here.',boardAsk:'Ask a question whenever you need.',boardPractice:'Try a practice question as you learn.',learner:'Learner',editProfile:'Edit profile',connect:'Enter classroom ↗',disconnect:'End session',inputLabel:'Ask your tutor',send:'Send',talk:'Hold to speak',avButton:'Audio / video sync',inputHint:'Enter to send · A new question interrupts playback',avOffset:'Video delay',avTest:'Test flash & sound',avReset:'Reset',avHelp:'If the sound is late, move right. If the picture is late, move left. This setting stays in this browser; test again after changing headphones.',tryAsk:'A starting point for your next question',suggestions:'Suggested questions',aiNotice:'AI explanations and grading can be wrong. Check important details against your course materials.',todayGoal:'Start with a learning goal',lessonHelp:'Enter your classroom, then request an explanation or practice.',topicLabel:'I want to understand',startLesson:'Start a lesson →',lessonEmpty:'Choose a topic below, or enter your own question.',stepChoose:'Choose a goal',stepChooseHelp:'Make your next learning task clear',stepLearn:'Explore the idea',stepLearnHelp:'Follow the board and ask questions',stepPractice:'Check your understanding',stepPracticeHelp:'Try a question and reflect on feedback',practice:'Request a practice question ↗',yourTurn:'YOUR TURN',exercise:'Practice question',exerciseHelp:'Use the choices below the classroom or type your answer.',profileGlance:'My learning profile',manage:'Edit ↗',profileEmpty:'Select a profile to see your learning records.',discover:'FOLLOW YOUR CURIOSITY',courseHeading:'Explore a topic worth understanding',catalogueNote:'Available catalogue: Chinese school subjects. Chapter titles and teaching are currently in Chinese; university courses are not included.',subject:'Subject',grade:'School grade',allSubjects:'All subjects',searchCourses:'Search topics',searchPlaceholder:'Search a chapter title…',coursesLoading:'Loading available topics…',moreCourses:'Show more topics ↓',conversation:'Classroom conversation',export:'Export',conversationEmpty:'Your questions and your tutor’s responses appear here.',notes:'My study notes',localOnly:'Stored in this browser only',notesPlaceholder:'An idea to remember. A question to revisit…',notesHelp:'Notes stay on this device, grouped by learner.',diagnostics:'Classroom settings & technical details',sessionSettings:'Session settings',sessionMode:'Mode',memoryIdentity:'Memory identifier',settingsHelp:'Test livestream mode does not use a student profile. The memory identifier connects session memories; it is not a login.',cameraHelp:'Focus check requires camera permission. Images are analyzed without being saved.',metrics:'Runtime diagnostics · measurements / estimates',metricsHelp:'Onset is measured from audio energy; it does not measure answer correctness. Simulated judging does not verify real actions.',intent:'Instruction state',timeline:'Event log',memory:'Session memory',footer:'YāLearn · Bring a question. Leave with understanding.',footerDetail:'AI classroom by Live Agent',close:'Close',helpOne:'Choose a learner profile, then enter the classroom.',helpTwo:'Choose a topic or enter a goal, then request a lesson. You can also type a question directly.',helpThree:'Interrupt to ask for clarification. Use the choices or text box to answer a practice question.',helpFour:'Edit or reset the profile and learning history. Notes are stored only in this browser.',helpLimit:'This edition translates the interface. The current curriculum covers Chinese school subjects and the teacher speaks Mandarin. Voice and video depend on service configuration.',privacyHelp:'This is a local classroom for trusted devices, without student authentication or account isolation. Recordings may include conversations; take care with personal information on shared devices.',
    ready:'Classroom available',unavailable:'Classroom unavailable',checking:'Checking classroom…',idle:'Ready when you are',connecting:'Preparing your classroom…',ended:'Session ended. Start again whenever you’re ready.',readyHint:'Your tutor is ready. Ask your first question.',demoProfile:'Example profile · Sample records are not your assessment.',profileEvidence:'Understanding values are uncalibrated estimates from the stored profile.',profileLoadFailed:'Could not load this profile. Try selecting it again.',studentsFailed:'Could not load learner profiles. Check that the backend is running, then try again.',serviceFailed:'The classroom service is not available. Start the backend and try again.',mockNotice:'Preview mode: placeholder video. Simple conversation is available; lesson and exercise generation require a configured teaching model.',languageNotice:'English interface · The current teaching language and school catalogue are Chinese. University course coverage is not available.',rulesLesson:'This preview cannot create lessons or practice questions. Configure a teaching model to use these actions.',noTeacher:'This persona does not support classroom lessons. Start the service with PERSONA=teacher.',selectGoal:'Enter a topic first.',lessonWaiting:'Preparing your lesson request…',lessonSent:'Lesson requested. Waiting for the tutor’s plan…',lessonPrepared:'Lesson material is prepared. Follow the live explanation.',lessonFailed:'The lesson could not be prepared. Ask a smaller question or try again.',outlineReady:'Your lesson plan is ready:',sectionReady:'Prepared section:',practiceWaiting:'Practice requested. Waiting for the question…',practiceClosed:'This question is closed. Ask for another when you’re ready.',correct:'The tutor marked this answer correct.',incorrect:'The tutor marked this answer incorrect. Ask for a hint and try again.',skipped:'You chose to skip. Ask the tutor to explain the idea.',requestNotStarted:'The tutor did not start that learning activity. Ask again or rephrase the request.',exerciseFailed:'The practice question could not be prepared. Try again or choose a smaller topic.',gradingFailed:'The answer could not be graded. Ask the tutor to try again.',exercisePending:'A practice question is waiting for your answer.',noTopics:'No matching topics. Try another grade or subject, or enter a custom goal.',catalogueError:'The topic catalogue could not be loaded.',allGrades:'All school grades',topicAction:'Choose topic ↗',textbook:'Textbook chapter',estimate:'Estimated placement',reference:'Catalogue reference',customTopic:'Custom topic request',emptyExport:'There is nothing to export yet.',noteSaved:'Saved on this device',noteFailed:'Could not save. Export your notes to keep a copy.',savedExample:'Example profile',noProfiles:'No learner profiles are available. Ask the operator to configure one.',publicMode:'Test livestream · No learner profile',localStorageHelp:'Notes could not be loaded from this browser. Export any new notes before leaving.'
  };
  const zh = {ready:'课堂服务可用',unavailable:'课堂服务不可用',checking:'正在检查课堂…',idle:'课堂准备好了',connecting:'正在准备课堂…',ended:'课堂已结束，随时可以重新开始。',readyHint:'老师准备好了，说说你的第一个问题吧。',demoProfile:'示例档案 · 这里的样例记录不是你的测评结果。',profileEvidence:'理解程度为档案中的估计值，尚未校准。',profileLoadFailed:'档案暂时加载失败，请重新选择。',studentsFailed:'学习档案加载失败，请确认后端运行后重试。',serviceFailed:'课堂服务暂时不可用，请启动后端后重试。',mockNotice:'演示模式：当前是占位视频，可体验简单对话；生成课程和练习需要配置教学模型。',rulesLesson:'当前演示不能生成课程和练习。启用教学模型后即可使用。',noTeacher:'当前人设不支持教学课程，请以 PERSONA=teacher 启动服务。',selectGoal:'先写下你想学的主题吧。',lessonWaiting:'正在准备你的课程请求…',lessonSent:'已请求课程，等待老师准备大纲…',lessonPrepared:'课程内容已备好，请跟随老师的实时讲解。',lessonFailed:'备课暂时失败了，可以换一个更具体的问题再试。',outlineReady:'课程大纲已准备：',sectionReady:'已备好：',practiceWaiting:'已请求练习，正在等待题目…',practiceClosed:'这道练习已结束，准备好后可以再来一道。',correct:'老师判定这次作答正确。',incorrect:'老师判定这次作答有误，可以请老师给你一个提示。',skipped:'这次先跳过，可以请老师再讲一遍思路。',requestNotStarted:'老师没有开始这项学习活动，可以重新提问或换一种说法。',exerciseFailed:'练习暂时生成失败，可以重试或换一个更具体的主题。',gradingFailed:'这次未能完成批改，可以请老师重试。',exercisePending:'有一道练习在等你作答。',noTopics:'没有找到匹配课程，试试其他年级、学科，或直接填写学习目标。',catalogueError:'课程目录暂时加载失败。',allGrades:'全部年级',topicAction:'选这个主题 ↗',textbook:'教材章节',estimate:'年级归属为估计',reference:'课程目录参考',customTopic:'自选主题请求',emptyExport:'还没有可以导出的内容。',noteSaved:'已保存到当前设备',noteFailed:'保存失败，请导出笔记以保留内容。',savedExample:'示例档案',noProfiles:'尚未配置学习档案，请联系服务维护者。',publicMode:'测试直播 · 不读取学习档案',localStorageHelp:'无法读取本浏览器中的笔记，离开前请导出新笔记。'};
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
  function setNoteStatus(key){noteStatusKey=key;el('noteStatus').textContent=t(key,originals.get(el('noteStatus')));}
  function setFeedback(key){feedbackKey=key;el('exerciseFeedback').textContent=key?t(key):'';}
  function setTopicStatus(topic){lessonMessage=null;el('lessonStatus').textContent=topic.subject+' · '+gradeLabel(topic.grade)+' · '+t(topic.basis.includes('estimate')?'estimate':topic.basis.includes('textbook')?'textbook':'reference');}
  function clearLearningScope(){pendingLesson=null;selectedTopic=null;resetLearningState();window.resetSessionView?.();el('text').value='';el('lessonTopic').value='';el('courseSearch').value='';setLessonStatus('lessonEmpty');renderCourses();updateLessonActions();}
  function resetLearningState(){feedbackKey=null;recentExercise=null;el('exerciseAnnouncement').textContent='';el('exerciseQuestion').textContent='';el('exerciseFeedback').textContent='';el('exerciseCard').hidden=true;el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));['stepChoose','stepLearn','stepPractice'].forEach(id=>el(id).classList.toggle('current',id==='stepChoose'));}
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
    if(connection!=='ready'&&connection!=='connecting'){el('conn').textContent=t('idle','待开始');el('overlay').textContent=next==='university'?'Your classroom is ready.\nEnter to meet your AI tutor.':next==='primary'?'小课堂准备好啦！\n点「进入课堂」和老师见面吧。':'课堂准备好了\n点击「进入课堂」与老师见面';}
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
    if(connection==='ready'){if(window.sendText(prompt,chosen)){setLessonStatus('lessonSent');el('stepLearn').classList.add('current');}}
    else{pendingLesson={text:prompt,context:chosen};setLessonStatus('lessonWaiting');el('connect').click();}
  }
  function renderExercise(ex){const announcement=el('exerciseAnnouncement');const spoken=ex?[t('yourTurn','轮到你啦'),ex.question||ex.concept,...(ex.option_texts||[])].join(' '):'';if(announcement.textContent!==spoken)announcement.textContent=spoken;recentExercise=ex||null;el('exerciseCard').hidden=!ex&&!el('exerciseFeedback').textContent;if(ex){const question=ex.question||ex.concept;el('exerciseQuestion').textContent=[question,...(ex.option_texts||[])].join('\n');el('suggestionLabel').textContent=t('exercisePending');el('stepPractice').classList.add('current');}else el('suggestionLabel').textContent=t('tryAsk',originals.get(el('suggestionLabel')));updateLessonActions();}
  function onLessonEvent(event){const message=event.detail;const data=message.data||{};if(message.event==='utterance_end'&&data.decision&&['lessonSent','practiceWaiting'].includes(lessonMessage?.key)){const expected=lessonMessage.key==='lessonSent'?'lesson':'exercise';if(data.decision.kind!==expected)setLessonStatus('requestNotStarted');}if(message.event==='error'&&['lessonSent','practiceWaiting'].includes(lessonMessage?.key))setLessonStatus('lessonFailed');if(message.event!=='lesson')return;
    if(data.stage==='outline'){setLessonStatus('outlineReady',data.title||data.topic||'');el('stepLearn').classList.add('current');}
    if(data.stage==='section')setLessonStatus('sectionReady',data.title||'');
    if(data.stage==='planned')setLessonStatus('lessonPrepared');
    if(data.stage==='outline_failed')setLessonStatus('lessonFailed');
    if(data.stage==='exercise_failed'||data.stage==='exercise_dropped')setLessonStatus('exerciseFailed');
    if(data.stage==='exercise_open'){setFeedback(null);renderExercise(data);}
    if(data.stage==='exercise_closed'){renderExercise(null);}
    if(data.stage==='exercise_graded'){el('exerciseCard').hidden=false;setFeedback(data.skipped?'skipped':data.correct?'correct':'incorrect');el('stepPractice').classList.add('current');}
    if(data.stage==='grading_failed')setFeedback('gradingFailed');
  }
  function loadNotes(){noteKey='liveAgent.notes.'+(el('mode').value==='public'?'public':encodeURIComponent(el('sid').value||'unselected'));el('notes').value=storage.get(noteKey)||'';setNoteStatus('localOnly');}
  function download(contents,name){if(!contents.trim()){setNoteStatus('emptyExport');return;}const url=URL.createObjectURL(new Blob([contents],{type:'text/plain;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  el('edition').onchange=()=>setEdition(el('edition').value);
  el('sid').onchange=selectProfile;el('mode').onchange=()=>{profileRequest++;selectedProfile=null;loadingProfile=false;clearLearningScope();el('uid').value=el('mode').value==='public'?'public-preview':'learner:'+el('sid').value;modePresentation();links();selectProfile();renderCourses();updateLessonActions();el('connect').disabled=!serviceReady||(el('mode').value!=='public'&&!studentsReady);el('connectionError').hidden=serviceReady&&(el('mode').value==='public'||studentsReady);if(el('mode').value!=='public'&&!studentsReady)bootstrap();window.layoutStage?.();};el('lessonTopic').oninput=()=>{selectedTopic=null;setLessonStatus('customTopic');updateLessonActions();};el('startLesson').onclick=requestLesson;
  el('practice').onclick=()=>{const topic=el('lessonTopic').value.trim(),chosen=selectedTopic?.topic===topic?selectedTopic:null;const grade=chosen?(chosen.grade<=6?'小学'+'一二三四五六'[chosen.grade-1]+'年级':(chosen.grade<=9?'初':'高')+'一二三'[(chosen.grade-7)%3]):'';const text=chosen?'给我出道'+grade+chosen.subject+'「'+topic+'」的练习题。':'给我出道'+topic+'练习题';if(window.sendText(text,chosen))setLessonStatus('practiceWaiting');};
  ['subjectFilter','gradeFilter','courseSearch'].forEach(id=>el(id).addEventListener(id==='courseSearch'?'input':'change',()=>{limit=6;renderCourses();}));
  el('moreCourses').onclick=()=>{limit+=6;renderCourses();};el('catalogueRetry').onclick=loadCatalogue;
  el('connectionRetry').onclick=()=>{if(serviceReady&&(studentsReady||el('mode').value==='public'))el('connect').click();else bootstrap();};
  el('helpOpen').onclick=()=>el('helpDialog').showModal();el('helpClose').onclick=()=>el('helpDialog').close();
  el('notes').oninput=()=>setNoteStatus(storage.set(noteKey||'liveAgent.notes.unselected',el('notes').value)?'noteSaved':'noteFailed');
  el('exportNotes').onclick=()=>download(el('notes').value,'study-notes.txt');
  el('exportChat').onclick=()=>download([...el('chat').querySelectorAll('.msg')].map(n=>n.textContent).join('\n\n'),'classroom-conversation.txt');
  window.addEventListener('live-agent:status',event=>{status=event.detail;updateRuntime();if(pendingLesson){const queued=pendingLesson;pendingLesson=null;if(status.responder==='rules'||!status.board)setLessonStatus(status.responder==='rules'?'rulesLesson':'noTeacher');else if(window.sendText(queued.text,queued.context))setLessonStatus('lessonSent');}updateLessonActions();});
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
let latestAttention = null;
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
  "board.sentence": "Sentence ", "board.sentenceSuffix": "", "idle": "Ready when you are",
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
  "event.forget": " · Delete “{term}”", "event.retry": " · Retry #{request}", "event.withCorrections": " · With corrections",
  "event.repeat": "(repeat the original instruction)", "event.done": "Done.", "event.afterVerification": "(after verification)",
  "event.superseded": "Replaced by a newer instruction", "event.narrationRemoved": "Removed unverified completion wording: “{text}”",
  "event.erasureComplete": "Deleted {count} records (including derived content, logs and generator state)",
  "event.erasurePending": "Deletion incomplete: generation paused while processing", "event.complete": "Complete",
  "event.incomplete": "Incomplete (safely paused)", "event.playbackStopped": "Playback stopped; unpresented content discarded",
  "event.outline": "Lesson outline: {title} ({count} sections)",
  "event.section": "Section {index} prepared: {title} ({lines} sentences, {points} board points)",
  "event.sectionFailed": "Section {index} generation failed{next}", "event.skipped": "; skipped", "event.retrying": "; retrying",
  "event.outlineFailed": "Lesson outline generation failed", "event.planned": "Whole lesson prepared: {title}",
  "event.figureJudgement": "Figure assessment “{title}”: ",
  "event.figurePoint": "Point {index}, complexity {complexity} {decision}{reason}",
  "event.figureNeeded": "→ figure", "event.figureNotNeeded": "→ no figure",
  "event.figure": "Figure for point {index} prepared ({kind})", "event.plot": "Plotted figure", "event.illustration": "Illustration",
  "event.figureFailed": "Figure generation failed: {error}", "event.exercise": "Practice ({concept}): {text}",
  "event.exerciseFailed": "Practice generation failed: {error}",
  "event.exerciseTimeout": "No answer for practice “{concept}”; the tutor will explain and continue",
  "event.gradingFailed": "Grading failed: {error}", "event.profileUpdated": "Learner profile updated ({changed})",
  "event.depth.review": "Review", "event.depth.core": "Core", "event.depth.new": "New material", "event.withPractice": "+practice",
  "event.sectionPractice": "Practice after this section: {text}", "event.unsure": "Not sure",
  "event.correct": "Correct", "event.incorrect": "Incorrect", "event.mastery": " · Estimated mastery {before} → {after}",
  "event.anchorsRemoved": "Absent from the first shot: {anchors} (removed from the prompt)", "event.correctedTarget": " · Correction → #{target}",
};
function tr(key, fallback) {
  const product = window.LiveAgentProduct;
  const value = product?.edition === "university" ? (ENGLISH[key] ?? fallback) : fallback;
  return product?.t?.(key, value) ?? value;
}
function diagnostic(key, fallback, values = {}) {
  return tr(`event.${key}`, fallback).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
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
  currentExercise = null; exerciseKey = ""; setChips(idleExamples(), false);
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
  verified = repairs = 0; lastUtterT = null; lastGraded = null; exerciseKey = ""; currentExercise = null;
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

function renderBadges(m) {
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
}
function boardSentenceLabel(k, n) {
  return tr("board.sentence", "第 ") + k + "/" + n + tr("board.sentenceSuffix", " 句");
}
function renderFocusLabel() {
  const d = latestAttention;
  if (d && d.state !== "off") {
    const st = d.stable || d.state;
    const names = {focused: "专注", distracted: "走神", absent: "不在画面", unknown: "无法判断"};
    $("focus").className = "focusline " + (st || "");
    $("focus").textContent = tr("attention.label", "专注检测：") + tr(`attention.${st}`, names[st] || st) + (d.reason ? ` (${d.reason})` : "");
  } else {
    $("focus").className = "focusline";
    $("focus").textContent = camStream && !d ? tr("camera.enabled", "专注检测已开启：画面用于判断，不保存。") : tr("camera.disabled", "专注检测未开启");
  }
}
function refreshLanguage() {
  setConn(sessionState === "ready" ? tr("session.ready", "老师已就绪") : sessionState === "connecting"
    ? tr("session.connecting", "连接中…") : connectionAttempt ? tr("session.closed", "连接已关闭") : tr("idle", "待开始"), sessionState === "ready");
  if (sessionStatus) renderBadges(sessionStatus);
  $("cam").textContent = camPending ? tr("camera.permission", "等待摄像头授权…") : camStream
    ? tr("camera.off", "关闭专注检测") : tr("camera.on", "开启专注检测");
  $("talk").textContent = recorder?.state === "recording" ? tr("voice.release", "松开发送") : micPressed
    ? tr("voice.permission", "等待麦克风授权…") : tr("voice.hold", "按住说话");
  $("talk").title = sessionStatus?.asr ? "" : tr("voice.disabled", "这次会话暂时不能识别语音，请用文字提问。");
  renderFocusLabel();
  if (currentExercise) renderExerciseChips(currentExercise);
  if (shownBoard?.key === "idle") {
    $("boardTitle").innerHTML = esc(tr("board.title", "学习黑板"));
    $("boardItems").innerHTML = [tr("board.ask", "可以提问题，老师会边讲边写。"), tr("board.lesson", "选一个学习主题，就可以开始上课。")]
      .map(text => `<li>${esc(text)}</li>`).join("");
  } else if (shownBoard) {
    $("boardTitle").innerHTML = shownBoard.title;
    const [k, n] = shownBoard.progress || [];
    if (k != null && n != null) for (const li of $("boardItems").children) li.querySelector(".dots")?.setAttribute("aria-label", boardSentenceLabel(k, n));
  }
  if (!$("avPanel").hidden) avInfo();
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
  renderBadges(m);
  if (m.persona) $("title").textContent = m.persona;
  $("talk").title = m.asr ? "" : tr("voice.disabled", "这次会话暂时不能识别语音，请用文字提问。");
  sessionChanged("ready", {status: m});
  if (firstReady) chat("sys", tr("session.started", "老师已准备好，可以开始提问了。"));
  productEvent("status", m);
}

// ---------------------------------------------------------------- panel
// ---------------------------------------------------------------- student profile and exercises
let personaChips = EXAMPLES, profile = null, exerciseKey = "", currentExercise = null, lastGraded = null;
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
  currentExercise = ex || null;
  const key = ex ? JSON.stringify([ex.concept, ex.question, ex.options || [], ex.option_texts || []]) : "";
  if (key === exerciseKey) return;
  exerciseKey = key;
  renderExerciseChips(currentExercise);
}
function renderExerciseChips(ex) {
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
        feed(t, "", "理解", `${dec.relation || ""}/${dec.kind || ""}` + (dec.forget_term ? diagnostic("forget", " · 删除「{term}」", {term: dec.forget_term}) : ""));
        (d.recalled || []).forEach(x => memo(tr("memory.recalled", "召回：") + x));
      }
      break;
    case "lock":
      if (d.transcript) chat("persona", d.transcript);
      feed(t, "", `锁定 #${k}`, (d.action ? d.action.slice(0, 70) : "") + (d.transcript ? ` · 「${d.transcript}」` : "") +
           (d.retry_of != null ? diagnostic("retry", " · 重试 #{request}", {request: d.retry_of}) : "") +
           ((d.corrections || []).length ? diagnostic("withCorrections", " · 附修正") : ""));
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
      feed(t, "warn", `前向修正 #${k}→#${d.earliest_correctable}`, d.correction ? " · " + d.correction.slice(0, 80) : diagnostic("repeat", "（重复原指令）"));
      break;
    case "completion_claim": feed(t, "ok", "完成声明", `「${d.text || diagnostic("done", "好了。")}」` + diagnostic("afterVerification", "（在验证之后）")); break;
    case "refusal": feed(t, "bad", "拒绝/降级", d.reason || ""); break;
    case "capacity_skip": feed(t, "warn", "容量跳过", d.reason || diagnostic("superseded", "被更新的指令取代")); break;
    case "narration_guard": feed(t, "warn", "叙述守卫", diagnostic("narrationRemoved", "去掉未验证的完成说法：「{text}」", {text: d.original})); break;
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
        memo(d.erasure_complete ? diagnostic("erasureComplete", "已删除 {count} 条记录（含派生内容、日志与生成器状态）", {count: d.deleted}) : diagnostic("erasurePending", "删除未完成：已暂停生成，等待处理"),
             d.erasure_complete ? "ok" : "bad");
        feed(t, d.erasure_complete ? "ok" : "bad", "删除", d.erasure_complete ? diagnostic("complete", "完成") : diagnostic("incomplete", "未完成（安全暂停）"));
      } else { feed(t, "", "打断", diagnostic("playbackStopped", "停止播放，丢弃未呈现内容")); }
      break;
    case "audit":
      if ((d.issues || []).length) feed(t, "warn", "审核", d.issues.join(", "));
      break;
    case "error": feed(t, "bad", "错误", `${d.where || ""} ${d.error || ""}`); break;
    case "lesson": {
      const s = {outline: diagnostic("outline", "课程大纲：{title}（{count} 节）", {title: d.title, count: (d.sections || []).length}),
                 section: diagnostic("section", "第 {index} 节已备好：{title}（{lines} 句，{points} 条板书）", {index: (d.section ?? 0) + 1, title: d.title, lines: d.lines, points: d.points}),
                 section_failed: diagnostic("sectionFailed", "第 {index} 节生成失败{next}", {index: (d.section ?? 0) + 1, next: d.attempt ? diagnostic("skipped", "，已跳过") : diagnostic("retrying", "，重试中")}),
                 outline_failed: diagnostic("outlineFailed", "课程大纲生成失败"), planned: diagnostic("planned", "整节课已备好：{title}", {title: d.title}),
                 figure_judgement: diagnostic("figureJudgement", "配图判断「{title}」：", {title: d.title}) + (d.judgements || []).map(j =>
                   diagnostic("figurePoint", "第 {index} 条 复杂度 {complexity} {decision}{reason}", {index: j.point + 1, complexity: j.complexity ?? "?",
                     decision: j.need ? diagnostic("figureNeeded", "→ 配图") : diagnostic("figureNotNeeded", "→ 不配"), reason: j.why ? ` (${j.why})` : ""})).join("; "),
                 figure: diagnostic("figure", "第 {index} 条的配图已画好（{kind}）", {index: (d.point ?? 0) + 1, kind: d.kind === "plot" ? diagnostic("plot", "精确作图") : diagnostic("illustration", "插图")}),
                 figure_failed: diagnostic("figureFailed", "配图失败：{error}", {error: d.error}),
                 exercise: diagnostic("exercise", "出题（{concept}）：{text}", {concept: d.concept, text: d.exercise}),
                 exercise_failed: diagnostic("exerciseFailed", "出题失败：{error}", {error: d.error}),
                 exercise_timeout: diagnostic("exerciseTimeout", "练习「{concept}」无人作答，老师讲解后继续", {concept: d.concept}),
                 grading_failed: diagnostic("gradingFailed", "批改失败：{error}", {error: d.error}),
                 profile_updated: diagnostic("profileUpdated", "学生档案已更新（{changed}）", {changed: (d.changed || []).join(", ")})}[d.stage];
      if (s) feed(t, d.stage.endsWith("failed") ? "bad" : "", "备课", s);
      if (d.stage === "outline" && d.plan) {
        const dep = {review: diagnostic("depth.review", "复习"), core: diagnostic("depth.core", "重点"), new: diagnostic("depth.new", "新课")};
        feed(t, "", d.adaptive ? "因材施教" : "教案", (d.note ? d.note + "；" : "") + d.plan.map((x, i) =>
          `${i + 1}.${x.title}[${dep[x.depth] || x.depth}${x.exercise ? diagnostic("withPractice", "+练习") : ""}]`).join(" "));
      }
      if (d.stage === "section" && d.exercise) feed(t, "", "练习", diagnostic("sectionPractice", "本节后出题：{text}", {text: d.exercise}));
      if (d.stage === "exercise_graded") {
        const m = d.mastery;
        feed(t, d.correct ? "ok" : "bad", "批改", `${d.concept}：${d.skipped ? diagnostic("unsure", "不会") : d.correct ? diagnostic("correct", "答对") : diagnostic("incorrect", "答错")}` +
             (d.misconception ? `（${d.misconception}）` : "") +
             (m && m.after != null ? diagnostic("mastery", " · 掌握度 {before} → {after}", {before: m.before == null ? "–" : Math.round(m.before * 100) + "%", after: Math.round(m.after * 100) + "%"}) : ""));
      }
      if (d.stage === "exercise_graded") lastGraded = d.concept;
      if (d.stage === "exercise_open") showExercise(d);
      if (d.stage === "exercise_closed") showExercise(null);
      break;
    }
    case "attention": {
      latestAttention = d;
      renderFocusLabel();
      if (d.nudge) feed(t, "warn", "提醒学生", `「${d.nudge}」`);
      break;
    }
    case "continuity":
      if ((d.anchor_removed || []).length) feed(t, "", `场景锚定 #${k}`, diagnostic("anchorsRemoved", "首个镜头未出现：{anchors}（不再在提示中描述）", {anchors: d.anchor_removed.join(", ")}));
      if (d.wrong && Object.keys(d.wrong).length) {
        feed(t, (d.corrections || []).length ? "warn" : "", `场景连续性 #${k}`,
             Object.entries(d.wrong).map(([n, c]) => `${n}×${c.join("/")}`).join("，") +
             ((d.corrections || []).length ? diagnostic("correctedTarget", " · 修正→#{target}", {target: d.target}) : ""));
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
    d.setAttribute("aria-label", boardSentenceLabel(k, n)); cur.appendChild(d);
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
  camPending = false; camStream = stream; latestAttention = null; $("cam").disabled = false;
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
  camRequest++; camPending = false; latestAttention = null;
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
window.LiveAgentMedia = {...window.LiveAgentMedia, refreshLanguage};
refreshLanguage();

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
function clearProfileView(message = t("loading")) {
  server = null; exams = []; edits = new Map(); clean();
  ["name", "grade", "newName", "newSubject", "newMastery"].forEach(id => { $(id).value = ""; });
  $("clearHist").checked = false; $("meta").textContent = "";
  $("profileName").textContent = message; $("profileGrade").textContent = "";
  $("avatar").textContent = "…"; $("demoBadge").hidden = true;
  $("exams").innerHTML = $("concepts").innerHTML = `<p class="empty">${esc(message)}</p>`;
  $("hist").innerHTML = `<tr><td colspan="5" class="empty">${esc(message)}</td></tr>`;
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
  state = "loading"; setReady(false); clearProfileView(); setStatus(t("loading"));
  try {
    const {students} = await api("/api/students");
    if (generation !== requestGeneration) return false;
    if (!students.length) { state = "failed"; clearProfileView(t("profile")); setStatus(t("noStudents"), "err"); return false; }
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
  state = "loading"; setReady(false); clearProfileView(); setStatus(t("loading"));
  history.replaceState(null, "", pageLink("/profile"));
  updateLinks();
  try {
    const loaded = await api(`/api/students/${encodeURIComponent(requestSid)}`);
    if (!isCurrent(requestGeneration, requestSid)) return false;
    if (loaded.id !== requestSid) throw new Error("Profile identity mismatch");
    server = loaded;
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false;
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

function loadError(e) { state = "failed"; setReady(false); clearProfileView(t("profile")); setStatus(t("loadFailed", {message:e.message}), "err"); $("retryLoad").hidden = false; }
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
  transcript:"Read scripts & input", transcriptLabel:"Planned scripts and recorded input", transcriptNote:"This reading aid contains planned tutor scripts and recorded user input. Scripts may include words that were never played. This is not an audio transcript or captions, and is not a reliable equivalent of the spoken replay. Spoken words and timing have not been verified.",
  transcriptLoading:"Loading session text…", transcriptEmpty:"Nothing is available in this reading aid.", transcriptMissing:"Readable text is unavailable for this record.", transcriptError:"Session text couldn’t be loaded. Try again.", transcriptRetry:"Retry session text", tutorScript:"Planned tutor script", userInput:"Recorded user input", scriptUnknown:"Playback completion is unknown; this planned text may include unplayed words.", scriptComplete:"All expected chunks were acknowledged; script words and actual audio are still unverified.", partialOmitted:"Planned scripts were omitted where complete chunk acknowledgements are missing. Missing acknowledgements do not prove playback stopped. This reading aid does not establish coverage of the recorded audio."
} : {
  chooseLearner:"请先去课堂选择学生，再查看这个学生保存的私人课堂。",
  publicScope:"只显示公开会话，没有明确归属的旧记录不显示。当前服务用于可信的本地环境，没有账号登录；列表筛选不等于文件访问权限隔离。",
  transcript:"阅读讲稿与输入", transcriptLabel:"计划讲稿与保存的用户输入", transcriptNote:"这些文字仅供阅读参考，包括老师的计划讲稿和保存的用户输入。讲稿可能含有从未播放的内容，不是音频转写或字幕，也不能可靠替代录像中的声音。实际说出的文字和时间位置尚未核对。",
  transcriptLoading:"正在载入会话文字…", transcriptEmpty:"这份阅读参考暂时没有可显示的讲稿或输入。", transcriptMissing:"这份记录暂时没有可读文字。", transcriptError:"暂时无法载入会话文字，请重试。", transcriptRetry:"重试载入文字", tutorScript:"老师计划讲稿", userInput:"保存的用户输入", scriptUnknown:"播放是否完成尚不明确；计划讲稿可能含有未播放的文字。", scriptComplete:"已收到全部预期片段的播放确认；讲稿文字与实际声音仍未核对。", partialOmitted:"没有收到完整片段确认的请求已省略计划讲稿。确认缺失不能证明播放中止；这份阅读参考也不能确定录音内容的覆盖情况。"
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
      const notices = [note];
      if (transcript.omitted_partial_requests?.length) {
        const omitted = document.createElement("p"); omitted.className = "script-caution"; omitted.textContent = t("partialOmitted"); notices.push(omitted);
      }
      if (!entries.length) { panel.replaceChildren(...notices, status); status.textContent = t("transcriptEmpty"); }
      else {
        panel.replaceChildren(...notices);
        const lines = document.createElement("ol"); lines.className = "transcript-lines";
        entries.forEach(entry => {
          const line = document.createElement("li"), label = document.createElement("strong"), text = document.createElement("p");
          label.textContent = t(entry.role === "teacher" ? "tutorScript" : "userInput"); text.textContent = entry.text;
          line.append(label);
          if (entry.role === "teacher") {
            const caution = document.createElement("p"); caution.className = "script-caution";
            caution.textContent = t(entry.presentation?.status === "complete" ? "scriptComplete" : "scriptUnknown"); line.append(caution);
          }
          line.append(text); lines.append(line);
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

===== FILE: .cache/student-review/contracts4.txt =====
Current live_agent/orchestrator.py lines 1097-1154:
1097:     async def _give_exercise(self, topic: str, lesson_context: dict | None = None, *,
1098:                              input_epoch: int | None = None, profile_epoch: int | None = None,
1099:                              plan_version: int | None = None) -> None:
1100:         """The student asked for an exercise: one on ``topic`` at the level the profile suggests."""
1101:         from live_agent.exercise import make_exercise
1102: 
1103:         d = self.director
1104:         self._exercises += 1
1105:         input_epoch = self._input_epoch if input_epoch is None else input_epoch
1106:         profile_epoch = self._profile_epoch if profile_epoch is None else profile_epoch
1107:         plan = d.plan_version if plan_version is None else plan_version
1108: 
1109:         def superseded() -> bool:
1110:             return input_epoch != self._input_epoch or profile_epoch != self._profile_epoch or plan != d.plan_version
1111: 
1112:         def drop_superseded() -> None:
1113:             self.log.emit(EventType.AUDIT, now(), where="exercise_generation", topic=topic, reason="superseded")
1114: 
1115:         if superseded():
1116:             drop_superseded()
1117:             return
1118:         from live_agent.curriculum import parse_grade
1119: 
1120:         exercise_profile, curriculum = self._catalogue_teaching_context(lesson_context)
1121:         g = parse_grade(exercise_profile.grade) if exercise_profile is not None else None
1122:         profile = exercise_profile.summary() if lesson_context else self._student_context()
1123:         profile = profile or "无（新学生，没有档案）"
1124:         if curriculum and exercise_profile is not None:
1125:             if lesson_context:
1126:                 profile += "\n" + curriculum.teaching_context(g, CHARS_PER_REQUEST, brief=True)
1127:             profile += "\n" + curriculum.topic_context(topic, g)
1128:             if curriculum.exercise_style(g):
1129:                 profile += f"\n这个年级的练习形式：{curriculum.exercise_style(g)}"
1130:         try:
1131:             craft = curriculum.practice_craft(g, curriculum.subject_of(topic, g)) \
1132:                 if curriculum and exercise_profile is not None else ""
1133:             ex = await make_exercise(d.llm, name=d.persona_name, topic=topic, profile=profile,
1134:                                      key=f"q{self._exercises}", craft=craft)
1135:         except Exception as e:  # noqa: BLE001
1136:             if superseded():
1137:                 drop_superseded()
1138:                 return
1139:             self.log.emit(EventType.LESSON, now(), stage="exercise_failed", topic=topic, error=str(e)[:160])
1140:             d.say_verified("抱歉，这道题我没出好，你可以换个问法。")
1141:             return
1142:         if superseded():
1143:             drop_superseded()
1144:             return
1145:         if d.exercise is not None or any(
1146:                 t in ex.question or t in ex.concept for t in d.erased_terms):
1147:             self.log.emit(EventType.LESSON, now(), stage="exercise_dropped", concept=ex.concept,
1148:                           reason="another exercise is open" if d.exercise is not None else "erasure")
1149:             return
1150:         lines = ex.lines(22)
1151:         d.pose_exercise(lines[1:])  # the responder already said it will give one
1152:         self.log.emit(EventType.LESSON, now(), stage="exercise", concept=ex.concept, exercise=ex.question,
1153:                       options=ex.options, kind=ex.kind)
1154: 

Current live_agent/orchestrator.py lines 1442-1485:
1442:             if term:  # the confirmation is spoken only after the erasure is verified (below)
1443:                 decision = {**decision, "steps": []}
1444:             queued_before = {id(x) for x in self.director.queue}
1445:             self.director.apply(utt, decision, memory_ids=memory_ids, recall_id=recall_id)
1446:             self._decisions += 1  # only applied decisions end the post-interruption wait
1447:             if self.answer_boards and (decision or {}).get("kind") == "content" \
1448:                     and self.director.answer_board_missing(decision):
1449:                 segs = [x for x in self.director.queue if id(x) not in queued_before and x.board is None and x.line]
1450:                 if segs:  # the responder left it out: write one now and show it from the next unlocked line
1451:                     self._spawn(self._answer_board(utt.text, segs), "answer_board")
1452:             self._make_figures()
1453:             kind = (decision or {}).get("kind")
1454:             if kind == "lesson" and (utt.lesson_context or str((decision or {}).get("topic") or "").strip()):
1455:                 topic = utt.lesson_context["topic"] if utt.lesson_context else str(decision["topic"]).strip()
1456:                 self._start_lesson(topic, utt.lesson_context)
1457:             elif kind == "lesson_stop":
1458:                 self._stop_lesson()
1459:             elif kind == "exercise" and self.director.exercise is not None:
1460:                 self.director.remind_exercise()  # one exercise at a time: the open one first
1461:             elif kind == "exercise":
1462:                 topic = utt.lesson_context["topic"] if utt.lesson_context else \
1463:                     str((decision or {}).get("topic") or "").strip() or self.director.lesson_title or "刚才讲的内容"
1464:                 self._spawn(self._give_exercise(topic, utt.lesson_context, input_epoch=epoch,
1465:                                                 profile_epoch=self._profile_epoch, plan_version=self.director.plan_version), "exercise")
1466:             elif self.director.exercise is not None:
1467:                 self.director.remind_exercise()  # a question while an exercise waits: back to it afterwards
1468:             if self.student is not None and not utt.lesson_context and (decision or {}).get("profile_update"):
1469:                 changed = self.student.apply_update(decision["profile_update"])
1470:                 if changed:
1471:                     self._save_profile()
1472:                     self.log.emit(EventType.LESSON, now(), stage="profile_updated", changed=changed)
1473:                     self._emit_profile()
1474:         self._drain_director_events(now())  # before the erasure, so its redaction covers these events
1475:         if term and self.memory is not None and hasattr(self.memory, "forget"):
1476:             complete = await self._erase(term)
1477:             line = "好的，这件事我已经忘掉了。" if complete else "抱歉，删除还没有完成，我已经通知工作人员处理。"
1478:             self.director.say_verified(line)  # a verified statement: not subject to the narration guard
1479:         if term:  # the decision itself names erased terms
1480:             raw = json.dumps(decision, ensure_ascii=False)
1481:             for x in sorted(self.director.erased_terms, key=len, reverse=True):
1482:                 raw = raw.replace(x, "[已删除]")
1483:             decision = json.loads(raw)
1484:         self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
1485:                       chains={c.chain_id: c.status.value for c in self.director.chains.values()},
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
  for (const link of ["classroom", "courses", "profile", "recordings"])
    element(link + "Link").dataset = {link};
  const controls = ["name", "grade", "addExam", "newName", "newSubject", "newMastery", "addConcept", "clearHist", "reset", "examScore", "examDelete", "conceptSlider", "conceptDelete"];
  const document = {hidden: false, getElementById: element,
    documentElement: {dataset: {}}, querySelectorAll: selector =>
      selector.includes("[data-profile-control]") ? controls.map(element) :
      selector === "[data-link]" ? ["classroom", "courses", "profile", "recordings"].map(link => element(link + "Link")) : []};
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
  assert.equal(page.element("name").value, "");
  assert.equal(page.run("server"), null);
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
  assert.equal(page.run("exams.length"), 0);
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

test("a stalled learner switch immediately clears every visible record and the confirmed draft", async () => {
  const page = editor(), oldProfile = profile(1,"Private A name");
  oldProfile.concepts = [{name:"Private A concept",subject:"Private A subject",mastery:0.6,source:"manual",attempts:0,correct:0,notes:[]}];
  oldProfile.history = [{t:"Private A time",concept:"Private A concept",correct:false,question:"Private A question",answer:"Private A answer"}];
  page.run(`server = ${JSON.stringify(oldProfile)}; render();`);
  page.editName("Private A unsaved draft");
  page.element("newName").value = "Private A new concept";
  page.element("newSubject").value = "Private A new subject";
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  for (const id of ["name","grade","newName","newSubject","newMastery"])
    assert.equal(page.element(id).value,"",id);
  for (const id of ["exams","concepts","hist"])
    assert.doesNotMatch(page.element(id).innerHTML,/Private A|期中|数学/,id);
  assert.equal(page.element("meta").textContent,"");
  assert.equal(page.element("profileName").textContent,"载入中…");
  assert.equal(page.element("profileGrade").textContent,"");
  assert.equal(page.element("demoBadge").hidden,true);
  assert.equal(page.run("server"),null);
  assert.equal(page.run("dirty"),false);
  page.requests[0].resolve(profile(3,"Actual B name","other"));
  await switching;
  assert.equal(page.element("profileName").textContent,"Actual B name");
  assert.equal(page.element("name").value,"Actual B name");
});

test("a failed learner switch keeps the form and identity blank with usable retry", async () => {
  const page = editor({edition:"university"});
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[0].reject(new Error("offline"));
  await switching;
  assert.equal(page.element("name").value,"");
  assert.equal(page.element("grade").value,"");
  assert.equal(page.element("meta").textContent,"");
  assert.doesNotMatch(page.element("profileName").textContent,/Saved name/);
  assert.equal(page.element("name").disabled,true);
  assert.equal(page.element("retryLoad").hidden,false);
  assert.equal(page.run("server"),null);
  for (const id of ["exams","concepts","hist"])
    assert.doesNotMatch(page.element(id).innerHTML,/期中|数学|Saved name/,id);
  const retrying = page.run("load()");
  page.requests[1].resolve(profile(2,"Actual B name","other"));
  await retrying;
  assert.equal(page.element("name").value,"Actual B name");
  assert.equal(page.element("name").disabled,false);
});

test("selected learner navigation updates before a pending GET and stays current when it fails", async () => {
  const page = editor({edition:"university"});
  assert.equal(page.element("classroomLink").href,"/?edition=university&student=demo");
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  assert.equal(page.requests[0].path,"/api/students/other");
  assert.equal(page.historyUrls.at(-1),"/profile?edition=university&student=other");
  assert.equal(page.element("classroomLink").href,"/?edition=university&student=other");
  assert.equal(page.element("recordingsLink").href,"/traces?edition=university&student=other");
  assert.equal(page.element("back").href,"/?edition=university&student=other");
  page.requests[0].reject(new Error("controlled profile failure"));
  await switching;
  assert.equal(page.historyUrls.at(-1),"/profile?edition=university&student=other");
  assert.equal(page.element("classroomLink").href,"/?edition=university&student=other");
  assert.equal(page.element("recordingsLink").href,"/traces?edition=university&student=other");
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
  assert.equal(page.historyUrls.length,0);
  assert.equal(page.element("classroomLink").href,"/?edition=secondary&student=demo");
  assert.equal(page.element("recordingsLink").href,"/traces?edition=secondary&student=demo");
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

test("a reading aid shows input and ACK-associated planned scripts without claiming audio equivalence", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const nodes = descendants(page.get("sessions")), button = nodes.find(node=>node.textContent === "Read scripts & input");
  const reading = button.onclick();
  assert.equal(button["aria-expanded"],"true");
  assert.equal(page.requests[1].path,"/api/traces/sess-test/transcript?student=demo");
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"script_aid",verified_audio:false,omitted_partial_requests:[],entries:[
    {role:"user",text:"<img src=x onerror=alert(1)>",source:"utterance_end"},
    {role:"teacher",kind:"planned_script",text:"A saved explanation.\nSecond line.",source:"lock",presented:true,may_include_unplayed_words:true,presentation:{status:"unknown",chunks_acknowledged:[0],chunks_expected:null}},
    {role:"teacher",text:"Never presented",source:"lock",presented:false},
  ]});
  await reading;
  const textNodes = descendants(page.get("sessions"));
  assert.equal(textNodes.some(node=>node.textContent === "<img src=x onerror=alert(1)>"),true);
  assert.equal(textNodes.some(node=>node.textContent === "A saved explanation.\nSecond line."),true);
  assert.equal(textNodes.some(node=>node.textContent === "Never presented"),false);
  assert.equal(textNodes.some(node=>node.textContent?.includes("not an audio transcript or captions")),true);
  assert.equal(textNodes.some(node=>node.textContent === "Planned tutor script"),true);
  assert.equal(textNodes.some(node=>node.textContent?.includes("may include unplayed words")),true);
  assert.equal(textNodes.filter(node=>node.tagName === "li").length,2);
  button.onclick(); await button.onclick();
  assert.equal(page.requests.length,2); // Already-read text is not fetched again.
});

test("complete chunk acknowledgements remain unverified audio and omitted partial scripts are explained", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const reading = descendants(page.get("sessions")).find(node=>node.textContent === "Read scripts & input").onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"script_aid",verified_audio:false,omitted_partial_requests:[1],entries:[
    {role:"teacher",kind:"planned_script",text:"Planned words",source:"lock",presented:true,may_include_unplayed_words:true,presentation:{status:"complete",chunks_acknowledged:[0,1],chunks_expected:2}},
  ]});
  await reading;
  const nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "All expected chunks were acknowledged; script words and actual audio are still unverified."),true);
  assert.equal(nodes.some(node=>node.textContent === "Planned scripts were omitted where complete chunk acknowledgements are missing. Missing acknowledgements do not prove playback stopped. This reading aid does not establish coverage of the recorded audio."),true);
  assert.equal(nodes.some(node=>node.textContent === "Planned words"),true);
});

test("a request missing complete chunk acknowledgements has an explicit reading-aid gap", async () => {
  const page = library(); await page.respond([session()]);
  const reading = descendants(page.get("sessions")).find(node=>node.textContent === "阅读讲稿与输入").onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"script_aid",verified_audio:false,omitted_partial_requests:[0],entries:[]});
  await reading;
  const nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "没有收到完整片段确认的请求已省略计划讲稿。确认缺失不能证明播放中止；这份阅读参考也不能确定录音内容的覆盖情况。"),true);
  assert.equal(nodes.some(node=>node.textContent === "这份阅读参考暂时没有可显示的讲稿或输入。"),true);
  assert.equal(nodes.some(node=>node.tagName === "li"),false);
});

test("an empty script is explicit rather than invented from the video", async () => {
  const page = library(); await page.respond([session()]);
  const button = descendants(page.get("sessions")).find(node=>node.tagName === "button" && node.textContent === "阅读讲稿与输入");
  const reading = button.onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"scripted",verified_audio:false,entries:[]});
  await reading;
  assert.equal(descendants(page.get("sessions")).some(node=>node.textContent === "这份阅读参考暂时没有可显示的讲稿或输入。"),true);
});

test("transcript scope mismatches expose no content and allow retry", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const button = descendants(page.get("sessions")).find(node=>node.textContent === "Read scripts & input");
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
  assert.equal(nodes.some(node=>node.textContent === "Nothing is available in this reading aid."),true);
});

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
        querySelector() { return null; },
        querySelectorAll(selector) { return selector.includes('.badge') ? this.children.filter(child => child.className === 'badge') : []; },
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

test('English camera controls are localized on load and board progress labels use the current language', () => {
  const app = page({ edition: 'university' });
  assert.equal(app.element('cam').textContent, 'Enable focus check');
  assert.equal(app.element('focus').textContent, 'Focus check is off');
  assert.equal(app.run('boardSentenceLabel(2, 3)'), 'Sentence 2/3');
  const dot = app.element('progress-dot'), item = app.element('board-item');
  item.querySelector = selector => selector === '.dots' ? dot : null;
  app.element('boardItems').children = [item];
  app.run('shownBoard = {key: "actual-lesson", title: "原始课程标题", progress: [2, 3]}; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(dot['aria-label'], 'Sentence 2/3');
  assert.equal(app.element('boardTitle').innerHTML, '原始课程标题');
});

test('language refresh translates a connected session without replaying hooks or overwriting profile data', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ asr: true, attention: true });
  app.run('onEvent({event: "attention", data: {state: "focused", stable: "distracted", reason: "raw source reason"}}); profile = {id: "actual-profile"};');
  const hooks = app.transitions.length, events = app.events.length, packets = app.sockets[0].sent.length, timers = app.timers.size;
  app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.element('conn').textContent, 'Tutor ready');
  const badges = app.element('badges').children.map(node => node.textContent).join('\n');
  assert.match(badges, /Video: Mock video/);
  assert.doesNotMatch(badges, /生成|质检|仅文字/);
  assert.equal(app.element('focus').textContent, 'Focus check: Distracted (raw source reason)');
  assert.equal(app.element('cam').textContent, 'Enable focus check');
  assert.equal(app.run('profile.id'), 'actual-profile');
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.events.length, events);
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.timers.size, timers);
});

test('exercise language refresh preserves focused answers, backend values and readiness without replaying events', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ board: true });
  app.run(`onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Fractions", question: "选一个分数",
    options: ["A", "B"], option_texts: ["A. 二分之一", "B. 三分之一"]}}); profile = {id: "actual-profile"};`);
  assert.deepEqual(app.element('chips').children.map(node => node.textContent), ['选 A', '选 B', '我不会']);
  app.element('chips').children[1].focus();
  const key = app.run('exerciseKey'), hooks = app.transitions.length, events = app.events.length;
  const packets = app.sockets[0].sent.length, timers = app.timers.size;
  app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
  const choices = app.element('chips').children;
  assert.deepEqual(choices.map(node => node.textContent), ['Choose A', 'Choose B', 'I’m not sure']);
  assert.deepEqual(choices.map(node => node.dataset.prompt), ['选 A', '选 B', '我不会']);
  assert.equal(choices[1]['aria-label'], 'Choose B: B. 三分之一');
  assert.equal(app.run('document.activeElement === $("chips").children[1]'), true);
  assert.equal(choices.every(node => node.classList.contains('answer') && !node.disabled), true);
  assert.equal(app.run('exerciseKey'), key);
  assert.equal(app.run('profile.id'), 'actual-profile');
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.events.length, events);
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.timers.size, timers);

  app.element('text').focus();
  app.run('sessionState = "connecting"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.element('chips').children.every(node => node.disabled), true);
  assert.equal(app.run('document.activeElement === $("text")'), true);
  assert.equal(app.run('sessionState'), 'connecting');
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.events.length, events);
  assert.equal(app.transitions.length, hooks);

  app.run('resetSessionView(); window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
});

for (const [name, end] of [
  ['End', app => app.element('disconnect').onclick()],
  ['backend error', app => app.sockets[0].onmessage({data: JSON.stringify({type: 'error', error: 'Service failed'})})],
  ['unclean close', app => app.sockets[0].onclose({code: 1006, wasClean: false})],
]) {
  test(`${name} clears exercise answers and accessible labels before language refresh`, async () => {
    const app = page(); await app.connect(); await app.open(); await app.status({board: true});
    app.run(`onEvent({event: "lesson", data: {stage: "exercise_open", concept: "PRIVATE CONCEPT", options: ["A", "B"],
      option_texts: ["PRIVATE CHOICE ONE", "PRIVATE CHOICE TWO"]}});`);
    assert.match(app.element('chips').children[0]['aria-label'], /PRIVATE CHOICE/);
    await end(app);
    const packets = app.sockets[0].sent.length, events = app.events.length;
    const assertCleared = () => {
      assert.equal(app.run('exerciseKey'), '');
      assert.equal(app.run('currentExercise'), null);
      assert.equal(app.element('chips').children.every(node => node.disabled), true);
      assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
      assert.doesNotMatch(app.element('chips').children.map(node => node['aria-label'] || '').join(' '), /PRIVATE/);
    };
    assertCleared();
    app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
    assertCleared();
    assert.equal(app.sockets[0].sent.length, packets);
    assert.equal(app.events.length, events);
  });
}

test('English diagnostics translate authored detail strings across event branches', () => {
  const app = page({edition: 'university'});
  const events = [
    {event: 'utterance_end', data: {decision: {relation: 'replace', kind: 'memory', forget_term: 'term'}, recalled: ['source fact']}},
    {event: 'lock', data: {action: 'action', transcript: 'script', retry_of: 2, corrections: ['fix']}},
    {event: 'verdict', data: {kind: 'action', label: 'complied', rationale: 'raw rationale'}},
    {event: 'verdict', data: {kind: 'action', label: 'not_complied'}},
    {event: 'verdict', data: {kind: 'action', label: 'unknown'}},
    {event: 'verdict', data: {kind: 'speech', label: 'not_complied'}},
    {event: 'repair', data: {earliest_correctable: 3}},
    {event: 'completion_claim'}, {event: 'refusal', data: {reason: 'raw refusal'}}, {event: 'capacity_skip'},
    {event: 'narration_guard', data: {original: 'raw source wording'}},
    {event: 'playback_stop', data: {erasure: true, erasure_complete: true, deleted: 2}},
    {event: 'playback_stop', data: {erasure: true, erasure_complete: false}}, {event: 'playback_stop'},
    {event: 'audit', data: {issues: ['source issue']}}, {event: 'error', data: {where: 'model', error: 'source error'}},
    {event: 'lesson', data: {stage: 'outline', title: 'Topic', sections: [1, 2], adaptive: true,
      plan: [{title: 'Review', depth: 'review', exercise: true}, {title: 'Core', depth: 'core'}, {title: 'New', depth: 'new'}]}},
    {event: 'lesson', data: {stage: 'section', section: 1, title: 'Topic', lines: 2, points: 3, exercise: 'raw exercise'}},
    {event: 'lesson', data: {stage: 'section_failed', section: 1}},
    {event: 'lesson', data: {stage: 'section_failed', section: 1, attempt: 1}},
    {event: 'lesson', data: {stage: 'outline_failed'}}, {event: 'lesson', data: {stage: 'planned', title: 'Topic'}},
    {event: 'lesson', data: {stage: 'figure_judgement', title: 'Topic', judgements: [
      {point: 0, complexity: 2, need: true, why: 'source reason'}, {point: 1, need: false}]}},
    {event: 'lesson', data: {stage: 'figure', point: 0, kind: 'plot'}},
    {event: 'lesson', data: {stage: 'figure', point: 1, kind: 'illustration'}},
    {event: 'lesson', data: {stage: 'figure_failed', error: 'source error'}},
    {event: 'lesson', data: {stage: 'exercise', concept: 'Concept', exercise: 'raw exercise'}},
    {event: 'lesson', data: {stage: 'exercise_failed', error: 'source error'}},
    {event: 'lesson', data: {stage: 'exercise_timeout', concept: 'Concept'}},
    {event: 'lesson', data: {stage: 'grading_failed', error: 'source error'}},
    {event: 'lesson', data: {stage: 'profile_updated', changed: ['Concept']}},
    {event: 'lesson', data: {stage: 'exercise_graded', concept: 'Concept', correct: true, mastery: {before: 0.5, after: 0.6}}},
    {event: 'lesson', data: {stage: 'exercise_graded', concept: 'Concept', skipped: true}},
    {event: 'lesson', data: {stage: 'exercise_graded', concept: 'Concept', misconception: 'source misconception', mastery: {after: 0.4}}},
    {event: 'attention', data: {state: 'focused', reason: 'source reason', nudge: 'source reminder'}},
    {event: 'continuity', data: {anchor_removed: ['source anchor'], wrong: {anchor: ['attribute']}, corrections: ['fix'], target: 3}},
  ];
  app.run(`for (const event of ${JSON.stringify(events)}) onEvent({...event, t: 1, request: 2});`);
  const feed = app.element('feed').children.map(node => node.innerHTML).join('\n');
  const memory = app.element('memory').children.map(node => node.innerHTML).join('\n');
  assert.doesNotMatch(feed + memory, /\p{Script=Han}/u);
  assert.match(feed, /Retry #2/);
  assert.match(feed, /Section 2 prepared: Topic \(2 sentences, 3 board points\)/);
  assert.match(feed, /Point 1, complexity 2 → figure \(source reason\)/);
  assert.match(feed, /Estimated mastery 50% → 60%/);
  assert.match(feed, /Correction → #3/);
  assert.match(memory, /Deleted 2 records/);
});

test('English diagnostics retain original backend reasons, curriculum titles and user text', () => {
  const app = page({edition: 'university'});
  app.run(`onEvent({event: "utterance_end", data: {decision: {forget_term: "用户事实"}, recalled: ["原始记忆"]}});
    onEvent({event: "refusal", data: {reason: "后端原始原因"}});
    onEvent({event: "lesson", data: {stage: "outline", title: "一次函数", sections: []}});
    onEvent({event: "lesson", data: {stage: "figure_judgement", title: "一次函数", judgements: [{point: 0, need: true, why: "后端配图依据"}]}});
    onEvent({event: "narration_guard", data: {original: "原始说法"}});`);
  const feed = app.element('feed').children.map(node => node.innerHTML).join('\n');
  assert.match(feed, /Delete “用户事实”/);
  assert.match(feed, /后端原始原因/);
  assert.match(feed, /Lesson outline: 一次函数 \(0 sections\)/);
  assert.match(feed, /后端配图依据/);
  assert.match(feed, /Removed unverified completion wording: “原始说法”/);
  assert.match(app.element('memory').children[0].innerHTML, /Recalled: 原始记忆/);
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
                page.evaluate("""() => {window.__sentTexts=[];window.__lessonContexts=[];const original=ws.send.bind(ws);ws.send=data=>{try{const packet=JSON.parse(data);if(packet.type==='text'){window.__sentTexts.push(packet.text);if(packet.lesson_context)window.__lessonContexts.push(packet.lesson_context);}}catch{};original(data);};window.LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}""")
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
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{decision:{kind:'chat'}}}}))")
                assert 'did not start' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_failed'}}}))")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                results.append({'activity outcomes':'unclassified request and generation failure resolve waiting status'})
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
                assert 'material is prepared' in page.locator('#lessonStatus').inner_text()
                assert 'Choose A' in page.locator('#chips').inner_text()
                page.evaluate('showExercise(null)')
                assert 'Which value?' in page.evaluate('window.__exerciseAnnounced')
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',question:'STALE AFTER ERROR'}}}));window.LiveAgentProduct.sessionChanged('error',{message:'controlled connection failure'});}""")
                assert not page.locator('#exerciseCard').is_visible()
                assert page.locator('#exerciseAnnouncement').text_content()==''
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
