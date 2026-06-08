"""Security primitives: password hashing, JWT access tokens, opaque tokens."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

# bcrypt caps input at 72 bytes; we hash longer inputs down first so the full
# password contributes entropy instead of being silently truncated.
_BCRYPT_MAX = 72


def _prepare(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX:
        raw = hashlib.sha256(raw).hexdigest().encode("utf-8")
    return raw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, *, extra: dict | None = None) -> str:
    now = _now()
    payload = {
        "sub": str(subject),
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=settings.JWT_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Access token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthenticationError("Invalid token audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthenticationError("Invalid token issuer") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid access token") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    return payload


def generate_opaque_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is persisted."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
