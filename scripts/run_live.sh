#!/usr/bin/env bash
# One-command launcher for the live agent (proposal v2.11 A2 system).
#
#   scripts/run_live.sh demo        # CPU only: mock video generator + rule-based responder (no GPUs, no models)
#   scripts/run_live.sh hybrid      # real Qwen3-8B responder + Qwen3-ASR (1 GPU), placeholder video
#   scripts/run_live.sh packed      # TaoMate-H3 (colocated teacher) + all helper models on 4 GPUs
#   scripts/run_live.sh full        # TaoMate-H3 (6 GPUs) + Qwen3-8B / Qwen3-VL-8B / Qwen3-ASR (1 GPU)
#   scripts/run_live.sh omni        # TaoMate-H3 on vLLM-Omni USP4 (4 GPUs) + the helper models (1 GPU)
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
PERSONA=${PERSONA:-hanfu}  # configs/persona_<name>: hanfu (reading host) | teacher (classroom Q&A)
mkdir -p .cache/logs .cache/sessions
extra=()
[ -d "configs/persona_$PERSONA" ] || { echo "unknown PERSONA=$PERSONA (no configs/persona_$PERSONA)"; exit 2; }
extra+=(--config "configs/persona_$PERSONA")
[ "$ALLOW_UNCALIBRATED" = "1" ] && extra+=(--dev-allow-uncalibrated)
[ "${RECORD:-1}" = "1" ] && extra+=(--record)  # traces: event log + presented video per session (/traces)
pids=()
set -m  # job control: each background child gets its own process group (cleanup kills whole trees)
RUN_ID=$(date +%Y%m%dT%H%M%S)-$$  # per-invocation logs: a run never parses (or releases) another run's GPUs
SERVER_LOG=.cache/logs/run_live_server.$RUN_ID.out
HELPER_LOG=.cache/logs/serve_models.$RUN_ID.out
OMNI_LOG=.cache/logs/vllm_omni.$RUN_ID.out
reserved_ids() {  # GPU ids that *our* gpu run calls reported reserving (from their own output)
  grep -ho "Reserved [0-9]* GPU(s): \[[0-9 ]*\]" "$@" 2>/dev/null | sed 's/.*\[\(.*\)\]/\1/' | tr ' ' '\n' | grep -E '^[0-9]+$' || true
}
still_ours() {  # filter GPU ids to those whose current reservation note starts with "live-agent"
  local ours
  ours=$(gpu status --no-schedule 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk -F'│' '
    NR==1 { for (i=1;i<=NF;i++) { h=$i; gsub(/ /,"",h); if (h=="NOTE") c=i } next }
    c && $c ~ /^ *live-agent/ { g=$1; gsub(/ /,"",g); print g }')
  grep -Fxf <(echo "$ours") || true
}
cleanup() {
  trap - EXIT INT TERM
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -INT -- "-$p" 2>/dev/null || kill -INT "$p" 2>/dev/null; } || true; done
  for _ in $(seq 1 60); do  # give gpu run up to 60 s to stop its command gracefully
    alive=0; for p in "${pids[@]:-}"; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && alive=1; done
    [ $alive = 0 ] && break; sleep 1
  done
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -9 -- "-$p" 2>/dev/null || kill -9 "$p" 2>/dev/null; } || true; done
  # canhazgpu can keep a reservation after its supervisor is interrupted: release exactly ours. A card can be
  # lost (idle release) and re-reserved by another job of the same user: release only cards still noted live-agent
  ids=$(reserved_ids "$SERVER_LOG" "$HELPER_LOG" "$OMNI_LOG" | sort -u | still_ours | paste -sd, -)
  if [ "$mode" != "demo" ] && [ -n "$ids" ] && command -v gpu >/dev/null; then
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
  packed)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    for p in 8101 8102 8103; do port_free $p || { echo "helper port $p already in use (models running?)"; exit 1; }; done
    : > "$SERVER_LOG"
    echo "[run_live] packed: TaoMate-H3 + helper models together on 4 GPUs (start-up ~6-8 min) ..."
    sel=(--gpus 4); [ -n "${GPU_IDS:-}" ] && sel=(--gpu-ids "$GPU_IDS")  # pin cards (e.g. avoid shared ones)
    gpu run "${sel[@]}" --timeout "$HOURS" --note "live-agent packed (TaoMate-H3 + helpers, run_live.sh)" -- \
      scripts/packed_stack.sh --director-mode "$DIRECTOR" --host "$HOST" --port "$PORT" "${extra[@]}" \
      > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    echo "[run_live] server log: $SERVER_LOG"
    ;;
  hybrid|full)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    for p in 8101 8102 8103; do port_free $p || { echo "helper port $p already in use (models running?)"; exit 1; }; done
    echo "[run_live] $mode: starting helper models on 1 GPU (log $HELPER_LOG) ..."
    : > "$HELPER_LOG"; : > "$SERVER_LOG"
    hsel=(--gpus 1); [ -n "${HELPER_GPU:-}" ] && hsel=(--gpu-ids "$HELPER_GPU")  # pin (avoid shared cards)
    gpu run "${hsel[@]}" --timeout "$HOURS" --note "live-agent helper models (run_live.sh)" -- \
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
    if [ "$mode" = "hybrid" ]; then
      # real Qwen3 responder / ASR, placeholder video (no TaoMate GPUs needed); the placeholder always
      # shows the locked action, so the simulated judge agrees with it
      echo "[run_live] helper models ready; starting hybrid server (real LLM + ASR, placeholder video) ..."
      python3 -m live_agent.server.app --generator mock --vlm-url mock --director-mode "$DIRECTOR" \
        --host "$HOST" --port "$PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    else
      echo "[run_live] helper models ready; starting TaoMate-H3 server on 6 GPUs (start-up ~2-3 min) ..."
      ssel=(--gpus 6); [ -n "${GPU_IDS:-}" ] && ssel=(--gpu-ids "$GPU_IDS")
      gpu run "${ssel[@]}" --timeout "$HOURS" --note "live-agent server (run_live.sh)" -- \
        python3 -m live_agent.server.app --generator taomate_h3 --director-mode "$DIRECTOR" \
          --host "$HOST" --port "$PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    fi
    echo "[run_live] server log: $SERVER_LOG"
    pids+=($!)
    ;;
  omni)
    # TaoMate-H3 served by vLLM-Omni (pure Ulysses SP on 4 GPUs, D-026/D-027) with the just-in-time prompt
    # hold (configs/vllm_omni/taomate_h3_usp4_jit.yaml, D-028); the web server itself needs no GPU
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    OMNI_DIR=${OMNI_DIR:-/data/zhoutaichang/worldmodel/vllm-omni-taomate}
    OMNI_PORT=${OMNI_PORT:-8191}
    OMNI_MODEL=${OMNI_MODEL:-/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe/FL2VA}
    [ -x "$OMNI_DIR/.venv/bin/vllm" ] || { echo "vLLM-Omni venv not found: $OMNI_DIR/.venv"; exit 1; }
    for p in 8101 8102 8103 "$OMNI_PORT"; do port_free $p || { echo "port $p already in use (models running?)"; exit 1; }; done
    : > "$HELPER_LOG"; : > "$OMNI_LOG"; : > "$SERVER_LOG"
    echo "[run_live] omni: helper models on 1 GPU (log $HELPER_LOG), vLLM-Omni TaoMate-H3 on 4 GPUs (log $OMNI_LOG) ..."
    hsel=(--gpus 1); [ -n "${HELPER_GPU:-}" ] && hsel=(--gpu-ids "$HELPER_GPU")
    gpu run "${hsel[@]}" --timeout "$HOURS" --note "live-agent helper models (run_live.sh)" -- \
      scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
    pids+=($!)
    osel=(--gpus 4); [ -n "${GPU_IDS:-}" ] && osel=(--gpu-ids "$GPU_IDS")
    repo=$PWD
    gpu run "${osel[@]}" --timeout "$HOURS" --note "live-agent vLLM-Omni TaoMate-H3 USP4 (run_live.sh)" -- \
      env -C "$OMNI_DIR" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/vllm serve "$OMNI_MODEL" --omni \
        --trust-remote-code --deploy-config "$repo/configs/vllm_omni/taomate_h3_usp4_jit.yaml" \
        --lora-path "$repo/.cache/models/TaoMate-H3" --host 127.0.0.1 --port "$OMNI_PORT" > "$OMNI_LOG" 2>&1 &
    pids+=($!)
    t0=$SECONDS
    until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null && curl -sf "http://127.0.0.1:$OMNI_PORT/health" >/dev/null 2>&1; do
      for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null || { echo "a model server exited during start-up:"; tail -5 "$HELPER_LOG" "$OMNI_LOG"; exit 1; }; done
      if grep -q "reservation lost\|releasing GPU reservation" "$HELPER_LOG" "$OMNI_LOG"; then
        echo "a GPU reservation was lost during start-up:"; tail -3 "$HELPER_LOG" "$OMNI_LOG"; exit 1
      fi
      [ $((SECONDS - t0)) -gt "${READY_TIMEOUT:-1800}" ] && { echo "model servers not ready in time:"; tail -5 "$HELPER_LOG" "$OMNI_LOG"; exit 1; }
      sleep 5
    done
    echo "[run_live] model servers ready ($((SECONDS - t0)) s); starting the web server ..."
    python3 -m live_agent.server.app --generator vllm_omni_h3 --omni-url "ws://127.0.0.1:$OMNI_PORT/v1/realtime/video" \
      --omni-model "$OMNI_MODEL" --director-mode "$DIRECTOR" --host "$HOST" --port "$PORT" "${extra[@]}" \
      > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    echo "[run_live] server log: $SERVER_LOG"
    ;;
  *) echo "usage: $0 demo|hybrid|packed|full|omni"; exit 2 ;;
esac

for _ in $(seq 1 "${READY_TIMEOUT:-900}"); do  # seconds; raise it when gpu run may queue for GPUs
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    echo "[run_live] ready: http://$HOST:$PORT   (Ctrl-C to stop)"
    break
  fi
  for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null || { echo "[run_live] a process exited during start-up"; exit 1; }; done
  if [ "$mode" != "demo" ] && grep -q "reservation lost" "$SERVER_LOG" "$HELPER_LOG" "$OMNI_LOG" 2>/dev/null; then
    echo "[run_live] a GPU reservation was lost during start-up"; exit 1
  fi
  sleep 1
done
wait -n "${pids[@]}"
