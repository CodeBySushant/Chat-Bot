"""Current-user endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db, get_current_user
from app.models.tenancy import User
from app.schemas import MeResponse, MembershipSummary, UserResponse
from app.services import company_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: User = Depends(get_current_user),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    companies = await company_service.list_user_companies(admin_db, user_id=user.id)
    return MeResponse(
        user=UserResponse.model_validate(user),
        memberships=[MembershipSummary(**c) for c in companies],
    )
