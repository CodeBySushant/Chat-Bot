"""Lead management endpoints (tenant-scoped, permission-gated)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse

from app.api.deps import TenantContext, require_permission
from app.schemas import (
    LeadAssign, LeadCreate, LeadListResponse, LeadNoteCreate, LeadResponse, LeadUpdate,
)
from app.services import lead_service
from app.repositories import leads_repo

router = APIRouter(prefix="/companies/{company_id}/leads", tags=["leads"])


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(body: LeadCreate, ctx: TenantContext = Depends(require_permission("leads:create"))):
    return await lead_service.create_lead(
        ctx.db, company_id=ctx.company.id, chatbot_id=body.chatbot_id, name=body.name,
        email=body.email, phone=body.phone, company=body.company, source=body.source,
        tags=body.tags, metadata=body.metadata, actor_user_id=ctx.user.id,
    )


@router.get("", response_model=LeadListResponse)
async def list_leads(
    ctx: TenantContext = Depends(require_permission("leads:read")),
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_to: uuid.UUID | None = None,
    chatbot_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total = await lead_service.list_leads(
        ctx.db, status=status_filter, assigned_to=assigned_to, chatbot_id=chatbot_id,
        q=q, limit=limit, offset=offset,
    )
    return LeadListResponse(total=total, items=items)


@router.get("/export", response_class=PlainTextResponse)
async def export_leads(ctx: TenantContext = Depends(require_permission("leads:export"))):
    csv_text = await lead_service.export_csv(ctx.db)
    return PlainTextResponse(
        csv_text, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/analytics")
async def lead_analytics(ctx: TenantContext = Depends(require_permission("analytics:read"))):
    return await lead_service.analytics(ctx.db)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads:read"))):
    lead = await leads_repo.get(ctx.db, lead_id)
    if lead is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: uuid.UUID, body: LeadUpdate, ctx: TenantContext = Depends(require_permission("leads:update"))):
    return await lead_service.update_lead(
        ctx.db, company_id=ctx.company.id, lead_id=lead_id,
        changes=body.model_dump(exclude_unset=True), actor_user_id=ctx.user.id,
    )


@router.post("/{lead_id}/assign", response_model=LeadResponse)
async def assign_lead(lead_id: uuid.UUID, body: LeadAssign, ctx: TenantContext = Depends(require_permission("leads:assign"))):
    return await lead_service.assign_lead(
        ctx.db, company_id=ctx.company.id, lead_id=lead_id,
        assignee_id=body.assignee_id, actor_user_id=ctx.user.id,
    )


@router.post("/{lead_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(lead_id: uuid.UUID, body: LeadNoteCreate, ctx: TenantContext = Depends(require_permission("leads:update"))):
    note = await lead_service.add_note(
        ctx.db, company_id=ctx.company.id, lead_id=lead_id, body=body.body, author_id=ctx.user.id,
    )
    return {"id": str(note.id), "body": note.body, "created_at": note.created_at.isoformat()}


@router.get("/{lead_id}/timeline")
async def timeline(lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads:read"))):
    acts = await lead_service.timeline(ctx.db, lead_id=lead_id)
    return [{"id": str(a.id), "activity_type": a.activity_type, "description": a.description,
             "data": a.data, "created_at": a.created_at.isoformat()} for a in acts]
