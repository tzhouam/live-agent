# live-agent

A real-time, personalized live persona on **TaoMate-H3** (MiniMax H3 + streaming LoRA): an online director
plans each 5-second request, checks what the viewer actually saw, repairs failed actions, remembers the user
in scoped memory and forgets on request. The research proposal is `docs/research_proposal_zh.md` (v2.11); the
implementation status, measurements and known limits are in `docs/implementation.md`.

## Run it

```bash
# CPU only, no GPUs or model servers: mock video, rule-based responder, simulated judge
scripts/run_live.sh demo

# Full stack: TaoMate-H3 on 6 GPUs + Qwen3-8B / Qwen3-VL-8B / Qwen3-ASR on 1 GPU (via canhazgpu)
scripts/run_live.sh full
```

Then open `http://127.0.0.1:8200` (from a laptop: `ssh -L 8200:127.0.0.1:8200 <host>`), press **连接**, and type
or hold **按住说话** to talk. Try "请喝口茶吧", "跟我挥挥手吧", "我妹妹住在杭州", then "请忘掉我妹妹住在哪".
Ctrl-C stops everything and releases the GPU reservations.

Options (environment variables): `PORT` (8200), `HOST` (127.0.0.1), `HOURS` (GPU reservation, 2h), `DIRECTOR`
(`closed_loop` = the A2 director, `open_loop` = the A1 baseline), `ALLOW_UNCALIBRATED` (1 by default, because no
capability is calibrated yet: `docs/e1_pilot.md`).

Requirements:
- **demo:** Python 3.12 with the packages imported by `live_agent` (fastapi, uvicorn, numpy, pillow).
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
