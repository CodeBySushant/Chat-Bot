"""Subscription lifecycle: subscribe, upgrade/downgrade, cancel. Plans are the
entitlement source; the configured provider handles external billing state."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailed
from app.db.enums import SubscriptionStatus
from app.models.billing import Plan, Subscription
from app.services.billing.providers import get_billing_provider

LIVE = (SubscriptionStatus.trialing, SubscriptionStatus.active, SubscriptionStatus.past_due)


async def list_plans(db: AsyncSession, *, public_only: bool = True) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.sort_order)
    if public_only:
        stmt = stmt.where(Plan.is_public.is_(True))
    return list((await db.execute(stmt)).scalars())


async def get_plan(db: AsyncSession, code: str) -> Plan:
    plan = (await db.execute(select(Plan).where(Plan.code == code))).scalar_one_or_none()
    if plan is None:
        raise NotFoundError(f"Plan '{code}' not found")
    return plan


async def get_live_subscription(db: AsyncSession, company_id: uuid.UUID) -> Subscription | None:
    return (
        await db.execute(
            select(Subscription).where(
                Subscription.company_id == company_id,
                Subscription.status.in_(LIVE),
                Subscription.deleted_at.is_(None),
            ).order_by(Subscription.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def change_plan(
    db: AsyncSession, *, company_id: uuid.UUID, plan_code: str
) -> Subscription:
    """Create or switch the company's live subscription (handles up/downgrade)."""
    plan = await get_plan(db, plan_code)
    provider = get_billing_provider()
    psub = await provider.create_subscription(company_id=str(company_id), plan_code=plan.code)

    now = datetime.now(timezone.utc)
    sub = await get_live_subscription(db, company_id)
    if sub is None:
        sub = Subscription(
            company_id=company_id, plan_code=plan.code, status=SubscriptionStatus.active,
            provider=provider.name, provider_subscription_id=psub.provider_subscription_id,
            current_period_start=now, current_period_end=now + timedelta(days=30),
            limits=dict(plan.entitlements),
        )
        db.add(sub)
    else:
        sub.plan_code = plan.code
        sub.limits = dict(plan.entitlements)
        sub.provider = provider.name
        sub.provider_subscription_id = psub.provider_subscription_id
        sub.status = SubscriptionStatus.active
        sub.canceled_at = None
    await db.flush()
    return sub


async def cancel_subscription(
    db: AsyncSession, *, company_id: uuid.UUID, at_period_end: bool = True
) -> Subscription:
    sub = await get_live_subscription(db, company_id)
    if sub is None:
        raise ValidationFailed("No active subscription to cancel")
    provider = get_billing_provider()
    await provider.cancel_subscription(
        provider_subscription_id=sub.provider_subscription_id or "", at_period_end=at_period_end
    )
    now = datetime.now(timezone.utc)
    if at_period_end:
        sub.canceled_at = now  # remains active until period end
    else:
        sub.status = SubscriptionStatus.canceled
        sub.canceled_at = now
    await db.flush()
    return sub
