"""Tenancy & RBAC models.

A *Company* is the tenant root. *Users* are global identities that join one or
more companies through *CompanyMember*. Authorization is permission-based:
*Permissions* are a global catalog, *Roles* bundle permissions (system roles are
company-agnostic; companies may define custom roles), and a membership is
assigned exactly one role.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.db.enums import CompanyStatus, MemberStatus


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Global user identity (not tenant-scoped)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["CompanyMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="CompanyMember.user_id",
    )

    __table_args__ = (
        # Case-insensitive uniqueness among live rows only (soft-delete safe).
        Index(
            "uq_users_email_active",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Company(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Tenant root."""

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[CompanyStatus] = mapped_column(
        PgEnum(CompanyStatus, name="company_status", create_type=False),
        nullable=False,
        server_default=CompanyStatus.active.value,
    )
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    members: Mapped[list["CompanyMember"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "uq_companies_slug_active",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global permission catalog, e.g. ``bots:create``, ``leads:export``."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("resource", "action"),)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A bundle of permissions.

    ``company_id IS NULL`` => system role available to every tenant.
    ``company_id`` set     => custom role owned by that tenant.
    """

    __tablename__ = "roles"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # System roles unique by slug globally; tenant roles unique within tenant.
        Index(
            "uq_roles_system_slug",
            "slug",
            unique=True,
            postgresql_where=text("company_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_roles_company_slug",
            "company_id",
            "slug",
            unique=True,
            postgresql_where=text("company_id IS NOT NULL AND deleted_at IS NULL"),
        ),
    )


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Role <-> Permission association."""

    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship()

    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)


class CompanyMember(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Membership of a user in a company, carrying their role."""

    __tablename__ = "company_members"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[MemberStatus] = mapped_column(
        PgEnum(MemberStatus, name="member_status", create_type=False),
        nullable=False,
        server_default=MemberStatus.invited.value,
    )
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(
        back_populates="memberships", foreign_keys=[user_id]
    )
    role: Mapped["Role"] = relationship()

    __table_args__ = (
        Index(
            "uq_company_members_company_user",
            "company_id",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
