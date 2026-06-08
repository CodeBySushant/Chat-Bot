"""Plan entitlements + billing-period helpers."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Plan, Subscription

UNLIMITED = -1
DEFAULT_PLAN = "free"

# metric -> entitlement key in plans.entitlements
METRIC_TO_LIMIT = {
    "chatbots": "chatbots",
    "documents": "documents",
    "storage_bytes": "storage_bytes",
    "leads": "leads",
    "conversations": "monthly_conversations",
    "messages": "monthly_messages",
    "ai_tokens": "ai_tokens",
}


def period_bounds(at: datetime | None = None) -> tuple[date, date]:
    """Current calendar-month billing period [start, end)."""
    at = at or datetime.now(timezone.utc)
    start = date(at.year, at.month, 1)
    end = date(at.year + 1, 1, 1) if at.month == 12 else date(at.year, at.month + 1, 1)
    return start, end


async def active_plan_code(db: AsyncSession, company_id: uuid.UUID) -> str:
    sub = (
        await db.execute(
            select(Subscription)
            .where(Subscription.company_id == company_id, Subscription.deleted_at.is_(None))
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if sub and sub.status in ("trialing", "active", "past_due"):
        return sub.plan_code
    return DEFAULT_PLAN


async def get_entitlements(db: AsyncSession, company_id: uuid.UUID) -> dict:
    code = await active_plan_code(db, company_id)
    plan = (await db.execute(select(Plan).where(Plan.code == code))).scalar_one_or_none()
    if plan is None:
        plan = (await db.execute(select(Plan).where(Plan.code == DEFAULT_PLAN))).scalar_one_or_none()
    return dict(plan.entitlements) if plan else {}


def is_unlimited(limit: int | None) -> bool:
    return limit is None or limit == UNLIMITED
