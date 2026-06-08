"""Chatbot endpoints (documents are scoped to a chatbot)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import TenantContext, require_permission
from app.schemas import ChatbotCreate, ChatbotResponse
from app.services import chatbot_service, usage_service
from sqlalchemy import func, select
from app.models.bots import Chatbot

router = APIRouter(prefix="/companies/{company_id}/chatbots", tags=["chatbots"])


@router.post("", response_model=ChatbotResponse, status_code=status.HTTP_201_CREATED)
async def create_chatbot(
    body: ChatbotCreate,
    ctx: TenantContext = Depends(require_permission("bots:create")),
):
    count = (await ctx.db.execute(
        select(func.count(Chatbot.id)).where(Chatbot.deleted_at.is_(None))
    )).scalar_one()
    await usage_service.check_quota(ctx.db, company_id=ctx.company.id, metric="chatbots", current=int(count))
    bot = await chatbot_service.create_chatbot(
        ctx.db, company_id=ctx.company.id, name=body.name, slug=body.slug
    )
    # create_chatbot commits, which clears the transaction-local GUC; re-assert it
    # so the metering insert passes RLS.
    from sqlalchemy import text
    await ctx.db.execute(
        text("SELECT set_config('app.current_company', :cid, true)"),
        {"cid": str(ctx.company.id)},
    )
    await usage_service.record_usage(ctx.db, company_id=ctx.company.id, metric="chatbots", chatbot_id=bot.id)
    await ctx.db.commit()
    return bot


@router.get("", response_model=list[ChatbotResponse])
async def list_chatbots(
    ctx: TenantContext = Depends(require_permission("bots:read")),
):
    return await chatbot_service.list_chatbots(ctx.db)
