#!/usr/bin/env bash
# One-command launcher for the live agent (proposal v2.11 A2 system).
#
#   scripts/run_live.sh demo        # CPU only: mock video generator + rule-based responder (no GPUs, no models)
#   scripts/run_live.sh full        # TaoMate-H3 (6 GPUs) + Qwen3-8B / Qwen3-VL-8B / Qwen3-ASR (1 GPU)
#
# Options (env): PORT (default 8200), HOST (default 127.0.0.1), HOURS (GPU reservation, default 2h),
#                DIRECTOR (closed_loop | open_loop), ALLOW_UNCALIBRATED (1 = accept `documented` actions; default 1
#                because no capability is calibrated yet — see docs/e1_pilot.md)
# Then open http://HOST:PORT (from a laptop: ssh -L 8200:127.0.0.1:8200 <this host>).
# Stop with Ctrl-C: every process and GPU reservation started here is released.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
mode=${1:-demo}
PORT=${PORT:-8200}; HOST=${HOST:-127.0.0.1}; HOURS=${HOURS:-2h}
DIRECTOR=${DIRECTOR:-closed_loop}; ALLOW_UNCALIBRATED=${ALLOW_UNCALIBRATED:-1}
mkdir -p .cache/logs .cache/sessions
extra=()
[ "$ALLOW_UNCALIBRATED" = "1" ] && extra+=(--dev-allow-uncalibrated)
pids=()
cleanup() {
  for p in "${pids[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

port_free() { ! (echo > "/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
port_free "$PORT" || { echo "port $PORT is in use; set PORT=..."; exit 1; }

case "$mode" in
  demo)
    echo "[run_live] demo: mock generator, rule-based responder, simulated judge, no ASR (CPU only)"
    python3 -m live_agent.server.app --generator mock --llm-url scripted --vlm-url mock --asr-url "" \
      --director-mode "$DIRECTOR" --host "$HOST" --port "$PORT" "${extra[@]}" &
    pids+=($!)
    ;;
  full)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    for p in 8101 8102 8103; do port_free $p || { echo "helper port $p already in use (models running?)"; exit 1; }; done
    echo "[run_live] full: starting helper models on 1 GPU (log .cache/logs/serve_models.out) ..."
    gpu run --gpus 1 --timeout "$HOURS" --note "live-agent helper models (run_live.sh)" -- \
      scripts/serve_models.sh > .cache/logs/serve_models.out 2>&1 &
    pids+=($!)
    until grep -q ALL_READY .cache/logs/serve_models.out 2>/dev/null; do
      kill -0 "${pids[0]}" 2>/dev/null || { echo "helper models failed:"; tail -20 .cache/logs/serve_models.out; exit 1; }
      sleep 5
    done
    echo "[run_live] helper models ready; starting TaoMate-H3 server on 6 GPUs (start-up ~2-3 min) ..."
    gpu run --gpus 6 --timeout "$HOURS" --note "live-agent server (run_live.sh)" -- \
      python3 -m live_agent.server.app --generator taomate_h3 --director-mode "$DIRECTOR" \
        --host "$HOST" --port "$PORT" "${extra[@]}" &
    pids+=($!)
    ;;
  *) echo "usage: $0 demo|full"; exit 2 ;;
esac

for _ in $(seq 1 900); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    echo "[run_live] ready: http://$HOST:$PORT   (Ctrl-C to stop)"
    break
  fi
  for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null || { echo "[run_live] a process exited during start-up"; exit 1; }; done
  sleep 1
done
wait -n "${pids[@]}"
