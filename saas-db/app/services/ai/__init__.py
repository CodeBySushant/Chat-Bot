"""Unified AI provider layer.

Usage::

    from app.services.ai import get_chat_provider, ChatMessage

    provider = get_chat_provider()              # honors AI_PROVIDER
    result = await provider.complete([ChatMessage("user", "Hello")])
    async for delta in provider.stream([ChatMessage("user", "Hi")]):
        ...
"""
from app.services.ai.base import (
    ChatMessage,
    ChatProvider,
    CompletionResult,
    Usage,
    to_wire_messages,
)
from app.services.ai.errors import (
    AIAuthError,
    AIConfigError,
    AIConnectionError,
    AIProviderError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
)
from app.services.ai.factory import (
    available_providers,
    close_providers,
    get_chat_provider,
    register_provider,
    reset,
)

__all__ = [
    "ChatMessage",
    "ChatProvider",
    "CompletionResult",
    "Usage",
    "to_wire_messages",
    "AIProviderError",
    "AIConfigError",
    "AIAuthError",
    "AIRateLimitError",
    "AITimeoutError",
    "AIConnectionError",
    "AIResponseError",
    "get_chat_provider",
    "available_providers",
    "register_provider",
    "close_providers",
    "reset",
]
