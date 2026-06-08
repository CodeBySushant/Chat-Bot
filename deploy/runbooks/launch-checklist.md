# Production Launch Checklist

## Infrastructure
- [ ] DNS for `api`, `app`, `cdn` → load balancer; TTL lowered for cutover.
- [ ] TLS certs issued (`init-letsencrypt.sh`); auto-renew sidecar running; HSTS preload submitted.
- [ ] Compose prod overrides applied (resource limits, replicas, hardening).
- [ ] CDN/WAF in front (DDoS, bot rules, geo); origin locked to CDN IPs.

## Data & migrations
- [ ] `alembic upgrade head` == `0006_seed_platform` (+ any obs migrations).
- [ ] RLS verified: `FORCE ROW LEVEL SECURITY` on all tenant tables; cross-tenant
      read test fails as expected.
- [ ] Seed data present (plans, system roles, permissions).

## Security
- [ ] Security-hardening checklist signed off.
- [ ] Secrets in Secrets Manager/Vault; none in env/images; rotation scheduled.
- [ ] Admin (`is_superuser`) accounts limited + MFA on the IdP.

## Observability
- [ ] Prometheus scraping api/worker/pg/redis/qdrant/node; alerts firing to pager.
- [ ] Grafana dashboards loaded (API Overview, Workers & Queue).
- [ ] Logs flowing to Loki/ELK with `request_id`; error tracking (Sentry DSN) set.
- [ ] Tracing to OTEL collector verified end-to-end.

## Resilience
- [ ] Backups running (pg nightly + WAL, qdrant daily, objects 6-hourly) and a
      **test restore** completed (backup-verification checklist).
- [ ] DR drill scheduled; RPO/RTO documented.
- [ ] Autoscaling policies (API HPA, worker on queue depth) configured.

## Business
- [ ] Stripe/billing in live mode; webhook endpoint verified; plans match seeds.
- [ ] Rate limits tuned for expected traffic; load test passed at target RPS.
