# Implementation (Phase 2)

Status: started 2026-09-26 on the owner's instruction (D-019). This document describes the implementation of
the proposal in `docs/research_proposal_zh.md` v2.11: the architecture as built, how to run it, and what is
verified. Every number is labelled *measured locally*, *cited*, *estimate* or *target*.

## Layout

| Path | Proposal § | What it is |
|---|---|---|
| `live_agent/types.py` | §9, §10 | Shared types: CanonProfile, BlockScript, IntentChain, Chunk, Verdict, TimelineEvent |
| `live_agent/prompt/h3_compiler.py` | §9 | BlockScript → TaoMate-H3 prompt string, in the official `integrated_multimodal_description` / `<d>` format. Canon fields are copied verbatim |
| `live_agent/capability.py` | §8.2 L4, §14.2 | Capability manifest. The compiler emits an action only when it is `executed`/`calibrated` and above the success threshold; otherwise it degrades or refuses (both logged as failures) |
| `live_agent/ledger.py` | §8.2 L3, §10.4 | State ledger (online CANVAS + A²RD): immutable canon, current state, per-request state, textual drift correction, bridging for unshown content |
| `live_agent/timeline.py` | §10, §11 | Single timeline, just-in-time locking (P_{k+1} = V_k + R − Λ − σ; Λ estimated online), earliest correctable request, latency model, JSONL event log |
| `live_agent/director/director.py` | §8.2 L1–2, §9 | Responder (LLM → intent chains + per-request segments), cancellation rule, narration policy ("done" is spoken only after verification), forward-repair queue, A1 open-loop mode |
| `live_agent/qc/judge.py` | §8.2 L5 | VLM judge on presented frames (K=4, may abstain), speech check (ASR character error rate), forward corrector ("semantic gradient"), mock judge |
| `live_agent/orchestrator.py` | §10–§12 | Lock loop, chunk streaming, presentation acks → QC → repair, barge-in (drop unpresented, bridge), erasure (memory cascade + generator reset) |
| `live_agent/memory/` | §12 | Typed, scoped SQLite memory: claim typing, echo detection, source-scope filtering before ranking, bi-temporal correction, erasure cascade with tombstones and `verify_erased` |
| `live_agent/memory_bridge.py` | §12 | Adapter from the memory service to the orchestrator |
| `live_agent/generator/base.py`, `mock.py` | §13 | Generator contract; CPU mock with the TaoMate-H3 chunk layout (39/34/34/17 frames, then 34/34/34/17) |
| `live_agent/generator/taomate_h3.py`, `taomate_worker/` | §13 (T1–T3) | TaoMate-H3 streaming adapter: mid-session prompt queue, audio-teacher lookahead, per-chunk output. Status is tracked in `docs/m0_measurements.md` |
| `live_agent/generator/puppet.py`, `live_agent/tts.py`, `live_agent/generator/textdraw.py` | D-047 | CPU skeleton-puppet backend: a 2D rig (keyframed poses per capability intent, mouth from the played audio envelope) plus external TTS clients (`synth` offline pseudo-speech, `url` OpenAI-compatible remote, `edge`, `piper`); peer of the TaoMate backends, per-session like the mock |
| `live_agent/backend/app.py`, `resources.py`, `config.py`, `runtime.py`, `transport.py` | — | API-only FastAPI backend: resource APIs, configuration, long-lived generator and session orchestration, WebSocket transport, profiles and private media. `live_agent/server/app.py` retains the old import/CLI path as a compatibility entry point |
| `frontend/server.mjs`, `frontend/public/` | D-045, D-046 | Separate Node frontend server and student classroom, profile editor and recording browser; Chinese primary/secondary and English university/adult interface configurations, actual school-topic navigation, lesson/exercise controls and browser-local notes. Same-origin HTTP/WebSocket proxy; AudioContext remains the playback clock and presentation acknowledgements retain their existing protocol |
| `live_agent/asr.py` | — | Qwen3-ASR client (vLLM transcription API) and audio decoding |
| `live_agent/eval/` | §7, §14, §15 | Evaluation: SCHEMA.md log format, scoring (intent chains, D table, outcome rules), stats (Wilson, Clopper–Pearson, KM, clustered bootstrap, Holm, κ, power), 30-task suite, simulated user, runner, report |
| `configs/persona_hanfu/` | §3 | Persona canon and capability manifest (24 actions covering the E2 suite; `documented` until E1 executes them) |
| `configs/persona_teacher/` | demo | Teacher persona (林老师): canon, responder rules for answers with a board, lessons, exercises and profile updates |
| `live_agent/lesson.py` | D-038, D-043 | Lesson planner: outline (subject, objectives, key point, difficulty, hook type, sections with depth and exercises), one section at a time (board points with the spoken lines under each, a guided question per section, a closing that returns to the objectives), figure judgement, and the rubric self-check of a section (`check_section`, rewrite with `feedback`) |
| `live_agent/exercise.py`, `live_agent/student.py` | D-038, D-039 | Exercises (choice / short answer, rule or LLM grading, practice-design rules from the craft data) and the student profile store |
| `live_agent/curriculum.py`, `configs/curriculum/` | D-040, D-043 | Course knowledge base: the national curriculum per subject and grade, the per-grade teaching profile (`pedagogy.json`) and the teaching craft (`teaching_craft.json`: lesson stages, teacher moves, grade bands, master teachers, board rules, quality checklist), rendered into the planner, section, exercise and self-check prompts by grade and subject; `tools/check_curriculum.py` validates the files |
| `live_agent/generator/base.py` `SessionView` | — | One live session on a long-lived shared generator: reset per session, local request numbering, stale chunks dropped (D-022) |
| `live_agent/sim.py` `Recorder` | — | MP4 of the *presented* stream (background-thread encoding), used for adjudication and E1 clips |
| `live_agent/eval/adjudicate.py` | §14, D-014 | Blinded human adjudication: shuffled items, random ids and media names, key kept apart; labels merged back as `source: adjudicated` verdicts with video→session time mapping (D-024) |
| `scripts/e1_rejudge.py`, `scripts/e1_validate.py` | §14.2 | Offline re-judging of saved E1 clips (judge v1/v2); blinded stratified human-validation page and judge-vs-human agreement (accuracy, κ, FP/FN) |
| `scripts/e1_calibrate.py` | §14.2 | E1: idle → action → idle per trial; VLM judge; Wilson CI; clips for the 20% human sample. A judge-only pass marks capabilities `executed`, and only human-validated labels make them `calibrated` |
| `scripts/serve_models.sh` | — | vLLM servers for Qwen3-8B (8101), Qwen3-VL-8B (8102), Qwen3-ASR-1.7B (8103) on one GPU (isolated venv `.venvs/serve`, vLLM 0.28.0 + torch cu129) |

## Running

Quick start: `scripts/run_live.sh demo` (CPU only) or `scripts/run_live.sh full` (7 GPUs); see `README.md`.
The launcher supervises separate frontend and backend processes. Configuration defaults are frontend
`127.0.0.1:8200` and backend `127.0.0.1:8201`; `PORT`/`HOST` configure the frontend and
`BACKEND_PORT`/`BACKEND_HOST` configure the backend. Startup readiness is the backend's `/api/health`
through the frontend proxy. The route and WebSocket boundary is documented in `docs/frontend_backend.md`.
The launcher defaults to `PERSONA=teacher`; use `PERSONA=hanfu` for the reading host. The CPU demo uses
the rule responder and cannot generate lessons or exercises. The page reports that limit. Real teaching
needs the existing configured model stack; student-interface checks did not run that GPU/model path.

```bash
# independent CPU backend, no helper models needed
python3 -m live_agent.backend.app --config configs/persona_teacher \
    --generator mock --llm-url scripted --vlm-url mock --asr-url "" \
    --dev-allow-uncalibrated --record --host 127.0.0.1 --port 8201
# independent frontend (another terminal; Node built-in modules only)
HOST=127.0.0.1 PORT=8200 BACKEND_URL=http://127.0.0.1:8201 npm --prefix frontend start
# open http://127.0.0.1:8200, /profile or /traces; tunnel only the frontend port if remote

# helper models (one GPU; always through canhazgpu)
gpu run --gpus 1 --timeout 6h --note "live-agent helper models" -- scripts/serve_models.sh

# API with real helper models and the mock generator (no video GPU needed)
python3 -m live_agent.backend.app --generator mock --dev-allow-uncalibrated --port 8201
# API with TaoMate-H3 (student on 4 GPUs, teacher on 2; started once, shared across sessions)
gpu run --gpus 6 --timeout 4h --note "live-agent backend" -- python3 -m live_agent.backend.app --generator taomate_h3
# use the same independently running frontend for either backend

# E2 simulation on the mock stack (real LLM responder, mock judge)
python3 -m live_agent.eval.runner --conditions A1 A2 --seeds 0 --speed 4 --out .cache/e2
# E2 / M1 on the real stack (TaoMate-H3 + LLM responder + VLM judge), recording what was presented
gpu run --gpus 6 --timeout 1h --note "live-agent M1" -- env PYTHONPATH=. python3 -m live_agent.eval.runner \
    --generator taomate_h3 --conditions A2 A1 --out .cache/m1 --record [--allow-uncalibrated]
python3 -m live_agent.eval.report .cache/m1/*.jsonl --compare A2:A1 -o .cache/m1/report.md

# blinded adjudication of the primary outcome
python3 -m live_agent.eval.adjudicate --help   # prepare (criteria frozen from the suite; key kept in
                                               # <batch>.key/, outside the annotator's folder) and merge
                                               # (two raters + optional arbiter; only reconciled verdicts
                                               # are appended; unresolved items listed)
python3 -m live_agent.eval.report <logs> --expected-seeds 0-4 -o report.md  # primary: exits 2 on any adjudication/observation/pairing gap
python3 -m live_agent.eval.report <logs> --source judge -o diag.md # labelled DIAGNOSTIC

# E1 calibration
gpu run --gpus 6 --timeout 4h --note "live-agent E1" -- env PYTHONPATH=. python3 scripts/e1_calibrate.py \
    --generator taomate_h3 --trials 30 --save-clips --out .cache/e1

# tests (CPU)
python3 -m pytest
npm --prefix frontend test
python3 scripts/student_frontend_check.py  # isolated browser/CPU services; Playwright + Chromium required
```

### Frontend/backend separation (2026-10-02, D-045)

The owner requested a separate frontend and backend. Browser pages and assets now live under `frontend/`;
Python owns the resource APIs and agent runtime. The frontend proxies `/api/*`, `/ws`, recordings and
board images with the existing methods, status codes and media bytes. The browser uses its current
origin, preserving the SSH/HTTPS bridge and avoiding a CORS dependency. The backend's old module path
delegates to the canonical API-only entry point and no longer serves HTML pages.

This is an engineering boundary change. The single-session generator constraint, single-process profile
version handling and student allow-list remain. Existing measurements below describe their recorded
implementation and dates; they do not establish GPU performance or physical lip sync for this refactor.
Validation (measured locally) is recorded in `docs/reviews/split1_results.md`: Python CPU tests,
frontend HTTP/WebSocket and profile-race tests, Chromium playback/profile/trace checks, and launcher
startup, failure and cleanup checks passed. Independent GPT-6 Sol review and repair dispositions are in
`docs/codex_reviews.md`. These checks do not establish a new model-backed experiment.

### Student classroom (2026-10-02, D-046)

The student page presents a focused classroom with teacher video, readable board, learner selection,
conversation, lesson topic and practice. Edition configuration is selected with `?edition=primary`,
`?edition=secondary` or `?edition=university`, or the page selector, and remembered in browser storage. The
primary and secondary interfaces use Chinese; the university/adult interface uses English. Profile
and recording links retain edition and learner selection. Technical diagnostics start collapsed.

`GET /api/curriculum/topics` returns the actual stored school chapter titles, grade and provenance;
the existing summary API remains unchanged. Subject/grade/search filters choose a topic or the student
can enter a custom goal. Lesson actions enable only after a teaching responder is ready. Selected
chapters carry backend-validated grade/subject/title context through both lesson and practice requests;
catalogue titles are trimmed consistently so padded titles retain that context. The planning-local grade
does not rewrite the learner profile. Custom text behavior remains. The rule-responder demo cannot create lessons or exercises, so the
interface gates those actions and explains the required teaching model. Exercise snapshots and events
now carry the actual question and full choice text while preserving the existing letter-option field;
the reference answer is not exposed. Feedback persists in the page instead of disappearing with the
pending question.

Every successful browser text submission and voice `speech_start` carries a unique request ID; the
backend keeps IDs optional for legacy clients. Voice ASR retains the ID and epoch from recording start,
so intervening newer input can supersede its result. Request IDs identify the activity that produced lesson/exercise status events and exercise state.
Exercise close, grading and timeout retain the exercise's creating owner; answer utterance events keep the
answer's own request ID. Correlated decision events report `applied: false` for superseded work. The student
page filters retired/mismatched activity events and exercise snapshots before updating status or controls.
Lesson/practice buttons remain blocked while a request is pending, while its generated practice question waits
to open, and while a question is open. An `exercise_existing` event is correlated to the current input
and carries the actual question plus its original creator ID, restoring the question without new
generation or changing ownership. Ordinary text/voice answers retain that creator for grading and close.
The latest input awaiting activity evidence is separate from the current question's creator. Matching
nonnull activity events or exercise snapshots can adopt a replacement lesson, preserving existing
backend replacement of an exercise from the current lesson. Newer input and matching terminal outcomes
retire the earlier candidate. Decision-property presence or `applied: false` triggers null-safe terminal
handling, including null/false and missing-decision outcomes for matching candidates and pending requests.
Panel errors retire only a pending request with the matching ID; unrelated,
missing or null error IDs do not affect it. Session-wide failure retains the existing connection lifecycle.
Uncorrelated packets retain their existing shape.

Notes are browser-local and grouped by learner, with a separate test-livestream bucket; notes and the
current conversation can be exported. Mode changes clear private content including screen-reader
exercise announcements, synchronize the browser URL, and hide private profile navigation in public mode.
Existing profile validation and version checks remain; changing learners blanks old visible fields
and disables writes until the matching response loads. Adult
or university profile grades are not added: the English editor displays the canonical school grade
or a disclosed blank for an unsupported grade. Recordings use actual learner/public attribution, with matching scope on the index, files and
readable logged script/input. Exact declared session ownership takes precedence over multipart filenames.
Known partial requests are omitted from the planned-script reading aid; remaining teacher scripts may
include unplayed words and are explicitly not captions or an audio equivalent. Unknown legacy attribution is excluded from scoped views. This local
service remains a trusted operator environment without learner authentication. The English edition explicitly discloses that the catalogue and
teaching remain Chinese/Mandarin and that no university/adult course catalogue has been verified.

Design references and exact contracts are in `docs/student_frontend.md`. Validation on 2026-10-02
(*measured locally*): frontend tests, 97 passed; affected backend/exercise/catalogue/lesson checks,
95 passed. The full CPU Python suite after student7 repairs passed 423 checks with 1 GPU-only
skip. Final classroom browser checks passed nine edition/viewport
cases and thirty-three behavior scenarios with no page errors or horizontal overflow, including local notes/export,
session, pending/generated activity gating, retirement/existing-question recovery, creator-owned answers,
replacement-lesson event/snapshot adoption, null/false/missing terminal decisions, matching panel errors, padded catalogue
context and synthetic exercise/privacy checks; results are in `.cache/student10_frontend_check.json`, with
empty stderr and previews in `.cache/student10-ui`. The measured pre-repair browser replay of actual backend events is in
`.cache/manual-lesson-owner/`; subsequent frontend repairs left backend/live code unchanged.
Initial profile
and recording browser checks, 12 edition/viewport cases, followed by 12 scoped private/public recording
cases with readable script text and no JavaScript errors or overflow; the
existing audiovisual page checks, all 12 passed against an isolated teacher CPU/JPEG environment.
Synthetic lesson events verify rendering, not real teaching. Formal GPT-6 Sol source review completed
through student9 and confirmed the named student8 major repairs; it did not execute the measured checks.
The final minor terminal-decision guard was fixed after review and passed direct browser regressions;
the reviewed scope and subsequent repair are distinguished in `docs/codex_reviews.md`. The recording-text
alternative remains partially accepted because it provides planned scripts rather than verified captions
or an audio equivalent.
No GPU/live-LLM teaching, learning efficacy, adult curriculum or physical device lip sync was qualified
by these checks.

### Puppet backend (2026-10-04, D-047)

`--generator puppet` is a fourth generator backend at the same level as `mock` / `taomate_h3` /
`vllm_omni_h3`: a CPU skeleton rig instead of video diffusion. The spoken line is synthesized by an
external TTS (`live_agent/tts.py`: `synth` deterministic pseudo-speech for tests and offline demos —
not speech; `url` for a remote OpenAI-compatible model; `edge` for Microsoft Edge neural voices;
`piper` for local voices), and each request's frames are drawn with PIL: capability intents map to
keyframed poses, and the mouth follows the audio envelope of the exact samples the viewer hears, so
lip sync holds by construction. `scripts/run_live.sh puppet` runs it CPU-only (no GPUs, no model
servers; `PUPPET_TTS`, `TTS_URL`/`TTS_MODEL`/`TTS_API_KEY`, and a hosted `LLM_URL` are optional).
Action compliance on this path is deterministic (the animation plays or the request is dropped);
the judge still runs so logs stay comparable across arms, but its verdicts are expected to be
`complied` whenever the frames were painted — this is the A0-baseline direction of
`docs/notes/cheap_avatar_backbone.md`, **not** a backbone replacement: TaoMate-H3 remains the A2
generator. Verified locally (2026-10-04): CPU tests for the generator protocol, audio/mouth
coupling, intent mapping, TTS clients (offline, with injected fakes), the backend API streaming a
real puppet session, and the launcher's CPU-only puppet mode. Measured TTS and compositing
latencies on the real voice paths are still open (the E2 runner accepts `--generator puppet`).
Teacher-capability coverage: all 17 intents map to a performed animation (test-asserted).

## Verified so far

- **GPU identity (measured locally, 2026-09-26):** `torch.cuda.get_device_capability()` = (9, 0), 132 SMs,
  139.8 GiB. Hopper, so FA3 is usable (D-020).
- **CPU test suite:** unit and end-to-end tests pass on the mock stack. They cover:
  - the prompt format;
  - JIT lock timing;
  - verified-then-claim ordering;
  - forward repair;
  - refusal of unsupported actions;
  - barge-in drop and bridging;
  - the open-loop baseline;
  - the memory rules;
  - the scoring rules;
  - statistics.
- **Deadlock classes found and fixed by tests:** barge-in or erasure dropping requests that the backlog guard
  was waiting on.

- **M0 component profile (measured locally):** in short runs (40 s sessions), the streaming adapter's generation
  period was 3.55 s per 4.958 s of media at 480x864 on 4+2 GPUs, so short-run throughput met the playback rate.
  This is not a real-time qualification: M1/M2 soak gates are open. See `docs/m0_measurements.md` and D-021.
- **Generator-path diagnostic run (not M1 qualification; measured locally, 2026-09-26; `.cache/m1`, 12 sessions = 6 tasks × A2/A1, seed 0,
  real TaoMate-H3 + Qwen3-8B responder + Qwen3-VL-8B judge, pre-E1 manifest with `--allow-uncalibrated`):**
  - 29–52 chunks per session, **0 playback gaps > 50 ms** in all 12 sessions (after moving the recorder off
    the event loop; the first attempt showed ~0.1 s gaps per chunk caused by the synchronous recorder).
  - A2: every completion claim came after a judge `complied` verdict (0/5 contradicted by the judge). One
    forward repair (M01 step 1) succeeded on the retry, 2 requests after the failure.
  - Judge-sourced chain outcomes: A2 4/6 success (A01, A03, D01, D04), C01 "never" because content rubric
    verdicts come only from adjudication, M01 "never" because of a converter bug (verdicts lacked `step`;
    fixed afterwards, with a test). A1 has no online judge by design, so it scores 0 under judge-only
    scoring. **This is not an A2-vs-A1 result:** the primary outcome is blinded adjudication (D-014), n is
    tiny, and the manifest is not yet calibrated.
  - On-topic speech onset (TFMR) median ≈ 4.2 s in both conditions. The judge-sourced TVC for A2 actions
    uses the start of the verified request as the compliance time (the online judge gives no first
    compliant frame), so it is a lower bound.
  - Spot check (manual, one session): in A2-E2-A01 the persona reaches for the teacup and lifts it toward her
    mouth in the verified request.
- **Server path with TaoMate-H3 (measured locally, 2026-09-26; `scripts/server_check.sh`):** FastAPI/WebSocket server,
  generator started once, and a headless client (`scripts/ws_client_check.py`) that plays chunks, acks with a
  mapped client clock and types two instructions with barge-in. 60 s session, loopback network:
  - Instruction → first audio-energy onset of the presented reply request: **2.2 s and 3.6 s**. This is a
    diagnostic proxy, not a verified on-topic speech onset (a teacup clink also crosses the threshold). On-topic
    onset is established only by adjudication. Before two fixes it was 10.8 s and 9.3 s:
    - after a barge-in, the timeline restarts, so the next request locks immediately instead of waiting for the
      dropped requests' slots;
    - the restart request waits up to 1.5 s for the in-flight responder decision instead of spending 5 s on a
      "listen" filler.
  - The action verdict arrives 7.7–8.2 s after the instruction (the full request is presented first, then the judge
    runs). The completion remark was heard 12.6 s after the instruction, after the verdict. A failed action got a
    forward correction in its reserved request. The speech check (ASR) returned CER 0.00 on most lines.
  - No playback gaps except the two barge-ins (the persona freezes until new content arrives: 2.6–3.5 s; the
    proposal's reaction-clip visual acknowledgement is not implemented).
  - Bugs found on this path and fixed:
    - ASR rejected 32 kHz WAV, so audio is now resampled to 16 kHz.
    - One failed check ended the session; failed checks now abstain.
    - The chunk header lacked the media duration.
    - The openai SDK's lazy imports stalled the event loop ~1.1 s on the first LLM call (found with a stack-sampling
      watchdog); the client is now warmed up at start-up. Ping RTT went from 1.0–1.8 s to 45–52 ms.
    - The judge's frame encoding moved off the event loop.
    - A chain whose request was cut by barge-in now counts as unexecuted (capacity skip, or resumed).
- **E2 dry run (simulation):** 54 sessions (A1/A2/A2-repeat × 6 tasks × 3 seeds, mock generator and judge,
  real LLM). The pipeline scores end to end. The repair offset j−k was 2 in every repair of this mock run
  (the failure is known only after the full request is presented, and request k+1 was already locked), so most
  repaired chains finished after the 15 s action deadline. This is the observed mock-run offset, not a structural
  constant: larger correction cost, lock timing or stalls can push the earliest correctable request to k+3 or
  later. The distribution on the measured path is reported per run (`repair_assignment.target_request`).

## Known deviations and scope limits (after Codex impl1/impl2)

- **Online checks cover action steps only.** Content and memory instructions get a speech (ASR) check but no
  online compliance question, so they cannot be forward-repaired; their outcomes come only from blinded
  adjudication. The drift detector and its three interventions (§10.4: textual correction, session reset,
  image re-anchoring) are not wired into the active path; only the textual bridging note after barge-in is.
  **The E2 pilot claim for A2's online loop is therefore restricted to action and multistep-action chains.**
- **Pre-play ASR of generated speech (§15) is not implemented.** ASR runs after presentation, off the event
  loop. The pre-generation script audit checks erased terms, length and an operator term blocklist. It is **not
  content moderation**: there is no moderation model, so the proposal's content-audit gate is open.
- **QC evidence = painted frames.** Browser acks report which frames were actually painted. QC samples only
  those frames and abstains if fewer than half were shown. The simulated client reports all frames.
- **Media retention:** decoded frames/audio are evicted after presentation and QC (a 30-min session would
  otherwise hold ~50 GiB [derived]); recordings are separate and opt-in.
- **Deadlines start at the client's utterance end.** Browser/WS clients stamp when a text was sent or a
  recording stopped; the server maps it to its clock, so ASR and queueing delay count toward D.
- **Barge-in races.** A barge-in changes the plan and pauses locking before its first await. A responder decision
  whose input was superseded by a newer barge-in is discarded and logged as a capacity skip (erasures are still
  honoured).
- **Erasure fails closed.** The generator reset counts as purged only when both TaoMate worker groups confirm it
  (`reset_done`), after adapter prompt buffers are cleared. Memory runs a paraphrase sweep (similarity
  threshold 0.5 [estimate]; cross-lingual paraphrases are not caught). If any purge target is unacknowledged,
  including `similarity_review` for similar surviving user facts, the session stays paused.
- **Transport:** the browser path sends JPEG frames + PCM16 per chunk instead of the proposal's per-chunk fMP4
  (`Chunk.encoded` is unused). Presentation acks carry the client's audio-output time (performance clock via
  `getOutputTimestamp`), mapped to server time with the lowest-RTT ping; the accuracy of this mapping is
  not yet measured.
- **Generator-path runs are not M1 qualification.** The §6.4 gate needs the client playback path and at least
  three 30-minute soak runs. The runs in `.cache/m1` are short generator-path diagnostics.

- **Round-3 additions:**
  - A1 chains close as `presented` (unjudged) once their planned segments are shown.
  - The RQ2 repeat arm repeats the original action and line.
  - The bridging note names the unseen action and is kept until the bridge is presented.
  - Stale `/dev/shm` payloads are unlinked, and adapter shutdown is cancellation-safe.
  - Public persona lines get lineage from a memory recall token issued by the bridge.
  - Erasure is physical: `secure_delete`, `VACUUM` and WAL truncation with a raw-file check. `VACUUM` runs on the
    event loop inside an erasure; the session is quiesced then, but the cost grows with the database size.

- **Round-5 additions:**
  - Erasure stops playback before the storage work and runs the deletion off the event loop (`forget_async`).
  - Recordings are deleted on erasure (the session is no longer recorded).
  - QC calls time out after 8 s and abstain (a proposed target).
  - Degrade and refuse lines state the capability decision. All 24 `degrade_to` lines were rewritten: several
    promised the action ("好，我站起来。") or even claimed it ("你看，写好了。").
  - Action-bearing lines allow intent wording only.
  - Completion remarks are held while a barge-in decision is pending.
  - The WebSocket session ends when the orchestrator stops on an error.
  - Paint timestamps are measured by the client.
  - Worker rank PIDs are gathered for the `/dev/shm` sweep.
- **E2 primary decisions need the end-to-end path.** The report refuses a primary decision for `simulation` or
  `generator_path` logs, because text is injected without TTS → VAD/ASR. A TTS-driven client (or human users) on
  the browser path is required; no TTS model is part of this repo yet.

- **Round-7 additions:**
  - An erasure invalidates and drains pending QC before redaction, so no late write can restore erased text.
  - QC never runs past the step deadline; an expired step fails with no late transition.
  - After a barge-in resolved by a new instruction, the old chain's "好了。" is dropped.
  - Speech (and claims) that became audible in a chunk cut mid-play are logged, and that request is bridged as
    partly shown.
  - The browser schedules decoded chunks strictly in arrival order.
  - `Orchestrator.stop` is cancellation-safe.
  - Ground-truth revision mapping follows the served utterance.
- **Narration guard limit:** the completion guard is pattern-based and cannot catch every paraphrase. False
  completion claims are measured independently from the recorded audio (adjudicated claim sweep).

- **Step deadlines are enforced online (round 10).** An independent sweeper expires every open action or
  multistep step at its deadline (D = 15 s from the utterance end, or from the previous step's verification),
  whatever happened to QC. **Consequence (research-relevant):** with 5 s requests, a failed first attempt is
  known only after that request has been fully presented (about 12–17 s after the instruction), and the retry
  lands two requests later. So in simulation a forward repair of an action essentially never completes within
  D. RQ2 (repair arm comparison) can still be measured on the repair targets, but H1a gains from repair should
  not be expected unless the first-attempt check can finish earlier (per-chunk QC, shorter requests) or D is
  re-registered for repairs. This is a proposal-level issue to decide before E2, not a code defect.

- **Captions:** the browser shows the *scripted* line as a caption. It is cleared on barge-in or erasure, but it
  is not validated against the generated speech (an unverified output channel, excluded from the QC evidence).

## Not yet verified

- **GPU re-check of rounds 5–11 (done, measured locally, 2026-09-26, commit c07e5ea).** The server path ran with
  TaoMate-H3 on GPUs 0–5 and the headless client (tea, then a barge-in with wave, a private fact, an erasure):
  - The first attempt **found a bug**: the expanded barge-in bridge note exceeded the compiler's 200-character
    correction limit (314), and the resulting `PromptError` ended the session. Fixed: the bridge fits the limit, and
    an invalid correction is an audit issue, never fatal.
  - Second run, clean:
    - Both actions were judge-verified, and each "好了。" was heard after its verdict.
    - The bridges after the barge-ins fit the limit.
    - The erasure completed with no pending targets, and neither "妹妹" nor "杭州" remains in the log.
    - The verified confirmation was spoken after the erasure.
    - 51 chunks were presented, with no gaps except around barge-ins.
    - No `/dev/shm` files and no worker processes remained after shutdown.
  - **Stall regression fixed:** a finer watchdog (0.15 s, all threads) located two event-loop costs, and both moved:
    - numpy loads of the ~40 MB `/dev/shm` chunk payloads now run on the adapter's reader thread;
    - WebSocket per-message deflate of JPEG/PCM frames is disabled.
- **One-command launcher verified (2026-09-26, measured locally).** `scripts/run_live.sh full` started the helper
  models and TaoMate-H3 via `gpu run` and served the scripted session (tea, wave, a private fact, an erasure):
  - zero errors and zero event-loop stalls over 0.2 s;
  - on stop it released exactly its own GPUs (0–6), with no processes or `/dev/shm` files left;
  - `scripts/run_live.sh demo` runs the whole loop on CPU only.
  - Launcher bugs found and fixed while testing:
    - runs shared log names, so one run's cleanup could release another run's GPU; logs are now per invocation,
      and only `full` mode releases;
    - there was no readiness timeout; there is now one, with lost-reservation detection;
    - child processes are now run in separate process groups, so cleanup leaves no orphans.
- **E1:** a judge-only pilot ran (24 × 5 trials on TaoMate-H3, `docs/e1_pilot.md`). It showed the VLM judge failing
  in both directions, so every capability stays `executed`. Next: two raters label the stratified sample
  (`scripts/e1_validate.py`), then full E1 runs with the validated judge.
- **Primary outcome:** nothing has been adjudicated yet. The tool exists; annotators are needed.
- 30-min soak, 768p/1080p, 60 s+ sessions on the TaoMate path, and the browser playback path on a remote
  client (σ, jitter) are not yet measured. The M1 run used the simulated client on the server host.
- None of the simulation outputs are experimental results. The mock judge's success probability is an
  input, not a measurement.
