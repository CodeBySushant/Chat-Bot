"""Audit logging to ``activity_logs``.

Two entry points:

* ``record(session, ...)`` adds an audit row to an *existing* transaction so it
  commits atomically with the action. Used for company/member creation, where a
  suitable session is already open (admin session for company creation; the
  tenant RLS session for member creation, whose GUC satisfies the WITH CHECK).
* ``record_global(...)`` opens its own BYPASSRLS admin transaction and commits
  immediately, best-effort. Used for tenant-less auth events (login, logout,
  password reset, email verification) whose ``company_id`` is NULL and therefore
  cannot pass the forced RLS WITH CHECK as the ``app_rw`` role.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.enums import ActorType
from app.db.session import AdminSessionFactory
from app.models.analytics import ActivityLog

logger = get_logger("app.audit")


async def record(
    session: AsyncSession,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    actor_type: ActorType = ActorType.user,
    company_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    changes: dict | None = None,
) -> None:
    """Stage an audit row on an existing session (caller commits)."""
    session.add(
        ActivityLog(
            company_id=company_id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip,
            user_agent=user_agent,
            changes=changes or {},
        )
    )
    await session.flush()


async def record_global(
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    actor_type: ActorType = ActorType.user,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    changes: dict | None = None,
) -> None:
    """Write a tenant-less audit row in its own transaction (best-effort)."""
    try:
        async with AdminSessionFactory() as session:
            await record(
                session,
                action=action,
                actor_user_id=actor_user_id,
                actor_type=actor_type,
                company_id=None,
                resource_type=resource_type,
                resource_id=resource_id,
                ip=ip,
                user_agent=user_agent,
                changes=changes,
            )
            await session.commit()
    except Exception:
        # Audit must never break the primary flow; surface for ops instead.
        logger.exception("Failed to write audit event %s", action)
