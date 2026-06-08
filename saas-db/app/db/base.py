"""Declarative base, metadata naming convention, and shared model mixins.

Every table in the schema is built from a predictable set of mixins so that
audit fields, soft-delete, UUID primary keys and the tenant discriminator are
guaranteed to be present and consistent across the whole database.

A strict naming convention is attached to the MetaData so that Alembic
autogenerate produces deterministic, human-readable constraint/index names
(e.g. ``fk_documents_chatbot_id_chatbots`` instead of an opaque hash).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Deterministic naming so migrations are stable and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """UUID v4 primary key generated in the database (``gen_random_uuid()``)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """``created_at`` / ``updated_at`` audit columns.

    ``updated_at`` is maintained by both SQLAlchemy (``onupdate``) and a
    database trigger (``set_updated_at``) so that raw SQL writes also keep it
    accurate.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CreatedAtMixin:
    """Single ``created_at`` column for append-only tables (events, logs)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SoftDeleteMixin:
    """Soft-delete marker. ``NULL`` == live row, timestamp == deleted."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class TenantMixin:
    """Mandatory, non-null tenant discriminator.

    ``company_id`` is the partition key of the multi-tenant model. It carries
    an ``ON DELETE CASCADE`` foreign key so that hard-deleting a company purges
    all of its data (used for account closure / GDPR erasure), and it is
    indexed because *every* tenant-scoped query filters on it.
    """

    @declared_attr.directive
    def company_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
