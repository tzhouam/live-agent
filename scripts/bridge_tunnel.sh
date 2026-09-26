#!/usr/bin/env bash
# Keep an ssh reverse tunnel from this GPU host to the jump host open (restarts on failure):
# jump:127.0.0.1:$REMOTE_PORT -> this host:127.0.0.1:$LOCAL_PORT (the web demo). Binds only to the
# jump host's loopback; the token proxy there (scripts/bridge_proxy.py) is the public entry point.
#   JUMP=Personal-Agent LOCAL_PORT=8200 REMOTE_PORT=18200 scripts/bridge_tunnel.sh
JUMP=${JUMP:-Personal-Agent}; LOCAL_PORT=${LOCAL_PORT:-8200}; REMOTE_PORT=${REMOTE_PORT:-18200}
while true; do
  ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=3 \
      -R "127.0.0.1:${REMOTE_PORT}:127.0.0.1:${LOCAL_PORT}" "$JUMP"
  echo "[bridge_tunnel] ssh exited ($?); reconnecting in 5 s" >&2
  sleep 5
done
