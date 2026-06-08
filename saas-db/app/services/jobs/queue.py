"""Durable job queue backed by the `jobs` table.

Atomic claim via `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED)` so
multiple workers/instances never double-process. Failed jobs retry with
exponential backoff; once `attempts >= max_attempts` they move to the `dead`
status (dead-letter) for inspection.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.db.session import AdminSessionFactory


@dataclass
class ClaimedJob:
    id: uuid.UUID
    task: str
    payload: dict
    attempts: int
    max_attempts: int


def _backoff_seconds(attempts: int) -> int:
    return min(3600, 2 ** attempts)  # 2,4,8,... capped at 1h


async def enqueue(
    task: str, payload: dict | None = None, *, queue: str = "default",
    max_attempts: int = 5, delay_seconds: int = 0, dedupe_key: str | None = None,
) -> uuid.UUID | None:
    run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    async with AdminSessionFactory() as db:
        row = (await db.execute(text(
            "INSERT INTO jobs (queue, task, payload, max_attempts, run_at, dedupe_key) "
            "VALUES (:q, :t, CAST(:p AS jsonb), :m, :r, :d) "
            "ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('pending','running') "
            "DO NOTHING RETURNING id"
        ), {"q": queue, "t": task, "p": _json(payload or {}), "m": max_attempts,
            "r": run_at, "d": dedupe_key})).first()
        await db.commit()
        return row[0] if row else None


async def claim_one(worker_id: str) -> ClaimedJob | None:
    async with AdminSessionFactory() as db:
        row = (await db.execute(text(
            "UPDATE jobs SET status='running', attempts=attempts+1, locked_at=now(), "
            "locked_by=:w, updated_at=now() "
            "WHERE id = (SELECT id FROM jobs WHERE status='pending' AND run_at <= now() "
            "           ORDER BY run_at FOR UPDATE SKIP LOCKED LIMIT 1) "
            "RETURNING id, task, payload, attempts, max_attempts"
        ), {"w": worker_id})).first()
        await db.commit()
        if row is None:
            return None
        return ClaimedJob(id=row[0], task=row[1], payload=row[2], attempts=row[3], max_attempts=row[4])


async def complete(job_id: uuid.UUID) -> None:
    async with AdminSessionFactory() as db:
        await db.execute(text(
            "UPDATE jobs SET status='succeeded', locked_at=NULL, updated_at=now() WHERE id=:i"
        ), {"i": str(job_id)})
        await db.commit()


async def fail(job: ClaimedJob, error: str) -> str:
    """Retry with backoff, or move to dead-letter once attempts are exhausted."""
    dead = job.attempts >= job.max_attempts
    async with AdminSessionFactory() as db:
        if dead:
            await db.execute(text(
                "UPDATE jobs SET status='dead', last_error=:e, locked_at=NULL, updated_at=now() WHERE id=:i"
            ), {"e": error[:2000], "i": str(job.id)})
        else:
            run_at = datetime.now(timezone.utc) + timedelta(seconds=_backoff_seconds(job.attempts))
            await db.execute(text(
                "UPDATE jobs SET status='pending', last_error=:e, run_at=:r, locked_at=NULL, updated_at=now() WHERE id=:i"
            ), {"e": error[:2000], "r": run_at, "i": str(job.id)})
        await db.commit()
    return "dead" if dead else "retry"


def _json(d: dict) -> str:
    import json
    return json.dumps(d)
