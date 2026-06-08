"""Application exceptions and their HTTP handlers.

All errors render as a consistent envelope:
    {"error": {"code": "...", "message": "...", "details": ...}}
"""
from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("app.errors")


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "error"

    def __init__(self, message: str, *, details: Any | None = None):
        self.message = message
        self.details = details
        super().__init__(message)


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"


class PermissionDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationFailed(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class QuotaExceeded(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "quota_exceeded"


class RateLimitExceeded(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"

    def __init__(self, message: str = "Too many requests", *, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message, details={"retry_after": retry_after})


def _envelope(code: str, message: str, details: Any | None = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        # Client/expected errors: info level, no stack trace.
        logger.info("AppError %s: %s", exc.code, exc.message)
        headers = {}
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error", "Request validation failed", exc.errors()
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Never leak internals; log full stack for ops.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred"),
        )
