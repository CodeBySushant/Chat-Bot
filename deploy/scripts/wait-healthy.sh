#!/usr/bin/env bash
# Block until a compose service reports healthy (used by deploys/rollbacks).
# Usage: wait-healthy.sh <service> <timeout-seconds>
set -euo pipefail
SVC="${1:?service}"; TIMEOUT="${2:-90}"; ELAPSED=0
COMPOSE="${COMPOSE:-compose/docker-compose.yml}"
while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  cid=$(docker compose -f "$COMPOSE" ps -q "$SVC" | head -1)
  [ -z "$cid" ] && { sleep 3; ELAPSED=$((ELAPSED+3)); continue; }
  status=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)
  echo "  $SVC: $status (${ELAPSED}s)"
  [ "$status" = "healthy" ] && exit 0
  sleep 5; ELAPSED=$((ELAPSED+5))
done
echo "Timed out waiting for $SVC to become healthy"; exit 1
