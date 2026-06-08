"""RAG chat endpoints (scoped to a company + chatbot)."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.api.deps import TenantContext, require_permission
from app.schemas import (
    AnswerResponse,
    AskRequest,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
    SourceRef,
)
from app.services import chatbot_service, conversation_service
from app.services.rag import service as rag_service

router = APIRouter(
    prefix="/companies/{company_id}/chatbots/{chatbot_id}/conversations",
    tags=["chat"],
)


async def _ensure_chatbot(ctx: TenantContext, chatbot_id: uuid.UUID) -> None:
    await chatbot_service.get_chatbot(ctx.db, chatbot_id=chatbot_id)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    chatbot_id: uuid.UUID,
    body: ConversationCreate,
    ctx: TenantContext = Depends(require_permission("conversations:read")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    conv = await conversation_service.create_conversation(
        ctx.db, company_id=ctx.company.id, chatbot_id=chatbot_id,
        channel=body.channel, visitor_id=body.visitor_id, title=body.title,
    )
    return conv


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    chatbot_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("conversations:read")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    return await conversation_service.list_conversations(ctx.db, chatbot_id=chatbot_id)


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("conversations:read")),
):
    await conversation_service.get_conversation(ctx.db, conversation_id=conversation_id)
    return await conversation_service.list_messages(ctx.db, conversation_id=conversation_id)


@router.post("/{conversation_id}/messages", response_model=AnswerResponse)
async def ask(
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: AskRequest,
    ctx: TenantContext = Depends(require_permission("conversations:read")),
):
    result = await rag_service.answer(
        company_id=ctx.company.id,
        chatbot_id=chatbot_id,
        conversation_id=conversation_id,
        question=body.question,
        top_k=body.top_k,
    )
    return AnswerResponse(
        conversation_id=result["conversation_id"],
        message_id=result["message_id"],
        answer=result["answer"],
        sources=[SourceRef(**s) for s in result["sources"]],
    )


@router.post("/{conversation_id}/messages/stream")
async def ask_stream(
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: AskRequest,
    ctx: TenantContext = Depends(require_permission("conversations:read")),
):
    company_id = ctx.company.id  # capture before the request session closes

    async def event_source():
        async for event in rag_service.answer_stream(
            company_id=company_id,
            chatbot_id=chatbot_id,
            conversation_id=conversation_id,
            question=body.question,
            top_k=body.top_k,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
