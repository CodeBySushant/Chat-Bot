# Disaster Recovery Runbook

## Objectives
| Metric | Target |
|--------|--------|
| **RPO** (max data loss) | **15 minutes** — Postgres WAL archiving / streaming replica + 6-hourly object sync; nightly base backups |
| **RTO** (max downtime)  | **60 minutes** for full region restore; **5 minutes** for app-tier failover |

Tiering: Postgres is tier-1 (RPO 15m via continuous archiving). Qdrant is tier-2
(daily snapshot; rebuildable from Postgres documents if lost). Object storage is
tier-2 (versioned S3, 6-hourly sync).

## Failover strategy
- **App tier (stateless):** API/worker/frontend are stateless and horizontally
  scaled. Loss of an instance is handled by the load balancer + compose/orchestrator
  restart. Loss of a host → redeploy images on a standby host (`TAG` from `.deploy-tag`).
- **Postgres:** run a streaming replica (or managed RDS Multi-AZ). On primary
  failure, promote the replica and repoint `DATABASE_URL`/`DATABASE_ADMIN_URL`
  secrets, then rolling-restart api+worker.
- **Qdrant:** restore the latest snapshot from S3 (below); meanwhile the RAG layer
  degrades gracefully (empty-retrieval short-circuit returns the fallback answer).
- **Region loss:** restore Postgres from the latest base backup + WAL, restore
  Qdrant snapshot, sync objects, bring the stack up in the DR region, switch DNS.

## Recovery procedures
1. **Declare incident**, page on-call, freeze deploys.
2. **Postgres restore:** `backups/pg_restore.sh <dump> chatbot_saas` (restores to
   `_restore`, verify, then rename-swap). For PITR, replay WAL to the target time.
3. **Qdrant restore:**
   ```
   curl -X PUT "$QDRANT_URL/collections/kb_chunks/snapshots/upload" \
     -H "api-key: $KEY" -F snapshot=@qdrant_<ts>.snapshot
   ```
4. **Objects:** `aws s3 sync s3://acme-object-backups/uploads <uploads-volume>`.
5. **Bring up app:** `docker compose -f compose/docker-compose.yml -f compose/docker-compose.prod.yml up -d`.
6. **Verify:** `/readyz` green on all api replicas; run the smoke checklist
   (login, ask a question, capture a lead, load the widget).
7. **Switch DNS** (if region failover) and lift the deploy freeze.

## Quarterly DR drill
Restore the latest prod backup into an isolated environment, run the smoke
checklist, record actual RTO/RPO, file gaps. Sign-off recorded in the runbook log.
