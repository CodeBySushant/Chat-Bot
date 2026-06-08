"""Tenant analytics dashboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import TenantContext, require_permission
from app.services import analytics_service

router = APIRouter(prefix="/companies/{company_id}/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(require_permission("analytics:read")),
    days: int = Query(default=30, ge=1, le=365),
):
    return await analytics_service.tenant_dashboard(ctx.db, company_id=ctx.company.id, days=days)
