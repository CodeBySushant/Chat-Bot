# Deployment Checklist

## Pre-deploy
- [ ] CI green on the commit: lint, mypy, tests, frontend build, security scans.
- [ ] DB migrations reviewed; **forward-only and backwards-compatible** (old code
      runs against new schema) so a rollback needs no down-migration.
- [ ] Image tags immutable (`vX.Y.Z` / `staging-<sha>`); not `latest` in prod.
- [ ] Changelog + on-call notified; deploy window agreed for risky changes.
- [ ] Feature flags default safe; secrets present in target env.

## Deploy (staging → production)
- [ ] Deploy to **staging** (auto on `develop`); run smoke checklist on staging.
- [ ] Tag release `vX.Y.Z` → production workflow (requires approval).
- [ ] `alembic upgrade head` runs once (forward-only).
- [ ] Rolling, **start-first** update (zero downtime); `wait-healthy.sh api 120`.
- [ ] On health failure → automatic rollback to `.deploy-tag.prev`.

## Post-deploy
- [ ] `/readyz` green on all replicas; error rate + p95 latency nominal (Grafana).
- [ ] Smoke: register/login, ask a grounded question (RAG), capture a lead,
      load the widget on a test page, open the admin dashboard.
- [ ] No new ERROR-level logs / dead-letter growth for 15 min.
- [ ] Record deployed tag; close the deploy ticket.
