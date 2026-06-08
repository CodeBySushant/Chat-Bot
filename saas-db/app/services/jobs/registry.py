"""Task registry: maps task names to async handlers `handler(payload: dict)`."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

TASKS: dict[str, Callable[[dict], Awaitable[None]]] = {}


def task(name: str):
    def deco(fn):
        TASKS[name] = fn
        return fn
    return deco
