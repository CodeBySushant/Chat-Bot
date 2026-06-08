#!/usr/bin/env bash
# Mirror the uploads/object-storage volume to S3 with versioning (point-in-time).
# Cron: 0 */6 * * *  /opt/chatbot-saas/deploy/backups/s3_sync.sh
set -euo pipefail
SRC="${UPLOADS_DIR:-/var/lib/docker/volumes/chatbot-saas_uploads/_data}"
DEST="${S3_UPLOADS:-s3://acme-object-backups/uploads}"
aws s3 sync "$SRC" "$DEST" --sse aws:kms --delete --only-show-errors
echo "$(date -Is) uploads synced to $DEST"
