# Scalability

## API (stateless) — horizontal
- Run N replicas behind nginx (`upstream` with DNS SD picks up new replicas).
  `docker compose up -d --scale api=6` or set `deploy.replicas`. On K8s use an HPA
  on CPU + `http_requests_in_progress`.
- Gunicorn runs 4 uvicorn workers/replica; size workers ≈ 2×vCPU.
- **Move the rate limiter to Redis** before scaling API >1 (the in-process limiter
  is per-instance). A Redis token-bucket makes limits global.

## Workers — autoscale on queue depth
- The job queue is DB-backed with `FOR UPDATE SKIP LOCKED`, so workers scale
  horizontally with zero coordination. Scale on `job_queue_depth{status="pending"}`
  (KEDA `postgresql` scaler on K8s, or a simple controller reading the gauge).
- Tune `JOB_WORKERS` per replica for in-process concurrency.

## Queue scaling
- DB queue is fine to thousands/min. Beyond that, partition by `queue` column and
  run dedicated worker fleets, or migrate hot queues to Redis Streams / SQS while
  keeping the same `enqueue/claim/complete/fail` interface.

## Database
- Vertical first (CPU/RAM, `shared_buffers`, `work_mem`). Then **read replicas**
  for analytics/dashboard reads (route read-only queries to a replica DSN).
- PgBouncer (transaction pooling) in front of Postgres to absorb many API replicas.
- Partitioning already in place for `messages`/`analytics_events`/`activity_logs`;
  add monthly partitions ahead of time (a `cleanup`/maintenance job can pre-create).

## Qdrant
- Run as a cluster with sharding + replication; the single-collection +
  per-tenant payload filter design shards cleanly. Scale replicas for read QPS,
  shards for vector count. Use quantization for large collections.

## Caching
- nginx caches the widget bundle (immutable, long TTL).
- Add Redis caching for hot read paths (widget config, plan/entitlements lookups).
