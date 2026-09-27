#!/usr/bin/env bash
# Serve the helper models (LLM, VLM judge, ASR) with vLLM on ONE reserved GPU.
# Usage (always through canhazgpu):
#   gpu run --gpus 1 --timeout 8h --note "live-agent helper models" -- scripts/serve_models.sh
# Ports: 8101 LLM (Qwen3-8B), 8102 VLM (Qwen3-VL-8B-Instruct), 8103 ASR (Qwen3-ASR-1.7B),
#        8104 board images (Qwen-Image-2512 + Lightning 4-step LoRA, vLLM-Omni) when IMAGE=1.
# SKIP_LLM=1: no local LLM (the responder is a hosted model), which leaves room for the image model.
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
wait_ready() {  # start the next server only after this one is healthy (memory profiling must not overlap)
  for _ in $(seq 1 180); do curl -sf "localhost:$1/health" >/dev/null && return 0; sleep 5; done
  echo "server on port $1 did not become ready" >&2; return 1
}
PIDS=()
if [ "${SKIP_LLM:-0}" != "1" ]; then
  CUDA_VISIBLE_DEVICES=$DEV_LLM "${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$LLM" --served-model-name qwen3-8b --port 8101 --gpu-memory-utilization "$UTIL_LLM" \
    --max-model-len "$LEN_LLM" --enable-prefix-caching > "$LOG/llm.log" 2>&1 &
  PIDS+=($!)
  wait_ready 8101
fi
CUDA_VISIBLE_DEVICES=$DEV_VLM "${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$VLM" --served-model-name qwen3-vl-8b --port 8102 --gpu-memory-utilization "$UTIL_VLM" \
  --max-model-len "$LEN_VLM" --limit-mm-per-prompt '{"image": 8}' > "$LOG/vlm.log" 2>&1 &
PIDS+=($!)
wait_ready 8102
CUDA_VISIBLE_DEVICES=$DEV_ASR "${VLLM:-/data/zhoutaichang/live-agent/.venvs/serve/bin/vllm}" serve "$ASR" --served-model-name qwen3-asr --port 8103 --gpu-memory-utilization "$UTIL_ASR" \
  --max-model-len 8192 > "$LOG/asr.log" 2>&1 &
PIDS+=($!)
wait_ready 8103
if [ "${IMAGE:-0}" = "1" ]; then  # started last: it takes the memory the vLLM servers left
  OMNI_DIR=${OMNI_DIR:-/data/zhoutaichang/worldmodel/vllm-omni-taomate}
  IMG=${IMAGE_PATH:-$(ls -d /data/models/hub/models--Qwen--Qwen-Image-2512/snapshots/*/ | head -1)}
  LORA=${IMAGE_LORA:-$(ls /data/models/hub/models--lightx2v--Qwen-Image-2512-Lightning/snapshots/*/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors | head -1)}
  CUDA_VISIBLE_DEVICES=${DEV_IMAGE:-${CUDA_VISIBLE_DEVICES:-0}} env -C "$OMNI_DIR" HF_HUB_OFFLINE=1 .venv/bin/vllm serve "$IMG" --omni \
    --served-model-name qwen-image --host 127.0.0.1 --port 8104 --lora-backend distill --lora-path "$LORA" > "$LOG/image.log" 2>&1 &
  PIDS+=($!)
  wait_ready 8104
fi
echo "ALL_READY"
trap 'kill "${PIDS[@]}" 2>/dev/null' EXIT INT TERM
wait -n "${PIDS[@]}"
echo "a model server exited; see $LOG" >&2
exit 1
