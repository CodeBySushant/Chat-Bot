# Production Infrastructure — Chatbot SaaS

Complete deployment layer for the multi-tenant chatbot platform (API, workers,
Postgres, Redis, Qdrant, dashboard, widget) behind Nginx + TLS, with CI/CD,
monitoring, logging, tracing, backups, DR, and operational runbooks.

> **Validation note.** Docker/Nginx are not available in the authoring sandbox, so
> infra files were validated by **syntax** (YAML via PyYAML, JSON via json, shell
> via `bash -n`) and the **application-layer** observability code (health/readiness,
> Prometheus `/metrics`, JSON logging, `_FILE` secrets, graceful shutdown) was
> **import- and live-tested** against a running server. Run `docker compose config`
> and `nginx -t` in your environment as the final gate before first deploy.

## Layout
```
deploy/
  docker/        Dockerfile.backend|worker|frontend|widget, .dockerignore, widget-nginx.conf
  compose/       docker-compose.yml (+ .prod.yml overrides, .monitoring.yml), .env.example
  nginx/         nginx.conf + conf.d/{api,security-headers,tls}.conf
  tls/           init-letsencrypt.sh, renew.sh  (Let's Encrypt automation)
  .github/workflows/  ci.yml, deploy-staging.yml, deploy-production.yml
  secrets/       secrets-strategy.md, rotate-secrets.sh
  monitoring/    prometheus/, grafana/, loki/, promtail/, otel/
  backups/       pg_backup.sh, pg_restore.sh, qdrant_backup.sh, s3_sync.sh
  postgres/init/ 00-roles.sql  (RLS app_rw + BYPASSRLS app_admin)
  scripts/       wait-healthy.sh
  runbooks/      disaster-recovery, security-hardening, scalability,
                 deployment/launch/security/backup-verification checklists
```

## Quick start
```bash
# 1. secrets (never commit these)
mkdir -p compose/secrets
openssl rand -base64 48 > compose/secrets/jwt_secret_key
echo -n 'strong-pg-pw'   > compose/secrets/postgres_password
printf 'postgresql+asyncpg://app_rw:strong-pg-pw@postgres:5432/chatbot_saas'   > compose/secrets/database_url
printf 'postgresql+asyncpg://app_admin:strong-pg-pw@postgres:5432/chatbot_saas' > compose/secrets/database_admin_url
cp compose/.env.example compose/.env     # edit non-secret config

# 2. bring up the core stack
docker compose -f compose/docker-compose.yml -f compose/docker-compose.prod.yml up -d

# 3. migrate + TLS
docker compose -f compose/docker-compose.yml run --rm api alembic upgrade head
./tls/init-letsencrypt.sh

# 4. observability
docker compose -f compose/docker-compose.monitoring.yml up -d
```

## Application-layer hooks (in `saas-db/`)
- `app/api/health.py` — `/healthz`, `/readyz` (DB+Qdrant+Redis), `/startupz`.
- `app/core/metrics.py` — Prometheus middleware + `/metrics` + AI/worker/queue instruments.
- `app/core/logging.py` — JSON formatter with `request_id` correlation.
- `app/core/tracing.py` — optional OpenTelemetry (env-gated, lazy imports).
- `app/core/config.py` — `_FILE` secret expansion for Docker/Vault/Secrets Manager.
- `app/worker_main.py` — dedicated worker entrypoint with SIGTERM graceful shutdown.

See each runbook for operational detail; checklists gate every launch.
