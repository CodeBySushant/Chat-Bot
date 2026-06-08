# Chatbot SaaS — Multi-Tenant AI Customer Support Platform

A production-grade, multi-tenant SaaS for building RAG-powered chatbots: knowledge
base ingestion + web crawling, retrieval-augmented generation across pluggable AI
providers, an embeddable widget, lead capture, analytics, subscription billing, a
super-admin platform, and a full production deployment layer.

## Repository layout

```
chatbot-saas/
  saas-db/      FastAPI backend (SQLAlchemy 2.0 async, Alembic, PostgreSQL + RLS, Qdrant)
  dashboard/    Next.js 15 dashboard / admin UI (App Router, Tailwind, shadcn/ui)
  widget/       Embeddable chat widget (TypeScript, Shadow DOM, esbuild — zero deps)
  deploy/       Production infra: Docker, Compose, Nginx, TLS, CI/CD, monitoring, backups, runbooks
```

## Architecture

- **Tenancy:** PostgreSQL Row-Level Security (`FORCE RLS` + `tenant_isolation`
  policy) keyed on a per-request `app.current_company` GUC. Two DB roles —
  `app_rw` (RLS-bound) and `app_admin` (BYPASSRLS, admin/worker only).
- **Backend:** layered `router → service → repository → model`; auth + RBAC,
  knowledge base, crawler, RAG, AI providers, widget API, leads, analytics,
  billing, admin, and a durable DB-backed job queue (`FOR UPDATE SKIP LOCKED`).
- **Observability:** `/healthz` `/readyz` `/startupz`, Prometheus `/metrics`,
  JSON logs with request-id correlation, optional OpenTelemetry tracing.

## Quick start (local, Docker)

```bash
cd deploy
mkdir -p compose/secrets
openssl rand -base64 48 > compose/secrets/jwt_secret_key
echo -n 'pg-pass' > compose/secrets/postgres_password
printf 'postgresql+asyncpg://app_rw:pg-pass@postgres:5432/chatbot_saas'    > compose/secrets/database_url
printf 'postgresql+asyncpg://app_admin:pg-pass@postgres:5432/chatbot_saas' > compose/secrets/database_admin_url
cp compose/.env.example compose/.env

docker compose -f compose/docker-compose.yml up -d
docker compose -f compose/docker-compose.yml run --rm api alembic upgrade head
# API:  http://localhost (via nginx)   Dashboard: app.example.com  Widget: cdn.example.com
```

## Quick start (backend, no Docker)

```bash
cd saas-db
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # set DATABASE_URL / DATABASE_ADMIN_URL / JWT_SECRET_KEY
# provision roles + schema
psql "$ADMIN_DSN" -f ../deploy/postgres/init/00-roles.sql
alembic upgrade head
uvicorn app.main:app --reload             # http://127.0.0.1:8000  (/docs, /healthz, /readyz, /metrics)
```

Run the worker (separate process):

```bash
python -m app.worker_main
```

## Dashboard

```bash
cd dashboard
npm install
npm run dev            # http://localhost:3000   (set NEXT_PUBLIC_API_BASE)
```

## Widget

```bash
cd widget
npm install
npm run build          # -> dist/widget.js
```

Embed on any site:

```html
<script src="https://cdn.example.com/widget.js" data-key="pk_xxx" data-api="https://api.example.com"></script>
```

## Tests

```bash
cd saas-db
pytest -q              # auth, RBAC, security, KB, crawl, RAG, AI, widget, platform e2e
```

## Migrations

```bash
cd saas-db
alembic upgrade head   # head = 0006_seed_platform
alembic downgrade -1
```

## Deployment

See `deploy/README.md` and `deploy/runbooks/` (deployment, launch, security, and
backup-verification checklists; disaster-recovery, security-hardening, scalability).

## License

Proprietary — © Acme. All rights reserved.
