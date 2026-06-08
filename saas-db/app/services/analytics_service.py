"""Analytics: event capture, idempotent daily rollups, and dashboards.

Events stream into analytics_events (partitioned). rollup_day() aggregates a
day's conversations/messages/leads into analytics_daily (company-level row,
made idempotent by delete-then-insert since the unique index ignores NULLs).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsDaily, AnalyticsEvent
from app.models.chat import Conversation, Lead, Message


async def record_event(
    db: AsyncSession, *, company_id: uuid.UUID, event_type: str, event_name: str,
    chatbot_id: uuid.UUID | None = None, conversation_id: uuid.UUID | None = None,
    properties: dict | None = None,
) -> None:
    db.add(AnalyticsEvent(
        company_id=company_id, chatbot_id=chatbot_id, conversation_id=conversation_id,
        event_type=event_type, event_name=event_name, properties=properties or {},
    ))


async def rollup_day(db: AsyncSession, *, company_id: uuid.UUID, day: date) -> dict:
    """Idempotently recompute the company-level analytics_daily row for `day`."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    conv = (await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.started_at >= start, Conversation.started_at < end,
            Conversation.deleted_at.is_(None))
    )).scalar_one()
    msgs = (await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= start, Message.created_at < end)
    )).scalar_one()
    tokens = (await db.execute(
        select(func.coalesce(func.sum(Message.token_count), 0)).where(
            Message.created_at >= start, Message.created_at < end)
    )).scalar_one()
    leads = (await db.execute(
        select(func.count(Lead.id)).where(
            Lead.captured_at >= start, Lead.captured_at < end, Lead.deleted_at.is_(None))
    )).scalar_one()

    # idempotent: clear any prior company-level row for this day, then insert.
    await db.execute(text(
        "DELETE FROM analytics_daily WHERE company_id = :cid AND day = :day AND chatbot_id IS NULL"
    ), {"cid": str(company_id), "day": day})
    db.add(AnalyticsDaily(
        company_id=company_id, chatbot_id=None, day=day,
        conversations_count=conv, messages_count=msgs, leads_count=leads, tokens_used=tokens,
    ))
    await db.commit()
    return {"day": day.isoformat(), "conversations": conv, "messages": msgs,
            "leads": leads, "tokens": int(tokens)}


async def tenant_dashboard(db: AsyncSession, *, company_id: uuid.UUID, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    daily_conv = (await db.execute(
        select(func.date(Conversation.started_at), func.count(Conversation.id))
        .where(Conversation.started_at >= since, Conversation.deleted_at.is_(None))
        .group_by(func.date(Conversation.started_at)).order_by(func.date(Conversation.started_at))
    )).all()
    daily_leads = (await db.execute(
        select(func.date(Lead.captured_at), func.count(Lead.id))
        .where(Lead.captured_at >= since, Lead.deleted_at.is_(None))
        .group_by(func.date(Lead.captured_at)).order_by(func.date(Lead.captured_at))
    )).all()
    funnel = (await db.execute(
        select(Lead.status, func.count(Lead.id)).where(Lead.deleted_at.is_(None)).group_by(Lead.status)
    )).all()
    top_bots = (await db.execute(
        select(Conversation.chatbot_id, func.count(Conversation.id).label("c"))
        .where(Conversation.deleted_at.is_(None)).group_by(Conversation.chatbot_id)
        .order_by(text("c DESC")).limit(5)
    )).all()
    popular_q = (await db.execute(
        select(Message.content, func.count(Message.id).label("c"))
        .where(Message.role == "user").group_by(Message.content)
        .order_by(text("c DESC")).limit(10)
    )).all()

    return {
        "daily_conversations": [{"day": str(d), "count": int(c)} for d, c in daily_conv],
        "daily_leads": [{"day": str(d), "count": int(c)} for d, c in daily_leads],
        "conversion_funnel": {(s.value if hasattr(s, "value") else str(s)): int(c) for s, c in funnel},
        "top_chatbots": [{"chatbot_id": str(b), "conversations": int(c)} for b, c in top_bots],
        "popular_questions": [{"question": q[:160], "count": int(c)} for q, c in popular_q],
    }
