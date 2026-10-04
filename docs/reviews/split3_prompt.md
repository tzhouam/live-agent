Act as independent GPT-6 Sol reviewer, read-only. This is targeted re-review of split2's sole new major finding: Omni/helper/service planned-port collisions could start GPU reservations before failure. All evidence is inlined. Do not use shell tools; the host sandbox cannot start.

All four split1 findings were resolved in split2. Focus here on the new port plan validation, normalization, ordering before frontend/GPU start, conditional helpers and the fake-command tests. Check that enabled listener selection preserves the existing modes and options. Do not repeat review of unchanged backend, profile, transport, model or research implementation. The tests intentionally never run GPUs/models. Report only actionable blocking/major/minor defects in this repair; if resolved by code inspection without a new practical regression, say so. Distinguish the reported test outcomes from independent inspection.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/reviews/split2_review.md =====
1. **Major — Omni mode can reserve GPUs for services with the same port.** In [run_live.sh](/data/zhoutaichang/live-agent/scripts/run_live.sh), `OMNI_PORT=8102` with the default `HELPERS=1` puts `8102` in the planned port list twice. `model_port_free` probes each port separately before either model starts, so both probes can pass. `OMNI_PORT=08200` also bypasses the direct comparison with normalized `PORT=8200` and depends on whether the frontend has bound yet. Normalize and validate `OMNI_PORT`, then reject duplicates across all planned listeners before `gpu run`. **Smallest check:** use a fake `gpu` command and an Omni executable stub; with `OMNI_PORT=8102`, assert the launcher exits before invoking `gpu run`.

**The four original findings are resolved by inspection of the inlined code, and I found no new practical regression in those repairs.** Normal WebSocket EOF leaves queued writes to drain through `pipe()`, while error and premature close still destroy the socket; [Node documents `pipe()`’s end and backpressure behavior](https://nodejs.org/download/release/v20.18.1/docs/api/stream.html#readablepipedestination-options). The profile poll rechecks edits, student, profile identity, and visibility after its fetch. Package and launcher require Node 18.2, matching the [version that added `closeAllConnections()`](https://nodejs.org/download/release/v18.19.1/docs/api/http.html#servercloseallconnections). The original equivalent-port repro is rejected after normalization.

The test outcomes are **reported, not independently run**. README was not inlined, so its version text could not be verified.
===== FILE: docs/reviews/split3_results.md =====
# Omni port collision repair — 2026-10-02

This targets split2's new major finding. The launcher now validates and normalizes the Omni port along
with service ports, constructs the full planned listener set (frontend, backend, enabled helpers, Omni),
and rejects duplicates before frontend startup or any GPU invocation. Free-port probes follow that
configuration check.

**Measured locally:** `python3 -m pytest tests/test_launcher.py` passes **11 tests**. The test uses an
executable fake `gpu` and a vLLM executable stub with an isolated absent API-key file. Cases include
Omni/helper collisions (with optional image helper), leading-zero Omni/service collisions, invalid
ports, full/packed helper/service collisions, and unique ports reaching the fake GPU boundary. Failure
cases assert no GPU command invocation and no frontend startup. The unique-port case verifies the
normalized Omni argument, expected fake failure and frontend cleanup. No actual GPU/model is started.

`bash -n scripts/run_live.sh` and `git diff --check` pass. Existing full CPU suite, backend/media tests,
28 frontend tests and Chromium checks are recorded in `split1_results.md`. GPU runtime is still
unverified for this refactor. Numeric test counts/outcomes are measured locally; ports and version
numbers are interface/configuration values.

===== FILE: scripts/run_live.sh =====
#!/usr/bin/env bash
# One-command launcher for the live agent (proposal v2.11 A2 system).
#
#   scripts/run_live.sh demo        # CPU only: mock video generator + rule-based responder (no GPUs, no models)
#   scripts/run_live.sh hybrid      # real Qwen3-8B responder + Qwen3-ASR (1 GPU), placeholder video
#   scripts/run_live.sh packed      # TaoMate-H3 (colocated teacher) + all helper models on 4 GPUs
#   scripts/run_live.sh full        # TaoMate-H3 (6 GPUs) + Qwen3-8B / Qwen3-VL-8B / Qwen3-ASR (1 GPU)
#   scripts/run_live.sh omni        # TaoMate-H3 on vLLM-Omni USP4 (4 GPUs) + the helper models (1 GPU)
#                                   OMNI_GPUS=2: USP2 on 2 GPUs instead (FP8 + CUDA-graph teacher, D-036)
#
# Options (env): PORT (frontend, default 8200), HOST (default 127.0.0.1),
#                BACKEND_PORT (default 8201), BACKEND_HOST (default 127.0.0.1), HOURS (default 2h),
#                DIRECTOR (closed_loop | open_loop), ALLOW_UNCALIBRATED (1 = accept `documented` actions; default 1
#                because no capability is calibrated yet — see docs/e1_pilot.md)
# Then open http://HOST:PORT (from a laptop: ssh -L 8200:127.0.0.1:8200 <this host>).
# Stop with Ctrl-C: every process and GPU reservation started here is released.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
mode=${1:-demo}
PORT=${PORT:-8200}; HOST=${HOST:-127.0.0.1}; HOURS=${HOURS:-2h}
BACKEND_PORT=${BACKEND_PORT:-8201}; BACKEND_HOST=${BACKEND_HOST:-127.0.0.1}
case "$mode" in demo|hybrid|packed|full|omni) ;; *) echo "usage: $0 demo|hybrid|packed|full|omni"; exit 2 ;; esac
for tool in node python3 curl; do command -v "$tool" >/dev/null || { echo "$tool not found"; exit 1; }; done
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 18 || (major === 18 && minor >= 2) ? 0 : 1)' || { echo "Node.js 18.2 or newer is required"; exit 1; }
listener_ports=("$PORT" "$BACKEND_PORT")
if [ "$mode" = "omni" ]; then OMNI_PORT=${OMNI_PORT:-8191}; listener_ports+=("$OMNI_PORT"); fi
for port in "${listener_ports[@]}"; do
  [[ "$port" =~ ^[0-9]+$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 )) || { echo "invalid port: $port"; exit 2; }
done
PORT=$((10#$PORT)); BACKEND_PORT=$((10#$BACKEND_PORT))
if [ "$mode" = "omni" ]; then OMNI_PORT=$((10#$OMNI_PORT)); fi
[ "$PORT" != "$BACKEND_PORT" ] || { echo "PORT and BACKEND_PORT must be different"; exit 2; }
if [ "$mode" = "omni" ]; then READY_TIMEOUT=${READY_TIMEOUT:-1800}; else READY_TIMEOUT=${READY_TIMEOUT:-900}; fi
[[ "$READY_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || { echo "READY_TIMEOUT must be a positive number of seconds"; exit 2; }
DIRECTOR=${DIRECTOR:-closed_loop}; ALLOW_UNCALIBRATED=${ALLOW_UNCALIBRATED:-1}
PERSONA=${PERSONA:-hanfu}  # configs/persona_<name>: hanfu (reading host) | teacher (classroom Q&A)
# Responder LLM: local Qwen3-8B by default; a hosted OpenAI-compatible model with LLM_URL + LLM_MODEL, its key read
# from LLM_API_KEY_FILE (default .cache/llm_api_key, git-ignored) into the backend environment
LLM_URL=${LLM_URL:-http://127.0.0.1:8101/v1}; LLM_MODEL=${LLM_MODEL:-qwen3-8b}
LLM_API_KEY_FILE=${LLM_API_KEY_FILE:-.cache/llm_api_key}
if [ -z "${LLM_API_KEY:-}" ] && [ -s "$LLM_API_KEY_FILE" ]; then LLM_API_KEY=$(tr -d '[:space:]' < "$LLM_API_KEY_FILE"); fi
export LLM_API_KEY=${LLM_API_KEY:-}
# no local LLM when the responder is hosted (frees the helper card, e.g. for the board image model)
[ "$LLM_URL" != "http://127.0.0.1:8101/v1" ] && export SKIP_LLM=1
# board images (Qwen-Image on the helper card): default on for the teacher persona
# HELPERS=0 (omni mode): no helper GPU; the VLM checks and speech recognition use the hosted API with the LLM key
# (qwen3.8-flash sees images; qwen-audio-3.0-realtime-plus transcribes), and board illustrations are off
HELPERS=${HELPERS:-1}
HOSTED_VLM_URL=${HOSTED_VLM_URL:-https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1}
HOSTED_ASR_URL=${HOSTED_ASR_URL:-wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime}
IMAGES=${IMAGES:-$([ "$PERSONA" = "teacher" ] && [ "$HELPERS" = "1" ] && echo 1 || echo 0)}; export IMAGE=$IMAGES
helper_ports=()
if [ "$mode" != "demo" ] && { [ "$mode" != "omni" ] || [ "$HELPERS" = "1" ]; }; then
  helper_ports=(8102 8103); [ "${SKIP_LLM:-0}" != "1" ] && helper_ports+=(8101); [ "$IMAGES" = "1" ] && helper_ports+=(8104)
fi
model_ports=("${helper_ports[@]}")
if [ "$mode" = "omni" ]; then model_ports+=("$OMNI_PORT"); fi
declare -A planned_ports=()
for port in "$PORT" "$BACKEND_PORT" "${model_ports[@]}"; do
  [ -z "${planned_ports[$port]:-}" ] || { echo "duplicate planned listener port: $port"; exit 2; }
  planned_ports[$port]=1
done
mkdir -p .cache/logs .cache/sessions
extra=()
[ -d "configs/persona_$PERSONA" ] || { echo "unknown PERSONA=$PERSONA (no configs/persona_$PERSONA)"; exit 2; }
extra+=(--config "configs/persona_$PERSONA")
[ "$mode" != "demo" ] && extra+=(--llm-url "$LLM_URL" --llm-model "$LLM_MODEL")
[ "$IMAGES" = "1" ] && [ "$mode" != "demo" ] && extra+=(--image-url "http://127.0.0.1:8104")
[ "$ALLOW_UNCALIBRATED" = "1" ] && extra+=(--dev-allow-uncalibrated)
[ "${RECORD:-1}" = "1" ] && extra+=(--record)  # traces: event log + presented video per session (/traces)
pids=()
set -m  # job control: each background child gets its own process group (cleanup kills whole trees)
RUN_ID=$(date +%Y%m%dT%H%M%S)-$$  # per-invocation logs: a run never parses (or releases) another run's GPUs
SERVER_LOG=.cache/logs/run_live_server.$RUN_ID.out
FRONTEND_LOG=.cache/logs/run_live_frontend.$RUN_ID.out
HELPER_LOG=.cache/logs/serve_models.$RUN_ID.out
OMNI_LOG=.cache/logs/vllm_omni.$RUN_ID.out
reserved_ids() {  # GPU ids that *our* gpu run calls reported reserving (from their own output)
  grep -ho "Reserved [0-9]* GPU(s): \[[0-9 ]*\]" "$@" 2>/dev/null | sed 's/.*\[\(.*\)\]/\1/' | tr ' ' '\n' | grep -E '^[0-9]+$' || true
}
still_ours() {  # a reused card must still carry this invocation's reservation note
  local ours
  ours=$(gpu status --no-schedule 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk -F'│' -v marker="live-agent $RUN_ID " '
    NR==1 { for (i=1;i<=NF;i++) { h=$i; gsub(/ /,"",h); if (h=="NOTE") c=i } next }
    c { note=$c; sub(/^ */,"",note); if (index(note,marker)==1) { g=$1; gsub(/ /,"",g); print g } }')
  grep -Fxf <(echo "$ours") || true
}
cleanup() {
  trap - EXIT INT TERM
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -INT -- "-$p" 2>/dev/null || kill -INT "$p" 2>/dev/null; } || true; done
  for _ in $(seq 1 60); do  # give gpu run up to 60 s to stop its command gracefully
    alive=0; for p in "${pids[@]:-}"; do [ -n "$p" ] && kill -0 -- "-$p" 2>/dev/null && alive=1; done
    [ $alive = 0 ] && break; sleep 1
  done
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -9 -- "-$p" 2>/dev/null || kill -9 "$p" 2>/dev/null; } || true; done
  # canhazgpu can keep a reservation after its supervisor is interrupted: release exactly ours. A card can be
  # lost (idle release) and re-reserved by another job: release only cards still marked with this RUN_ID
  if [ "$mode" != "demo" ] && command -v gpu >/dev/null; then
    ids=$(reserved_ids "$SERVER_LOG" "$HELPER_LOG" "$OMNI_LOG" | sort -u | still_ours | paste -sd, -)
    if [ -n "$ids" ]; then gpu release --gpu-ids "$ids" >/dev/null 2>&1 && echo "[run_live] released GPUs $ids"; fi
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

port_free() {
  python3 - "$1" "${2:-127.0.0.1}" <<'PY'
import socket
import sys
try:
    family, kind, proto, _, address = socket.getaddrinfo(sys.argv[2], int(sys.argv[1]), type=socket.SOCK_STREAM)[0]
    with socket.socket(family, kind, proto) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(address)
except (OSError, ValueError):
    sys.exit(1)
PY
}
port_free "$PORT" "$HOST" || { echo "frontend port $HOST:$PORT is unavailable; set PORT=..."; exit 1; }
port_free "$BACKEND_PORT" "$BACKEND_HOST" || { echo "backend port $BACKEND_HOST:$BACKEND_PORT is unavailable; set BACKEND_PORT=..."; exit 1; }
for port in "${model_ports[@]}"; do port_free "$port" || { echo "model port $port unavailable"; exit 1; }; done
connect_host() {
  case "$1" in 0.0.0.0) echo 127.0.0.1 ;; ::) echo '[::1]' ;; *:*) echo "[$1]" ;; *) echo "$1" ;; esac
}
BACKEND_URL="http://$(connect_host "$BACKEND_HOST"):$BACKEND_PORT"
FRONTEND_URL="http://$(connect_host "$HOST"):$PORT"
processes_alive() {
  for p in "${pids[@]}"; do
    kill -0 "$p" 2>/dev/null || { echo "[run_live] a process exited; see $FRONTEND_LOG and $SERVER_LOG"; return 1; }
  done
}
env -u LLM_API_KEY HOST="$HOST" PORT="$PORT" BACKEND_URL="$BACKEND_URL" node frontend/server.mjs > "$FRONTEND_LOG" 2>&1 &
pids+=($!)
echo "[run_live] frontend log: $FRONTEND_LOG; backend: $BACKEND_URL"

case "$mode" in
  demo)
    echo "[run_live] demo: mock generator, rule-based responder, simulated judge, no ASR (CPU only)"
    python3 -m live_agent.backend.app --generator mock --llm-url scripted --vlm-url mock --asr-url "" \
      --director-mode "$DIRECTOR" --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    ;;
  packed)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    : > "$SERVER_LOG"; : > "$HELPER_LOG"
    echo "[run_live] packed: TaoMate-H3 + helper models together on 4 GPUs (start-up ~6-8 min) ..."
    sel=(--gpus 4); [ -n "${GPU_IDS:-}" ] && sel=(--gpu-ids "$GPU_IDS")  # pin cards (e.g. avoid shared ones)
    gpu run "${sel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID packed" -- \
      env HELPER_LOG="$HELPER_LOG" scripts/packed_stack.sh --director-mode "$DIRECTOR" --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" \
      > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    echo "[run_live] server log: $SERVER_LOG"
    ;;
  hybrid|full)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    echo "[run_live] $mode: starting helper models on 1 GPU (log $HELPER_LOG) ..."
    : > "$HELPER_LOG"; : > "$SERVER_LOG"
    hsel=(--gpus 1); [ -n "${HELPER_GPU:-}" ] && hsel=(--gpu-ids "$HELPER_GPU")  # pin (avoid shared cards)
    gpu run "${hsel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID helpers" -- \
      scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
    pids+=($!)
    t0=$SECONDS
    until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null; do
      processes_alive || { tail -20 "$HELPER_LOG"; exit 1; }
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
      python3 -m live_agent.backend.app --generator mock --vlm-url mock --director-mode "$DIRECTOR" \
        --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    else
      echo "[run_live] helper models ready; starting TaoMate-H3 server on 6 GPUs (start-up ~2-3 min) ..."
      ssel=(--gpus 6); [ -n "${GPU_IDS:-}" ] && ssel=(--gpu-ids "$GPU_IDS")
      gpu run "${ssel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID backend" -- \
        python3 -m live_agent.backend.app --generator taomate_h3 --director-mode "$DIRECTOR" \
          --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    fi
    echo "[run_live] server log: $SERVER_LOG"
    pids+=($!)
    ;;
  omni)
    # TaoMate-H3 served by vLLM-Omni (pure Ulysses SP on 4 GPUs, D-026/D-027) with the just-in-time prompt
    # hold (configs/vllm_omni/taomate_h3_usp4_jit.yaml, D-028); the web server itself needs no GPU
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    OMNI_DIR=${OMNI_DIR:-/data/zhoutaichang/worldmodel/vllm-omni-taomate}
    OMNI_MODEL=${OMNI_MODEL:-/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe/FL2VA}
    [ -x "$OMNI_DIR/.venv/bin/vllm" ] || { echo "vLLM-Omni venv not found: $OMNI_DIR/.venv"; exit 1; }
    : > "$HELPER_LOG"; : > "$OMNI_LOG"; : > "$SERVER_LOG"
    OMNI_GPUS=${OMNI_GPUS:-4}  # 4: USP4 (default); 2: USP2 with FP8 linears and CUDA-graph teacher (D-036)
    case "$OMNI_GPUS" in 2|4) ;; *) echo "OMNI_GPUS must be 2 or 4"; exit 1;; esac
    echo "[run_live] omni: helper models $([ "$HELPERS" = "1" ] && echo "on 1 GPU (log $HELPER_LOG)" || echo "hosted (API)"), vLLM-Omni TaoMate-H3 on $OMNI_GPUS GPUs (log $OMNI_LOG) ..."
    if [ "$HELPERS" = "1" ]; then
      hsel=(--gpus 1); [ -n "${HELPER_GPU:-}" ] && hsel=(--gpu-ids "$HELPER_GPU")
      gpu run "${hsel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID helpers" -- \
        scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
      pids+=($!)
    else
      echo "ALL_READY (hosted VLM and ASR)" > "$HELPER_LOG"
      extra+=(--vlm-url "$HOSTED_VLM_URL" --vlm-model "$LLM_MODEL" --asr-url "$HOSTED_ASR_URL"
              --asr-model qwen-audio-3.0-realtime-plus)
    fi
    osel=(--gpus "$OMNI_GPUS"); [ -n "${GPU_IDS:-}" ] && osel=(--gpu-ids "$GPU_IDS")
    repo=$PWD
    gpu run "${osel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID omni USP$OMNI_GPUS" -- \
      env -C "$OMNI_DIR" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/vllm serve "$OMNI_MODEL" --omni \
        --trust-remote-code --deploy-config "$repo/configs/vllm_omni/taomate_h3_usp${OMNI_GPUS}_jit.yaml" \
        --init-timeout 2400 --stage-init-timeout 2400 \
        --lora-path "$repo/.cache/models/TaoMate-H3" --host 127.0.0.1 --port "$OMNI_PORT" > "$OMNI_LOG" 2>&1 &
    pids+=($!)
    t0=$SECONDS
    until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null && curl --noproxy '*' --connect-timeout 1 --max-time 2 -sf "http://127.0.0.1:$OMNI_PORT/health" >/dev/null 2>&1; do
      processes_alive || { tail -5 "$HELPER_LOG" "$OMNI_LOG"; exit 1; }
      if grep -q "reservation lost\|releasing GPU reservation" "$HELPER_LOG" "$OMNI_LOG"; then
        echo "a GPU reservation was lost during start-up:"; tail -3 "$HELPER_LOG" "$OMNI_LOG"; exit 1
      fi
      [ $((SECONDS - t0)) -gt "${READY_TIMEOUT:-1800}" ] && { echo "model servers not ready in time:"; tail -5 "$HELPER_LOG" "$OMNI_LOG"; exit 1; }
      sleep 5
    done
    echo "[run_live] model servers ready ($((SECONDS - t0)) s); starting the backend ..."
    python3 -m live_agent.backend.app --generator vllm_omni_h3 --omni-url "ws://127.0.0.1:$OMNI_PORT/v1/realtime/video" \
      --omni-model "$OMNI_MODEL" --director-mode "$DIRECTOR" --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" \
      > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    echo "[run_live] server log: $SERVER_LOG"
    ;;
  *) echo "usage: $0 demo|hybrid|packed|full|omni"; exit 2 ;;
esac

ready=0
t0=$SECONDS
while [ $((SECONDS - t0)) -lt "$READY_TIMEOUT" ]; do  # raise it when gpu run may queue for GPUs
  processes_alive || exit 1
  if curl --noproxy '*' --connect-timeout 1 --max-time 2 -sf "$FRONTEND_URL/api/health" >/dev/null 2>&1; then
    echo "[run_live] ready: $FRONTEND_URL   (backend $BACKEND_URL; Ctrl-C to stop)"
    ready=1
    break
  fi
  if [ "$mode" != "demo" ] && grep -q "reservation lost" "$SERVER_LOG" "$HELPER_LOG" "$OMNI_LOG" 2>/dev/null; then
    echo "[run_live] a GPU reservation was lost during start-up"; exit 1
  fi
  sleep 1
done
[ "$ready" = "1" ] || { echo "[run_live] frontend/backend not ready after $READY_TIMEOUT s; see $FRONTEND_LOG and $SERVER_LOG"; exit 1; }
status=0
wait -n "${pids[@]}" || status=$?
echo "[run_live] a process exited; stopping the stack"
[ "$status" -ne 0 ] || status=1
exit "$status"

===== FILE: tests/test_launcher.py =====
"""Launcher preflight checks with executable stubs; no GPU or model process starts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required by the launcher")


@pytest.fixture
def launcher_env(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    calls = tmp_path / "gpu_calls.jsonl"
    gpu = tools / "gpu"
    gpu.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['FAKE_GPU_CALLS'], 'a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'run': sys.exit(9)\n"
        "if sys.argv[1] == 'status':\n"
        "    print(' GPU │ NOTE ')\n"
        "    sys.exit(0)\n"
        "sys.exit(2)\n"
    )
    gpu.chmod(0o755)
    omni = tmp_path / "omni"
    executable = omni / ".venv" / "bin" / "vllm"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 99\n")
    executable.chmod(0o755)
    # Reserve all candidates together so even the fixture cannot select duplicates.
    sockets = [socket.socket() for _ in range(3)]
    try:
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        ports = [str(sock.getsockname()[1]) for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()
    env = dict(
        os.environ,
        PATH=str(tools) + os.pathsep + os.environ["PATH"],
        FAKE_GPU_CALLS=str(calls),
        OMNI_DIR=str(omni),
        PORT=ports[0],
        BACKEND_PORT=ports[1],
        OMNI_PORT=ports[2],
        HOST="127.0.0.1",
        BACKEND_HOST="127.0.0.1",
        PERSONA="hanfu",
        HELPERS="1",
        IMAGES="0",
        SKIP_LLM="0",
        LLM_URL="http://127.0.0.1:8101/v1",
        LLM_API_KEY="",
        LLM_API_KEY_FILE=str(tmp_path / "nonexistent_key"),
        RECORD="0",
        READY_TIMEOUT="2",
    )
    return env, calls


@pytest.mark.parametrize(
    "mode, overrides, expected",
    [
        ("omni", {"OMNI_PORT": "8102"}, "duplicate planned listener port: 8102"),
        ("omni", {"OMNI_PORT": "8103"}, "duplicate planned listener port: 8103"),
        ("omni", {"OMNI_PORT": "8104", "IMAGES": "1"}, "duplicate planned listener port: 8104"),
        ("omni", {"PORT": "8200", "OMNI_PORT": "08200"}, "duplicate planned listener port: 8200"),
        ("omni", {"BACKEND_PORT": "8201", "OMNI_PORT": "08201"}, "duplicate planned listener port: 8201"),
        ("omni", {"OMNI_PORT": "0"}, "invalid port: 0"),
        ("omni", {"OMNI_PORT": "65536"}, "invalid port: 65536"),
        ("omni", {"OMNI_PORT": "not-a-port"}, "invalid port: not-a-port"),
        ("full", {"BACKEND_PORT": "8102"}, "duplicate planned listener port: 8102"),
        ("packed", {"PORT": "8103"}, "duplicate planned listener port: 8103"),
    ],
)
def test_invalid_planned_ports_fail_before_start(launcher_env, mode, overrides, expected):
    env, calls = launcher_env
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), mode],
        env={**env, **overrides}, cwd=ROOT, text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert expected in result.stdout
    assert "[run_live] frontend log:" not in result.stdout
    assert not calls.exists(), "preflight must not invoke even the fake GPU command"


def test_unique_ports_reach_fake_gpu_boundary_and_clean_frontend(launcher_env):
    env, calls = launcher_env
    expected_omni_port = env["OMNI_PORT"]
    env = {**env, "HELPERS": "0", "OMNI_PORT": "0" + expected_omni_port}
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), "omni"],
        env=env, cwd=ROOT, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    runs = [command for command in commands if command[0] == "run"]
    assert len(runs) == 1
    run = runs[0]
    assert ".venv/bin/vllm" in run
    assert run[run.index("--port") + 1] == expected_omni_port
    assert "duplicate planned listener port" not in result.stdout
    assert "[run_live] ready:" not in result.stdout
    for name in ("PORT", "BACKEND_PORT"):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", int(env[name]))) != 0
