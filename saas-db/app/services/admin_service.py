"""Platform super-admin service: tenant ops, revenue, operations, security.

Runs under the BYPASSRLS admin engine (cross-tenant by design) — only reachable
through require_superuser.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import CompanyStatus, SubscriptionStatus
from app.models.analytics import ActivityLog
from app.models.billing import Plan, Subscription, UsageRecord
from app.models.chat import Conversation, Lead, Message
from app.models.jobs import Job
from app.models.tenancy import Company, User

LIVE = (SubscriptionStatus.trialing, SubscriptionStatus.active, SubscriptionStatus.past_due)


async def list_tenants(db: AsyncSession, *, limit: int = 100, offset: int = 0) -> dict:
    total = (await db.execute(select(func.count(Company.id)))).scalar_one()
    rows = (await db.execute(
        select(Company).order_by(Company.created_at.desc()).limit(limit).offset(offset)
    )).scalars()
    return {"total": int(total), "tenants": [
        {"id": str(c.id), "name": c.name, "slug": c.slug, "status": c.status.value,
         "created_at": c.created_at.isoformat()} for c in rows
    ]}


async def set_tenant_status(db: AsyncSession, *, company_id: uuid.UUID, status: str) -> None:
    company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if company is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Tenant not found")
    company.status = CompanyStatus(status)
    await db.commit()


async def revenue_dashboard(db: AsyncSession) -> dict:
    # MRR = sum of monthly-normalized plan price for live subscriptions.
    rows = (await db.execute(
        select(Plan.price_cents, Plan.interval, func.count(Subscription.id))
        .join(Subscription, Subscription.plan_code == Plan.code)
        .where(Subscription.status.in_(LIVE), Subscription.deleted_at.is_(None))
        .group_by(Plan.price_cents, Plan.interval)
    )).all()
    mrr = 0.0
    for price, interval, count in rows:
        monthly = price / 12.0 if interval == "year" else float(price)
        mrr += monthly * count
    mrr_dollars = round(mrr / 100.0, 2)

    by_plan = (await db.execute(
        select(Subscription.plan_code, func.count(Subscription.id))
        .where(Subscription.status.in_(LIVE), Subscription.deleted_at.is_(None))
        .group_by(Subscription.plan_code)
    )).all()
    canceled = (await db.execute(
        select(func.count(Subscription.id)).where(Subscription.canceled_at.is_not(None))
    )).scalar_one()
    active = (await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status.in_(LIVE))
    )).scalar_one()
    denom = (active + canceled) or 1
    return {
        "mrr": mrr_dollars, "arr": round(mrr_dollars * 12, 2),
        "active_subscriptions": int(active),
        "subscriptions_by_plan": {p: int(c) for p, c in by_plan},
        "churn_rate": round(canceled / denom, 4),
    }


async def operations_dashboard(db: AsyncSession) -> dict:
    job_rows = (await db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status))).all()
    jobs = {s: int(c) for s, c in job_rows}
    since = datetime.now(timezone.utc) - timedelta(days=30)
    tokens = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0))
        .where(UsageRecord.metric == "ai_tokens", UsageRecord.occurred_at >= since)
    )).scalar_one()
    ai_cost = round(int(tokens) / 1000.0 * settings.AI_COST_PER_1K_TOKENS, 4)
    return {
        "job_queue": jobs,
        "dead_letter": jobs.get("dead", 0),
        "ai_tokens_30d": int(tokens),
        "ai_cost_30d": ai_cost,
    }


async def security_dashboard(db: AsyncSession) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    def _count(action_like):
        return select(func.count(ActivityLog.id)).where(
            ActivityLog.created_at >= since, ActivityLog.action.like(action_like))
    failed = (await db.execute(_count("login.fail%"))).scalar_one()
    audit = (await db.execute(
        select(func.count(ActivityLog.id)).where(ActivityLog.created_at >= since)
    )).scalar_one()
    return {"failed_logins_7d": int(failed), "audit_events_7d": int(audit)}


async def system_metrics(db: AsyncSession) -> dict:
    active_tenants = (await db.execute(
        select(func.count(Company.id)).where(Company.status == CompanyStatus.active)
    )).scalar_one()
    return {
        "active_tenants": int(active_tenants),
        "total_users": int((await db.execute(select(func.count(User.id)))).scalar_one()),
        "total_conversations": int((await db.execute(select(func.count(Conversation.id)))).scalar_one()),
        "total_messages": int((await db.execute(select(func.count(Message.id)))).scalar_one()),
        "total_leads": int((await db.execute(select(func.count(Lead.id)))).scalar_one()),
    }
