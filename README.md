# live-agent

A real-time, personalized live persona on **TaoMate-H3** (MiniMax H3 + streaming LoRA): an online director
plans each 5-second request, checks what the viewer actually saw, repairs failed actions, remembers the user
in scoped memory and forgets on request. The research proposal is `docs/research_proposal_zh.md` (v2.11); the
implementation status, measurements and known limits are in `docs/implementation.md`.

The browser UI lives in `frontend/` and runs as a separate Node process. The Python backend in
`live_agent/backend/` owns the agent, model connections, memory, profiles and recordings. The frontend
serves `/`, `/profile` and `/traces`, and proxies the existing HTTP APIs, media and `/ws` to the backend
on the same browser origin. See `docs/frontend_backend.md` for the interface.

The student classroom has primary-school and secondary-school editions in Chinese and a
university/adult edition with English interface text. These are interface configurations: the current
catalogue covers Chinese school subjects, and teaching remains Chinese/Mandarin in every edition.
There is no verified university/adult course catalogue or English teaching mode. Research references,
implemented flows and validation limits are in [docs/student_frontend.md](docs/student_frontend.md).

## Run it

```bash
# CPU only, no GPUs or model servers: mock video, rule-based responder, simulated judge
scripts/run_live.sh demo

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
asks for a learner selection. This remains a trusted local operator service without learner
authentication. Edition links use `?edition=primary`, `?edition=secondary` or `?edition=university`, and
the selection is remembered in this browser.

In `demo` mode the video, responder and judge are stand-ins. The rule responder cannot generate lessons
or practice questions; the page explains this and disables those actions after the session reports its
configuration. Use it to inspect the interface and transport. `hybrid`, `full` and `omni` use their
existing model/GPU setup; those live teaching paths were not qualified by this student-interface change.
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
Model selection, `GPU_IDS`, `HELPER_GPU`, `OMNI_GPUS`, `HELPERS`, `IMAGES`, hosted-model options and
`RECORD` keep their existing roles. Keep the
backend on loopback for the existing SSH or HTTPS bridge; expose only the frontend port.

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
