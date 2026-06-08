"""Conversation, Message, and Lead models.

``messages`` is range-partitioned by ``created_at`` because it is the
highest-volume table in the system. Partitioning requires the partition key to
be part of the primary key, hence the composite PK ``(id, created_at)``. Old
partitions can be detached and archived cheaply. Messages are immutable
(append-only): no ``updated_at``, no soft delete.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.db.enums import (
    ConversationChannel,
    ConversationStatus,
    LeadStatus,
    MessageRole,
)


class Conversation(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A chat session between a visitor and a chatbot."""

    __tablename__ = "conversations"

    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
    )
    visitor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    channel: Mapped[ConversationChannel] = mapped_column(
        PgEnum(ConversationChannel, name="conversation_channel", create_type=False),
        nullable=False,
        server_default=ConversationChannel.widget.value,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        PgEnum(ConversationStatus, name="conversation_status", create_type=False),
        nullable=False,
        server_default=ConversationStatus.open.value,
    )
    title: Mapped[str | None] = mapped_column(String(512))
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    lead: Mapped["Lead | None"] = relationship(
        back_populates="conversation", uselist=False
    )

    __table_args__ = (
        Index(
            "ix_conversations_company_chatbot_created",
            "company_id",
            "chatbot_id",
            "created_at",
        ),
    )


class Message(TenantMixin, Base):
    """A single message in a conversation. Partitioned by ``created_at``."""

    __tablename__ = "messages"

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
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        PgEnum(MessageRole, name="message_role", create_type=False), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    model: Mapped[str | None] = mapped_column(String(128))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retrieved_chunk_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    citations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    feedback: Mapped[int | None] = mapped_column(SmallInteger)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    conversation: Mapped["Conversation"] = relationship()

    __table_args__ = (
        CheckConstraint("feedback IN (-1, 0, 1)", name="feedback_range"),
        Index(
            "ix_messages_conversation_created", "conversation_id", "created_at"
        ),
        Index(
            "ix_messages_company_created", "company_id", "created_at"
        ),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )


class Lead(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A captured lead, optionally tied to the conversation it came from."""

    __tablename__ = "leads"

    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
    )
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[LeadStatus] = mapped_column(
        PgEnum(LeadStatus, name="lead_status", create_type=False),
        nullable=False,
        server_default=LeadStatus.new.value,
    )
    source: Mapped[str | None] = mapped_column(String(128))
    company: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    fields: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped["Conversation | None"] = relationship(back_populates="lead")

    __table_args__ = (
        # At most one lead per conversation (when linked).
        Index(
            "uq_leads_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text("conversation_id IS NOT NULL"),
        ),
        Index("ix_leads_company_status", "company_id", "status"),
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
    )
