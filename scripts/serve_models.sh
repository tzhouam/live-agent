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
"${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$LLM" --served-model-name qwen3-8b --port 8101 --gpu-memory-utilization 0.30 \
  --max-model-len 16384 --enable-prefix-caching > "$LOG/llm.log" 2>&1 &
P1=$!
sleep 60   # stagger start-up so memory profiling does not overlap
"${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$VLM" --served-model-name qwen3-vl-8b --port 8102 --gpu-memory-utilization 0.30 \
  --max-model-len 16384 --limit-mm-per-prompt '{"image": 8}' > "$LOG/vlm.log" 2>&1 &
P2=$!
sleep 60
"${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$ASR" --served-model-name qwen3-asr --port 8103 --gpu-memory-utilization 0.15 \
  --max-model-len 8192 > "$LOG/asr.log" 2>&1 &
P3=$!
trap 'kill $P1 $P2 $P3 2>/dev/null' EXIT INT TERM
wait -n $P1 $P2 $P3
echo "a model server exited; see $LOG" >&2
exit 1
