"""Request-scoped middleware: correlation id + access logging.

Tenant scoping itself is applied per-transaction in the DB dependency
(``get_tenant_context`` issues ``SET LOCAL app.current_company``); this
middleware handles cross-cutting request concerns (correlation id, timing).
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, request_id_ctx

logger = get_logger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            request_id_ctx.reset(token)
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers["X-Request-ID"] = rid
        return response
