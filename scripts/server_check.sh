#!/usr/bin/env bash
# Backend-path check with TaoMate-H3: start the API (generator started once), run the headless client.
# Run under canhazgpu, e.g.:
#   gpu run --gpu-ids 0,1,2,3,4,5 --timeout 1h --note "live-agent server-path check" -- scripts/server_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
BACKEND_PORT=${BACKEND_PORT:-8201}
mkdir -p .cache/logs .cache/server_check
python3 -m live_agent.backend.app --generator taomate_h3 --dev-allow-uncalibrated --host 127.0.0.1 --port "$BACKEND_PORT" \
  --log-dir .cache/server_check > .cache/logs/server_check_server.log 2>&1 &
srv=$!
trap 'kill $srv 2>/dev/null; wait $srv 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
ready=0
for i in $(seq 1 600); do
  if curl --noproxy '*' --connect-timeout 1 --max-time 2 -sf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then ready=1; break; fi
  kill -0 $srv 2>/dev/null || { echo "server died"; tail -30 .cache/logs/server_check_server.log; exit 1; }
  sleep 1
done
[ "$ready" = "1" ] || { echo "backend not ready after readiness timeout"; tail -30 .cache/logs/server_check_server.log; exit 1; }
python3 scripts/ws_client_check.py --url "ws://127.0.0.1:$BACKEND_PORT/ws" --seconds 80 --say "8:请喝口茶吧" --say "30:跟我挥挥手吧" --say "50:我妹妹住在杭州" --say "62:请忘掉我妹妹住在哪"
