"""FastAPI dependency-injection providers."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDenied
from app.db.enums import CompanyStatus, MemberStatus
from app.db.session import AdminSessionFactory, SessionFactory
from app.core.security import decode_access_token
from app.models.tenancy import CompanyMember, Company, Role, User
from app.services import company_service

bearer_scheme = HTTPBearer(auto_error=False)


# ---- Session providers ----
async def get_global_db() -> AsyncIterator[AsyncSession]:
    """app_rw session, no tenant context (global / RLS-free tables)."""
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_admin_db() -> AsyncIterator[AsyncSession]:
    """BYPASSRLS session for bootstrap operations."""
    async with AdminSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ---- Current user ----
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_global_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token subject") from exc

    user = (
        await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is disabled")
    return user


# ---- Tenant context ----
@dataclass
class TenantContext:
    db: AsyncSession
    user: User
    company: Company
    member: CompanyMember
    role_slug: str
    permissions: list[str]

    def has(self, code: str) -> bool:
        return code in self.permissions


def _company_id_from_path(request: Request) -> uuid.UUID:
    raw = request.path_params.get("company_id")
    if raw is None:
        raise NotFoundError("Company not specified")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise NotFoundError("Invalid company id") from exc


async def get_tenant_context(
    request: Request,
    user: User = Depends(get_current_user),
) -> AsyncIterator[TenantContext]:
    """Open a tenant-scoped (RLS) session and verify the user's membership.

    The tenant GUC is set first; RLS then scopes every read to that company, so
    the membership lookup itself is the authorization gate -- setting an
    arbitrary company id in the URL grants nothing without a real membership row.
    """
    company_id = _company_id_from_path(request)
    async with SessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_company', :cid, true)"),
            {"cid": str(company_id)},
        )
        member = (
            await db.execute(
                select(CompanyMember).where(
                    CompanyMember.user_id == user.id,
                    CompanyMember.deleted_at.is_(None),
                    CompanyMember.status == MemberStatus.active,
                )
            )
        ).scalar_one_or_none()
        if member is None:
            raise PermissionDenied("You are not an active member of this company")

        company = (
            await db.execute(select(Company).where(Company.id == company_id))
        ).scalar_one_or_none()
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Company not found")
        if company.status != CompanyStatus.active:
            raise PermissionDenied("This company is not active")

        role = (
            await db.execute(select(Role).where(Role.id == member.role_id))
        ).scalar_one_or_none()
        permissions = await company_service.load_permissions(db, role_id=member.role_id)

        ctx = TenantContext(
            db=db,
            user=user,
            company=company,
            member=member,
            role_slug=role.slug if role else "unknown",
            permissions=permissions,
        )
        try:
            yield ctx
        except Exception:
            await db.rollback()
            raise


def require_permission(code: str):
    """Dependency factory enforcing a permission within the tenant context."""

    async def _checker(
        ctx: TenantContext = Depends(get_tenant_context),
    ) -> TenantContext:
        if not ctx.has(code):
            raise PermissionDenied(f"Missing required permission: {code}")
        return ctx

    return _checker


# ---- Request metadata helpers ----
def client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


# ---- Platform super-admin ----
@dataclass
class AdminContext:
    user: User
    db: AsyncSession


async def require_superuser(
    user: User = Depends(get_current_user),
) -> AsyncIterator[AdminContext]:
    """Gate platform-admin endpoints. Provides a BYPASSRLS admin session
    (cross-tenant by design). Only users with is_superuser pass."""
    if not getattr(user, "is_superuser", False):
        raise PermissionDenied("Super-admin privileges required")
    async with AdminSessionFactory() as db:
        yield AdminContext(user=user, db=db)
