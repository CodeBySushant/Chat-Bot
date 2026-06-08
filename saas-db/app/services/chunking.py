"""Chunking strategy.

Recursive, separator-aware splitter: it tries to break on the most semantic
boundary that keeps pieces under the target size (paragraph -> line ->
sentence -> word), then packs pieces into ~``size`` windows with ``overlap``
characters carried between consecutive chunks for context continuity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass
class Chunk:
    index: int
    text: str
    char_count: int
    token_count: int
    page_number: int | None = None


def _approx_tokens(text: str) -> int:
    # Cheap, model-agnostic estimate (~4 chars/token).
    return max(1, math.ceil(len(text) / 4))


def _split_recursive(text: str, size: int, seps: list[str]) -> list[str]:
    """Split text into pieces each <= size, breaking on the best separator."""
    if len(text) <= size:
        return [text] if text.strip() else []
    if not seps:
        # No separators left: hard-split on size.
        return [text[i : i + size] for i in range(0, len(text), size)]

    sep, rest = seps[0], seps[1:]
    parts = text.split(sep)
    pieces: list[str] = []
    for part in parts:
        candidate = part + sep
        if len(candidate) <= size:
            pieces.append(candidate)
        else:
            pieces.extend(_split_recursive(part, size, rest))
    return [p for p in pieces if p.strip()]


def _pack(pieces: list[str], size: int, overlap: int) -> list[str]:
    """Greedily combine pieces up to size, carrying an overlap tail forward."""
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
        elif len(current) + len(piece) <= size:
            current += piece
        else:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap and len(current) > overlap else ""
            current = (tail + piece) if tail else piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_text(
    text: str,
    *,
    size: int,
    overlap: int,
    page_number: int | None = None,
    start_index: int = 0,
) -> list[Chunk]:
    if not text or not text.strip():
        return []
    pieces = _split_recursive(text, size, _SEPARATORS)
    packed = _pack(pieces, size, overlap)
    chunks: list[Chunk] = []
    for i, body in enumerate(packed, start=start_index):
        chunks.append(
            Chunk(
                index=i,
                text=body,
                char_count=len(body),
                token_count=_approx_tokens(body),
                page_number=page_number,
            )
        )
    return chunks
