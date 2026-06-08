"""OpenAI-compatible chat provider (also works against any OpenAI-style API)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from app.core.logging import get_logger
from app.services.ai.base import (
    ChatProvider,
    CompletionResult,
    Usage,
    to_wire_messages,
)
from app.services.ai.errors import (
    AIAuthError,
    AIConnectionError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
)

logger = get_logger("app.ai.openai")


class OpenAIProvider(ChatProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        default_temperature: float,
        default_max_tokens: int,
    ):
        self.model = model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )

    def _payload(self, messages, model, temperature, max_tokens, stream) -> dict:
        return {
            "model": model or self.model,
            "messages": to_wire_messages(messages),
            "temperature": self._default_temperature if temperature is None else temperature,
            "max_tokens": self._default_max_tokens if max_tokens is None else max_tokens,
            "stream": stream,
        }

    def _raise_for_status(self, status: int, body: str) -> None:
        if status < 400:
            return
        msg = f"OpenAI provider HTTP {status}: {body[:300]}"
        if status in (401, 403):
            raise AIAuthError(msg, provider=self.name, status=status)
        if status == 429:
            raise AIRateLimitError(msg, provider=self.name, status=status)
        raise AIResponseError(msg, provider=self.name, status=status)

    async def complete(
        self, messages: Sequence, *, model=None, temperature=None, max_tokens=None, **kwargs
    ) -> CompletionResult:
        payload = self._payload(messages, model, temperature, max_tokens, stream=False)
        try:
            resp = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(str(exc), provider=self.name) from exc
        except httpx.TransportError as exc:
            raise AIConnectionError(str(exc), provider=self.name) from exc

        self._raise_for_status(resp.status_code, resp.text)
        try:
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            usage = data.get("usage") or {}
            return CompletionResult(
                text=text,
                model=data.get("model", payload["model"]),
                finish_reason=choice.get("finish_reason"),
                usage=Usage(
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise AIResponseError(
                f"Malformed OpenAI response: {exc}", provider=self.name
            ) from exc

    async def stream(
        self, messages: Sequence, *, model=None, temperature=None, max_tokens=None, **kwargs
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, model, temperature, max_tokens, stream=True)
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=payload
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    self._raise_for_status(resp.status_code, body)
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[len("data:"):].strip()
                    if line == "[DONE]":
                        break
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        obj.get("choices", [{}])[0].get("delta", {}).get("content")
                    )
                    if delta:
                        yield delta
        except httpx.TimeoutException as exc:
            raise AITimeoutError(str(exc), provider=self.name) from exc
        except httpx.TransportError as exc:
            raise AIConnectionError(str(exc), provider=self.name) from exc

    async def aclose(self) -> None:
        await self._client.aclose()
