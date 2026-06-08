#!/usr/bin/env bash
# Bootstrap Let's Encrypt certificates for all domains, then switch nginx to them.
# Idempotent: skips domains that already have a live cert. Run once on a new host.
set -euo pipefail

DOMAINS=("api.example.com" "app.example.com" "cdn.example.com")
EMAIL="ops@example.com"
STAGING="${STAGING:-0}"   # set STAGING=1 to use LE staging while testing
COMPOSE="docker compose -f compose/docker-compose.yml"
LE_PATH="/etc/letsencrypt"

echo "### Starting nginx (HTTP only) to serve ACME challenges..."
$COMPOSE up -d nginx

staging_arg=""
[ "$STAGING" != "0" ] && staging_arg="--staging"

for domain in "${DOMAINS[@]}"; do
  if $COMPOSE run --rm --entrypoint "test -d $LE_PATH/live/$domain" certbot; then
    echo "### Cert for $domain already exists, skipping."
    continue
  fi
  echo "### Requesting certificate for $domain..."
  $COMPOSE run --rm --entrypoint "\
    certbot certonly --webroot -w /var/www/certbot \
      $staging_arg --email $EMAIL --agree-tos --no-eff-email \
      --rsa-key-size 4096 -d $domain --non-interactive" certbot
done

echo "### Reloading nginx with certificates..."
$COMPOSE exec nginx nginx -s reload
echo "### Done. Certs renew automatically via the certbot sidecar (every 12h)."
