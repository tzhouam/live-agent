# live-agent

A real-time, personalized live persona on **TaoMate-H3** (MiniMax H3 + streaming LoRA): an online director
plans each 5-second request, checks what the viewer actually saw, repairs failed actions, remembers the user
in scoped memory and forgets on request. The research proposal is `docs/research_proposal_zh.md` (v2.11); the
implementation status, measurements and known limits are in `docs/implementation.md`.

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

# Same, with the classroom teacher persona: students ask, the teacher answers or gives a whole lesson with a board beside
# the video ("给我上一节…的课"; D-032, D-034); LLM_URL/LLM_MODEL select a hosted responder (D-033)
PERSONA=teacher GPU_IDS=0,1,2,3 HELPER_GPU=4 PORT=8203 HOURS=8h scripts/run_live.sh omni
```

`omni` needs the vLLM-Omni worktree `/data/zhoutaichang/worldmodel/vllm-omni-taomate` (branch
`feat/taomate-h3-realtime`, with its `.venv`; override with `OMNI_DIR`). It serves on `OMNI_PORT` (8191) with
`configs/vllm_omni/taomate_h3_usp4_jit.yaml`, whose `taomate_h3_hold_for_prompt` makes each 5 s request wait
for the director's just-in-time prompt. Start-up takes about 6 min (4 x 87 GiB load plus one warm-up request).

The web demo page shows:
- **Stage:** the persona video (portrait) and its spoken line.
- **Controls:** text or push-to-talk input, plus one-click example prompts.
- **Director panel:**
  - intent chains with their status (in progress, verified, failed, skipped);
  - a live timeline of every locked 5 s request, judge verdict, forward repair and completion claim;
  - memory recall and erasure;
  - metrics (instruction→speech onset, Λ, verified actions, repairs, RTT).

In `demo` mode the video is a placeholder that prints the action and line the director locked, and the
responder and judge are stand-ins. It shows how the agent works, but it is not a measurement.

Then open `http://127.0.0.1:8200` (from a laptop: `ssh -L 8200:127.0.0.1:8200 <host>`), press **连接**, and type
or hold **按住说话** to talk. Try "请喝口茶吧", "跟我挥挥手吧", "我妹妹住在杭州", then "请忘掉我妹妹住在哪".
Ctrl-C stops everything and releases the GPU reservations.

Options (environment variables): `PORT` (8200), `HOST` (127.0.0.1), `HOURS` (GPU reservation, 2h), `DIRECTOR`
(`closed_loop` = the A2 director, `open_loop` = the A1 baseline), `ALLOW_UNCALIBRATED` (1 by default, because no
capability is calibrated yet: `docs/e1_pilot.md`).

Requirements:
- **demo:** Python 3.12 with the packages imported by `live_agent` (fastapi, uvicorn, numpy, pillow, av, websockets, latex2mathml for board formulas).
- **full:** additionally the environments built by `scripts/m0/setup_env.sh` (`.venvs/taomate-h3`) and the serve
  venv (`.venvs/serve`), the TaoMate-H3 LoRA in `.cache/models/TaoMate-H3`, the MiniMax-H3 weights in
  `/data/models`, 7 free Hopper GPUs, and `/usr/bin/ffmpeg` with libx264.

## Check it

```bash
python3 -m pytest                      # CPU test suite
scripts/server_check.sh                # full-stack scripted session (run under `gpu run --gpus 6`, helper models up)
```

## Evaluate

`python3 -m live_agent.eval.runner` (E2 sessions), `python3 -m live_agent.eval.adjudicate` (blinded human labels),
`python3 -m live_agent.eval.report` (the primary report refuses to run without complete adjudication),
`scripts/e1_calibrate.py`, `scripts/e1_validate.py` (capability calibration). See `docs/implementation.md`.

## Remote access through Personal-Agent (when local port forwarding is not allowed)

```
browser --https--> Caddy on Personal-Agent (live-agent.43.155.186.30.nip.io:443)
        --> token proxy 127.0.0.1:8200 (scripts/bridge_proxy.py, ~/live-agent-bridge/ on Personal-Agent)
        --> ssh reverse tunnel 127.0.0.1:18200 (scripts/bridge_tunnel.sh, run on the GPU host)
        --> web demo 127.0.0.1:8200 on the GPU host
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
