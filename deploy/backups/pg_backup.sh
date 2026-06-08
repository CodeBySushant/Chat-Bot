#!/usr/bin/env bash
# Daily encrypted PostgreSQL backup -> local + S3, with retention pruning.
# Cron (host): 0 2 * * *  /opt/chatbot-saas/deploy/backups/pg_backup.sh
set -euo pipefail

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${BACKUP_DIR:-/backups}"
FILE="${OUT_DIR}/pg_chatbot_saas_${TS}.dump"
S3_BUCKET="${S3_BUCKET:-s3://acme-db-backups/postgres}"
RETAIN_DAYS="${RETAIN_DAYS:-14}"

mkdir -p "$OUT_DIR"
echo "[$(date -Is)] pg_dump -> $FILE"
docker compose -f /opt/chatbot-saas/compose/docker-compose.yml exec -T postgres \
  pg_dump -U postgres -d chatbot_saas -Fc --no-owner --no-privileges > "$FILE"

# integrity check
docker compose -f /opt/chatbot-saas/compose/docker-compose.yml exec -T postgres \
  pg_restore --list /dev/null < "$FILE" >/dev/null 2>&1 || { echo "Dump verify FAILED"; exit 1; }

# encrypt at rest (age) then ship to S3 with SSE
if command -v age >/dev/null; then age -r "$AGE_RECIPIENT" -o "${FILE}.age" "$FILE" && rm "$FILE" && FILE="${FILE}.age"; fi
aws s3 cp "$FILE" "${S3_BUCKET}/" --sse aws:kms

# prune local + remote older than retention
find "$OUT_DIR" -name 'pg_chatbot_saas_*' -mtime +"$RETAIN_DAYS" -delete
aws s3 ls "${S3_BUCKET}/" | awk '{print $4}' | while read -r f; do
  d=$(echo "$f" | grep -oE '[0-9]{8}'); [ -n "$d" ] && \
  [ "$(date -d "$d" +%s 2>/dev/null || echo 0)" -lt "$(date -d "-${RETAIN_DAYS} days" +%s)" ] && \
  aws s3 rm "${S3_BUCKET}/${f}" || true
done
echo "[$(date -Is)] backup complete: $FILE"
