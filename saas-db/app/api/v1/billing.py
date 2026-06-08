"""Billing + subscription endpoints (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import TenantContext, require_permission
from app.schemas import ChangePlanRequest, PlanResponse, SubscriptionResponse
from app.services import billing_service, usage_service
from app.services.billing.entitlements import active_plan_code, get_entitlements

router = APIRouter(prefix="/companies/{company_id}/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(ctx: TenantContext = Depends(require_permission("billing:read"))):
    return await billing_service.list_plans(ctx.db)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(ctx: TenantContext = Depends(require_permission("billing:read"))):
    code = await active_plan_code(ctx.db, ctx.company.id)
    ent = await get_entitlements(ctx.db, ctx.company.id)
    usage = await usage_service.current_usage(ctx.db, ctx.company.id)
    sub = await billing_service.get_live_subscription(ctx.db, ctx.company.id)
    return SubscriptionResponse(
        plan_code=code,
        status=sub.status.value if sub else "none",
        entitlements=ent, usage=usage,
        current_period_end=sub.current_period_end if sub else None,
    )


@router.post("/subscribe", response_model=SubscriptionResponse)
async def change_plan(body: ChangePlanRequest, ctx: TenantContext = Depends(require_permission("billing:manage"))):
    await billing_service.change_plan(ctx.db, company_id=ctx.company.id, plan_code=body.plan_code)
    ent = await get_entitlements(ctx.db, ctx.company.id)
    usage = await usage_service.current_usage(ctx.db, ctx.company.id)
    sub = await billing_service.get_live_subscription(ctx.db, ctx.company.id)
    resp = SubscriptionResponse(
        plan_code=body.plan_code, status=sub.status.value if sub else "active",
        entitlements=ent, usage=usage, current_period_end=sub.current_period_end if sub else None,
    )
    await ctx.db.commit()
    return resp


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel(ctx: TenantContext = Depends(require_permission("billing:manage"))):
    sub = await billing_service.cancel_subscription(ctx.db, company_id=ctx.company.id, at_period_end=True)
    ent = await get_entitlements(ctx.db, ctx.company.id)
    usage = await usage_service.current_usage(ctx.db, ctx.company.id)
    resp = SubscriptionResponse(
        plan_code=sub.plan_code, status=sub.status.value, entitlements=ent,
        usage=usage, current_period_end=sub.current_period_end,
    )
    await ctx.db.commit()
    return resp
