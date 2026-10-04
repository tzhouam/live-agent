#!/usr/bin/env bash
# Everything on 4 GPUs (run inside ONE `gpu run --gpus 4` reservation; CUDA_VISIBLE_DEVICES = those 4):
# helper models packed next to TaoMate-H3 (student + colocated audio teacher on all 4 cards).
# Memory per card [measured locally, M0]: TaoMate colocated ~106 GiB + <=24 GiB helper, of 140 GiB.
# (ASR needs >=0.10: at 0.06 vLLM had no room left for its KV cache.)
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
IFS=, read -r -a D <<< "${CUDA_VISIBLE_DEVICES:?run inside gpu run --gpus 4}"
[ "${#D[@]}" -ge 4 ] || { echo "need 4 GPUs, got ${CUDA_VISIBLE_DEVICES}"; exit 1; }
HELPER_LOG=${HELPER_LOG:-.cache/logs/serve_models.packed.out}
mkdir -p "$(dirname "$HELPER_LOG")"
: > "$HELPER_LOG"
DEV_LLM=${D[0]} DEV_VLM=${D[1]} DEV_ASR=${D[2]} UTIL_LLM=0.16 UTIL_VLM=0.17 UTIL_ASR=0.10 LEN_LLM=8192 LEN_VLM=8192 \
  scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
H=$!
trap 'kill "$H" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
t0=$SECONDS
until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null; do
  kill -0 $H 2>/dev/null || { echo "helper models failed:"; tail -20 "$HELPER_LOG"; exit 1; }
  [ $((SECONDS - t0)) -lt "${READY_TIMEOUT:-1200}" ] || { echo "packed helper models not ready in time:"; tail -20 "$HELPER_LOG"; exit 1; }
  sleep 5
done
echo "[packed] helper models ready on GPUs ${D[0]},${D[1]},${D[2]}; starting TaoMate-H3 on ${D[0]},${D[1]},${D[2]},${D[3]} (colocated teacher)"
python3 -m live_agent.backend.app --generator taomate_h3 --taomate-student-devices "${D[0]},${D[1]},${D[2]},${D[3]}" \
  --taomate-colocate-teacher "$@"
