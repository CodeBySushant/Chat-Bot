# Backup Verification Checklist

Run **monthly** (and after any backup config change). A backup is only real once
a restore has been proven.

## Postgres
- [ ] Latest nightly dump exists in S3 and locally; size within ±20% of trend.
- [ ] `pg_restore --list` on the dump succeeds (not truncated/corrupt).
- [ ] **Test restore** into an isolated DB: `pg_restore.sh <dump> chatbot_saas`
      → row counts on `companies`, `users`, `leads`, `messages` match prod ±.
- [ ] Decryption (age/KMS) works with the current recovery key.
- [ ] WAL archiving continuous (no gaps); PITR to an arbitrary timestamp tested.

## Qdrant
- [ ] Daily snapshot present in S3; restore into a scratch Qdrant succeeds.
- [ ] Collection `kb_chunks` point count matches `embeddings` row count in Postgres.
- [ ] A sample similarity query returns expected neighbours post-restore.

## Object storage (uploads)
- [ ] S3 versioning enabled; 6-hourly sync ran; a random uploaded file restores
      byte-identical (checksum match).

## Retention & alerting
- [ ] Retention enforced: pg 14d local / 30d+ remote, qdrant 14 snapshots, objects versioned.
- [ ] Backup-failure alert fires (simulate a failed run) and pages on-call.
- [ ] Recovery keys stored in the secrets manager + offline escrow; access tested.

Sign-off: ___________  Date: ___________  Actual restore time: ______
