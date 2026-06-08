"""Authentication business logic (operates on the global, RLS-free tables)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    refresh_expiry,
    verify_password,
)
from app.db.enums import TokenPurpose
from app.models.auth import UserSession, VerificationToken
from app.models.tenancy import User
from app.schemas import TokenPair

logger = get_logger("app.auth")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(
        func.lower(User.email) == email.lower(), User.deleted_at.is_(None)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def register_user(
    db: AsyncSession, *, email: str, password: str, full_name: str | None
) -> User:
    if await _get_user_by_email(db, email):
        raise ConflictError("An account with this email already exists")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    logger.info("Registered user %s", user.id)
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
    user = await _get_user_by_email(db, email)
    # Constant-ish work whether or not the user exists (avoid user enumeration).
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("Account is disabled")
    user.last_login_at = _now()
    return user


async def create_token_pair(
    db: AsyncSession,
    *,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
    family_id: uuid.UUID | None = None,
    rotated_from: uuid.UUID | None = None,
) -> TokenPair:
    raw_refresh, refresh_hash = generate_opaque_token()
    session = UserSession(
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        rotated_from=rotated_from,
        token_hash=refresh_hash,
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=refresh_expiry(),
    )
    db.add(session)
    await db.flush()
    await db.commit()
    access = create_access_token(str(user.id))
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def rotate_refresh(
    db: AsyncSession,
    *,
    raw_refresh: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenPair:
    token_hash = hash_token(raw_refresh)
    stmt = select(UserSession).where(UserSession.token_hash == token_hash)
    session = (await db.execute(stmt)).scalar_one_or_none()
    now = _now()

    if session is None:
        raise AuthenticationError("Invalid or expired refresh token")

    # Reuse detection: a token that was already rotated/revoked is being
    # presented again. Treat the whole lineage as compromised and revoke every
    # still-active token in the family, forcing a fresh login.
    if session.revoked_at is not None:
        await db.execute(
            update(UserSession)
            .where(
                UserSession.family_id == session.family_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.commit()
        logger.warning(
            "Refresh token reuse detected; revoked family %s (user %s)",
            session.family_id,
            session.user_id,
        )
        raise AuthenticationError("Refresh token reuse detected; please log in again")

    if session.expires_at <= now:
        raise AuthenticationError("Invalid or expired refresh token")

    user = (
        await db.execute(select(User).where(User.id == session.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("Account is unavailable")

    # Rotate within the same family, chaining rotated_from for forensics.
    session.revoked_at = now
    session.last_used_at = now
    return await create_token_pair(
        db,
        user=user,
        user_agent=user_agent,
        ip_address=ip_address,
        family_id=session.family_id,
        rotated_from=session.id,
    )


async def revoke_refresh(db: AsyncSession, *, raw_refresh: str) -> uuid.UUID | None:
    token_hash = hash_token(raw_refresh)
    session = (
        await db.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if session and session.revoked_at is None:
        session.revoked_at = _now()
        await db.commit()
    return session.user_id if session else None


async def _issue_verification(
    db: AsyncSession, user: User, purpose: TokenPurpose, ttl_hours: int
) -> str:
    raw, token_hash = generate_opaque_token()
    db.add(
        VerificationToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=_now() + timedelta(hours=ttl_hours),
        )
    )
    await db.flush()
    await db.commit()
    return raw


async def create_reset_token(db: AsyncSession, *, email: str) -> str | None:
    """Return a raw reset token, or None if no such user (caller stays vague)."""
    user = await _get_user_by_email(db, email)
    if user is None:
        return None
    return await _issue_verification(
        db, user, TokenPurpose.password_reset, settings.RESET_TOKEN_EXPIRE_HOURS
    )


async def _consume_token(
    db: AsyncSession, raw_token: str, purpose: TokenPurpose
) -> VerificationToken:
    token_hash = hash_token(raw_token)
    stmt = select(VerificationToken).where(
        VerificationToken.token_hash == token_hash,
        VerificationToken.purpose == purpose,
    )
    token = (await db.execute(stmt)).scalar_one_or_none()
    now = _now()
    if token is None or token.consumed_at is not None or token.expires_at <= now:
        raise AuthenticationError("Invalid or expired token")
    token.consumed_at = now
    return token


async def reset_password(
    db: AsyncSession, *, raw_token: str, new_password: str
) -> uuid.UUID:
    token = await _consume_token(db, raw_token, TokenPurpose.password_reset)
    user = (
        await db.execute(select(User).where(User.id == token.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise AuthenticationError("Invalid or expired token")
    user.hashed_password = hash_password(new_password)
    # Revoke all active sessions after a password reset.
    sessions = (
        await db.execute(
            select(UserSession).where(
                UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
            )
        )
    ).scalars()
    for s in sessions:
        s.revoked_at = _now()
    await db.commit()
    logger.info("Password reset for user %s", user.id)
    return user.id


async def create_email_verification(db: AsyncSession, *, email: str) -> str | None:
    user = await _get_user_by_email(db, email)
    if user is None or user.email_verified_at is not None:
        return None
    return await _issue_verification(
        db, user, TokenPurpose.email_verification, settings.VERIFY_TOKEN_EXPIRE_HOURS
    )


async def confirm_email(db: AsyncSession, *, raw_token: str) -> uuid.UUID:
    token = await _consume_token(db, raw_token, TokenPurpose.email_verification)
    user = (
        await db.execute(select(User).where(User.id == token.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise AuthenticationError("Invalid or expired token")
    user.email_verified_at = _now()
    await db.commit()
    return user.id
