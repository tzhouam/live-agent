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
| `live_agent/generator/puppet.py`, `puppet_art.py`, `assets/vtuber_teacher/`, `live_agent/tts.py`, `live_agent/generator/textdraw.py` | D-047, D-050 | CPU skeleton-puppet backend: authored 2D VTuber sprites, keyframed poses per capability intent and mouth aperture from the played audio envelope, plus external TTS clients (`synth` offline pseudo-speech, `url` OpenAI-compatible remote, `edge`, `piper`); peer of the TaoMate backends, per-session like the mock |
| `live_agent/backend/app.py`, `resources.py`, `config.py`, `runtime.py`, `transport.py` | — | API-only FastAPI backend: resource APIs, configuration, long-lived generator and session orchestration, WebSocket transport, profiles and private media. `live_agent/server/app.py` retains the old import/CLI path as a compatibility entry point |
| `frontend/server.mjs`, `frontend/public/` | D-045, D-046 | Separate Node frontend server and student classroom, profile editor and recording browser; Chinese primary/secondary and English university/adult interface configurations, actual school-topic navigation, lesson/exercise controls and browser-local notes. Same-origin HTTP/WebSocket proxy; AudioContext remains the playback clock and presentation acknowledgements retain their existing protocol |
| `live_agent/asr.py` | — | Qwen3-ASR client (vLLM transcription API) and audio decoding |
| `live_agent/eval/` | §7, §14, §15 | Evaluation: SCHEMA.md log format, scoring (intent chains, D table, outcome rules), stats (Wilson, Clopper–Pearson, KM, clustered bootstrap, Holm, κ, power), 30-task suite, simulated user, runner, report |
| `configs/persona_hanfu/` | §3 | Persona canon and capability manifest (24 actions covering the E2 suite; `documented` until E1 executes them) |
| `configs/persona_teacher/` | demo | Teacher persona (林老师): canon, responder rules for answers with a board, lessons, exercises and profile updates |
| `live_agent/lesson.py` | D-038, D-043, D-053 | Lesson planner: outline (subject, objectives, key point, difficulty, hook type, sections with depth and exercises), one section at a time (board points with the spoken lines under each, an optional question where it helps understanding, a closing that returns to the objectives), figure judgement, and the rubric self-check of a section (`check_section`, rewrite with `feedback`) |
| `live_agent/board_diagram.py`, `board_images.py` | D-053 | Bounded relation-diagram JSON validation and CPU PNG rendering; local figure maker uses the configured teaching model when no image-provider server is configured. Exact graph/geometry remains in `board_plot.py` |
| `live_agent/exercise.py`, `live_agent/student.py` | D-038, D-039 | Exercises (choice / short answer, rule or LLM grading, practice-design rules from the craft data) and the student profile store |
| `live_agent/curriculum.py`, `configs/curriculum/` | D-040, D-043 | Course knowledge base: the national curriculum per subject and grade, the per-grade teaching profile (`pedagogy.json`) and the teaching craft (`teaching_craft.json`: lesson stages, teacher moves, grade bands, master teachers, board rules, quality checklist), rendered into the planner, section, exercise and self-check prompts by grade and subject; `tools/check_curriculum.py` validates the files |
| `live_agent/generator/base.py` `SessionView` | — | One live session on a long-lived shared generator: reset per session, local request numbering, stale chunks dropped (D-022) |
| `live_agent/sim.py` `Recorder` | — | MP4 of the *presented* stream (background-thread encoding), used for adjudication and E1 clips |
| `live_agent/eval/adjudicate.py` | §14, D-014 | Blinded human adjudication: shuffled items, random ids and media names, key kept apart; labels merged back as `source: adjudicated` verdicts with video→session time mapping (D-024) |
| `scripts/e1_rejudge.py`, `scripts/e1_validate.py` | §14.2 | Offline re-judging of saved E1 clips (judge v1/v2); blinded stratified human-validation page and judge-vs-human agreement (accuracy, κ, FP/FN) |
| `scripts/e1_calibrate.py` | §14.2 | E1: idle → action → idle per trial; VLM judge; Wilson CI; clips for the 20% human sample. A judge-only pass marks capabilities `executed`, and only human-validated labels make them `calibrated` |
| `scripts/serve_models.sh` | — | vLLM servers for Qwen3-8B (8101), Qwen3-VL-8B (8102), Qwen3-ASR-1.7B (8103) on one GPU (isolated venv `.venvs/serve`, vLLM 0.28.0 + torch cu129) |
| `scripts/run_live.sh`, `scripts/puppet_service.py` | D-051 | CPU `puppet-full` classroom with hosted teaching/vision/transcription, Edge Mandarin voice, real learner-profile defaults and a local process supervisor |

## Running

Quick start: `scripts/run_live.sh puppet-full` (CPU VTuber with hosted teaching),
`scripts/run_live.sh demo` (CPU stand-ins) or `scripts/run_live.sh full` (configuration: 7 GPUs); see `README.md`.
The launcher supervises separate frontend and backend processes. Configuration defaults are frontend
`127.0.0.1:8200` and backend `127.0.0.1:8201`; `PORT`/`HOST` configure the frontend and
`BACKEND_PORT`/`BACKEND_HOST` configure the backend. Startup readiness is the backend's `/api/health`
through the frontend proxy. The route and WebSocket boundary is documented in `docs/frontend_backend.md`.
The launcher defaults to `PERSONA=teacher`; use `PERSONA=hanfu` for the reading host. The CPU demo uses
the rule responder and cannot generate lessons or exercises. The page reports that limit. Real teaching
uses a configured teaching model, including the hosted CPU service described under D-051 below;
student-interface checks did not run the GPU/model path.

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

Initial visual refinement (2026-10-05, D-048): the puppet depicted a VTuber-style
anime teacher with layered ponytail hair, teal eyes, thin glasses, a blouse and cardigan,
and a softly lit classroom with detailed lectern props. Artwork lives in
`live_agent/generator/puppet_art.py`; the existing pose and audio-envelope animation stays
in `puppet.py`. Head tilt rotates the whole face, stroke widths scale with the output,
and supersampling smooths the edges. Static scenery is cached with a bounded cache.
No model weights, GPU renderer or additional packages are needed. Local visual inspection
covered the existing gesture library; generator, backend streaming and launcher checks
are recorded with D-048. A warm-scene render-only sample at the default portrait resolution
(configuration: 480 × 864) measured 31.8 fps over 120 frames [measured locally]; this excludes
TTS, encoding and transport and does not establish end-to-end real-time qualification.
This geometric renderer was superseded by D-049. Its preview artifacts and render
measurement are in `.cache/puppet-refinement/`.

Previous appearance (2026-10-05, D-049): owner requested a fancier Japanese cartoon style.
`puppet_art.py` composited bundled anime sprites from
`live_agent/generator/assets/anime_teacher/`: detailed hair and eyes, embroidered outfit,
painted classroom with sakura daylight, shaded props and distinct finger poses. The
built-in imagegen artwork, exact prompts and rig coordinates are preserved there.
Generator/backend API tests, including facial patch isolation and cache immutability,
passed [measured locally]. A warm-scene render-only sample at the
default portrait size (configuration: 480 × 864) measured 407.5 fps over 240 frames
[measured locally]; this excludes TTS, encoding and transport. Historical previews and the
measurement are `.cache/puppet-refinement/anime-teacher.png`, `anime-teacher.gif`,
`anime-poses.png` and `anime-measurement.json`. This visual refinement does not qualify
real-voice latency or learning efficacy.

Natural appearance introduced in D-050 (2026-10-05): the owner rejected D-049's appearance as scary
and asked for a realistic VTuber character blended into the scene. The replacement
uses authored **2D sprites with a softly realistic 3D anime visual style**, not an actual
VRM, Live2D or 3D rig. A continuous head/neck/torso bust preserves the adult teacher's
collar during restrained shared bust/joint movement. Character and classroom lighting
match; tabletop/front-lip occlusion and prop/hand contact shadows give the scene depth.
Staged arm lifts keep hands on camera through gesture transitions. Registered,
feathered face patches preserve the bust while the audio envelope deforms its mouth
aperture; smiling and blinking are independent.

Built-in imagegen artwork, exact prompts, `repair-prompt.txt` and rig coordinates live
in `live_agent/generator/assets/vtuber_teacher/`. Rendering selects `atlas-v2.png`
(shoulder-edge repair); the initial `atlas.png` is preserved. Immutable source artwork
and bounded caches feed the existing CPU RGB/PCM streaming contract, with no MiniMax,
GPU or image service at runtime. At the D-050 appearance check, the service used the rule responder
and Edge Mandarin TTS; generated lessons and exercises were unavailable on that responder.
D-051 changes the service configuration to real hosted teaching while retaining this artwork.
The Edge client loads its optional networking module and decodes received audio in
workers, keeping those synchronous steps off the streaming event loop.

A render-only sample at portrait size (configuration: 480 × 864) measured 240 frames
in 3.278549 s, or 73.2 fps [measured locally; excludes TTS, encoding and transport],
recorded in `.cache/puppet-refinement/natural-measurement.json`. Generator/backend
regression verification passed 44 tests [measured locally], including smile/blink
independence, gesture-transition wrist/elbow bounds and Edge worker responsiveness.
A short fresh-service HTTPS Chromium check received 16 video chunks, reported the
Mandarin wave reply's speech onset as heard, and recorded zero WebSocket/page/server
session errors [measured locally]. Evidence: `service-natural-check.json` and
`service-natural-classroom.png`, `service-natural-teacher.png`, `service-natural-wave.png`
in the preview directory. Pose, transition, facial and animated previews were inspected
locally. D-050 previews are
`.cache/puppet-refinement/natural-vtuber.png`, `natural-vtuber.gif`, `natural-poses.png`,
`natural-transitions.png` and `natural-faces.png`. Visual inspection and render-only
throughput do not qualify sustained end-to-end latency, physical-device audio/video
sync, user acceptance or learning efficacy.

### Full private CPU VTuber service (2026-10-05, D-051)

The owner's request, "make it real full service", enables the existing model-backed classroom on
the natural VTuber generator. `scripts/run_live.sh puppet-full` keeps D-050's authored CPU animation
and Edge Mandarin voice, and configures the owner-selected `qwen3.8-flash` responder through Aliyun's
Anthropic Messages endpoint, the compatible visual endpoint with the same model, and
`qwen-audio-3.0-realtime-plus` transcription through the realtime WebSocket endpoint. The credential
comes from the ignored `.cache/llm_api_key` file or `LLM_API_KEY`; it reaches the backend environment
and is removed from the frontend environment. Provider URLs/models remain configurable. The launcher
checks missing credentials and invalid provider/TTS configuration before starting processes, and its
CPU modes never reserve or release GPUs. No MiniMax weights or local board-image model are loaded.

The hosted ASR client waits for the updated-session acknowledgement before uploading audio, then
sends the manual commit and response request consecutively. It returns on an authoritative completed
transcript or the explicitly configured verbatim-text fallback. Configuration, upload, recognition and
connection cleanup share a deadline of 45 s [target enforced by the client]. The previous shorter
deadline caused a recoverable voice-input timeout during staging; provider response times remain
variable. This is a bounded operation, not a low-latency service guarantee.

The real teaching model uses the existing responder, curriculum and teaching-craft prompts,
lesson outline/section planner, spoken-line-aligned board, practice generation and rule/LLM grading.
Question/option rendering uses the existing safe mathematics renderer and preserves leading decimals
and numbered options in their displayed text.
Graded exercises update the selected private learner profile; profile corrections, scoped memory
and erasure keep their existing code paths. The full mode's configuration defaults are
`STUDENT=learner` and `STUDENTS=learner,demo`. An absent `learner` record loads an empty profile,
without invented names, exams or mastery. The explicitly fictional `demo` seed remains selectable.
Other launcher modes preserve their `demo` default. The teacher needs the learner's grade from the
profile or an explicit catalogue choice to personalize school-level teaching.

Recordings contain the presented stream and retain private learner scope. The recording browser,
playback, downloads and planned-script reading aid use that scope. This access control serves a
trusted operator behind the existing shared-token HTTPS bridge; it does not authenticate each learner.
The backend supports a single active agent session. Relevant private learning context reaches the
hosted teaching provider, and audio/video used for recognition and checks reaches the configured
providers. Browser-local notes remain separate from the saved server profile.

`python3 scripts/puppet_service.py start`, `status` and `stop` manage the local service. The supervisor
monitors frontend/backend health, restarts its managed launcher after failure, and adopts an existing
repository bridge or manages a bridge it starts. An adopted bridge is left running on stop. State is
`.cache/puppet-service/state.json`; logs are `.cache/logs/puppet-service.log`,
`.cache/logs/puppet-service-launcher.log` and `.cache/logs/puppet-service-bridge.log`.
The service has process supervision; automatic startup after a host reboot is not configured.

Validation on 2026-10-05 [measured locally]: the affected Python suite passed 166 tests, the frontend
passed 98 tests, and the isolated student-interface browser checks passed 43 checks with zero page
errors. Direct hosted-provider probes succeeded for the responder, recognition of the teacher image
and transcription of Edge-generated Mandarin; evidence is `.cache/full-puppet/provider-check.json`.

An isolated verification profile exercised a real Qwen answer with board and heard speech, an adaptive
lesson outline and accepted section, interruption, a generated arithmetic exercise answered by
independent calculation, correct grading, saved profile history and reload after reconnect. That run
received 64 video chunks with zero page/server diagnostics [measured locally]. The planner recorded
two failed section-generation attempts before a later section was accepted; the short check does not
establish reliability over sustained lessons. Evidence: `.cache/full-puppet/full-flow/report.json`.
The recording's presented MP4 contained H.264 video and AAC audio and advanced during actual browser
playback; scoped transcript download also succeeded. Evidence:
`.cache/full-puppet/recording-playback.json` and the full-flow report.

A Chromium fake microphone sent synthetic Mandarin through actual MediaRecorder capture and hosted
ASR, received the exact transcript and a real model answer, and rendered an exercise with no browser
errors [measured locally]. Release-to-transcript time was 26.306 s in that sample; this is observed
provider delay, not a responsiveness claim. Evidence: `.cache/full-puppet/microphone/report.json`.
The private HTTPS check verified the real responder, enabled ASR/VLM, heard Mandarin, formula rendering
in generated practice and an untouched blank `learner` profile; it received 8 video chunks and no
page/server diagnostics [measured locally]. Evidence: `.cache/full-puppet/live/report.json`.

Production is under the local supervisor. Terminating its owned backend caused a fresh launcher to
restore frontend/backend health in 8.741 s [measured locally, a single injected failure], while the
existing adopted bridge remained running. Evidence: `.cache/full-puppet/live/restart-check.json`.
These engineering checks do not establish learning efficacy, sustained latency, physical-device
audio/video sync, reboot persistence or individual learner authentication.

### VTuber body and arm proportions (2026-10-05, D-052)

The owner reported that the body/arm proportions still looked strange and requested an actual visual
check. The correction retains the teacher's face, classroom, props and D-051 service, and adjusts the
body placement and arm rig. The bust moves higher relative to the tabletop, placing the desk near
the waist and showing the blouse/cardigan through the torso. Longer upper-arm and forearm chains
reach the desk; authored sleeve axes are fitted to shoulder/elbow/wrist positions with uniform scale
and rotation. A rounded patch from the authored fabric blends the elbow join. Inward-moving upper
arms render over the torso while staying behind the tabletop and forearms, maintaining the connection
through drink and presentation gestures.

Built-in imagegen authored `live_agent/generator/assets/vtuber_teacher/sleeve-atlas-v3.png`.
Only its lower upper-arm/forearm tiles are consumed. The face, expressions and hands remain sourced
from `atlas-v2.png`; the classroom and props remain sourced from their existing files. Earlier atlases
are preserved. `proportions-prompt.txt` saves the exact edit and source/output provenance;
`rig.json` documents attachment geometry.

At the default portrait configuration (480 × 864), the current rig targets a 270 × 467 bust starting
at vertical coordinate 145, shoulder joints at 377, an upper-arm length of 145 and a forearm length
of 128 [configuration targets, not anatomical measurements]. Animation angles and gesture contacts
are recalculated for this geometry. The renderer keeps the existing RGB/PCM streaming, facial
patches, audio-driven mouth and TTS behavior; the service continues to use the real hosted teaching
providers on the CPU VTuber path.

The preliminary visual comparison is `.cache/puppet-proportions/before.png` and
`repaired-joints.png`. Final evidence is recorded in `.cache/puppet-proportions/poses.png`,
`transition-*.png`, `transitions.gif`, `browser-staging/report.json` and `live/report.json`.
The final generator module passed 21 tests [measured locally]. A complete transformed-alpha sweep
checks the sleeves, palms, bust and held props across 6,171 sampled poses (17 animations × 121 times
× 3 phases [measured locally]). It caught an open-palm transition clip and a spinning-hand fingertip
clip that previous joint-only bounds missed; both were corrected. Contact checks cover the mug's
resting origin and rim-to-mouth alignment, the centered held book and palm overlap with the globe.
Facial changes remain inside their geometry-relative authored regions. Fresh spin, drink and
presentation previews were inspected locally.

The final native pose montage and wave/drink/presentation transition sheets were inspected locally;
`transitions.gif` is saved for further review. `.cache/puppet-proportions/artwork-review.json` records
the qualitative review and source asset hashes. Staged browser verification passed 14 layouts with the board shown
and hidden across 7 viewports, received 12 H.264 chunks and reported no overflow or page/console/
request errors [measured locally]. Portrait aspect ratio was preserved; independent desktop, tablet
and phone screenshot inspection found no blocking visual defects. Evidence:
`.cache/puppet-proportions/browser-staging/report.json` and its native-canvas/stage/classroom previews.

Final private HTTPS verification confirmed the real `puppet` / `qwen3.8-flash` runtime with configured
hosted ASR and VLM, received 12 video chunks across 3 desktop/tablet/phone layouts and displayed an
actual requested wave [measured through private HTTPS]. The portrait retained its aspect ratio,
with no overflow or page/protocol errors, and the real `learner` profile remained empty.
The final native teacher/wave and desktop/tablet/phone classroom screenshots were inspected locally.
The functional hosted-provider checks remain the D-051 evidence. Evidence for this appearance check:
`.cache/puppet-proportions/live/report.json`, `teacher-native.png`, `wave-native.png`,
`wave-classroom.png` and the viewport screenshots in that directory.

The service supervisor was refreshed to load the final artwork and restored healthy frontend/backend
processes while preserving the existing adopted bridge's identity and ownership. Evidence:
`.cache/puppet-proportions/service-refresh.json`. Owned staging processes were stopped and checked;
evidence is `staging-cleanup.json` in the same directory. These implementation and visual checks do
not establish user aesthetic approval, a 3D avatar rig, sustained latency or learning efficacy.
D-050 and D-051 measurements remain historical checks of their recorded revisions.

### CPU board diagrams and complete teacher speech (2026-10-05, D-053)

The owner reported missing board images and asked for a more natural, realistic teacher tone.
Inspection found that the CPU classroom configured no illustration maker: precision plot requests
could render locally, while prompt-based figures were marked queued without being generated.
Figures that finished after a board was already shown could also remain absent until a later
request locked that board again.

The correction gives illustration prompts a CPU educational-diagram path.
`live_agent/board_images.py` provides `LocalDiagramMaker`; when the board and real teaching model are
enabled without an image-provider URL, the backend selects that maker. The existing teaching model
plans a bounded declarative arrangement of shapes, arrows and labels, and `board_diagram.py` validates
and renders it to the existing board-image route. Configuration limits are 8 nodes, 10 directed arrows,
unique positions on a 3 × 3 grid, box/ellipse shapes and a 1024 × 768 PNG [configured bounds/targets].
Quoted required labels must occur in the actual drawn labels; numeric graph/geometry requests retain
`board_plot.py`'s precision path. This is a relationship schematic, with no new GPU image model, paid
provider or foundation-model training.

Invalid specifications are repaired using the previous JSON and validation feedback, up to 3 attempts
within a shared 30 s planning/render deadline [configuration targets enforced by the maker].
Self-arrows are rejected; valid cycles across distinct nodes remain supported. Invalid labels,
missing required labels and layouts whose labels cannot fit do not publish a PNG.

Completed figures include the URL and escaped caption in the existing lesson `figure` event.
The frontend caches them by unique lesson-board key and point, refreshes matching displayed/queued
boards and preserves their reveal progress. Unique keys keep a delayed figure attached to its
originating lesson rather than a replacement lesson with the same section number. The cache clears
on disconnect/reset/erasure. A failed image collapses its figure area while retaining board text;
later updates can retry it.

The localized `放大配图` / `Enlarge diagram` control and keyboard-activatable thumbnail open a native
dialog with the current image, caption and alternative text. Close/Escape returns focus to the
opener, and the image preserves its aspect ratio during resizing. Board/figure changes,
disconnect, privacy erasure and session reset close the dialog and clear its private content.

The teacher keeps the existing adult female Mandarin Edge voice, `zh-CN-XiaoxiaoNeural`. The saved
calm profile uses rate `-4%`, pitch `-8Hz` and volume `+0%` [configuration targets]. Revised teacher
wording asks for complete spoken sentences, specific correction/praise, optional questions and fewer
repeated forms of address or canned enthusiastic openings. These choices target natural explanations;
generated voice samples do not establish human-rated naturalness or the owner's listening acceptance.
The puppet preserves the whole synthesized utterance instead of trimming it to a nominal
request length. It retains four indexed chunks per request [configuration target], with chunk timing
following the actual speech and a brief ending pause. The first chunk declares the full
`request_duration_s`; the orchestrator records it before forwarding that chunk, then reconciles it
against the observed sum after the final chunk. The scheduler therefore has the actual short/long
request duration before playback begins. The earlier fixed-duration behavior and its measurements remain historical evidence
for those revisions.
The CPU launcher exposes these settings as `TTS_RATE`, `TTS_PITCH`, `TTS_VOLUME` and
`PUPPET_SPEECH_TIMING`, defaulting to the calm profile and `natural` timing. The optional `fixed`
timing mode also retains the complete utterance; it keeps the configured nominal minimum duration.

The same-text generated Edge samples are `.cache/teacher-tone/voice-before.wav` and `voice-calm.wav`.
Their durations were 5.448 s and 5.688 s respectively [measured locally, generated samples].
The affected voice/persona/generator suite passed 38 tests [measured locally]. A real 44-character
Edge utterance returned 314,880 samples over 9.840 s; playback preserved every source sample across
four chunks and lasted 10.083 s [measured locally]. The prior nominal first-request window would
discard 74,089 nontrivial source samples in that probe [measured locally]. Evidence:
`.cache/teacher-tone/complete-speech-verification.json`, `teacher-complete-source.wav` and
`teacher-complete-playback.wav`.

Reconstructed teaching samples are `teacher-before.wav` and `teacher-after.wav` in the same directory
(20.042 s and 10.125 s [measured locally]). They change both wording and timing, so that comparison
does not isolate prosody; `voice-before.wav` and `voice-calm.wav` use the same text for that purpose.
The final lesson module passed 32 tests and the frontend suite passed 109 tests, including 49
`live.js` tests [measured locally]. An isolated Chromium test at desktop, tablet and phone sizes sent
controlled delayed figure events through the real frontend/backend proxy. It loaded an actual local
PNG, refreshed the current point without changing reveal/progress state, suppressed figures from
other points/lessons and retained correct forward/reverse selection, with no browser errors or
overflow [measured locally]. Evidence: `.cache/board-figures/browser/report.json`. This fixture/mock
service test made no hosted-provider calls. Independent preview inspection found no overlap between
diagram nodes and arrow labels. A second controlled browser run passed 13 enlargement, keyboard,
focus and privacy-cleanup checks across 6 layouts without errors or overflow [measured locally].
Enlarged desktop/phone/landscape screenshots were independently inspected, with no clipping or
overlap defect. Evidence: `.cache/board-figures/browser-modal/report.json` and its screenshots;
this run also used a fixture/mock backend and made no hosted-provider calls.

Short/long timing integration regressions passed in an affected 35-test speech/board-delivery/launcher
run [measured locally]. A real water-cycle plan exposed an invalid self-arrow; the final lesson tests
cover successful self-arrow/missing-label repairs, bounded persistent failure and the shared deadline.
Additional affected Python runs passed 112 tests covering speech, board delivery, lessons, profiles,
curriculum, practice and the launcher, plus 103 tests for pipeline, director, backend, wire, activity
and catalogue behavior [measured locally]. These are separate reported runs; the module-level results above overlap with
some of those checks and are not added as a unique total.

Final real-provider staging passed on 2026-10-06. The configured `qwen3.8-flash` teacher and CPU
renderer produced a water-cycle diagram, an exact quadratic plot and a planned photosynthesis
lesson-point diagram. Each PNG returned HTTP 200 through the frontend/backend proxy and appeared
on the played board. The water-cycle figure refreshed a board that was already visible; the lesson
figure appeared at its matching reveal point. Desktop/tablet/phone layouts and diagram/plot
enlargement, Escape and content-clearing checks passed without overflow or page errors. The run
received 105 video chunks and captured the complete four-chunk Edge speech request
[measured through isolated localhost staging]. Evidence: `.cache/board-tone/staging-final/report.json`,
`teacher-playback.wav` and source/classroom/enlarged-phone screenshots inspected locally.
This flow made real teaching-model and Edge speech calls; hosted ASR and VLM were configured,
and their functional qualification remains the historical D-051 evidence.

The production service was refreshed and its frontend/backend health checks passed while preserving
the adopted bridge. Evidence: `.cache/board-tone/service-refresh.json`. An initial private HTTPS
probe stopped its strict verification after observing a nonfatal 0.235 s event-loop pause during
saved-memory SQLite retrieval [measured through private HTTPS after refresh]; the sampled stack
was outside the image pipeline. A later probe displayed the diagram across all desktop/tablet/phone
views and enlargement, then observed a nonfatal 0.412 s pause at SQLite ingest/event-read operations
[measured through private HTTPS]. The session monitor continued running in both cases. The final
harness classifies these performance diagnostics separately from fatal/protocol/input errors.
Evidence for the initial observation:
`.cache/board-tone/private-cold-probe.json`. The pause cause is unestablished; a read-only indexed-query
audit did not reproduce it. These observations are performance limits and do not establish cache
behavior, sustained service latency or a need for a memory-architecture change.

The final private HTTPS functional check passed on 2026-10-06. A newly generated CPU diagram and
exact plot each returned HTTP 200 and refreshed their already-visible matching board. Both displayed
correctly at desktop/tablet/phone sizes, with working enlargement, Escape and content clearing.
The run received 40 video chunks and captured a complete four-chunk real Edge utterance lasting
5.8749375 s, beyond the previous nominal request window [measured through private HTTPS].
There were no JavaScript page errors or fatal/protocol/input errors; the report retains one nonfatal
0.201 s event-loop diagnostic [measured through private HTTPS]. The real `learner` profile remained
empty before and after verification. Evidence: `.cache/board-tone/private-live-qualified/report.json`
and `teacher-playback.wav`; source diagrams and actual desktop/phone-enlarged classroom screenshots
were inspected locally. The supervised service remained healthy with the adopted bridge preserved,
and only the owned staging processes were stopped. This new functional check used real teacher-model
and Edge speech calls, with hosted ASR/VLM configured rather than freshly qualified.

The change retains the D-052 sprite teacher and D-051 private service. It does
not establish user acceptance of vocal realism, a new 3D avatar, fresh ASR/VLM qualification, sustained
latency or learning efficacy.

### More illustrated explanations and a board gallery (2026-10-06, D-054)

The owner asked for more images during explanations. The figure policy now favors useful visuals
for substantive knowledge points, including simple concepts, concrete examples, definitions,
comparisons and processes. Complexity is no longer a gate for illustration. Greetings, empty
transitions and summaries with no new content can still skip a figure. A planned lesson has a
default budget of up to 6 point figures, bounded by the board's point count and `MAX_ITEMS`
[configuration limits]. Existing queued or ready figures remain authoritative; malformed or
duplicate model records cannot consume a point ahead of a corrected request. Numeric graph and
geometry specifications retain their exact plotting path.

Ordinary knowledge answers now invoke this planner automatically, including when the responder
left its board to the existing fallback. Each answer board gets at most one additional judgement,
with up to 4 point figures and a 20 s judgement deadline [configuration limits]. An existing
overview is retained; otherwise the first new figure becomes the overview so answers without a
reveal index show an image automatically. Spoken answer sentences enter the prompt once as shared
context, without inventing a sentence-to-board-point mapping. Identical requested figure content
is deduplicated. Answer keys are unique across sessions, keeping delayed image events attached
to their originating answer.

`Board.view` includes all ready figures with their point and escaped caption, while its selected
`figure` retains the exact-current-point-or-overview rule. The frontend combines these snapshots
with late-ready image events into a gallery. Localized Previous/Next controls, an image counter
and the existing enlargement dialog let the learner inspect the other diagrams. Manual selection
survives unchanged speech chunks and new arrivals; a board or reveal-point change returns to the
automatic image. When the current point has no automatic image, a Browse control opens the ready
collection. Replacement boards, disconnect, reset and erasure clear the gallery and enlarged image.
A minimum board height for stacked layouts keeps image and gallery controls visible on a narrow
phone without stretching the teacher canvas.

The final review also found a board-only erasure case: clean queued speech could restore a board
whose caption or points contained an erased term. Erasure now detaches matching boards throughout
controller queues and locked script snapshots, discards their pending figures and drains in-flight
visual work before playback resumes. Unaffected speech and boards are retained.

The affected Python run passed 167 tests across board delivery, director, persona, lesson, activity,
catalogue, backend and pipeline modules [measured locally]. A final 51-test board-delivery/director
run passed after adding erased-board identity tracking and prompt/plot-only snapshot regressions
[measured locally; overlaps the broader run]. The frontend suite passed 118 tests, including 58
live-page tests [measured locally]. Controlled browser verification passed 16 checks across 6
layouts, with 4 real PNG URLs returning HTTP 200, working gallery navigation and bounds, manual
selection persistence, automatic point changes, late arrivals, enlargement/Escape/focus, localization,
failure recovery and erasure/reset/disconnect cleanup [measured locally]. It found and resolved a
collapsed thumbnail on a narrow phone. No overflow, failed requests or page errors remained.
Evidence: `.cache/board-gallery/browser/report.json` and inspected desktop/small-phone/enlarged
screenshots. This controlled check used an isolated mock backend and made no hosted calls.

An ordinary photosynthesis question, without a request for pictures, produced an overview and
point diagrams in real-provider staging. The browser loaded and browsed 3 completed images with
HTTP 200, desktop/tablet/phone layouts, enlargement, Escape and disconnect cleanup; the backend
generated all 5 requested diagrams [measured through isolated localhost
staging]. There was one automatic visual-planning call for the answer, with no page or protocol
errors. Evidence: `.cache/visual-teaching/staging/report.json`, its packet capture and the isolated
backend event log at `.cache/full-puppet/sessions/sess-a022dfa046a2.jsonl`. The first report stops
at 3 ready images; it is not a browser display qualification
of the later two. Source diagrams and an actual classroom screenshot were inspected locally.

The refreshed private HTTPS service passed the final ordinary-question check on 2026-10-06.
It delivered 4 ready diagrams (overview, raw materials, light/energy and products), each returning
HTTP 200; the browser navigated 3 distinct gallery images with matching captions and counters
[measured through private HTTPS]. All planned images were ready before the responsive checks.
Desktop/tablet/phone display, aspect preservation, enlargement, Escape and disconnect clearing
passed, with one automatic planning call and no page/fatal/protocol/input errors. The real learner
profile remained empty before and after verification. The report retains a nonfatal 0.464 s
event-loop pause [measured through private HTTPS]; its cause and sustained latency remain
unestablished. Evidence: `.cache/visual-teaching/private-live/report.json`, packet capture, source
PNGs and actual classroom/enlarged screenshots inspected locally. The service remains healthy,
with the adopted bridge identity preserved (`.cache/visual-teaching/service-refresh.json`). Only
owned staging was stopped (`.cache/visual-teaching/staging-cleanup.json`).

These teaching-model and Edge speech checks retain D-052's teacher artwork and D-053's complete
speech path. They do not establish human-rated illustration quality, learning efficacy, sustained
latency or fresh hosted ASR/VLM qualification. The CPU maker still produces relationship schematics;
no new image model, GPU, provider or foundation-model training is introduced.

### More responsive opt-in attention checks (2026-10-06, D-055)

The owner reported that concentration analysis was insufficiently sensitive. Inspection found
camera captures at 320 × 240 every 3 s [previous configuration], dropped newer frames during a
VLM request, an extra reminder delay after state confirmation, and reminders gated to planned
lessons. Low-confidence or unknown observations could reinforce stale confident state. The focus
label was only visible inside diagnostic details.

The browser now requests camera detail up to 640 × 480, captures at a 1.5 s interval with JPEG
quality 0.75, and sends the first ready frame after playback starts [configuration targets].
Downscaling preserves the camera's original aspect ratio. A single inference worker retains only
the latest pending frame; older pending frames are replaced rather than queued. The VLM prompt
asks for observable head/gaze/hand/object cues, explicit uncertainty when the image is ambiguous,
and no distraction inference from a normal blink, brief downward glance or glasses alone.

The default confirmation window is 2 observations with confidence at least 0.5 [configuration
targets]. A first focused observation is usable; a distraction/absence change requires repeated
evidence. Reminder evidence counts the actual consecutive supporting observations, so confirmation
does not add another unnecessary sample delay. Uncertain/invalid observations clear stale state
and cannot count toward a reminder. Reset epochs discard classifications that finish after a
reset. Camera-off cancels the inference task, discards the pending frame and stops browser uploads;
rapid re-enable waits for cancellation cleanup before starting fresh work. Stop and erasure use
the same clearing path.

Reminders can now be inserted between spoken requests during ordinary board explanations as well
as planned lessons. Listening, an undecided user request and queued non-teaching actions retain
priority. The reminder cooldown is 20 s [configuration target], with the existing per-episode
limits retained. Uncertainty does not reset the episode counter. The localized focus label now
appears beside the camera control, distinguishes a provisional observation from its confirmed
state, and shows Unclear for uncertain frames. Late camera results cannot re-open this status
after opt-out.

The affected attention/board/pipeline/backend suite passed 75 tests; the final attention module
passed 16 tests after adding in-flight reset invalidation [measured locally, overlapping runs].
The frontend suite passed 120 tests [measured locally]. These cover brief-glance rejection,
quick changes/recovery, uncertain and invalid evidence, ordinary-answer reminders, listening/action
priority, latest-frame replacement, no parallel inference, camera-off/rapid re-enable and stale
result suppression. Controlled real-browser verification passed the camera/frontend/proxy/monitor
path for focused, confirming distraction, confirmed distraction, unclear, recovery and confirmed
absence, plus desktop/tablet/phone layout and opt-out cleanup [measured locally]. It uploaded
7 fake-camera frames at 640 × 480, with subsequent steady capture intervals near 1.5 s and first
capture at 0.145 s [measured locally; the first interval was 1.408 s]. No page errors, overflow
or camera image data in the persisted event log remained. Evidence:
`.cache/attention/controlled/report.json`, metadata-only classification log and screenshots.
This controlled test uses a scripted VLM and an explicit fake Chromium camera; it does not measure
human attention-classification accuracy or hosted inference latency.

The refreshed private service passed a real configured-VLM camera check with the authored empty
classroom backdrop used as an explicit camera fixture [measured through private HTTPS]. The first
capture arrived at 0.141 s; repeated absence was confirmed after 8.393 s from enabling the camera
[measured in this probe, not a latency guarantee]. The VLM's inference time remains a material part
of response latency; the capture interval is not an inference-latency claim. The portrait fixture
was captured at 267 × 480 from a 936 × 1681 source without stretching [measured through private
HTTPS]. The visible status and desktop/tablet/phone layouts passed; disabling the camera ended its
tracks, stopped uploads and suppressed stale results. No page/fatal/protocol/input errors or
event-loop diagnostics were observed, and the real learner profile stayed empty. Evidence:
`.cache/attention/private-live/report.json`, packet capture and locally inspected screenshots.
This qualifies absence on an authored empty-room fixture, not human distraction/gaze sensitivity,
learning efficacy, cognition or general concentration accuracy. No private human camera recording
was used. The supervised frontend/backend remained healthy with the adopted bridge preserved
(`.cache/attention/service-refresh.json`); controlled staging processes were stopped in their
test harness's cleanup. Existing avatar, illustration gallery, speech and providers remain in use.

### Richer teacher facial animation (2026-10-06, D-056)

At the owner's request for more realistic and fluent teacher images, built-in imagegen authored
`expressions-v1.png` against a crop of the existing teacher's face. A registered atlas supplies
small/open/rounded/spread speaking mouths, an encouraging smile and a thoughtful resting mouth
[configuration: six authored states]. The original face, glasses, hairstyle, torso, scene and
joint geometry remain the base; only feathered local mouth patches change. Runtime registration
matches skin color at patch edges. Mouth amplitude follows the delivered audio; acoustic spectral
brightness adds restrained rounded/spread variation with smoothing. This is approximate acoustic
animation, not phoneme recognition. Exact prompt, reference crop, extraction coordinates and
limitations are saved in `live_agent/generator/assets/vtuber_teacher/expressions-v1-prompts.json`.
Original assets remain available alongside the versioned additions.

Blink opening and closing now interpolate over their authored facial images [configuration:
0.24 s blink, faster closing than opening]. Breathing, sway and blinking share a session motion
clock across request boundaries; reset starts a new clock and canceled old requests cannot advance
it. Gesture timing continues to follow each complete utterance. No runtime image service, new
provider, GPU or training is introduced.

Affected generator/speech/teacher-TTS verification passed 42 tests [measured locally], including
partial-blink localization, distinct acoustic shapes, silence, continuity, immutable cached art,
complete speech and the existing 6,171 gesture/phase transition samples [measured locally].
Actual Edge Mandarin preview used two complete utterances across eight chunks, totaling 299
frames and 12.458 s [measured locally]. The mean absolute pixel change across their request
boundary was 0.0734 [measured locally; not a perceptual-quality score]. Native expression montage,
speech strip and classroom screenshots were inspected. Evidence:
`.cache/teacher-motion/speech-report.json`, `speech.mp4`, `montage.png` and `speech-strip.png`.

The refreshed private HTTPS classroom passed a configured Qwen answer, heard Edge speech,
moving video and desktop/tablet/phone aspect checks [measured through private HTTPS]. It received
20 video chunks and sampled 40 distinct facial crops [measured; crop variation also includes head
motion and is not proof of phoneme accuracy]. No page/fatal/protocol errors occurred. One brief
0.226 s event-loop diagnostic was retained [measured; not a clean-latency qualification].
The real learner profile stayed empty and the adopted bridge was preserved. Evidence:
`.cache/teacher-motion/private-live/report.json`, native frames, inspected screenshots and
`service-refresh.json`. The service remained healthy after verification. Appearance/fluent-motion
acceptance still requires the owner's judgement; no human realism or speech-quality study occurred.

### Teaching preparation and quality checks (2026-10-06, D-057)

The owner requested a stronger teaching workflow and judgement of generated quality. The private
`puppet-full` teacher now reviews knowledge answers and every lesson section before queuing them.
The previous default only logged lesson reviews in the background; revision mode also bypassed
the first section and did not enforce a review of its rewrite. The new workflow drafts, checks,
rewrites weak material, reviews the rewrite and then presents accepted material. The outline is also
reviewed before its intro appears; a failed outline can be revised and reviewed once. Section review
is scoped to its own goal, so prerequisite/recap sections need not teach the whole course. Answer preparation
allows at most two repairs; lesson preparation allows one [configuration bounds]. Each preparation gate has a 60 s deadline [configuration target]. Failed lesson sections stop preparation with
a brief explanation. Known failed answers are withheld; if the first answer reviewer is unavailable,
the original can continue with an explicit `unreviewed` audit status. Nothing marks this as a pass.

`live_agent/teaching_quality.py` requires evidence for correctness, reasoning, a worked example,
clarity and alignment of board/script/exercise/planned image. Acceptance requires full scores on
correctness, reasoning, example and alignment, and at least partial clarity with no critical errors
[configuration rubric: 0–2]. Minor wording advice cannot hold an otherwise sound explanation.
Teacher prompts now ask for the student's actual sticking point, a causal explanation, an expanded
example and necessary conditions. Review guidance avoids demanding optional advanced material or
incorrectly rejecting content based on the model's character counts. Reviews remain judgements of
the configured Qwen model, not independent factual authority or measured learning outcomes.

Local rational arithmetic rejects supported false numeric fraction equations and explicit spoken
fraction-counterexample/result errors before any model review. Clearly labelled wrong examples
remain available for misconception analysis. Supported same-denominator proper-fraction sums use
an exact equal-part plot [configuration: denominator at most eight, total at most one whole].
The plot renderer accepts bounded blue/green/white fills to distinguish the addends and the unused
parts; it preserves every part's size. Unsupported mathematics/visuals retain the existing paths.
This is a bounded exact check, not a general mathematical or scientific verifier.

Rewriters can change only answer speech and board content, preserving original user instructions;
they cannot inject actions, learner-profile updates or memory facts. Section rewrites must preserve
the planned exercise and correction of the student's last mistake. Provider-format handling retries
incomplete answer generation and conservatively repairs one observed root-closing defect before
the `steps` field; it never invents missing/truncated speech or merges new control fields. A held
answer does not trigger an unreviewed automatic board fallback. Existing interruption, erasure,
camera, avatar, full-utterance audio and gallery paths remain in use.

Final affected quality/planner/director/renderer/backend/launcher/pipeline verification passed
225 tests [measured locally].
They exercise acceptance and rejection, bounded repairs, malformed/partial verdicts, preserved user
intent, first-section gate order, timeout after a failed draft, exact arithmetic, labelled mistakes,
native equal-unit plots and constrained format repair. Compiler and shell syntax checks passed.
The configured provider was exercised with fraction, density and day/night questions plus a lesson
section. Prompts and raw generated outputs are retained under `.cache/teaching-quality/`, including
rejected and failed probes. These are case inspections, not a benchmark or a measured improvement
in teaching efficacy. In particular, density drafts and their reviews still showed limitations;
some content was withheld instead of accepted.

The coding agent read generated teaching, including planned-image text, and caught factual errors
that an early model review had approved: a wrong denominator-addition counterexample and a reversed
fraction label. Other probes revealed overreaching reviewer suggestions, unreliable character counts,
and unsupported microscopic density diagrams. The exact check and reviewer/writer guidance were
adjusted in response; the evidence is not represented as universally successful. Editorial inspection,
code hashes and remaining limits are in `.cache/teaching-quality/editorial-audit.json`.

The refreshed private classroom delivered a reviewed fraction explanation, heard Edge Mandarin
and the native equal-part image [measured through private HTTPS]. It received 28 video chunks and
sampled 40 frames, with 39 distinct facial crops [measured; head motion contributes to crop changes].
Desktop/tablet/phone aspect checks passed, the real learner stayed empty, and no page/fatal/protocol
errors or event-loop diagnostics occurred in that probe. Actual desktop and phone screenshots were
inspected. Evidence: `.cache/teaching-quality/private-live/report.json`, packets and screenshots.
The private lesson-start probe verified an accepted outline review before intro and a failed first
section revised and re-reviewed successfully before it entered the queue [measured through private
HTTPS]. Its first accepted section was prepared at 48.63 s in this probe [measured, not a guaranteed
start latency]. The learner remained empty and no page/fatal/protocol errors or event-loop diagnostics
occurred; evidence: `.cache/teaching-quality/private-lesson/report.json`. Earlier withheld lesson
probes and a brief 0.210 s diagnostic are retained [measured in an earlier probe].
The adopted bridge was preserved and supervised service health passed. Extra provider calls add
preparation latency; deterministic checks cover a limited subset, and passed editorial scores do not
prove general factual accuracy, human preference or learning efficacy.

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

### Calmer teaching gestures (2026-10-06, D-058)

The owner reported strange teaching movement. Inspection of native rendered
sequences showed that ordinary explanation and board presentation used the same
large raised-arm template: the elbow passed from the resting bend through a
backward sweep, and board presentation repeated this with both arms. Those
speech poses now use a modest lift near the desk, keep the elbow in its resting
bend direction, and leave the other hand resting. Authored open/relaxed palms
crossfade at a shared wrist instead of snapping between silhouettes. Oscillation
fades at hold boundaries and uses the continuous motion clock.

Evidence is retained in `.cache/teacher-gestures/`: before/after pose strips,
an inspected motion strip, a native preview with real Mandarin audio, test logs,
source hashes and private service/browser reports. The preview contains complete
speech across 8 chunks and 299 frames / 12.458 seconds [measured locally].
Affected verification covers 44 distinct tests, including 6,171 actual sprite
boundary samples [measured locally]. The initial run exposed a missing test
import; the corrected test and remaining quick cases passed without repeating
the already passed boundary sweep (`verification.json` records the split).
Explicit requested prop/action poses remain available; this changes ordinary
speech motion and oscillator transitions, not the underlying layered CPU rig.
No human realism or animation-quality rating has been established.

The refreshed private HTTPS classroom also passed a real reviewed fraction
answer and heard-speech probe: 40 captured motion frames were inspected, the
teacher aspect ratio was preserved on desktop/tablet/phone, no page/protocol or
performance errors occurred, and the real learner remained empty [measured in
this probe]. The existing adopted bridge process was preserved. These checks
verify delivery and the inspected motion sequence, not teaching efficacy or
realistic movement across every explicit action.


### Detailed custom browser teacher (2026-10-08, D-059)

The owner approved a locally developed detailed Japanese anime teacher using generated artwork
and browser mesh deformation. This is a **custom PixiJS rig, not Live2D/Cubism**. PixiJS 8.22.0
[pinned dependency version] is vendored with its MIT license and provenance; runtime assets and
dependencies are served from the local frontend. The existing private classroom has not been
restarted or deployed for this change.

Built-in imagegen produced four source images [measured asset count]: a consistent adult teacher
reference plus body/arm, face and pointing/waving-hand atlases. They and the exact prompts are
preserved in `frontend/public/assets/teacher-mesh/source/`. The extraction script
`scripts/build_teacher_mesh_assets.py` crops runtime layers and records source regions and trim
bounds in `rig-v1.json`; the existing authored classroom supplies the background. Face, eyes,
lids, brows, mouth shapes, glasses, hair, clothing, arms and hands remain separate. The rig
manifest defines layer order, attachment axes, mesh grids, masking and limited deformations.
All geometric and motion bounds in that manifest are configuration targets, not anatomy
measurements. Runtime skin masks register authored pointing/waving wrists inside the continuous
arm cuffs, removing duplicate sleeve geometry while preserving the source pixels.

The optional local `?avatar=mesh` path loads a separate WebGL avatar canvas while retaining the
existing server-video canvas. Ten gestures [implemented capability count] are supported: idle,
listen, explain, present, point, smile, think, nod, shake and wave. Pointing uses the authored
index finger; its session-local capability phrase makes no pointer-prop pickup/putdown claim,
while preserving the capability identifier and original video-only phrase. Other requested
actions use existing capability degradation/refusal. The negotiated subset remains conservative
for that session even after video fallback. Head/gaze, breathing, blinks and hair settling use
restrained deformation; mouth amplitude and coarse shape variation follow the delivered audio,
not phoneme recognition. Request-relative and continuous-motion timing span chunk boundaries.
Interruptions, reset and disconnect clear stale playback/animation.

Session negotiation adds optional renderer/model identity and supported capabilities. Negotiated
chunks carry `avatar` gesture, full-request duration, request offset, continuous-motion offset and
playback epoch. Legacy clients retain their existing hello/status/chunk contracts. Missing assets,
unsupported WebGL and renderer failure retain video fallback; a mid-chunk renderer switch makes
that chunk's visual evidence unknown rather than mixing unrelated pictures.

Mesh QC consumes only timestamped captures of the actual displayed browser avatar. Capture
bounds are 160,000 data-URL characters, 120,000 decoded JPEG bytes, dimensions at most 640 by
1,152 pixels, twelve captures per chunk and twenty-four per request [configuration limits].
Decoded evidence is reduced to at most 320 by 576 pixels [configuration memory bound]. Current
request/chunk, playing state, renderer/model, epoch, frame/media-time agreement and monotonic
capture order are validated; stale, duplicate, unsolicited and oversized captures are rejected.
Missing mesh evidence produces UNKNOWN without asking the judge to inspect puppet frames.
Video fallback resumes painted server-frame evidence for subsequent video chunks. Teacher
captures remain separate from student-camera attention analysis, whose opt-in flow is unchanged.
Server recording API entries carry `visual_source: "server_video_fallback"` for negotiated mesh
sessions while preserving their existing category/part labels; the recording UI explains this
source and labels playback/downloads accordingly. These files do not record the browser mesh.

`scripts/teacher_mesh_check.py --serve` provides an isolated loopback preview using prerecorded
PCM/JPEG transport through the actual frontend and `WSTransport`; no teaching provider, saved
learner or running private-service process is used. Without `--serve`, it writes actual canvas
screenshots, timestamps, protocol diagnostics, responsive-layout checks and a browser-avatar
recording under the selected `.cache/teacher-mesh/` output directory. A supplied `--speech-wav`
provides PCM16 speech; an existing historical preview is reused when available, otherwise clearly
labeled synthetic tones are used. Browser recordings capture the real WebGL canvas plus the
scheduled audio branch, separately from fallback server recordings.

Backend/wire/director/puppet regression verification passed 157 tests [measured locally before
the subsequent finger-point adaptation]. The adaptation and mesh evidence checks then passed
73 focused mesh/teacher/director tests [measured locally; overlapping coverage], including a
compiled-script test which selects the point gesture with the truthful finger phrase and leaves
legacy detection unchanged. A final current-code run of the same focused suite passed 73 tests
in 2.97 seconds [measured locally]; its complete output is
`.cache/teacher-mesh/backend-final-tests.log`. Earlier browser diagnostics are retained under
`.cache/teacher-mesh/acceptance-first/`, `acceptance-second/`, `acceptance-third/` and
`acceptance-protocol/`; they must not be read as final visual approval. The final frontend suite
passed 134 tests [measured locally], including controlled gesture/boundary checks. Final browser
acceptance passed with stable runtime/source hashes in
`.cache/teacher-mesh/acceptance-final/report.json`:

- All 50 sampled canvas frames were distinct; the sampled animation covered all four audio
  chunks, with maximum request-clock error 0.030448 seconds [measured locally, a sampled media
  timing check rather than perceptual lip-sync accuracy].
- The actual transport accepted 28 of 28 delivered browser captures and rejected explicit
  duplicate/stale-epoch probes [measured locally]. Mesh acks never claimed hidden fallback frames
  as painted. Stop, disconnect and reconnect cleared stale playback; context loss, missing model
  and unavailable WebGL each selected video fallback [measured locally].
- Desktop, tablet and phone retained the avatar content aspect ratio, kept it within the stage
  and had no horizontal overflow [measured locally]. Letterboxing preserves the content ratio
  when a viewport's canvas element has a different shape.
- The browser-compatible actual-avatar recording is `acceptance-final/browser-avatar.mp4`:
  13.586 seconds, H.264 at 480 by 864 pixels plus AAC audio [measured locally]. It records the
  WebGL canvas and actual scheduled PCM branch, not server fallback video. The native WebM,
  screenshots, frame timestamps and protocol records are retained alongside it.
- CPU render-submission duration over 1,031 calls had median 0.300 ms, p95 0.700 ms and maximum
  4.200 ms [measured locally in headless Chromium/SwiftShader with PNG snapshots and canvas/audio
  recording active]. These timings exclude device-display latency and do not guarantee display
  frame rate or performance on a student's browser. No page/console errors or external asset
  requests occurred [measured locally].

The implementation and acceptance reviewers inspected the actual pointing, waving, blink,
mouth-shape and ordered spoken-animation frames. A slight neck blend and an angular
pointing wrist remain visible; this is limited front-facing mesh deformation. No fresh teaching
provider/ASR/VLM qualification or learning assessment was performed by the local rendering
fixture. Source hashes in the final report bind its results to the inspected runtime/asset
revision. No new provider, purchase, commissioned art, GPU training or deployment is introduced;
professional Live2D equivalence, human realism and learning efficacy remain unestablished.
The final source review also verified disposal of per-instance mask textures and derived texture
views on reconnect while preserving shared artwork sources. The browser acceptance was rerun
after that resource-cleanup repair; the preceding run remains in `acceptance-pre-cleanup/`.


#### Artwork and gesture refinement within D-059

The locally active artwork is now `rig-v2.json` with `asset_revision: 2` [asset revision]. The
negotiated wire model `teacher-mesh-v1` and manifest format `version: 1` [format version] remain
compatible. Built-in imagegen produced `reference-v2.png`, `body-atlas-v2.png` and
`face-atlas-v2.png`; exact prompts are saved in `source/prompts-v2.json`. The original reference,
atlases and prompts remain preserved. Point/wave extraction reuses the existing authored hand
atlas. There are seventeen matching runtime PNG tiles [measured asset count]. The extraction
script now defaults to the refined revision and accepts `--revision 1` to rebuild the earlier
assets explicitly; each manifest retains the source crop/trim provenance.

The refinement adjusts adult almond-shaped eyes, a softer jaw, mouth/neckline placement,
hand size and closer camera framing. Continuous face/neck skin is visible beneath a transparent
clothing collar, eliminating the prior collar alpha blend. A shoulder-level wave and a separate
thinking pose add distinct movement while maintaining the same supported capability set.
A separate read-only visual review accepted the `polish-second` stills, with minor observations
of slender fingers and slightly sleepy eyes; this is an inspected-assembly judgement, not human
aesthetic approval or a realism measurement.

Initial refinement verification passed six focused rig checks and 136 frontend tests in
1,321.582 ms [measured locally; `.cache/teacher-mesh/frontend-polish-tests.log`]. Motion review
then identified overlapping hand silhouettes during the full arm lift. Authored hand shapes now
switch during the first/last 0.16 seconds of a request [configuration transition bound], while
the arm remains near rest; wrist axes and hand rotation remain registered throughout the lift.
A separate review and the implementation reviewer accepted the repaired motion and final
face/torso assembly. Minor limitations remain: the brief hand-shape switch, slender fingers and
subtle collar appearance; the rig still provides limited front-facing deformation.

Final frontend verification passed 136 tests in 1,386.865 ms [measured locally;
`.cache/teacher-mesh/frontend-polish-final-tests.log`]. The final refined-artwork browser run
passed with unchanged runtime/source hashes in `.cache/teacher-mesh/polish-final/report.json`:

- All 50 speech-animation samples were distinct and covered all four audio chunks, with maximum
  sampled request-clock error 30.759 ms [measured locally, not a perceptual lip-sync rating].
  The actual backend accepted 27 of 28 delivered browser captures and rejected explicit duplicate
  and stale-epoch probes [measured locally].
- Stop, disconnect, reconnect, context loss, missing model and unavailable WebGL checks passed;
  desktop/tablet/phone content aspect, stage bounds and overflow checks passed with no page or
  console errors or external asset requests [measured locally].
- Controlled wave and think recordings used a 5-second gesture duration each [configuration
  target] and yielded 60 and 61 sampled frames respectively, with no changed pixels at the canvas
  boundary [measured locally]. These are actual-renderer motion samples and changed-pixel bounds;
  the videos/montages were also inspected for anatomy and transition artifacts.
- `polish-final/browser-avatar.mp4` contains actual WebGL canvas output plus the scheduled audio
  branch: format/video duration 13.890 seconds, H.264 at 480 by 864 pixels and AAC audio
  [measured locally with ffprobe]. The native browser WebM and silent controlled gesture MP4s
  are retained alongside it. Human audibility and lossless complete-utterance audio capture were
  not qualified by this fixture.
- CPU render-submission timing over 917 calls had median 0.300 ms, p95 0.700 ms and maximum
  5.500 ms [measured in headless Chromium/SwiftShader with PNG snapshots and canvas/audio recording
  active]. These values do not measure device-display latency or guarantee display performance.

The earlier `acceptance-final/` measurements remain specific to the earlier artwork. The running
private service and learner profiles remain untouched; no deployment, new provider, training or
purchase is introduced. Generated-teaching efficacy and professional Live2D equivalence remain
unestablished.


Supplemental delivery packaging preserves the acceptance measurements above. The
[spoken preview](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-delivery/spoken-preview.mp4)
and [delivery report](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-delivery/report.json)
record the actual avatar canvas and scheduled PCM branch, beginning 50 ms before the first
audio source [measured locally]. The MP4 format duration is 12.944 seconds with H.264 at
480 by 864 pixels and AAC audio [measured locally]. Offline waveform alignment found normalized
correlation 0.972656 over all non-silent source content, at an alignment offset of 78.5 ms;
0.631 seconds of trailing source silence were excluded [measured locally]. This supports
non-silent content coverage within codec/resampling differences, not human voice naturalness,
audibility or lossless complete-audio capture.

Comparable actual native-canvas views are [earlier artwork](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-final/before-v1.png)
and [refined artwork](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-final/after-v2.png).
The [final quality audit](/data/zhoutaichang/live-agent/.cache/teacher-mesh/quality-audit-polish.json)
binds reviewed artifacts, source/runtime hashes, final tests, supplemental pointing bounds,
spoken-delivery evidence and remaining visual limits to acceptance for local preview. It records
no runtime/source mutation after acceptance and preservation of the running private service.

### Local mesh classroom latency repair (2026-10-08)

After the owner requested the full local service and reported lag, it was diagnosed on the
isolated classroom at workspace ports 8250/8251 [configuration]. The original private service
at ports 8200/8201 [configuration] and its adopted bridge were preserved. The new service uses
separate demo profiles, memory and session output under `.cache/teacher-mesh/full-service/`.
It was restarted locally to apply these changes; no public deployment or provider change occurred.

Two earlier provider-backed answers took 21.132 and 22.006 seconds from input to mapped
audio-energy onset [measured locally]. Input-to-applied-decision took 16.142 and 17.116 seconds;
the additional applied-decision-to-first-spoken-lock pauses were 3.028 and 2.017 seconds
[measured locally]. Draft and review were not separately instrumented in those traces.

The mesh client now schedules PCM before hidden fallback decoding completes, attaches late
decoded frames to the actual queued chunk, and explicitly closes retired/stale bitmaps. Unique
avatar textures preload concurrently. Actual-canvas QC JPEGs use 320 by 576 pixels while the
visible canvas and browser recording retain 480 by 864 pixels [configuration]. New clients opt
into sparse standby video through `hello.avatar_video_frames: true`: the mesh stream samples
at a maximum configured 2 fps, preserving logical `n_frames`, media duration, audio and original
server recordings. Optional `video_frames` and `video_frame_indices` describe transmitted native
source frames. Actual mesh captures remain separate; buffered video fallback only reports source
indices really transmitted/painted. Later fallback chunks restore full video, and legacy clients
retain their existing protocol. Already-reviewed replies bypass a silent filler's playback deadline
once, preserving erasure/barge gates and holding-generator pacing. Internal editorial metadata is
kept in the audit rather than repeated in future dialogue prompts; shorter review notes retain the
same rubric, exact-arithmetic checks and pass thresholds. Per-input draft/review/rewrite timings
are now recorded, without shared mutable timing state.

Verification evidence is in `.cache/teacher-mesh/lag-after/`, separately from historical visual
acceptance. The frontend suite passed 145 tests; focused backend/protocol tests passed 70 tests;
workflow/director/quality/persona/activity suites passed 110 tests, with a supplemental 6-case
gate check after strengthening subsequent-lock coverage [measured locally; overlapping cases].
Full sparse browser acceptance and a deliberate configured 5-second bitmap delay passed. With
that delay, mesh PCM scheduled 4.700 ms after arrival while legacy video correctly waited
4967.3 ms [measured locally, synthetic decode stress]. Desktop/tablet/phone, stale capture,
interruption/reset/reconnect, missing-model/WebGL/context-loss fallback and cleanup checks
passed; both browser reports bind 46 unchanged runtime hashes [measured locally]. The full
capture accepted 28 of 28 actual-canvas JPEGs [measured locally].

A warmed offline codec benchmark sampled 15 runs per mode from recorded content [measured
locally; no provider calls]. Representative H.264 median encode time was 139.759 ms for full
video versus 16.295 ms for standby samples, with 59.3% fewer video bytes [measured locally].
This does not remove server puppet drawing or recording work and is not a total latency claim.

One fresh provider-backed smoke passed preparation review, displayed a real board image,
scheduled nonzero PCM, animated the actual mesh and used sparse H.264 standby video with no
page errors or real-learner profile changes. Its input-to-audio-energy-onset was 16.689 seconds;
drafting took 9.744 seconds, review 4.203 seconds, applied decision to spoken lock 0.038 seconds,
and lock to first chunk ready 2.387 seconds [measured locally]. The evidence is
`lag-after/response-timing.json` and `lag-after/live-service/live-service-check.json`.
These observations differ in provider/network/load and generated content; they do not establish
a controlled percentage speedup or device-display FPS. Answer preparation remains the main
delay. Teaching efficacy and human voice/aesthetic quality remain unqualified.

### Adult proportion repair and serving validation (historical, 2026-10-08, D-062)

This historical browser mesh default was `rig-v3.json` (`asset_revision:3` [asset version]);
wire identity remains `teacher-mesh-v1` and manifest `version:1` [format version].
The current local full classroom serves it through the separately authorized Personal-Agent
bridge described in README. The original classroom and real learner profiles remain separate.

The first new assembly was rejected after actual WebGL inspection: the rear-view hair tile
formed a second crown, face/hair ears were misregistered, pre-bent sleeves became bulky,
and resting hands did not meet the desk naturally. Built-in imagegen produced a separate
near-straight sleeve atlas; all generated sources and exact prompts are retained in
`frontend/public/assets/teacher-mesh/source/prompts-v3.json`. Extraction remains deterministic
cropping, with no hand-painted substitute. The repaired assembly uses uniform tile scaling,
an armless torso with shoulder overlap, a smaller adult head relative to the shoulders,
a longer torso, coherent limb bones, palm-down rest hands, and a faint desk contact shadow.
The front hair includes the ponytail, so the rear-view head is excluded. The head pivot is
model-configurable. These are art-direction choices, not cited anthropometric norms.

`handPose` centralizes the actual sprite transforms. Regression checks use runtime PNG alpha
and hand skin masks, testing painted joint overlap, continuous bone lengths, complete hand
silhouettes, gesture continuity and return to rest. All supported gestures were swept at
configured durations of 1.8/5/12 s and several motion-clock origins; measured right-hand clearance
was 13.7 native pixels against an 8-pixel design target. Current frontend checks passed 150 tests
[measured locally; `.cache/teacher-mesh/adult-v3-serving-frontend-tests.log`].

The final default actual-browser acceptance is
`.cache/teacher-mesh/adult-v3-serving-final/report.json`: 64 runtime hashes remained unchanged,
50 actual speech frames were distinct, all 4 chunks were sampled, and maximum request/audio-clock
error was 25.794 ms [measured locally]. Actual-canvas capture freshness, interruptions, reconnect,
missing-model/WebGL failures, sparse-to-full fallback and desktop/tablet/phone aspect/overflow
checks passed. The full-service browser check additionally found and repaired an idle loading
placeholder: successful mesh negotiation now hides it immediately, without waiting for the
first spoken video chunk. This is covered by the frontend mesh-ready assertion.

The actual avatar and scheduled PCM recording is
`.cache/teacher-mesh/adult-v3-serving-final/browser-avatar.mp4`, H.264 at 480×864 with AAC,
13.783 s [measured locally]. During headless SwiftShader capture/recording, frontend render loops
were 49.1/s and CPU render-submission median/p95 were 0.30/0.60 ms [measured locally; not device-display
performance or provider-response latency]. Independent visual inspection accepted speech,
complete wave/thinking motions and responsive classroom views. Pointed jacket shoulder caps
and a brief translucent finger overlap during hand-shape crossfades remain minor limits.

Matched actual native-canvas comparisons are saved in `.cache/teacher-mesh/adult-v3-final/`:
`before-v2.png`, `after-v3.png`, and `before-after-v3.png`. The isolated fixture supports
`--model frontend/public/assets/teacher-mesh/rig-v2.json --serve` to inspect older/staged artwork
without changing the serving default. Final quality provenance is in
`.cache/teacher-mesh/adult-v3-quality-audit.json`.

The final bridge verification additionally reproduced a cross-client authentication defect:
Caddy could reuse the proxy's already-authenticated upstream HTTP connection. D-063 disables
upstream keepalive only for the new vtuber route, and ordinary HTTP forwarding now requests
Connection:close while authenticated WebSocket upgrades retain duplex streaming. The required
nonpooling topology is documented. All 4 post-repair fresh-client pairs returned authorized
200, no-cookie401 and invalid-cookie401 [measured locally]; 17 offline bridge tests passed.
Actual local and HTTPS browsers loaded the accepted v3 manifest and animated cleanly, with
loading overlay and decoration hidden. Original route/proxy/service identities and learner
profile hashes were preserved. Evidence is in
`.cache/teacher-mesh/personal-agent-bridge/serving-v3-check.json`,
`keepalive-auth-regression.json`, and `remote-bridge-repair.json`.

### Registered face and connected arm repair (2026-10-08, D-064)

The owner rejected the v3 face and arms after the earlier acceptance. Reassessment
confirmed that source-aspect preservation alone had not kept eyes, nose, glasses and
mouth in a coherent coordinate system. The linear elbow warp also collapsed/inverted
painted sleeve geometry. The earlier visual acceptance was too lenient; its bounded
tests remain historical evidence, not aesthetic approval of v4.

The serving default is now `rig-v4.json` (`asset_revision:4` [asset version]), retaining
wire identity `teacher-mesh-v1`. Built-in imagegen produced an intact adult head and
aligned expression edits, matching torso/garment artwork and distinct authored hand
sides. Exact prompts and source hashes are in `source/prompts-v4.json`; rejected
source/assembly revisions remain available. The rebuild command remains
`python3 scripts/build_teacher_mesh_assets.py`; `--revision 3` explicitly rebuilds v3.

The intact head preserves the original face/glasses landmarks. Expression patches
share its source scale and transform; similarity registration uses stable artwork
features outside edited openings. Opaque half/closed eyelids and soft/A/O mouth states
replace the underlying features rather than fading irises or multiple lips together.
The corrected collar closes under the painted neck. Upper sleeves, forearms and
soft elbow cloth use rigid positive-determinant transforms and recorded native bind
lengths. Upper arms draw above the torso when crossing it, preventing floating
forearms. Distinct hand sides retain their authored lighting without mirroring.

Wave/thinking/index lifts use request-relative wrist paths and fixed-branch two-bone
IK. Opaque hand changes happen after lift, avoiding translucent fingers and the old
bow sweep; short requests reduce pose amplitude. The full-lift minimum is 3.5 seconds
[configuration]. These are artist-authored frontal poses, not biomechanical norms.

Independent review rejected the first integrated v4 for open cup-like elbow overlaps,
socket outlines, broad sleeves and dangling hands. The second was rejected for
forearm occlusion and translucent hand transitions. The third actual-canvas motion
review accepted the face/arm repairs within documented limits. Staged spoken animation
also preserved face/glasses registration, connected sleeves and desk return; its
Mandarin sample exercised neutral/soft/A mouth states, while controlled captures
covered rounded O. Evidence: `.cache/teacher-mesh/face-arms-v4-third/` and
`face-arms-v4-staged-full/spoken-visual-review.json`.

Final frontend verification passed 167 tests [measured locally;
`.cache/teacher-mesh/face-arms-v4-final-frontend-tests.log`]. Actual-asset regressions
cover shared facial source coordinates, sleeve bind registration, distinct hand
sides, full painted silhouettes and connected motion across chunk clocks. The
configured canvas margin is 8 native pixels [target]; geometry bounds support
clipping checks and do not substitute for the native visual review.

The final default browser acceptance is
`.cache/teacher-mesh/face-arms-v4-delivery-final/report.json`: 87 runtime hashes stayed
unchanged, 50 native speech captures were distinct, all 4 chunks were sampled and
maximum request/audio-clock error was 33.841 ms [measured locally]. Capture freshness,
duplicate/stale rejection, interruption/reconnect, sparse/full fallback, missing-model/
WebGL failure and desktop/tablet/phone layout checks passed. Actual review captures
remain 320×576 while displayed/recorded canvas is 480×864 [configured dimensions].

Final capture observed 49.6 frontend render loops/s and 0.20/0.30 ms median/p95 CPU
submission in headless Chromium/SwiftShader [measured locally with recording and
concurrent bridge verification; not device-display or provider-response guarantees].
The selected PNG textures total 6,603,448 bytes [measured locally, excluding code];
initial network/model loading remains separate from steady animation performance.
The actual browser recording is `face-arms-v4-delivery-final/browser-avatar.mp4`,
H.264/AAC at 480×864, 24 fps and 13.500 s [measured with ffprobe]. The export now fixes
the output rate explicitly: earlier VFR browser recordings produced duplicated
1000-fps MP4 frames [measured artifact defect], despite the configured 24-fps capture.
Native WebM and timestamped PNG evidence are retained. This fixes the review artifact,
without changing live avatar timing.

The actual protected HTTPS classroom additionally loaded the exact current manifest
and verified texture bytes. All 30 controlled native poses reuse the saved before
inputs [measured locally]; matched views are `face-arms-v4-before/idle-0.5.png` and
`face-arms-v4-after/idle-0.5.png`. Their comparison is
`face-arms-v4-delivery-final/before-after.png`. Actual WebSocket mesh negotiation,
animated live canvas and responsive views passed without learner-profile changes or
original/full-classroom process replacement. Evidence: `face-arms-v4-after/capture.json`.
A rebuild produced byte-identical accepted assets. The final provenance bundle is
`.cache/teacher-mesh/face-arms-v4-quality-audit.json`.

Remaining limits: facial/hand poses switch discretely, with approximate acoustic
mouth selection rather than phoneme articulation. The intact face has no independent
gaze/hair motion or distinct smiling state; smile retains its warm neutral expression.
The index is lecture emphasis with no spatial board-coordinate binding. This is a
front-facing custom mesh avatar, not Cubism or demonstrated human realism. Existing
teaching preparation, voice, board, profiles and the owner-authorized bridge remain
in place. No new provider, purchase, training or classroom process restart was used.

### Arm-proportion reassessment (2026-10-09, D-065)

The owner subsequently rejected the v4 arm proportions. Its earlier geometry and
bounded visual acceptance did not establish a satisfactory silhouette. Fresh
protected-HTTPS captures reproduced the rejected appearance using identical saved
pose inputs; the baseline is `.cache/teacher-mesh/arm-ratio-v5-before/capture.json`.
Independent inspection identified short upper-arm silhouettes relative to the
torso, excessive fabric near the proximal forearm/cuff, and inconsistent hand
scale between resting and active poses.

The alpha audit in `.cache/teacher-mesh/v5-proportion-audit/before-v4.json` separates
painted cross-section measurements from configured joints. Central sleeve widths
were similar; the mismatch was concentrated at the elbow overlap and cuff. The
seated source reference is foreshortened and does not supply anatomical bone-length
ground truth. This repair therefore uses explicit art-direction targets and actual
rendered review rather than asserting anthropometric correctness.

The separate v5 builder preserves the registered v4 head, facial patches and
expression configuration. Its source artwork and prompts are versioned independently,
including rejected intermediate artwork. Upper-arm/forearm sections retain uniform
source scale, and explicit wrist, palm and finger landmarks replace fitting each
hand pose to a different image height. Wrist paths are retuned with the longer upper
silhouette so lifts remain reachable and return to the desk. Validation and serving
disposition are recorded below.

The first integrated v5 was held for angular elbow overlap and an enlarged open
palm. A localized open-hand source repairs palm aspect; scale uses supported wrist/
palm landmarks and allows curled fingers a shorter projected reach. Elbow overlap
uses rounded alpha extraction of the painted cloth. Further review rejected the
initial constant short forearm even though its resting pose improved: a seated
reference's foreshortening does not carry over to the raised poses. The next staging
restores lower-arm reach and moves the resting elbow outward, preserving desk
contact without dropping the fingers behind the foreground lip. Intermediate
captures and failing landmark checks remain saved as historical evidence.

The serving default is now `rig-v5.json`, retaining wire model `teacher-mesh-v1`.
The final configured bone lengths are 156.18/110 native pixels, ratio 0.704
[measured from authored configuration, not human anatomy]. Actual alpha measurements
show upper/forearm midpoint widths of approximately 42.3/36.0 native pixels and a
30.6-pixel cuff on the right sleeve [measured locally]. Wrist spans range from
17.75 to 19.46 native pixels; wrist-to-MCP palm lengths range from 29.58 to 32.50
native pixels [measured locally from supported source landmarks]. Curled open
fingers retain their shorter projected reach instead of inflating the palm to
match extended fingers. The intact head and expression specifications remain
exactly equal to v4. Source provenance is `source/prompts-v5.json`; measurement
methods and comparisons are in `.cache/teacher-mesh/v5-proportion-audit/`.

Independent native review inspected complete sampled wave/thinking sequences and
the staged actual spoken canvas before the default changed. Reviews are
`arm-ratio-v5-third/independent-motion-review.json` and
`arm-ratio-v5-staged-full/spoken-visual-review.json`. The final default check is
`arm-ratio-v5-delivery-final/report.json`: all 96 runtime hashes match current files,
50 native speech captures were distinct, all 4 audio chunks were sampled, and maximum
request/audio-clock error was 18.402 ms [measured locally]. Capture freshness,
duplicate/stale rejection, interruption/reconnect, missing-model/WebGL failure,
sparse/full fallback, board images and desktop/tablet/phone layouts passed.
Final frontend verification passed 171 tests [measured locally;
`arm-ratio-v5-final-frontend-tests.log`]. Tests include actual painted sleeve taper,
supported palm/wrist landmarks, every gesture's painted silhouettes and clearance
above the foreground desk lip; these support clipping and consistency checks,
not a claim of anatomically exact human movement.

Final headless Chromium/SwiftShader capture observed 52.2 render loops/s and
0.10/0.30 ms median/p95 CPU submission [measured locally with recording and concurrent
HTTPS verification; not device-display or provider-response guarantees]. Selected
textures total 7,231,731 bytes across 22 PNGs [measured locally, excluding code].
The spoken preview is `arm-ratio-v5-delivery-final/browser-avatar.mp4`, H.264/AAC at
480×864, 24 fps and 13.292 s [measured with ffprobe]. Native WebM and timestamped
canvas evidence are retained; human audibility and phonetic accuracy were not
established by these visual checks.

Actual protected HTTPS loaded the exact accepted manifest and texture bytes, with
30 controlled poses matching fresh before-state inputs [measured locally]. Evidence
is `arm-ratio-v5-after/capture.json`; matched idle and wave comparisons are
`arm-ratio-v5-delivery-final/before-after.png` and `before-after-wave.png`. Actual
WebSocket mesh negotiation and animated live canvas passed. Learner profiles and
original/full-classroom process identities were preserved, without authentication,
bridge or provider changes. An isolated temporary rebuild reproduced all v5 outputs
byte-for-byte without rewriting served assets. Final provenance is
`.cache/teacher-mesh/arm-ratio-v5-quality-audit.json`.

Remaining visual limits are rigid painted cloth folds, authored hand-state changes,
limited frontal shoulder/body motion and approximate energy-based mouth selection.
These are a custom two-dimensional rig, not a professional Cubism model or demonstrated
human realism. All browser checks reused recorded Mandarin rather than calling a
teaching provider; built-in imagegen supplied the versioned artwork.

### Longer arms and larger hands (2026-10-09, D-066)

The owner rejected the v5 proportions and explicitly clarified: arms too short,
hands too small. That direction supersedes the earlier inferred correction focused
on taper and relative upper/forearm length. V6 increases actual limb and hand scale,
reusing every existing painted texture with uniform source transforms. The registered
head and torso retain their sizes and move upward together by 28 native pixels
[authored composition configuration], matching the translated shoulder attachments.
Resting elbows spread outward, wrists bend gently toward the viewer, and raised wrist
paths move with the character. Larger hands remain separated above the desk lip.

Configured shoulder-to-wrist bone length rises from 266.18 to 315.05 native pixels,
an increase of 18.4%; extended-hand landmark reach rises from 66 to 82 native pixels,
an increase of 24.2%; cupped palm wrist-to-MCP reach rises from 32.5 to 40 native
pixels, an increase of 23.1% [measured locally from authored rig/source landmarks,
not anthropometric standards]. Face size, registered patches and source artwork
remain unchanged. Parent/source hashes and all target values are in `rig-v6.json`;
reproducible before/after measurements are in `.cache/teacher-mesh/v6-proportion-audit/`.

Independent native review inspected the complete sampled wave/thinking motions and
actual spoken canvas before switching the default. Evidence is
`arm-hands-v6-first/independent-motion-review.json` and
`arm-hands-v6-staged-full/spoken-visual-review.json`. The larger palms, longer reach,
cuffs, elbow overlap and desk return stay coherent in inspected poses. Authored hand
changes, rigid painted folds, limited frontal shoulder/body motion and approximate
energy-driven mouth states remain explicit limits. This remains a custom browser rig.

Final default verification passed 174 frontend tests and retained 97 unchanged runtime
hashes [measured locally]. The actual canvas supplied 50 distinct spoken samples across
four audio chunks, with a maximum sampled request-clock error of 41.020 ms; all 28
timestamped JPEG captures were accepted and duplicate/stale probes rejected [measured
locally]. Gesture continuity, interruption, reconnect, sparse/full fallback and
desktop/tablet/phone aspect/overflow checks passed. The final report is
`arm-hands-v6-delivery-final/report.json`. Headless Chromium/SwiftShader observed
48.47 render loops/s and 0.10/0.30 ms median/p95 CPU submission during recording
[measured locally, not device-display or provider-response guarantees]. The preview
`browser-avatar.mp4` is H.264/AAC, 480×864 at 24 fps, 13.625 s [measured with ffprobe];
human audibility, teacher tone and phonetic lip synchronization were not assessed.

The existing protected HTTPS classroom loaded the accepted v6 manifest and all
selected texture bytes. Thirty native poses matched the saved, unchanged actual v5
baseline inputs [measured locally]; `arm-hands-v6-after/capture.json` records this
check. Unscaled matched idle/wave panels are in `arm-hands-v6-delivery-final/`, alongside
an isolated byte-identical rebuild check. Learner profiles and original/full-classroom
process identities were preserved. No new provider call, source image, dependency,
authentication change, service restart or deployment was needed. Final evidence and
runtime hashes are bound by `.cache/teacher-mesh/arm-hands-v6-quality-audit.json`.

### Narrower modest torso (2026-10-09, D-067)

The owner additionally identified an overly wide chest. Actual native v6 inspection
confirmed pronounced convex blouse fullness and outward-bowed jacket edges. A
targeted built-in imagegen edit replaces only the torso painting with a narrower
ribcage, more modest chest projection and straighter blouse drape. The exact prompt
and unmodified generated source are versioned as `source/prompts-v7.json` and
`source/torso-modest-v7.png`. No horizontal stretching or whole-character scaling is
used. `scripts/build_teacher_mesh_v7.py` retains the main alpha component and
registers the new tile uniformly at the existing width and origin. All registered
head layers, arm bones, sleeve transforms, larger hand sizes and gesture paths are
identical to v6. The upper collar and shoulder fabric still overlap the existing
neck/sleeve attachments.

At native canvas y500/520, the torso alpha width changes from 278.84/279.54 to
244.51/237.25 pixels [measured locally at alpha >127 from uniformly mapped texture
rows; not body circumference, anatomical norms or a standalone visual acceptance
criterion]. The body rect height changes by 0.185 pixels because the generated
texture keeps its own aspect ratio [measured from authored registration]. The
isolated builder reproduces the manifest and torso tile byte-for-byte without
rewriting served files; evidence is `torso-v7-audit/rebuild-check.json`.

Independent artwork/motion review inspected the actual native gesture poses and
complete sampled wave/thinking sequences; spoken review inspected all saved native
speech frames and decoded primary-video frames. Both accepted the narrower torso
and clean neck/shoulder/sleeve connections while retaining the enlarged v6 hands.
Evidence is `torso-v7-audit/independent-motion-review.json` and
`torso-v7-audit/spoken-visual-review.json`. These are bounded visual judgments, not
anthropometric proof or an assessment of voice quality.

The staged full media check passed with 99 stable runtime hashes, 50 distinct actual
canvas speech samples over four chunks, a maximum sampled request-clock error of
24.740 ms, and 28 accepted timestamped JPEG captures with duplicate/stale rejection
[measured locally]. Gesture continuity, interruption/reconnect, renderer fallback
and desktop/tablet/phone bounds/aspect checks passed. Evidence and actual browser
recording are in `torso-v7-staged-full/`. Its MP4 is H.264/AAC at 480×864, 24 fps and
13.375 s [measured with ffprobe]. Headless SwiftShader observed 47.75 render loops/s
and 0.10/0.30 ms median/p95 CPU submission during capture [measured locally, not
device-display or provider-latency guarantees]. Only the manifest default changed
after staged acceptance; `torso-v7-audit/default-switch-runtime.json` records those
hash differences, and actual HTTPS verification separately binds the final defaults.
Painted finger/expression changes, cloth folds, limited frontal motion and approximate
energy-driven mouth states remain the same limitations. No teacher-tone, phonetic
or teaching-efficacy claim is made.

Final default checks passed 174 frontend tests, and the existing protected HTTPS
classroom delivered the exact v7 rig and selected texture bytes in 30 native poses
matching the unchanged actual v6 baseline inputs [measured locally]. Live WebSocket
negotiation, animation and desktop/tablet/phone layouts passed. Evidence and unscaled
idle/wave comparison panels are in `torso-v7-after/`. Learner profiles and existing
original/full-classroom process identities were preserved. Only the built-in
imagegen artwork edit was called; no teaching provider call, new dependency,
authentication change, service restart or deployment was needed. Final provenance is
`.cache/teacher-mesh/torso-v7-quality-audit.json`.
