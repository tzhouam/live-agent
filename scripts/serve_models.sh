#!/usr/bin/env bash
# Serve the helper models (LLM, VLM judge, ASR) with vLLM on ONE reserved GPU.
# Usage (always through canhazgpu):
#   gpu run --gpus 1 --timeout 8h --note "live-agent helper models" -- scripts/serve_models.sh
# Ports: 8101 LLM (Qwen3-8B), 8102 VLM (Qwen3-VL-8B-Instruct), 8103 ASR (Qwen3-ASR-1.7B).
set -euo pipefail
LOG=${LOG_DIR:-/data/zhoutaichang/live-agent/.cache/logs}
mkdir -p "$LOG"
LLM=${LLM_PATH:-/data/models/Qwen3-8B}
VLM=${VLM_PATH:-/data/models/hub/Qwen3-VL-8B-Instruct}
ASR=${ASR_PATH:-/data/models/Qwen3-ASR-1.7B}
# Placement / memory (defaults: all three on the one reserved GPU). For packing next to TaoMate-H3
# (scripts/run_live.sh packed) each server gets its own card and a small memory share.
DEV_LLM=${DEV_LLM:-${CUDA_VISIBLE_DEVICES:-0}}; DEV_VLM=${DEV_VLM:-${CUDA_VISIBLE_DEVICES:-0}}
DEV_ASR=${DEV_ASR:-${CUDA_VISIBLE_DEVICES:-0}}
UTIL_LLM=${UTIL_LLM:-0.30}; UTIL_VLM=${UTIL_VLM:-0.30}; UTIL_ASR=${UTIL_ASR:-0.15}
LEN_LLM=${LEN_LLM:-16384}; LEN_VLM=${LEN_VLM:-16384}
CUDA_VISIBLE_DEVICES=$DEV_LLM "${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$LLM" --served-model-name qwen3-8b --port 8101 --gpu-memory-utilization "$UTIL_LLM" \
  --max-model-len "$LEN_LLM" --enable-prefix-caching > "$LOG/llm.log" 2>&1 &
P1=$!
wait_ready() {  # start the next server only after this one is healthy (memory profiling must not overlap)
  for _ in $(seq 1 180); do curl -sf "localhost:$1/health" >/dev/null && return 0; sleep 5; done
  echo "server on port $1 did not become ready" >&2; return 1
}
wait_ready 8101
CUDA_VISIBLE_DEVICES=$DEV_VLM "${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$VLM" --served-model-name qwen3-vl-8b --port 8102 --gpu-memory-utilization "$UTIL_VLM" \
  --max-model-len "$LEN_VLM" --limit-mm-per-prompt '{"image": 8}' > "$LOG/vlm.log" 2>&1 &
P2=$!
wait_ready 8102
CUDA_VISIBLE_DEVICES=$DEV_ASR "${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$ASR" --served-model-name qwen3-asr --port 8103 --gpu-memory-utilization "$UTIL_ASR" \
  --max-model-len 8192 > "$LOG/asr.log" 2>&1 &
P3=$!
wait_ready 8103 && echo "ALL_READY"
trap 'kill $P1 $P2 $P3 2>/dev/null' EXIT INT TERM
wait -n $P1 $P2 $P3
echo "a model server exited; see $LOG" >&2
exit 1
