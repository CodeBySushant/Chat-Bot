"""Base interface and shared types for chat/LLM providers.

A provider supports two operations over a list of chat messages:
  * ``complete`` — return the full assistant message (non-streaming).
  * ``stream``   — async-iterate text deltas as they arrive.

Both accept the same call signature so switching providers needs no caller
changes. Messages may be passed as ``ChatMessage`` objects or plain dicts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

Message = "ChatMessage | dict"


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class CompletionResult:
    text: str
    model: str
    finish_reason: str | None = None
    usage: Usage | None = None


def to_wire_messages(messages: Sequence) -> list[dict]:
    """Normalize ChatMessage|dict|tuple into provider wire dicts."""
    out: list[dict] = []
    for m in messages:
        if isinstance(m, ChatMessage):
            out.append({"role": m.role, "content": m.content})
        elif isinstance(m, dict):
            out.append({"role": m["role"], "content": m["content"]})
        elif isinstance(m, (tuple, list)) and len(m) == 2:
            out.append({"role": m[0], "content": m[1]})
        else:
            raise TypeError(f"Unsupported message type: {type(m)!r}")
    return out


class ChatProvider(ABC):
    """Common interface every chat provider implements."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    async def complete(
        self,
        messages: Sequence,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> CompletionResult:
        ...

    @abstractmethod
    def stream(
        self,
        messages: Sequence,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Return an async iterator of text deltas."""
        ...

    async def aclose(self) -> None:  # pragma: no cover - overridden as needed
        return None
