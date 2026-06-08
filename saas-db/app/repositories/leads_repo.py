"""Lead data access. Pure queries; business logic lives in the service."""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Lead
from app.models.crm import LeadActivity, LeadNote


async def get(db: AsyncSession, lead_id: uuid.UUID) -> Lead | None:
    return (
        await db.execute(
            select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None))
        )
    ).scalar_one_or_none()


async def search(
    db: AsyncSession, *, status: str | None, assigned_to: uuid.UUID | None,
    chatbot_id: uuid.UUID | None, q: str | None, limit: int, offset: int,
) -> tuple[list[Lead], int]:
    base = select(Lead).where(Lead.deleted_at.is_(None))
    if status:
        base = base.where(Lead.status == status)
    if assigned_to:
        base = base.where(Lead.assigned_to == assigned_to)
    if chatbot_id:
        base = base.where(Lead.chatbot_id == chatbot_id)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(or_(
            func.lower(Lead.name).like(like),
            func.lower(Lead.email).like(like),
            func.lower(Lead.company).like(like),
        ))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(Lead.captured_at.desc()).limit(limit).offset(offset))
    ).scalars()
    return list(rows), int(total)


async def status_counts(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(
            select(Lead.status, func.count(Lead.id))
            .where(Lead.deleted_at.is_(None)).group_by(Lead.status)
        )
    ).all()
    return {s.value if hasattr(s, "value") else str(s): int(c) for s, c in rows}


async def notes_for(db: AsyncSession, lead_id: uuid.UUID) -> list[LeadNote]:
    return list((
        await db.execute(
            select(LeadNote).where(LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc())
        )
    ).scalars())


async def activities_for(db: AsyncSession, lead_id: uuid.UUID) -> list[LeadActivity]:
    return list((
        await db.execute(
            select(LeadActivity).where(LeadActivity.lead_id == lead_id)
            .order_by(LeadActivity.created_at.desc())
        )
    ).scalars())
