"""Platform super-admin endpoints (require_superuser; BYPASSRLS, cross-tenant)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminContext, require_superuser
from app.schemas import TenantStatusUpdate
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tenants")
async def tenants(ctx: AdminContext = Depends(require_superuser),
                  limit: int = Query(default=100, ge=1, le=500), offset: int = 0):
    return await admin_service.list_tenants(ctx.db, limit=limit, offset=offset)


@router.patch("/tenants/{company_id}/status")
async def set_status(company_id: uuid.UUID, body: TenantStatusUpdate,
                     ctx: AdminContext = Depends(require_superuser)):
    await admin_service.set_tenant_status(ctx.db, company_id=company_id, status=body.status)
    return {"company_id": str(company_id), "status": body.status}


@router.get("/dashboards/revenue")
async def revenue(ctx: AdminContext = Depends(require_superuser)):
    return await admin_service.revenue_dashboard(ctx.db)


@router.get("/dashboards/operations")
async def operations(ctx: AdminContext = Depends(require_superuser)):
    return await admin_service.operations_dashboard(ctx.db)


@router.get("/dashboards/security")
async def security(ctx: AdminContext = Depends(require_superuser)):
    return await admin_service.security_dashboard(ctx.db)


@router.get("/metrics")
async def metrics(ctx: AdminContext = Depends(require_superuser)):
    return await admin_service.system_metrics(ctx.db)
