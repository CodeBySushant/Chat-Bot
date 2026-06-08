"""Qdrant vector store wrapper.

Single shared collection with a per-tenant payload filter (the design from the
blueprint): every point carries ``company_id`` and every query is filtered by it,
so retrieval cannot cross tenants. A payload index on ``company_id`` keeps the
filter fast. Uses embedded local mode (on-disk) when no ``QDRANT_URL`` is set,
which is API-identical to a real server.

The qdrant client is synchronous; calls are offloaded with ``asyncio.to_thread``
so they never block the event loop.
"""
from __future__ import annotations

import asyncio
import threading
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.vectorstore")

_client: QdrantClient | None = None
# Embedded (local) Qdrant is single-writer; serialize access across worker
# threads. A real Qdrant server handles concurrency itself, so the lock is only
# engaged in local mode.
_local_lock = threading.Lock()


def _is_local() -> bool:
    return not settings.QDRANT_URL


class _MaybeLock:
    def __enter__(self):
        if _is_local():
            _local_lock.acquire()
        return self

    def __exit__(self, *exc):
        if _local_lock.locked():
            _local_lock.release()
        return False


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if settings.QDRANT_URL:
            _client = QdrantClient(
                url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY
            )
            logger.info("Qdrant client connected to %s", settings.QDRANT_URL)
        else:
            _client = QdrantClient(path=settings.QDRANT_PATH)
            logger.info("Qdrant client in local mode at %s", settings.QDRANT_PATH)
    return _client


def _ensure_collection_sync() -> None:
    with _MaybeLock():
        client = get_client()
        name = settings.QDRANT_COLLECTION
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM, distance=Distance.COSINE
                ),
            )
            # Tenant isolation filter performance.
            client.create_payload_index(
                collection_name=name,
                field_name="company_id",
                field_schema="keyword",
            )
            client.create_payload_index(
                collection_name=name,
                field_name="document_id",
                field_schema="keyword",
            )
            logger.info("Created Qdrant collection %s", name)


async def ensure_collection() -> None:
    await asyncio.to_thread(_ensure_collection_sync)


def _tenant_filter(company_id: uuid.UUID, **extra) -> Filter:
    must = [
        FieldCondition(key="company_id", match=MatchValue(value=str(company_id)))
    ]
    for key, value in extra.items():
        if value is not None:
            must.append(FieldCondition(key=key, match=MatchValue(value=str(value))))
    return Filter(must=must)


def _upsert_sync(points: list[PointStruct]) -> None:
    with _MaybeLock():
        get_client().upsert(collection_name=settings.QDRANT_COLLECTION, points=points)


async def upsert_chunks(
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    document_id: uuid.UUID,
    items: list[dict],
) -> None:
    """items: [{chunk_id, chunk_index, text, vector}]."""
    points = [
        PointStruct(
            id=str(it["chunk_id"]),
            vector=it["vector"],
            payload={
                "company_id": str(company_id),
                "chatbot_id": str(chatbot_id),
                "document_id": str(document_id),
                "chunk_id": str(it["chunk_id"]),
                "chunk_index": it["chunk_index"],
                "text": it["text"],
            },
        )
        for it in items
    ]
    await asyncio.to_thread(_upsert_sync, points)


def _search_sync(company_id, chatbot_id, vector, top_k):
    with _MaybeLock():
        return get_client().query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=vector,
            query_filter=_tenant_filter(company_id, chatbot_id=chatbot_id),
            limit=top_k,
            with_payload=True,
        ).points


async def search(
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID | None,
    vector: list[float],
    top_k: int,
) -> list[dict]:
    hits = await asyncio.to_thread(_search_sync, company_id, chatbot_id, vector, top_k)
    return [
        {
            "score": h.score,
            "chunk_id": h.payload.get("chunk_id"),
            "document_id": h.payload.get("document_id"),
            "chunk_index": h.payload.get("chunk_index"),
            "text": h.payload.get("text"),
        }
        for h in hits
    ]


def _delete_document_sync(company_id, document_id) -> None:
    with _MaybeLock():
        get_client().delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=_tenant_filter(company_id, document_id=document_id),
        )


async def delete_document(*, company_id: uuid.UUID, document_id: uuid.UUID) -> None:
    await asyncio.to_thread(_delete_document_sync, company_id, document_id)


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
