"""In-process fixed-window rate limiter.

Keyed by (bucket, client-ip). Suitable for a single worker / tests; for
multi-worker production replace the backing store with Redis (same interface).
"""
from __future__ import annotations

import asyncio
import time

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded

# bucket -> settings attribute holding the per-window max
_BUCKET_LIMITS = {
    "login": "RATE_LIMIT_LOGIN_MAX",
    "register": "RATE_LIMIT_REGISTER_MAX",
    "refresh": "RATE_LIMIT_REFRESH_MAX",
    "password_reset": "RATE_LIMIT_PASSWORD_RESET_MAX",
}


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        # key -> (window_start_epoch, count)
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def check(self, bucket: str, key: str, *, limit: int, window: int) -> None:
        now = time.monotonic()
        async with self._lock:
            window_start, count = self._hits.get(f"{bucket}:{key}", (now, 0))
            if now - window_start >= window:
                window_start, count = now, 0
            count += 1
            self._hits[f"{bucket}:{key}"] = (window_start, count)
            if count > limit:
                retry_after = max(1, int(window - (now - window_start)))
                raise RateLimitExceeded(
                    "Too many requests, slow down", retry_after=retry_after
                )

    def reset(self) -> None:
        self._hits.clear()


limiter = FixedWindowRateLimiter()


def _client_key(request: Request) -> str:
    # Honor a single proxy hop if present; fall back to socket peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str):
    """Dependency factory enforcing the configured limit for a bucket."""

    async def _dep(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        limit = getattr(settings, _BUCKET_LIMITS[bucket])
        await limiter.check(
            bucket,
            _client_key(request),
            limit=limit,
            window=settings.RATE_LIMIT_WINDOW_SECONDS,
        )

    return _dep
