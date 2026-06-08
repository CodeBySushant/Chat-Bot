"""Chatbot and widget configuration models."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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
from app.db.enums import ChatbotStatus


class Chatbot(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A configured assistant. Owns knowledge, conversations and leads."""

    __tablename__ = "chatbots"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ChatbotStatus] = mapped_column(
        PgEnum(ChatbotStatus, name="chatbot_status", create_type=False),
        nullable=False,
        server_default=ChatbotStatus.draft.value,
    )

    # Generation config
    system_prompt: Mapped[str | None] = mapped_column(Text)
    greeting: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'openai'")
    )
    model: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("'gpt-4o-mini'")
    )
    embedding_model: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("'text-embedding-3-small'")
    )
    temperature: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.20")
    )
    top_k: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("8")
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1024")
    )

    # Public widget key (publishable, scoped to chat only).
    public_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    widget_configuration: Mapped["WidgetConfiguration | None"] = relationship(
        back_populates="chatbot",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        Index(
            "uq_chatbots_company_slug",
            "company_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "temperature >= 0 AND temperature <= 2",
            name="temperature_range",
        ),
        CheckConstraint("top_k > 0 AND top_k <= 50", name="top_k_range"),
    )


class WidgetConfiguration(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """Embeddable widget appearance, behavior and security for one chatbot."""

    __tablename__ = "widget_configurations"

    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    theme: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    primary_color: Mapped[str] = mapped_column(
        String(9), nullable=False, server_default=text("'#2563eb'")
    )
    position: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'bottom-right'")
    )
    launcher_icon_url: Mapped[str | None] = mapped_column(String(1024))
    greeting: Mapped[str | None] = mapped_column(Text)
    suggested_prompts: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    lead_capture: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'en'")
    )
    # Origin allowlist enforced on every public widget request.
    allowed_domains: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )

    chatbot: Mapped["Chatbot"] = relationship(back_populates="widget_configuration")

    __table_args__ = (
        UniqueConstraint("chatbot_id", name="one_config_per_chatbot"),
    )
