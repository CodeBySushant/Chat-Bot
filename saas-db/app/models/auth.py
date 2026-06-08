"""Authentication lifecycle models (global, not tenant-scoped).

UserSession backs revocable refresh tokens (only the SHA-256 hash is stored).
VerificationToken backs password-reset and email-verification flows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.enums import TokenPurpose


class UserSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A refresh-token session. Rotated on every refresh; revocable."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Lineage: all refresh tokens minted from one login share a family_id.
    # rotated_from points at the token this one replaced (audit/forensics).
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rotated_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_sessions.id", ondelete="SET NULL")
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(INET)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_user_sessions_user_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_user_sessions_family_id", "family_id"),
        Index(
            "ix_user_sessions_family_active",
            "family_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class VerificationToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Single-use token for password reset / email verification."""

    __tablename__ = "verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[TokenPurpose] = mapped_column(
        PgEnum(TokenPurpose, name="token_purpose", create_type=False),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_verification_tokens_user_purpose", "user_id", "purpose"),
    )
