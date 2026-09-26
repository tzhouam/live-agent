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
set -m  # job control: each background child gets its own process group (cleanup kills whole trees)
RUN_ID=$(date +%Y%m%dT%H%M%S)-$$  # per-invocation logs: a run never parses (or releases) another run's GPUs
SERVER_LOG=.cache/logs/run_live_server.$RUN_ID.out
HELPER_LOG=.cache/logs/serve_models.$RUN_ID.out
reserved_ids() {  # GPU ids that *our* gpu run calls reported reserving (from their own output)
  grep -ho "Reserved [0-9]* GPU(s): \[[0-9 ]*\]" "$@" 2>/dev/null | sed 's/.*\[\(.*\)\]/\1/' | tr ' ' '\n' | grep -E '^[0-9]+$' || true
}
cleanup() {
  trap - EXIT INT TERM
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -INT -- "-$p" 2>/dev/null || kill -INT "$p" 2>/dev/null; } || true; done
  for _ in $(seq 1 60); do  # give gpu run up to 60 s to stop its command gracefully
    alive=0; for p in "${pids[@]:-}"; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && alive=1; done
    [ $alive = 0 ] && break; sleep 1
  done
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -9 -- "-$p" 2>/dev/null || kill -9 "$p" 2>/dev/null; } || true; done
  # canhazgpu can keep a reservation after its supervisor is interrupted: release exactly ours
  ids=$(reserved_ids "$SERVER_LOG" "$HELPER_LOG" | sort -u | paste -sd, -)
  if [ "$mode" = "full" ] && [ -n "$ids" ] && command -v gpu >/dev/null; then
    gpu release --gpu-ids "$ids" >/dev/null 2>&1 && echo "[run_live] released GPUs $ids"
  fi
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
    echo "[run_live] full: starting helper models on 1 GPU (log $HELPER_LOG) ..."
    : > "$HELPER_LOG"; : > "$SERVER_LOG"
    gpu run --gpus 1 --timeout "$HOURS" --note "live-agent helper models (run_live.sh)" -- \
      scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
    pids+=($!)
    t0=$SECONDS
    until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null; do
      kill -0 "${pids[0]}" 2>/dev/null || { echo "helper models failed:"; tail -20 "$HELPER_LOG"; exit 1; }
      if grep -q "reservation lost\|releasing GPU reservation" "$HELPER_LOG"; then
        echo "helper GPU reservation was lost:"; tail -5 "$HELPER_LOG"; exit 1
      fi
      [ $((SECONDS - t0)) -gt 1200 ] && { echo "helper models not ready after 20 min:"; tail -20 "$HELPER_LOG"; exit 1; }
      sleep 5
    done
    echo "[run_live] helper models ready; starting TaoMate-H3 server on 6 GPUs (start-up ~2-3 min) ..."
    gpu run --gpus 6 --timeout "$HOURS" --note "live-agent server (run_live.sh)" -- \
      python3 -m live_agent.server.app --generator taomate_h3 --director-mode "$DIRECTOR" \
        --host "$HOST" --port "$PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    echo "[run_live] server log: $SERVER_LOG"
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
  if [ "$mode" = "full" ] && grep -q "reservation lost" "$SERVER_LOG" "$HELPER_LOG" 2>/dev/null; then
    echo "[run_live] a GPU reservation was lost during start-up"; exit 1
  fi
  sleep 1
done
wait -n "${pids[@]}"
