#!/usr/bin/env bash
# M0: 3 repetitions of the released TaoMate-H3 path (10 s, 480x864) under one reservation.
# Usage: gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: ..." -- bash scripts/m0/run_baseline_reps.sh <tag-prefix> [n]
set -euo pipefail
cd "$(dirname "$0")/../.."
prefix=${1:-r4_480p}
n=${2:-3}
for i in $(seq 1 "$n"); do
  .venvs/taomate-h3/bin/python scripts/m0/profile_released.py --tag "${prefix}_rep${i}"
done
