"""Chatbot service (documents attach to a chatbot, so KB needs this)."""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.bots import Chatbot


async def create_chatbot(
    db: AsyncSession, *, company_id: uuid.UUID, name: str, slug: str
) -> Chatbot:
    dup = (
        await db.execute(
            select(Chatbot.id).where(
                Chatbot.slug == slug, Chatbot.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise ConflictError("A chatbot with this slug already exists")
    bot = Chatbot(
        company_id=company_id,
        name=name,
        slug=slug,
        public_key=secrets.token_urlsafe(24),
    )
    db.add(bot)
    try:
        await db.commit()
    except IntegrityError as exc:
        raise ConflictError("A chatbot with this slug already exists") from exc
    return bot


async def list_chatbots(db: AsyncSession) -> list[Chatbot]:
    return list(
        (
            await db.execute(
                select(Chatbot)
                .where(Chatbot.deleted_at.is_(None))
                .order_by(Chatbot.created_at.desc())
            )
        ).scalars()
    )


async def get_chatbot(db: AsyncSession, *, chatbot_id: uuid.UUID) -> Chatbot:
    bot = (
        await db.execute(
            select(Chatbot).where(
                Chatbot.id == chatbot_id, Chatbot.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if bot is None:
        raise NotFoundError("Chatbot not found")
    return bot
