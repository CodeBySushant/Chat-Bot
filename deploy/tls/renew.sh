#!/usr/bin/env bash
# Manual renewal hook (the certbot sidecar already auto-renews). Add a host cron
# as a belt-and-braces fallback:
#   0 3 * * * /opt/chatbot-saas/deploy/tls/renew.sh >> /var/log/certbot-renew.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f compose/docker-compose.yml run --rm certbot renew --webroot -w /var/www/certbot --quiet
docker compose -f compose/docker-compose.yml exec nginx nginx -s reload
echo "$(date -Is) renew + reload complete"
