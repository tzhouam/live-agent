#!/usr/bin/env bash
# Streaming adapter validation: 2 lookahead repetitions + 1 sequential-teacher run, 4 GPUs colocated.
# Usage: gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: ..." -- bash scripts/m0/run_stream_reps.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venvs/taomate-h3/bin/python
D=${CUDA_VISIBLE_DEVICES}
$PY scripts/m0/validate_streaming.py --tag s4_coloc_rep2 --colocate --student-devices "$D"
$PY scripts/m0/validate_streaming.py --tag s4_coloc_rep3 --colocate --student-devices "$D"
$PY scripts/m0/validate_streaming.py --tag s4_coloc_seq --colocate --sequential --student-devices "$D"
