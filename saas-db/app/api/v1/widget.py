"""Public, key-authenticated widget API (no user JWT).

Every endpoint resolves the chatbot from its ``public_key`` and enforces the
domain allowlist via Origin/Referer before doing any work. Tenant context comes
from the resolved company id, never from the client.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.exceptions import PermissionDenied
from app.core.ratelimit import limiter
from app.services import conversation_service, widget_service
from app.services.rag import service as rag_service
from app.services.widget_service import WidgetContext

router = APIRouter(prefix="/widget", tags=["widget"])


async def widget_ctx(
    public_key: str,
    origin: str | None = Header(default=None),
    referer: str | None = Header(default=None),
) -> WidgetContext:
    ctx = await widget_service.resolve_public_key(public_key)
    if not widget_service.origin_allowed(ctx.allowed_domains, origin, referer):
        raise PermissionDenied("This domain is not allowed to embed this widget")
    return ctx


class ConfigResponse(BaseModel):
    chatbot_name: str
    greeting: str
    primary_color: str
    position: str
    suggested_prompts: list
    lead_capture: dict
    locale: str
    launcher_icon_url: str | None
    show_branding: bool


@router.get("/{public_key}/config", response_model=ConfigResponse)
async def get_config(ctx: WidgetContext = Depends(widget_ctx)):
    return ConfigResponse(
        chatbot_name=ctx.chatbot_name,
        greeting=ctx.greeting,
        primary_color=ctx.primary_color,
        position=ctx.position,
        suggested_prompts=ctx.suggested_prompts,
        lead_capture=ctx.lead_capture,
        locale=ctx.locale,
        launcher_icon_url=ctx.launcher_icon_url,
        show_branding=ctx.show_branding,
    )


class StartConversation(BaseModel):
    visitor_id: str | None = Field(default=None, max_length=64)


class ConversationResponse(BaseModel):
    conversation_id: str


@router.post("/{public_key}/conversations", response_model=ConversationResponse)
async def start_conversation(
    body: StartConversation,
    ctx: WidgetContext = Depends(widget_ctx),
):
    from app.db.session import tenant_session

    async with tenant_session(ctx.company_id) as db:
        conv = await conversation_service.create_conversation(
            db, company_id=ctx.company_id, chatbot_id=ctx.chatbot_id,
            channel="widget", visitor_id=body.visitor_id,
        )
    return ConversationResponse(conversation_id=str(conv.id))


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


@router.post("/{public_key}/conversations/{conversation_id}/messages/stream")
async def widget_stream(
    conversation_id: uuid.UUID,
    body: AskBody,
    request: Request,
    ctx: WidgetContext = Depends(widget_ctx),
):
    # Light abuse protection keyed by public key + client IP.
    client_ip = request.client.host if request.client else "unknown"
    await limiter.check(
        "widget_message", f"{ctx.chatbot_id}:{client_ip}", limit=30, window=60
    )

    company_id, chatbot_id = ctx.company_id, ctx.chatbot_id

    # Validate the conversation belongs to this chatbot BEFORE the stream starts,
    # so a forged/foreign conversation id returns a clean 404 (not a mid-stream error).
    from app.db.session import tenant_session
    from app.core.exceptions import NotFoundError
    from sqlalchemy import select
    from app.models.chat import Conversation

    async with tenant_session(company_id) as db:
        conv = (
            await db.execute(
                select(Conversation.id).where(
                    Conversation.id == conversation_id,
                    Conversation.chatbot_id == chatbot_id,
                    Conversation.deleted_at.is_(None),
                )
            )
        ).first()
    if conv is None:
        raise NotFoundError("Conversation not found")

    async def event_source():
        async for event in rag_service.answer_stream(
            company_id=company_id, chatbot_id=chatbot_id,
            conversation_id=conversation_id, question=body.question,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class LeadBody(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    conversation_id: uuid.UUID | None = None
    fields: dict | None = None


class LeadResponse(BaseModel):
    lead_id: str


@router.post("/{public_key}/leads", response_model=LeadResponse)
async def capture_lead(
    body: LeadBody,
    ctx: WidgetContext = Depends(widget_ctx),
):
    if not (body.name or body.email or body.phone):
        raise PermissionDenied("At least one contact field is required")
    lead_id = await widget_service.capture_lead(
        company_id=ctx.company_id, chatbot_id=ctx.chatbot_id,
        conversation_id=body.conversation_id, name=body.name,
        email=body.email, phone=body.phone, fields=body.fields,
    )
    return LeadResponse(lead_id=str(lead_id))
