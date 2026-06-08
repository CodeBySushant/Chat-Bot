"""Knowledge-base document endpoints (scoped to a company + chatbot)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import TenantContext, require_permission
from app.schemas import (
    DocumentChunkResponse,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services import chatbot_service, knowledge_service, vector_store
from app.services.embeddings import get_embedder
from app.workers.ingest_worker import pool

router = APIRouter(
    prefix="/companies/{company_id}/chatbots/{chatbot_id}/documents",
    tags=["knowledge"],
)


async def _ensure_chatbot(ctx: TenantContext, chatbot_id: uuid.UUID) -> None:
    # RLS scopes the lookup to the tenant; raises 404 if not visible.
    await chatbot_service.get_chatbot(ctx.db, chatbot_id=chatbot_id)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    chatbot_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permission("documents:create")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    data = await file.read()
    doc = await knowledge_service.create_document(
        ctx.db,
        company_id=ctx.company.id,
        chatbot_id=chatbot_id,
        filename=file.filename,
        data=data,
    )
    # Hand off to the background pipeline (row is committed and durable).
    pool.enqueue(doc.id, ctx.company.id)
    return DocumentResponse(
        id=doc.id,
        chatbot_id=doc.chatbot_id,
        title=doc.title,
        source_type=doc.source_type.value,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        status=doc.status.value,
        token_count=doc.token_count,
        chunk_count=0,
        error=doc.error,
        created_at=doc.created_at,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    chatbot_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:read")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    rows = await knowledge_service.list_documents(ctx.db, chatbot_id=chatbot_id)
    return [DocumentResponse(**r) for r in rows]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    chatbot_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:read")),
):
    row = await knowledge_service.get_document(ctx.db, document_id=document_id)
    return DocumentResponse(**row)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def list_document_chunks(
    chatbot_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:read")),
):
    rows = await knowledge_service.list_chunks(ctx.db, document_id=document_id)
    return [DocumentChunkResponse(**r) for r in rows]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    chatbot_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:delete")),
):
    from fastapi import Response

    await knowledge_service.delete_document(
        ctx.db, company_id=ctx.company.id, document_id=document_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    chatbot_id: uuid.UUID,
    body: SearchRequest,
    ctx: TenantContext = Depends(require_permission("documents:read")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    vector = get_embedder().embed([body.query])[0]
    hits = await vector_store.search(
        company_id=ctx.company.id,
        chatbot_id=chatbot_id,
        vector=vector,
        top_k=body.top_k,
    )
    return SearchResponse(
        query=body.query, results=[SearchResult(**h) for h in hits]
    )
