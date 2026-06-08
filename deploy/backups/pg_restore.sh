#!/usr/bin/env bash
# Restore a PostgreSQL dump. Usage: pg_restore.sh <dump-file> [target-db]
# DESTRUCTIVE: drops & recreates the target schema. Confirm before running.
set -euo pipefail
DUMP="${1:?usage: pg_restore.sh <dump-file> [db]}"
DB="${2:-chatbot_saas}"
COMPOSE="/opt/chatbot-saas/compose/docker-compose.yml"

read -rp "This will OVERWRITE database '$DB'. Type the db name to confirm: " confirm
[ "$confirm" = "$DB" ] || { echo "Aborted."; exit 1; }

[ "${DUMP##*.}" = "age" ] && { age -d -i "$AGE_KEY" -o "${DUMP%.age}" "$DUMP"; DUMP="${DUMP%.age}"; }

echo "Putting API into maintenance (scale to 0)..."
docker compose -f "$COMPOSE" stop api worker

docker compose -f "$COMPOSE" exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS ${DB}_restore;"
docker compose -f "$COMPOSE" exec -T postgres psql -U postgres -c "CREATE DATABASE ${DB}_restore;"
docker compose -f "$COMPOSE" exec -T postgres pg_restore -U postgres -d "${DB}_restore" --no-owner < "$DUMP"

echo "Restored into ${DB}_restore. Verify, then swap:"
echo "  ALTER DATABASE ${DB} RENAME TO ${DB}_old; ALTER DATABASE ${DB}_restore RENAME TO ${DB};"
echo "Then: docker compose -f $COMPOSE up -d api worker"
