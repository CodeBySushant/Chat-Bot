"""Document ingestion pipeline.

process_document runs: load -> extract -> clean -> chunk -> embed -> store in
Qdrant -> persist chunk/embedding rows -> mark ready. It runs outside any
request, so it opens its own RLS session and sets the tenant GUC from the
document's company. CPU-bound work (extract/clean/chunk/embed) is offloaded to a
thread so the event loop stays responsive.

Consistency: DB chunk/embedding rows are flushed, then vectors are upserted to
Qdrant; only if the upsert succeeds is the transaction committed. On any failure
the DB transaction is rolled back and the document is marked ``failed`` (with any
partial vectors deleted), so we never leave rows without vectors.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.enums import ProcessingStatus
from app.db.session import SessionFactory
from app.models.knowledge import Document, DocumentChunk, Embedding
from app.services import chunking, extraction, text_cleaning, vector_store
from app.services.embeddings import get_embedder

logger = get_logger("app.ingestion")


async def _set_guc(db: AsyncSession, company_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.current_company', :cid, true)"),
        {"cid": str(company_id)},
    )


def _build_pipeline(kind: str, data: bytes) -> list[dict]:
    """Synchronous CPU work: extract -> clean -> chunk -> embed."""
    segments = extraction.extract(kind, data)
    built: list[dict] = []
    index = 0
    for seg in segments:
        cleaned = text_cleaning.clean(seg.text)
        if not cleaned:
            continue
        chunks = chunking.chunk_text(
            cleaned,
            size=settings.CHUNK_SIZE_CHARS,
            overlap=settings.CHUNK_OVERLAP_CHARS,
            page_number=seg.page_number,
            start_index=index,
        )
        for ch in chunks:
            built.append(
                {
                    "chunk_id": uuid.uuid4(),
                    "chunk_index": ch.index,
                    "text": ch.text,
                    "char_count": ch.char_count,
                    "token_count": ch.token_count,
                    "page_number": ch.page_number,
                }
            )
        index += len(chunks)

    if not built:
        return []

    embedder = get_embedder()
    vectors = embedder.embed([b["text"] for b in built])
    for b, vec in zip(built, vectors):
        b["vector"] = vec
    return built


async def _mark_failed(document_id: uuid.UUID, company_id: uuid.UUID, error: str) -> None:
    async with SessionFactory() as db:
        await _set_guc(db, company_id)
        doc = (
            await db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if doc is not None:
            doc.status = ProcessingStatus.failed
            doc.error = error[:2000]
            await db.commit()
    logger.warning("Document %s failed: %s", document_id, error)


async def process_document(document_id: uuid.UUID, company_id: uuid.UUID) -> None:
    # 1) Load + mark processing.
    async with SessionFactory() as db:
        await _set_guc(db, company_id)
        doc = (
            await db.execute(
                select(Document).where(
                    Document.id == document_id, Document.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if doc is None:
            logger.warning("Document %s not found for processing", document_id)
            return
        kind = doc.meta.get("kind", "")
        storage_key = doc.storage_key
        chatbot_id = doc.chatbot_id
        doc.status = ProcessingStatus.processing
        await db.commit()

    try:
        path = os.path.join(settings.STORAGE_DIR, storage_key)
        with open(path, "rb") as fh:
            data = fh.read()

        import asyncio

        built = await asyncio.to_thread(_build_pipeline, kind, data)
        if not built:
            await _mark_failed(document_id, company_id, "No extractable text found")
            return

        embedder = get_embedder()

        # 2) Persist chunk + embedding rows (flush, not commit yet).
        async with SessionFactory() as db:
            await _set_guc(db, company_id)
            total_tokens = 0
            for b in built:
                content_hash = hashlib.sha256(b["text"].encode("utf-8")).hexdigest()
                db.add(
                    DocumentChunk(
                        id=b["chunk_id"],
                        company_id=company_id,
                        document_id=document_id,
                        chunk_index=b["chunk_index"],
                        content=b["text"],
                        content_hash=content_hash,
                        token_count=b["token_count"],
                        char_count=b["char_count"],
                        page_number=b["page_number"],
                    )
                )
                db.add(
                    Embedding(
                        company_id=company_id,
                        chunk_id=b["chunk_id"],
                        provider=embedder.provider,
                        model=embedder.model,
                        dimensions=embedder.dim,
                        collection_name=settings.QDRANT_COLLECTION,
                        vector_id=str(b["chunk_id"]),
                        status=ProcessingStatus.ready,
                    )
                )
                total_tokens += b["token_count"]
            await db.flush()

            # 3) Upsert vectors; commit only if Qdrant succeeds.
            try:
                await vector_store.upsert_chunks(
                    company_id=company_id,
                    chatbot_id=chatbot_id,
                    document_id=document_id,
                    items=built,
                )
            except Exception:
                await db.rollback()
                await vector_store.delete_document(
                    company_id=company_id, document_id=document_id
                )
                raise

            doc = (
                await db.execute(select(Document).where(Document.id == document_id))
            ).scalar_one()
            doc.status = ProcessingStatus.ready
            doc.token_count = total_tokens
            doc.error = None
            await db.commit()

        logger.info(
            "Document %s ready: %d chunks, %d tokens",
            document_id,
            len(built),
            total_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - convert to a failed status
        await _mark_failed(document_id, company_id, str(exc))
