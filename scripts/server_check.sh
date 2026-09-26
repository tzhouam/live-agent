#!/usr/bin/env bash
# Server-path check with TaoMate-H3: start the server (generator started once), run the headless client.
# Run under canhazgpu, e.g.:
#   gpu run --gpu-ids 0,1,2,3,4,5 --timeout 1h --note "live-agent server-path check" -- scripts/server_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
python3 -m live_agent.server.app --generator taomate_h3 --dev-allow-uncalibrated --port 8200 \
  --log-dir .cache/server_check > .cache/logs/server_check_server.log 2>&1 &
srv=$!
trap 'kill $srv 2>/dev/null; wait $srv 2>/dev/null || true' EXIT
for i in $(seq 1 600); do
  curl -sf http://127.0.0.1:8200/ >/dev/null 2>&1 && break
  kill -0 $srv 2>/dev/null || { echo "server died"; tail -30 .cache/logs/server_check_server.log; exit 1; }
  sleep 1
done
python3 scripts/ws_client_check.py --seconds 80 --say "8:请喝口茶吧" --say "30:跟我挥挥手吧" --say "50:我妹妹住在杭州" --say "62:请忘掉我妹妹住在哪"
