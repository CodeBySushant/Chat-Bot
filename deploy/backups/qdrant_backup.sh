#!/usr/bin/env bash
# Daily Qdrant snapshot of every collection -> S3.
# Cron: 0 2 * * *  /opt/chatbot-saas/deploy/backups/qdrant_backup.sh
set -euo pipefail
QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"
API_KEY="${QDRANT_API_KEY:?set QDRANT_API_KEY}"
S3_BUCKET="${S3_BUCKET:-s3://acme-db-backups/qdrant}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Full storage snapshot (all collections)
SNAP=$(curl -sf -X POST "$QDRANT_URL/snapshots" -H "api-key: $API_KEY" | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['name'])")
echo "Created snapshot $SNAP"
curl -sf "$QDRANT_URL/snapshots/$SNAP" -H "api-key: $API_KEY" -o "/tmp/qdrant_${TS}.snapshot"
aws s3 cp "/tmp/qdrant_${TS}.snapshot" "${S3_BUCKET}/" --sse aws:kms
# keep only the 14 most recent remote snapshots
aws s3 ls "${S3_BUCKET}/" | sort | head -n -14 | awk '{print $4}' | xargs -r -I{} aws s3 rm "${S3_BUCKET}/{}"
rm -f "/tmp/qdrant_${TS}.snapshot"
echo "Qdrant backup complete"
