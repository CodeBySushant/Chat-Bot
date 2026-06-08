#!/usr/bin/env bash
# Rotate JWT signing key (dual-key overlap) and/or DB password, then rolling-restart.
# Usage: rotate-secrets.sh jwt | db
set -euo pipefail
COMPOSE="/opt/chatbot-saas/compose/docker-compose.yml"
SECRETS_DIR="/opt/chatbot-saas/compose/secrets"

rotate_jwt() {
  # Generate a new key; keep the previous one for the max access-token lifetime so
  # in-flight tokens still verify. The app should accept JWT_SECRET_KEY + JWT_SECRET_KEY_PREV.
  cp "$SECRETS_DIR/jwt_secret_key" "$SECRETS_DIR/jwt_secret_key.prev"
  openssl rand -base64 48 > "$SECRETS_DIR/jwt_secret_key"
  echo "New JWT key written; previous retained as .prev (retire after token TTL)."
}
rotate_db() {
  NEW=$(openssl rand -base64 32 | tr -d '/+=')
  docker compose -f "$COMPOSE" exec -T postgres psql -U postgres -c "ALTER ROLE app_rw PASSWORD '$NEW';"
  printf 'postgresql+asyncpg://app_rw:%s@postgres:5432/chatbot_saas' "$NEW" > "$SECRETS_DIR/database_url"
  echo "DB password rotated."
}
case "${1:?usage: rotate-secrets.sh jwt|db}" in
  jwt) rotate_jwt ;;
  db)  rotate_db ;;
  *) echo "unknown: $1"; exit 1 ;;
esac
docker compose -f "$COMPOSE" -f /opt/chatbot-saas/compose/docker-compose.prod.yml up -d --no-deps api worker
echo "Rolling restart triggered."
