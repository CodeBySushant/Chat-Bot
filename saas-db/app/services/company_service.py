"""Company and membership business logic."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.core.logging import get_logger
from app.db.enums import MemberStatus
from app.models.tenancy import (
    Company,
    CompanyMember,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.services import audit

logger = get_logger("app.company")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _system_role(db: AsyncSession, slug: str) -> Role:
    role = (
        await db.execute(
            select(Role).where(
                Role.slug == slug,
                Role.is_system.is_(True),
                Role.company_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if role is None:
        raise NotFoundError(f"System role '{slug}' is not configured")
    return role


async def create_company(
    admin_db: AsyncSession,
    *,
    user: User,
    name: str,
    slug: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Company:
    """Create a company and make the creator its owner (bootstrap, BYPASSRLS)."""
    exists = (
        await admin_db.execute(
            select(Company.id).where(
                Company.slug == slug, Company.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise ConflictError("A company with this slug already exists")

    company = Company(name=name, slug=slug)
    admin_db.add(company)
    await admin_db.flush()

    owner = await _system_role(admin_db, "owner")
    admin_db.add(
        CompanyMember(
            company_id=company.id,
            user_id=user.id,
            role_id=owner.id,
            status=MemberStatus.active,
            joined_at=_now(),
        )
    )
    await admin_db.flush()
    await audit.record(
        admin_db,
        action="company.created",
        actor_user_id=user.id,
        company_id=company.id,
        resource_type="company",
        resource_id=company.id,
        ip=ip,
        user_agent=user_agent,
        changes={"name": name, "slug": slug},
    )
    await admin_db.commit()
    logger.info("Company %s created by user %s", company.id, user.id)
    return company


async def list_user_companies(admin_db: AsyncSession, *, user_id: uuid.UUID) -> list[dict]:
    """List the companies a user belongs to (cross-tenant bootstrap query)."""
    stmt = (
        select(Company, Role.slug, CompanyMember.status)
        .join(CompanyMember, CompanyMember.company_id == Company.id)
        .join(Role, Role.id == CompanyMember.role_id)
        .where(
            CompanyMember.user_id == user_id,
            CompanyMember.deleted_at.is_(None),
            Company.deleted_at.is_(None),
        )
        .order_by(Company.created_at)
    )
    rows = (await admin_db.execute(stmt)).all()
    return [
        {
            "company_id": c.id,
            "company_name": c.name,
            "company_slug": c.slug,
            "role_slug": role_slug,
            "status": status.value if hasattr(status, "value") else status,
        }
        for c, role_slug, status in rows
    ]


async def add_member(
    tenant_db: AsyncSession,
    *,
    company_id: uuid.UUID,
    email: str,
    role_slug: str,
    actor_user_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Add an existing user to the current tenant with a system role."""
    user = (
        await tenant_db.execute(
            select(User).where(
                func.lower(User.email) == email.lower(), User.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("No user with that email exists")

    role = await _system_role(tenant_db, role_slug)
    member = CompanyMember(
        company_id=company_id,
        user_id=user.id,
        role_id=role.id,
        status=MemberStatus.active,
        invited_by_id=actor_user_id,
        joined_at=_now(),
    )
    tenant_db.add(member)
    try:
        await tenant_db.flush()
        # Capture everything needed for the response BEFORE committing, because
        # the commit clears the transaction-local RLS GUC.
        result = {
            "id": member.id,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role_slug": role.slug,
            "status": member.status.value,
        }
        # Audit row shares the tenant transaction (company_id matches the GUC,
        # so it satisfies the forced RLS WITH CHECK).
        await audit.record(
            tenant_db,
            action="member.created",
            actor_user_id=actor_user_id,
            company_id=company_id,
            resource_type="company_member",
            resource_id=member.id,
            ip=ip,
            user_agent=user_agent,
            changes={"email": user.email, "role_slug": role.slug},
        )
        await tenant_db.commit()
    except IntegrityError as exc:
        raise ConflictError("User is already a member of this company") from exc
    return result


async def list_members(tenant_db: AsyncSession, *, company_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(CompanyMember, User, Role.slug)
        .join(User, User.id == CompanyMember.user_id)
        .join(Role, Role.id == CompanyMember.role_id)
        .where(CompanyMember.deleted_at.is_(None))
        .order_by(CompanyMember.created_at)
    )
    rows = (await tenant_db.execute(stmt)).all()
    return [
        {
            "id": m.id,
            "user_id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role_slug": role_slug,
            "status": m.status.value,
        }
        for m, u, role_slug in rows
    ]


async def load_permissions(tenant_db: AsyncSession, *, role_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return list((await tenant_db.execute(stmt)).scalars())
