"""Error hierarchy for the AI provider layer.

Providers translate transport/HTTP failures into this common taxonomy so callers
handle errors identically regardless of which backend is configured.
"""
from __future__ import annotations


class AIProviderError(Exception):
    """Base class for all AI provider failures."""

    def __init__(self, message: str, *, provider: str | None = None, status: int | None = None):
        self.provider = provider
        self.status = status
        super().__init__(message)


class AIConfigError(AIProviderError):
    """Misconfiguration (unknown provider, missing API key, etc.)."""


class AIAuthError(AIProviderError):
    """Authentication/authorization failure (HTTP 401/403)."""


class AIRateLimitError(AIProviderError):
    """Rate limited / quota exceeded (HTTP 429)."""


class AITimeoutError(AIProviderError):
    """Request timed out."""


class AIConnectionError(AIProviderError):
    """Could not connect to the provider."""


class AIResponseError(AIProviderError):
    """Provider returned an error status or an unparseable response."""
