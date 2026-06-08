"""Conversation + message persistence (conversation memory)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.enums import ConversationChannel, MessageRole
from app.models.chat import Conversation, Message
from app.services.ai import ChatMessage
from app.services import usage_service, analytics_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_conversation(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    channel: str = "api",
    visitor_id: str | None = None,
    title: str | None = None,
) -> Conversation:
    conv = Conversation(
        company_id=company_id,
        chatbot_id=chatbot_id,
        channel=ConversationChannel(channel),
        visitor_id=visitor_id,
        title=title,
    )
    db.add(conv)
    await db.flush()
    await usage_service.record_usage(db, company_id=company_id, metric="conversations", chatbot_id=chatbot_id)
    await analytics_service.record_event(
        db, company_id=company_id, chatbot_id=chatbot_id, conversation_id=conv.id,
        event_type="conversation", event_name="conversation_started")
    await db.commit()
    return conv


async def get_conversation(
    db: AsyncSession, *, conversation_id: uuid.UUID
) -> Conversation:
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise NotFoundError("Conversation not found")
    return conv


async def list_conversations(
    db: AsyncSession, *, chatbot_id: uuid.UUID
) -> list[Conversation]:
    return list(
        (
            await db.execute(
                select(Conversation)
                .where(
                    Conversation.chatbot_id == chatbot_id,
                    Conversation.deleted_at.is_(None),
                )
                .order_by(Conversation.started_at.desc())
            )
        ).scalars()
    )


async def list_messages(
    db: AsyncSession, *, conversation_id: uuid.UUID
) -> list[Message]:
    return list(
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
        ).scalars()
    )


async def load_history(
    db: AsyncSession, *, conversation_id: uuid.UUID, turns: int
) -> list[ChatMessage]:
    """Most recent user/assistant messages as provider ChatMessages (chronological)."""
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(turns)
        )
    ).scalars()
    history = [
        ChatMessage(m.role.value, m.content)
        for m in rows
        if m.role in (MessageRole.user, MessageRole.assistant)
    ]
    history.reverse()
    return history


async def persist_message(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model: str | None = None,
    latency_ms: int | None = None,
    retrieved_chunk_ids: list | None = None,
    citations: list | None = None,
) -> Message:
    msg = Message(
        company_id=company_id,
        conversation_id=conversation_id,
        role=MessageRole(role),
        content=content,
        token_count=max(1, len(content) // 4),
        model=model,
        latency_ms=latency_ms,
        retrieved_chunk_ids=retrieved_chunk_ids or [],
        citations=citations or [],
    )
    db.add(msg)
    # Maintain the denormalized conversation counter.
    conv = (
        await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
    ).scalar_one_or_none()
    if conv is not None:
        conv.message_count = (conv.message_count or 0) + 1
    await db.commit()
    return msg
