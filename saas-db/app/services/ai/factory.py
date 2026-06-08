"""Factory + registry for chat providers.

Selection is driven entirely by ``settings.AI_PROVIDER``; switching providers is
an environment-variable change with no code edits. New ("future") providers are
added by implementing ``ChatProvider`` and calling ``register_provider``.
"""
from __future__ import annotations

from collections.abc import Callable

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import ChatProvider
from app.services.ai.errors import AIConfigError
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.openai_provider import OpenAIProvider

logger = get_logger("app.ai.factory")

# name -> builder. Builders read settings lazily so config/env is authoritative.
_REGISTRY: dict[str, Callable[[], ChatProvider]] = {}
_instances: dict[str, ChatProvider] = {}


def register_provider(name: str, builder: Callable[[], ChatProvider]) -> None:
    _REGISTRY[name.lower()] = builder


def _build_openai() -> ChatProvider:
    if not settings.OPENAI_API_KEY:
        raise AIConfigError(
            "AI_PROVIDER=openai requires OPENAI_API_KEY", provider="openai"
        )
    return OpenAIProvider(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        model=settings.OPENAI_CHAT_MODEL,
        timeout=settings.AI_REQUEST_TIMEOUT,
        default_temperature=settings.AI_DEFAULT_TEMPERATURE,
        default_max_tokens=settings.AI_DEFAULT_MAX_TOKENS,
    )


def _build_ollama() -> ChatProvider:
    return OllamaProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.AI_REQUEST_TIMEOUT,
        default_temperature=settings.AI_DEFAULT_TEMPERATURE,
        default_max_tokens=settings.AI_DEFAULT_MAX_TOKENS,
    )


register_provider("openai", _build_openai)
register_provider("ollama", _build_ollama)


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def get_chat_provider(name: str | None = None) -> ChatProvider:
    """Return a cached provider instance for ``name`` (default: settings)."""
    name = (name or settings.AI_PROVIDER).lower()
    if name not in _REGISTRY:
        raise AIConfigError(
            f"Unknown AI provider '{name}'. Available: {available_providers()}"
        )
    if name not in _instances:
        _instances[name] = _REGISTRY[name]()
        logger.info("Initialized AI provider '%s'", name)
    return _instances[name]


async def close_providers() -> None:
    for provider in _instances.values():
        try:
            await provider.aclose()
        except Exception:  # pragma: no cover
            logger.exception("Error closing provider %s", provider.name)
    _instances.clear()


def reset() -> None:
    """Drop cached instances (used by tests after changing config)."""
    _instances.clear()
