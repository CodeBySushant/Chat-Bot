"""Concrete background tasks: rollups, usage aggregation, invoicing, sync, cleanup."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import AdminSessionFactory, tenant_session
from app.services import analytics_service
from app.services.jobs.registry import task

logger = get_logger("app.jobs")


@task("analytics_rollup")
async def analytics_rollup(payload: dict) -> None:
    company_id = uuid.UUID(payload["company_id"])
    day = date.fromisoformat(payload["day"]) if payload.get("day") else datetime.now(timezone.utc).date()
    async with tenant_session(company_id) as db:
        await analytics_service.rollup_day(db, company_id=company_id, day=day)


@task("usage_aggregation")
async def usage_aggregation(payload: dict) -> None:
    """Recompute the current-period counter for a company+metric from records
    (self-healing if a real-time increment was missed)."""
    company_id = uuid.UUID(payload["company_id"])
    metric = payload["metric"]
    from app.services.billing.entitlements import period_bounds
    start, end = period_bounds()
    async with tenant_session(company_id) as db:
        await db.execute(text(
            "INSERT INTO usage_counters (company_id, metric, period_start, period_end, value) "
            "SELECT :cid, :m, :s, :e, COALESCE(SUM(quantity),0) FROM usage_records "
            "WHERE company_id=:cid AND metric=:m AND occurred_at >= :s "
            "ON CONFLICT (company_id, metric, period_start) "
            "DO UPDATE SET value=EXCLUDED.value, updated_at=now()"
        ), {"cid": str(company_id), "m": metric, "s": start, "e": end})
        await db.commit()


@task("invoice_generation")
async def invoice_generation(payload: dict) -> None:
    """Generate a draft invoice for a subscription period (simplified)."""
    company_id = uuid.UUID(payload["company_id"])
    async with tenant_session(company_id) as db:
        await db.execute(text(
            "INSERT INTO invoices (company_id, number, status, currency, amount_due) "
            "VALUES (:cid, :num, 'draft', 'USD', :amt)"
        ), {"cid": str(company_id), "num": f"INV-{uuid.uuid4().hex[:12].upper()}",
            "amt": payload.get("amount_due", 0)})
        await db.commit()


@task("billing_sync")
async def billing_sync(payload: dict) -> None:
    from app.services.billing.providers import get_billing_provider
    get_billing_provider()  # production: reconcile provider state -> subscriptions
    logger.info("billing_sync ran for %s", payload.get("company_id"))


@task("cleanup")
async def cleanup(payload: dict) -> None:
    """Retention: drop analytics events + dead jobs older than the window."""
    days = int(payload.get("retain_days", 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with AdminSessionFactory() as db:
        await db.execute(text("DELETE FROM analytics_events WHERE occurred_at < :c"), {"c": cutoff})
        await db.execute(text("DELETE FROM jobs WHERE status IN ('succeeded','dead') AND updated_at < :c"), {"c": cutoff})
        await db.commit()


@task("_test_fail")
async def _test_fail(payload: dict) -> None:
    raise RuntimeError("intentional failure for retry/DLQ test")
