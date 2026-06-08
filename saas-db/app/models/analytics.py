"""Analytics & audit models.

``analytics_events`` (raw telemetry) and ``activity_logs`` (audit trail) are
append-only and range-partitioned by time. ``analytics_daily`` is a
pre-aggregated rollup the dashboards read from, so the read path never scans raw
events.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.enums import ActorType


class AnalyticsEvent(TenantMixin, Base):
    """Raw event telemetry. Partitioned by ``occurred_at``."""

    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=func.now(),
    )
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chatbots.id", ondelete="SET NULL")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    visitor_id: Mapped[str | None] = mapped_column(String(64))
    session_id: Mapped[str | None] = mapped_column(String(64))
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_analytics_events_company_type_time",
            "company_id",
            "event_type",
            "occurred_at",
        ),
        Index(
            "ix_analytics_events_chatbot_time", "chatbot_id", "occurred_at"
        ),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )


class AnalyticsDaily(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Daily rollup per chatbot, populated by a scheduled worker."""

    __tablename__ = "analytics_daily"

    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chatbots.id", ondelete="CASCADE")
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    conversations_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    messages_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    leads_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "chatbot_id", "day", name="rollup_grain"
        ),
        Index("ix_analytics_daily_company_day", "company_id", "day"),
    )


class ActivityLog(Base):
    """Append-only audit trail. Partitioned by ``created_at``.

    ``company_id`` is nullable: platform-level events (e.g. global admin
    actions) are not tied to a tenant, so this model does not use TenantMixin.
    """

    __tablename__ = "activity_logs"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=func.now(),
    )
    actor_type: Mapped[ActorType] = mapped_column(
        PgEnum(ActorType, name="actor_type", create_type=False), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    changes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        Index(
            "ix_activity_logs_company_created", "company_id", "created_at"
        ),
        Index(
            "ix_activity_logs_resource", "resource_type", "resource_id"
        ),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )
