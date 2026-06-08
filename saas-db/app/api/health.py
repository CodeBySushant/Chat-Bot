"""Liveness, readiness, and startup probes.

- /healthz  liveness: process is up (no dependency checks; never blocks).
- /readyz   readiness: DB + Qdrant (+ Redis if configured) reachable.
- /startupz startup: same as readiness, used as a startup probe before traffic.

Readiness failures return 503 so orchestrators stop routing traffic without
killing the pod.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import engine

router = APIRouter(tags=["system"])
logger = get_logger("app.health")


async def _check_db() -> tuple[bool, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, repr(exc)


async def _check_qdrant() -> tuple[bool, str]:
    # Embedded local mode is always "ready"; only probe a remote server.
    if not settings.QDRANT_URL:
        return True, "embedded"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as c:
            headers = {"api-key": settings.QDRANT_API_KEY} if settings.QDRANT_API_KEY else {}
            r = await c.get(f"{settings.QDRANT_URL}/readyz", headers=headers)
            return (r.status_code == 200), f"http {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, repr(exc)


async def _check_redis() -> tuple[bool, str]:
    if not settings.REDIS_URL:
        return True, "not-configured"
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        try:
            await client.ping()
            return True, "ok"
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        return False, repr(exc)


@router.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok", "service": settings.PROJECT_NAME, "env": settings.ENVIRONMENT}


async def _readiness() -> tuple[bool, dict]:
    db, qd, rd = await asyncio.gather(_check_db(), _check_qdrant(), _check_redis())
    checks = {
        "database": {"ok": db[0], "detail": db[1]},
        "qdrant": {"ok": qd[0], "detail": qd[1]},
        "redis": {"ok": rd[0], "detail": rd[1]},
    }
    return all(c["ok"] for c in checks.values()), checks


@router.get("/readyz", include_in_schema=False)
async def readyz(response: Response):
    ok, checks = await _readiness()
    response.status_code = 200 if ok else 503
    return {"status": "ready" if ok else "not_ready", "checks": checks}


@router.get("/startupz", include_in_schema=False)
async def startupz(response: Response):
    ok, checks = await _readiness()
    response.status_code = 200 if ok else 503
    return {"status": "started" if ok else "starting", "checks": checks}
