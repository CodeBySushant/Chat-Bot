"""Company and membership endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    TenantContext,
    client_ip,
    get_admin_db,
    get_current_user,
    get_tenant_context,
    require_permission,
    user_agent,
)
from app.models.tenancy import User
from app.schemas import (
    CompanyCreate,
    CompanyResponse,
    MemberAddRequest,
    MemberResponse,
    MembershipSummary,
    RoleContextResponse,
)
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CompanyCreate,
    request: Request,
    user: User = Depends(get_current_user),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    company = await company_service.create_company(
        admin_db,
        user=user,
        name=body.name,
        slug=body.slug,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    return company


@router.get("", response_model=list[MembershipSummary])
async def list_my_companies(
    user: User = Depends(get_current_user),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    rows = await company_service.list_user_companies(admin_db, user_id=user.id)
    return [MembershipSummary(**r) for r in rows]


@router.get("/{company_id}/me", response_model=RoleContextResponse)
async def my_role(ctx: TenantContext = Depends(get_tenant_context)):
    return RoleContextResponse(
        company_id=ctx.company.id,
        role_slug=ctx.role_slug,
        permissions=ctx.permissions,
    )


@router.get("/{company_id}/members", response_model=list[MemberResponse])
async def list_members(
    ctx: TenantContext = Depends(require_permission("members:invite")),
):
    rows = await company_service.list_members(ctx.db, company_id=ctx.company.id)
    return [MemberResponse(**r) for r in rows]


@router.post(
    "/{company_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    body: MemberAddRequest,
    request: Request,
    ctx: TenantContext = Depends(require_permission("members:invite")),
):
    member = await company_service.add_member(
        ctx.db,
        company_id=ctx.company.id,
        email=body.email,
        role_slug=body.role_slug,
        actor_user_id=ctx.user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    return MemberResponse(**member)
