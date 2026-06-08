"""Retrieval stage: embed the query, search Qdrant (tenant-scoped), and hydrate
citation metadata (document title, source URI, page) from Postgres.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge import Document, DocumentChunk
from app.services import vector_store
from app.services.embeddings import get_embedder

logger = get_logger("app.rag.retrieval")


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    chunk_index: int | None
    text: str
    score: float
    title: str | None = None
    source_uri: str | None = None
    page_number: int | None = None


async def retrieve(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    query: str,
    top_k: int,
    min_score: float,
) -> list[RetrievedChunk]:
    # 1) Embed the query (offloaded so a network embedder doesn't block the loop).
    vector = (await asyncio.to_thread(get_embedder().embed, [query]))[0]

    # 2) Vector search — tenant + chatbot filter is enforced inside the store.
    hits = await vector_store.search(
        company_id=company_id, chatbot_id=chatbot_id, vector=vector, top_k=top_k
    )
    hits = [h for h in hits if h["score"] is None or h["score"] >= min_score]
    if not hits:
        return []

    # 3) Hydrate citation metadata from Postgres in one pass.
    chunk_ids = [uuid.UUID(h["chunk_id"]) for h in hits if h.get("chunk_id")]
    pages: dict[str, int | None] = {}
    if chunk_ids:
        rows = (
            await db.execute(
                select(DocumentChunk.id, DocumentChunk.page_number).where(
                    DocumentChunk.id.in_(chunk_ids)
                )
            )
        ).all()
        pages = {str(cid): pg for cid, pg in rows}

    doc_ids = [uuid.UUID(h["document_id"]) for h in hits if h.get("document_id")]
    docs: dict[str, tuple[str | None, str | None]] = {}
    if doc_ids:
        rows = (
            await db.execute(
                select(Document.id, Document.title, Document.source_uri).where(
                    Document.id.in_(doc_ids)
                )
            )
        ).all()
        docs = {str(did): (title, uri) for did, title, uri in rows}

    out: list[RetrievedChunk] = []
    for h in hits:
        title, uri = docs.get(h.get("document_id"), (None, None))
        out.append(
            RetrievedChunk(
                chunk_id=h.get("chunk_id"),
                document_id=h.get("document_id"),
                chunk_index=h.get("chunk_index"),
                text=h.get("text") or "",
                score=float(h.get("score") or 0.0),
                title=title,
                source_uri=uri,
                page_number=pages.get(h.get("chunk_id")),
            )
        )
    return out
