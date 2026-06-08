"""Knowledge-base service: document lifecycle on top of the tenant session."""
from __future__ import annotations

import hashlib
import os
import re
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.enums import DocumentSourceType, ProcessingStatus
from app.models.knowledge import Document, DocumentChunk
from app.services import vector_store
from app.services.validation import validate_upload

logger = get_logger("app.knowledge")

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(filename: str) -> str:
    base = os.path.basename(filename)
    cleaned = _SAFE_NAME_RE.sub("_", base).strip("._") or "upload"
    return cleaned[:200]


async def create_document(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> Document:
    kind, mime = validate_upload(filename, data)
    document_id = uuid.uuid4()
    content_hash = hashlib.sha256(data).hexdigest()

    storage_key = f"{company_id}/{document_id}/{_safe_name(filename)}"
    full_path = os.path.join(settings.STORAGE_DIR, storage_key)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as fh:
        fh.write(data)

    doc = Document(
        id=document_id,
        company_id=company_id,
        chatbot_id=chatbot_id,
        source_type=DocumentSourceType.upload,
        title=filename,
        storage_key=storage_key,
        mime_type=mime,
        file_size=len(data),
        content_hash=content_hash,
        status=ProcessingStatus.pending,
        meta={"kind": kind, "original_filename": filename},
    )
    db.add(doc)
    await db.commit()
    logger.info("Created document %s (%s) for chatbot %s", document_id, kind, chatbot_id)
    return doc


async def _chunk_counts(db: AsyncSession, document_ids: list[uuid.UUID]) -> dict:
    if not document_ids:
        return {}
    rows = (
        await db.execute(
            select(DocumentChunk.document_id, func.count(DocumentChunk.id))
            .where(
                DocumentChunk.document_id.in_(document_ids),
                DocumentChunk.deleted_at.is_(None),
            )
            .group_by(DocumentChunk.document_id)
        )
    ).all()
    return {doc_id: count for doc_id, count in rows}


async def list_documents(db: AsyncSession, *, chatbot_id: uuid.UUID) -> list[dict]:
    docs = list(
        (
            await db.execute(
                select(Document)
                .where(
                    Document.chatbot_id == chatbot_id, Document.deleted_at.is_(None)
                )
                .order_by(Document.created_at.desc())
            )
        ).scalars()
    )
    counts = await _chunk_counts(db, [d.id for d in docs])
    return [_doc_dict(d, counts.get(d.id, 0)) for d in docs]


async def get_document(db: AsyncSession, *, document_id: uuid.UUID) -> dict:
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    counts = await _chunk_counts(db, [doc.id])
    return _doc_dict(doc, counts.get(doc.id, 0))


async def list_chunks(db: AsyncSession, *, document_id: uuid.UUID) -> list[dict]:
    # Confirm the document is visible in this tenant first.
    exists = (
        await db.execute(
            select(Document.id).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise NotFoundError("Document not found")
    chunks = list(
        (
            await db.execute(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.deleted_at.is_(None),
                )
                .order_by(DocumentChunk.chunk_index)
            )
        ).scalars()
    )
    return [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "page_number": c.page_number,
            "token_count": c.token_count,
            "char_count": c.char_count,
        }
        for c in chunks
    ]


async def delete_document(
    db: AsyncSession, *, company_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    # Remove vectors first (idempotent), then the rows (chunks/embeddings cascade).
    await vector_store.delete_document(company_id=company_id, document_id=document_id)
    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()
    # Best-effort: drop the stored file.
    try:
        path = os.path.join(settings.STORAGE_DIR, doc.storage_key or "")
        if doc.storage_key and os.path.exists(path):
            os.remove(path)
    except OSError:
        logger.warning("Could not delete stored file for %s", document_id)


def _doc_dict(doc: Document, chunk_count: int) -> dict:
    return {
        "id": doc.id,
        "chatbot_id": doc.chatbot_id,
        "title": doc.title,
        "source_type": doc.source_type.value,
        "mime_type": doc.mime_type,
        "file_size": doc.file_size,
        "status": doc.status.value,
        "token_count": doc.token_count,
        "chunk_count": chunk_count,
        "error": doc.error,
        "created_at": doc.created_at,
    }
