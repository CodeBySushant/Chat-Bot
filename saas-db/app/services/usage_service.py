"""Usage metering: append-only records + period counters + quota checks."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import QuotaExceeded
from app.models.billing import UsageCounter, UsageRecord
from app.services.billing.entitlements import (
    METRIC_TO_LIMIT, get_entitlements, is_unlimited, period_bounds,
)


async def record_usage(
    db: AsyncSession, *, company_id: uuid.UUID, metric: str, quantity: int = 1,
    chatbot_id: uuid.UUID | None = None, metadata: dict | None = None,
) -> None:
    """Append a usage record and atomically bump the period counter (upsert)."""
    start, end = period_bounds()
    db.add(UsageRecord(
        company_id=company_id, metric=metric, quantity=quantity,
        chatbot_id=chatbot_id, metadata_=metadata or {},
    ))
    stmt = pg_insert(UsageCounter).values(
        company_id=company_id, metric=metric, period_start=start, period_end=end, value=quantity,
    ).on_conflict_do_update(
        constraint="uq_usage_counter",
        set_={"value": UsageCounter.__table__.c.value + quantity, "updated_at": text("now()")},
    )
    await db.execute(stmt)


async def current_usage(db: AsyncSession, company_id: uuid.UUID) -> dict[str, int]:
    start, _ = period_bounds()
    rows = (
        await db.execute(
            select(UsageCounter.metric, UsageCounter.value).where(
                UsageCounter.company_id == company_id, UsageCounter.period_start == start
            )
        )
    ).all()
    return {m: v for m, v in rows}


async def check_quota(
    db: AsyncSession, *, company_id: uuid.UUID, metric: str, requested: int = 1,
    current: int | None = None,
) -> None:
    """Raise QuotaExceeded if (current + requested) would exceed the plan limit.

    `current` lets callers pass a live row count for *total* resource limits
    (chatbots, documents, leads); when omitted, the monthly period counter is
    used (conversations, messages, ai_tokens)."""
    ent = await get_entitlements(db, company_id)
    limit_key = METRIC_TO_LIMIT.get(metric, metric)
    limit = ent.get(limit_key)
    if is_unlimited(limit):
        return
    used = current if current is not None else (await current_usage(db, company_id)).get(metric, 0)
    if used + requested > limit:
        raise QuotaExceeded(
            f"Plan limit reached for '{metric}' ({used}/{limit}). Upgrade your plan to continue.",
            details={"metric": metric, "used": used, "limit": limit},
        )
