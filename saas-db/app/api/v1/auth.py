"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, get_global_db, user_agent
from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.db.enums import ActorType
from app.schemas import (
    DevTokenResponse,
    EmailVerifyConfirm,
    EmailVerifyRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.services import audit, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register"))],
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_global_db)):
    user = await auth_service.register_user(
        db, email=body.email, password=body.password, full_name=body.full_name
    )
    return user


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit("login"))],
)
async def login(
    body: LoginRequest, request: Request, db: AsyncSession = Depends(get_global_db)
):
    user = await auth_service.authenticate(db, email=body.email, password=body.password)
    tokens = await auth_service.create_token_pair(
        db, user=user, user_agent=user_agent(request), ip_address=client_ip(request)
    )
    await audit.record_global(
        action="user.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    return tokens


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit("refresh"))],
)
async def refresh(
    body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_global_db)
):
    return await auth_service.rotate_refresh(
        db,
        raw_refresh=body.refresh_token,
        user_agent=user_agent(request),
        ip_address=client_ip(request),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest, request: Request, db: AsyncSession = Depends(get_global_db)
):
    user_id = await auth_service.revoke_refresh(db, raw_refresh=body.refresh_token)
    if user_id is not None:
        await audit.record_global(
            action="user.logout",
            actor_user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            ip=client_ip(request),
            user_agent=user_agent(request),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-reset/request",
    response_model=DevTokenResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("password_reset"))],
)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_global_db),
):
    raw = await auth_service.create_reset_token(db, email=body.email)
    await audit.record_global(
        action="user.password_reset_requested",
        actor_type=ActorType.system,
        ip=client_ip(request),
        user_agent=user_agent(request),
        changes={"email": body.email},
    )
    # Always respond the same way to avoid leaking which emails are registered.
    # In production the token is emailed; in dev we surface it for testing.
    return DevTokenResponse(
        detail="If that email exists, a reset link has been sent",
        dev_token=None if settings.is_production else raw,
    )


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_global_db),
):
    user_id = await auth_service.reset_password(
        db, raw_token=body.token, new_password=body.new_password
    )
    await audit.record_global(
        action="user.password_reset",
        actor_user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/verify-email/request",
    response_model=DevTokenResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_email_verification(
    body: EmailVerifyRequest, db: AsyncSession = Depends(get_global_db)
):
    raw = await auth_service.create_email_verification(db, email=body.email)
    return DevTokenResponse(
        detail="If that email needs verification, a link has been sent",
        dev_token=None if settings.is_production else raw,
    )


@router.post("/verify-email/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email_verification(
    body: EmailVerifyConfirm,
    request: Request,
    db: AsyncSession = Depends(get_global_db),
):
    user_id = await auth_service.confirm_email(db, raw_token=body.token)
    await audit.record_global(
        action="user.email_verified",
        actor_user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
