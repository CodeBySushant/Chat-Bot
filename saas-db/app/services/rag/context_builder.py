"""Context builder: rank, de-duplicate, and pack retrieved chunks into a bounded
context window, numbering each as a citable source.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.rag.retrieval import RetrievedChunk


@dataclass
class BuiltContext:
    text: str
    used: list[RetrievedChunk]  # in citation order ([1], [2], ...)


def build_context(chunks: list[RetrievedChunk], *, max_chars: int) -> BuiltContext:
    """Highest-scored first, drop duplicates, stop at the character budget."""
    ranked = sorted(chunks, key=lambda c: c.score, reverse=True)

    used: list[RetrievedChunk] = []
    seen_text: set[str] = set()
    blocks: list[str] = []
    budget = max_chars

    for c in ranked:
        body = c.text.strip()
        if not body:
            continue
        key = body[:200]
        if key in seen_text:
            continue
        n = len(used) + 1
        label = c.title or c.source_uri or f"document {c.document_id}"
        if c.page_number:
            label += f" (p.{c.page_number})"
        block = f"[{n}] {label}\n{body}"
        if len(block) > budget and used:
            break
        seen_text.add(key)
        used.append(c)
        blocks.append(block)
        budget -= len(block)
        if budget <= 0:
            break

    return BuiltContext(text="\n\n".join(blocks), used=used)
