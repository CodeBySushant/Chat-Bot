"""Billing and programmatic-access models: Subscription, Invoice, ApiKey."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.db.enums import InvoiceStatus, SubscriptionStatus


class Subscription(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A company's plan subscription (mirrors the billing provider)."""

    __tablename__ = "subscriptions"

    plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        PgEnum(SubscriptionStatus, name="subscription_status", create_type=False),
        nullable=False,
        server_default=SubscriptionStatus.trialing.value,
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'stripe'")
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True
    )
    seats: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    limits: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="subscription")

    __table_args__ = (
        # At most one live (non-canceled) subscription per company.
        Index(
            "uq_subscriptions_company_live",
            "company_id",
            unique=True,
            postgresql_where=text(
                "status IN ('trialing','active','past_due') AND deleted_at IS NULL"
            ),
        ),
    )


class Invoice(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A billing invoice."""

    __tablename__ = "invoices"

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        index=True,
    )
    number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        PgEnum(InvoiceStatus, name="invoice_status", create_type=False),
        nullable=False,
        server_default=InvoiceStatus.draft.value,
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'USD'")
    )
    amount_due: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    amount_paid: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    provider_invoice_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    line_items: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="invoices"
    )

    __table_args__ = (
        Index("ix_invoices_company_status", "company_id", "status"),
    )


class ApiKey(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A hashed programmatic API key for a tenant."""

    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Plaintext is shown once at creation; only the hash is stored.
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_api_keys_company_active", "company_id", "revoked_at"),
    )


class Plan(Base):
    """Global plan catalog (no tenant; read-only to app_rw)."""
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    interval: Mapped[str] = mapped_column(String(8), nullable=False, server_default=text("'month'"))
    entitlements: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UsageCounter(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Per-company, per-metric aggregate for the current billing period."""
    __tablename__ = "usage_counters"

    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("company_id", "metric", "period_start", name="uq_usage_counter"),)


class UsageRecord(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Append-only metering events (source of truth for usage aggregation)."""
    __tablename__ = "usage_records"

    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
