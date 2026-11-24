# live-agent

A real-time, personalized live persona on **TaoMate-H3** (MiniMax H3 + streaming LoRA): an online director
plans each 5-second request, checks what the viewer actually saw, repairs failed actions, remembers the user
in scoped memory and forgets on request. The research proposal is `docs/research_proposal_zh.md` (v2.11); the
implementation status, measurements and known limits are in `docs/implementation.md`.

The private classroom can also run a natural anime VTuber on the CPU, with hosted Qwen teaching,
speech recognition and visual checks plus Mandarin speech (D-051). Its lesson planner, board, exercises,
saved learner profiles and scoped recordings use the existing classroom backend.

The browser UI lives in `frontend/` and runs as a separate Node process. The Python backend in
`live_agent/backend/` owns the agent, model connections, memory, profiles and recordings. The frontend
serves `/`, `/profile` and `/traces`, and proxies the existing HTTP APIs, media and `/ws` to the backend
on the same browser origin. See `docs/frontend_backend.md` for the interface.

The student classroom has primary-school and secondary-school editions in Chinese and a
university/adult edition with English interface text. These are interface configurations: the current
catalogue covers Chinese school subjects, and teaching remains Chinese/Mandarin in every edition.
There is no verified university/adult course catalogue or English teaching mode. Research references,
implemented flows and validation limits are in [docs/student_frontend.md](docs/student_frontend.md).

A fourth interface edition, `?edition=live`, is the non-teaching realtime live agent (D-068): it keeps
the stage, chat/voice input, memory and diagnostics, and hides the catalogue, lesson, practice, board
and learner-profile surfaces. A persona whose `canon.json` has no `board` (the default `hanfu` reading
host; `scripts/run_live.sh live`) is that live agent end to end — its backend serves no curriculum or
learner-profile endpoints, attaches no learner, runs no attention checks, and ignores catalogue
topic selections, so classroom workflows cannot be reached. Its speech path is audio-first: the TTS
utterance is synthesized before the frames, and the mouth and chunk timing follow the audio the
viewer hears. Teaching personas and editions are unchanged.

## Run it

```bash
# The realtime live agent (D-068): the CPU VTuber stack with the non-teaching hanfu persona.
# No classroom features: no catalogue, lessons, exercises or learner profiles; the page's
# ?edition=live view keeps the stage, chat/voice, memory and diagnostics only.
scripts/run_live.sh live

# CPU only, no GPUs or model servers: mock video, rule-based responder, simulated judge
scripts/run_live.sh demo

# CPU only: natural anime VTuber teacher with authored 2D sprites (D-047/D-050) + TTS, rule responder.
# Voice: edge (Microsoft Edge neural voices, needs the network + `pip install edge-tts`),
#        synth (offline pseudo-speech, no speech content) or piper (local, PUPPET_MODEL=<.onnx>);
#        TTS_URL + TTS_MODEL + TTS_API_KEY route to a remote OpenAI-compatible TTS instead.
# A hosted responder works with LLM_URL + LLM_MODEL (+ LLM_API_KEY_FILE), still no GPUs.
scripts/run_live.sh puppet

# Private teaching service: CPU VTuber + Edge Mandarin voice, hosted qwen3.8-flash teaching/vision,
# and hosted speech recognition. Uses the existing ignored .cache/llm_api_key file; no GPU or MiniMax.
# The default learner profile starts empty; demo remains an explicitly fictional example.
scripts/run_live.sh puppet-full

# Real language/speech models on 1 GPU (Qwen3-8B responder, Qwen3-ASR), placeholder video: follows free-form
# commands; use when the 6 video GPUs are busy
scripts/run_live.sh hybrid

# Full stack: TaoMate-H3 on 6 GPUs + Qwen3-8B / Qwen3-VL-8B / Qwen3-ASR on 1 GPU (via canhazgpu)
scripts/run_live.sh full

# TaoMate-H3 served by vLLM-Omni (pure Ulysses SP on 4 GPUs, D-026..D-028) + the helper models on 1 GPU
GPU_IDS=0,1,2,3 HELPER_GPU=4 PORT=8203 HOURS=8h scripts/run_live.sh omni

# The launcher defaults to the classroom teacher. Select the reading-host persona explicitly if needed.
PERSONA=hanfu scripts/run_live.sh demo
```

`omni` needs the vLLM-Omni worktree `/data/zhoutaichang/worldmodel/vllm-omni-taomate` (branch
`feat/taomate-h3-realtime`, with its `.venv`; override with `OMNI_DIR`). It serves on `OMNI_PORT` (8191) with
`configs/vllm_omni/taomate_h3_usp4_jit.yaml`, whose `taomate_h3_hold_for_prompt` makes each 5 s request wait
for the director's just-in-time prompt. Start-up takes about 6 min (4 x 87 GiB load plus one warm-up request).

Open `http://127.0.0.1:8200` (from a laptop: `ssh -L 8200:127.0.0.1:8200 <host>`). Choose an edition and an
operator-allowed learner profile, then enter the classroom. The page keeps the video and readable board
beside text/voice input. Browse actual topics by school grade, subject and search, choose a topic or
write a custom goal, then request a lesson. With a configured teaching model, this sends a Chinese
lesson request through the existing responder; it is not a separate course-generation API.

Practice displays the actual question, choices or text-answer prompt and grading feedback. Study notes
stay in this browser, grouped by learner, and can be exported; they are not synchronized profile data.
The conversation can also be exported. `/profile` edits the existing learning records, with estimated
understanding values disclosed. Classroom recording links retain the selected learner or public scope;
the index, playback, downloads and planned-script reading aid use that scope. A direct `/traces` visit
asks for a learner selection. This remains a trusted operator service: the HTTPS bridge uses a shared
access token, and profiles do not have separate user authentication. Edition links use `?edition=primary`, `?edition=secondary` or `?edition=university`, and
the selection is remembered in this browser.

In `demo` mode the video, responder and judge are stand-ins. The default `puppet` mode has a real
animated teacher and Edge speech but retains the rule responder. The rule responder cannot generate lessons
or practice questions; the page explains this and disables those actions after the session reports its
configuration. `puppet-full` enables those actions through the hosted teaching model, with live
speech recognition and visual checks. Edit the `learner` profile's name and grade before starting a
personalized lesson, or select a school topic with its explicit grade. Learner records and memories
stay in the private session scope; relevant context and audio/video checks reach the configured hosted
providers. `hybrid`, `full` and `omni` use their existing model/GPU setup; those live teaching paths were
not qualified by the student-interface change.
Ctrl-C stops the launcher's processes and releases its GPU reservations.

Technical diagnostics are collapsed under classroom settings. **音画同步 / Audio / video sync** retains
the beep-and-flash calibration and browser-only delay setting (D-044); use it again after changing
headphones. The page also exposes the existing director timeline, memory and runtime diagnostics there.

The launcher starts and supervises both processes, checks both listening ports before GPU reservations,
and reports ready only when `/api/health` succeeds through the frontend proxy. Startup failures and
readiness timeouts stop its children. Each invocation uses its own logs in `.cache/logs/`.

Options (environment variables; values below are configuration defaults): `PORT` (frontend, 8200),
`HOST` (frontend, 127.0.0.1), `BACKEND_PORT` (8201), `BACKEND_HOST` (127.0.0.1), `HOURS` (GPU reservation, 2h), `DIRECTOR`
(`closed_loop` = the A2 director, `open_loop` = the A1 baseline), `ALLOW_UNCALIBRATED` (1 by default, because no
capability is calibrated yet: `docs/e1_pilot.md`), `PERSONA` (`teacher`; `hanfu` selects the reading host).
`STUDENT` selects the default profile and `STUDENTS` is its comma-separated allow-list. Configuration
defaults in `puppet-full` are `learner` and `learner,demo`; the other modes default to `demo` only.
Model selection, `GPU_IDS`, `HELPER_GPU`, `OMNI_GPUS`, `HELPERS`, `IMAGES`, hosted-model options and
`RECORD` keep their existing roles. Keep the
backend on loopback for the existing SSH or HTTPS bridge; expose only the frontend port.

For `puppet-full`, `LLM_URL` and `LLM_MODEL` default to the owner-selected Aliyun Anthropic Messages
endpoint and `qwen3.8-flash`. `HOSTED_VLM_URL`/`HOSTED_VLM_MODEL` and
`HOSTED_ASR_URL`/`HOSTED_ASR_MODEL` select the hosted visual and transcription providers. Their default
endpoints and models are in `scripts/run_live.sh`. `LLM_API_KEY_FILE` defaults to
`.cache/llm_api_key`, which is git-ignored; the key is passed in the backend environment, never in
launcher arguments or frontend assets. No local board-image model is started in this CPU mode.

D-053 adds a CPU educational-diagram path for board illustration prompts, using the configured
teaching model to plan bounded shapes and labels before local PNG rendering. Exact mathematics
continues through the existing plot renderer. Completed figures refresh the active lesson board,
including images that finish after the board first appears. Use `放大配图` / `Enlarge diagram`
or activate the thumbnail to inspect a larger image; Close/Escape returns to the board.
The teacher keeps the adult female
Mandarin voice, with restrained prosody and fewer forced conversational fillers; utterance timing
preserves the complete synthesized speech. `TTS_RATE`, `TTS_PITCH`, `TTS_VOLUME` and
`PUPPET_SPEECH_TIMING` select the CPU voice profile and timing; defaults are `-4%`, `-8Hz`, `+0%`
and `natural` [configuration targets]. Real-model diagram/plot/lesson and browser checks passed;
the refreshed supervised service passed private HTTPS diagram/plot and complete-speech checks.
Verification evidence and observed brief event-loop pauses are recorded in
[docs/implementation.md](docs/implementation.md).

D-054 makes illustrations the default for substantive explanations, including simple concepts,
examples and comparisons. Ordinary answers now plan additional point diagrams automatically;
lessons can illustrate each board point. The board keeps all completed images in a gallery:
use `上一张` / `下一张` (`Previous` / `Next`) to browse, then enlarge the selected image.
Automatic lesson images still follow the point being explained; a manual selection remains selected
until the teacher changes the point or board. Images clear when the private session ends or is erased.

D-055 makes opt-in focus checks more responsive: sharper, aspect-preserving camera snapshots,
the latest pending frame instead of dropped updates, quicker confirmation of repeated observations,
and a visible status beside the camera control. Unclear frames clear stale assessments. The teacher
can give a brief reminder during ordinary board explanations as well as planned lessons; reminders
respect listening/action priority and a cooldown. Camera-off cancels pending checks and stops uploads.
This estimates visible participation cues; human attention-detection accuracy is not measured.

D-056 adds authored speaking-mouth, smile and thoughtful-listening images, smooth blink transitions
and an idle-motion clock that continues across speech clips. Mouth opening follows the actual
audio, while coarse acoustic brightness varies rounded and spread shapes. This is approximate
audio animation, not phoneme recognition. Source artwork and the built-in imagegen prompt are
saved in `live_agent/generator/assets/vtuber_teacher/expressions-v1-prompts.json`.

D-057 adds a preparation workflow to `puppet-full` teaching: draft → check arithmetic and teaching
content → rewrite weak material → review again → present. The outline, knowledge answers and every lesson
section, including the first, are checked before they enter playback. Section review follows its own
learning goal, without requiring a prerequisite section to cover the whole course. Revisions preserve user
instructions and cannot introduce learner facts or actions. Known failed material is withheld;
review errors and outcomes are logged. Minor wording suggestions do not block otherwise sound
content. Fraction additions supported by the exact checker use equal-part pictures from numerical
data. The reviewer is the configured model, so its scores remain editorial judgements and can be
wrong; a passed review does not establish learning efficacy. Preparation can take longer.
`ANSWER_SELF_CHECK=0` disables answer review and `LESSON_SELF_CHECK=off|log|revise` selects lesson
review behavior in the private teacher launcher; defaults enable answer review and lesson revision.

D-058 replaces the ordinary explanation and board-introduction arm sweeps with small gestures
near the desk. The elbow bends in the resting direction, the other hand stays at rest, and palms
blend at a shared wrist. Hand oscillation fades in and out instead of jumping at hold boundaries.
This is still a layered CPU puppet; the movement changes do not establish human realism.

### Preview the custom browser mesh teacher locally

D-059 adds an optional detailed Japanese anime teacher with separate authored layers and a
custom PixiJS mesh rig. This is **not a Live2D/Cubism model**. PixiJS 8.22.0 [pinned dependency
version], artwork and the rig are served locally. The default classroom retains its existing
video renderer; append `avatar=mesh` to a local classroom URL to request the browser avatar.
A compatible teacher/puppet session negotiates its supported gestures and falls back to video
when the model or WebGL cannot run. Teaching, audio, board images and learner data keep their
existing backend paths.

```bash
# Isolated loopback preview; open the URL printed by the command. Ctrl-C closes its fixture processes.
python3 scripts/teacher_mesh_check.py --serve

# Save browser screenshots, protocol evidence and a recording of the actual WebGL avatar/audio.
python3 scripts/teacher_mesh_check.py --out .cache/teacher-mesh/acceptance
```

The fixture reuses an existing speech recording when available; `--speech-wav` selects a PCM16
WAV. Without a recording it uses labeled synthetic tones. It calls no teaching provider and does
not modify saved learners or the running private service. Assets, exact built-in imagegen prompts,
extraction details and current limits are documented in
[the avatar asset README](frontend/public/assets/teacher-mesh/README.md). The initial artwork
revision passed local animated-canvas/audio, interruption/fallback and responsive-layout checks
[measured locally; `.cache/teacher-mesh/acceptance-final/`]. The current refinement loads
`rig-v7.json`: one intact painted head preserves facial landmarks and glasses; registered
blink/speech patches cover the original features without translucent ghosts. Separate rigid
sleeve sections keep their painted proportions, with connected shoulder/elbow/wrist geometry,
rounded cloth overlap, fitted upper sleeves, tapered forearms and consistently scaled palms.
Longer arms and larger palms follow the owner's explicit size correction; a common
head/body lift and retuned elbow/wrist paths preserve desk contact and raised poses. A repainted
torso narrows the chest and softens the blouse's exaggerated fullness while preserving shoulder
attachments. Built-in imagegen sources and exact prompts are in `source/prompts-v4.json`,
`source/prompts-v5.json` and `source/prompts-v7.json`;
earlier revisions remain available.
Rebuild with `python3 scripts/build_teacher_mesh_assets.py` (OpenCV, NumPy and Pillow required).
The wire model remains `teacher-mesh-v1`.

Native stills, full gesture motions and spoken animation were inspected before switching the
isolated local classroom to this artwork through its existing Personal-Agent bridge. Browser
verification covers speech clocks, capture freshness, interruption/reconnect, fallback and
desktop/tablet/phone layouts. Current evidence and remaining limits are recorded in
[the implementation notes](docs/implementation.md#narrower-modest-torso-2026-10-09-d-067).
Expressions and hand shapes use discrete painted states; smile retains the warm neutral face,
and the raised-index gesture has no spatial board-coordinate binding. This is a front-facing
custom mesh avatar. For an isolated earlier/staged-model preview, use
`python3 scripts/teacher_mesh_check.py --model frontend/public/assets/teacher-mesh/rig-v2.json --serve`.

### Supervise the private VTuber service

```bash
python3 scripts/puppet_service.py start
python3 scripts/puppet_service.py status
python3 scripts/puppet_service.py stop
```

The supervisor starts `puppet-full`, monitors frontend/backend health and restarts its managed launcher
after failure. It adopts an existing repository bridge when available, or manages the bridge process
it starts. Stopping the service leaves an adopted bridge running. State is in
`.cache/puppet-service/state.json`; supervisor, launcher and bridge logs are in `.cache/logs/` with the
`puppet-service` prefix. This is a private shared-token service with a single active agent session;
reboot startup and separate learner accounts are not implemented. The existing HTTPS access URL and
token-cookie flow described below remain the entry point.

Real teaching, microphone transcription, grading/profile persistence, scoped recording playback and
supervisor recovery were checked locally. The exact evidence and limits are in
[docs/implementation.md](docs/implementation.md#full-private-cpu-vtuber-service-2026-10-05-d-051).
Hosted voice recognition can take noticeably longer than typed input; the service remains dependent
on its configured providers.

### Run the frontend and backend independently

```bash
# Terminal A: API-only CPU backend, with no model services required
python3 -m live_agent.backend.app --config configs/persona_teacher \
  --generator mock --llm-url scripted --vlm-url mock --asr-url "" \
  --dev-allow-uncalibrated --record --host 127.0.0.1 --port 8201

# Terminal B: frontend pages and same-origin HTTP/WebSocket proxy
HOST=127.0.0.1 PORT=8200 BACKEND_URL=http://127.0.0.1:8201 npm --prefix frontend start

# Probe the backend through the frontend
curl http://127.0.0.1:8200/api/health
```

Open `http://127.0.0.1:8200`, `http://127.0.0.1:8200/profile` or `http://127.0.0.1:8200/traces`.
`BACKEND_URL` is a frontend-server setting; the browser uses relative API and WebSocket URLs, so no
CORS setup or browser configuration is needed. `python3 -m live_agent.server.app` remains a compatibility
entry point for the API-only backend. Its default port is now `8201`; browser pages are served by the
frontend process.

The split preserves the current limits: one active agent session, one Python backend process for shared
profile versions, and the existing student allow-list without per-student authentication. It does not
change model quality, evaluation qualification or physical lip-sync validation.

Requirements:
- **demo:** Node.js 18.2 or newer (required by `frontend/package.json`; built-in modules without npm dependencies), plus Python 3.12 with
  the packages imported by `live_agent` (fastapi, uvicorn, numpy, pillow, av, websockets, latex2mathml for board formulas).
- **puppet-full:** the CPU dependencies above, `edge-tts` and network access to the configured voice,
  teaching, visual and transcription providers. Use the existing owner-provided API key; keep it in the
  ignored private key file. No GPU or MiniMax weights are required.
- **full:** additionally the environments built by `scripts/m0/setup_env.sh` (`.venvs/taomate-h3`) and the serve
  venv (`.venvs/serve`), the TaoMate-H3 LoRA in `.cache/models/TaoMate-H3`, the MiniMax-H3 weights in
  `/data/models`, 7 free Hopper GPUs, and `/usr/bin/ffmpeg` with libx264.

## Check it

```bash
python3 -m pytest                      # CPU test suite
npm --prefix frontend test             # frontend state, profile and HTTP/WebSocket proxy tests
python3 scripts/student_frontend_check.py  # isolated CPU browser checks; requires Playwright/Chromium
scripts/server_check.sh                # backend scripted session (run under `gpu run --gpus 6`, helper models up)
python3 scripts/lipsync_page_check.py http://127.0.0.1:8200   # page clock: frames vs heard audio (headless Chromium)
```

Student-interface checks passed locally on the CPU stack, and independent GPT-6 Sol source review and
repair dispositions are recorded in [docs/codex_reviews.md](docs/codex_reviews.md). The final minor
null-decision guard was verified locally after review. Measured checks and their scope are recorded in
[docs/student_frontend.md](docs/student_frontend.md).

Lip sync of a recording (`.cache/sessions/<session>.mp4`) is measured with `tools/av_sync.py` (MediaPipe jawOpen vs
the audio level; it needs mediapipe in a separate venv and the Face Landmarker model file, see the tool's docstring).

## Evaluate

`python3 -m live_agent.eval.runner` (E2 sessions), `python3 -m live_agent.eval.adjudicate` (blinded human labels),
`python3 -m live_agent.eval.report` (the primary report refuses to run without complete adjudication),
`scripts/e1_calibrate.py`, `scripts/e1_validate.py` (capability calibration). See `docs/implementation.md`.

## Remote access through Personal-Agent (when local port forwarding is not allowed)

```
browser --https--> Caddy on Personal-Agent (live-agent.43.155.186.30.nip.io:443)
        --> token proxy 127.0.0.1:8200 (scripts/bridge_proxy.py, ~/live-agent-bridge/ on Personal-Agent)
        --> ssh reverse tunnel 127.0.0.1:18200 (scripts/bridge_tunnel.sh, run on the GPU host)
        --> frontend 127.0.0.1:8200 on the GPU host
        --> backend 127.0.0.1:8201 on the GPU host (HTTP/WebSocket proxy)
```

Open `https://live-agent.43.155.186.30.nip.io/?token=<token>` once; the token is in `.cache/bridge_token` on the GPU host.
Requests without the token cookie get 401. HTTPS also enables the microphone button.

Setup and rollback:
- **Caddy:** one `live-agent.43.155.186.30.nip.io { reverse_proxy 127.0.0.1:8200 }` block was appended to
  `/etc/caddy/Caddyfile`, following the existing nip.io pattern.
  - Backup: `/etc/caddy/Caddyfile.before-live-agent-20260926`.
  - Roll back: `sudo cp /etc/caddy/Caddyfile.before-live-agent-20260926 /etc/caddy/Caddyfile && sudo systemctl reload caddy`.
- **Stop the proxy:** `ssh Personal-Agent 'pkill -f "bridge_proxy.py --listen"'`.
- **Stop the tunnel:** `pkill -f bridge_tunnel.sh` on the GPU host.

### Updated mesh classroom through Personal-Agent

The owner-requested local full classroom also has a separate, token-protected HTTPS bridge:
`https://vtuber.43.155.186.30.nip.io/?avatar=mesh&edition=secondary&student=demo`.
Sign in with its access link first; the bootstrap removes the token while preserving classroom
options. The access token is stored privately in
`.cache/teacher-mesh/personal-agent-bridge/access_token`; it is not a provider API key.

The teaching service runs on this host at frontend/backend ports 8250/8251 [configuration], with
isolated demo storage under `.cache/teacher-mesh/full-service/`. A dedicated reconnecting tunnel
forwards Personal-Agent loopback 18250 to local 8250 [configuration]. A separate user service,
`live-agent-mesh-bridge.service`, runs the token proxy on Personal-Agent loopback 8250; Caddy
terminates HTTPS for the new hostname. Provider credentials remain on this host. The original
classroom, proxy, tunnel and HTTPS route remain available.

Keep `transport http { keepalive off }` on this hostname's Caddy reverse proxy.
The token bridge authenticates the first request of a connection; pooling that connection
across browser clients can bypass a later request's authentication. Ordinary HTTP forwarding
also requests `Connection: close`; authenticated WebSocket upgrades retain their duplex
stream. Fresh cross-client authentication and actual browser checks are recorded in
`.cache/teacher-mesh/personal-agent-bridge/keepalive-auth-regression.json` and
`serving-v3-check.json`. The original hostname's configuration is unchanged.

Check the local teaching service with
`python3 scripts/puppet_service.py status --state-dir .cache/teacher-mesh/full-service/state`.
Check the dedicated tunnel with
`supervisorctl -c .cache/teacher-mesh/personal-agent-bridge/supervisord.conf status`.
Check the remote proxy with
`ssh Personal-Agent 'systemctl --user status live-agent-mesh-bridge.service'`.
Stop only the new tunnel with the same `supervisorctl` configuration and `shutdown`, or stop
only the new remote proxy with `systemctl --user stop live-agent-mesh-bridge.service` over SSH.
The local controller reconnects SSH during the current host/container lifetime; it is not a
host-boot registration. The remote proxy is enabled with user lingering.

HTTPS/authentication and real browser speech evidence is kept separately in
`.cache/teacher-mesh/personal-agent-bridge/`. Caddy was validated before reloading; its previous
configuration is backed up under `/etc/caddy/Caddyfile.before-vtuber-*` on Personal-Agent.
