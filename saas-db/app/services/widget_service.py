"""Public widget backend: resolves a chatbot by its public key (no user JWT),
enforces the per-widget domain allowlist, and captures leads.

Authentication for the widget is the chatbot's ``public_key`` plus an optional
domain allowlist checked against the request Origin/Referer. Tenant context is
established server-side from the resolved company id, so the public surface never
trusts a client-supplied company/chatbot id.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDenied
from app.core.logging import get_logger
from app.db.enums import ChatbotStatus, LeadStatus
from app.db.session import AdminSessionFactory, tenant_session
from app.models.bots import Chatbot, WidgetConfiguration
from app.models.chat import Lead

logger = get_logger("app.widget")

DEFAULT_PRIMARY = "#e8590c"  # ember


@dataclass
class WidgetContext:
    chatbot_id: uuid.UUID
    company_id: uuid.UUID
    chatbot_name: str
    greeting: str
    primary_color: str
    position: str
    suggested_prompts: list
    lead_capture: dict
    locale: str
    launcher_icon_url: str | None
    allowed_domains: list[str]
    show_branding: bool


async def resolve_public_key(public_key: str) -> WidgetContext:
    """Look up an active chatbot + its widget config by public key (BYPASSRLS)."""
    async with AdminSessionFactory() as db:
        row = (
            await db.execute(
                select(Chatbot, WidgetConfiguration)
                .outerjoin(WidgetConfiguration, WidgetConfiguration.chatbot_id == Chatbot.id)
                .where(Chatbot.public_key == public_key, Chatbot.deleted_at.is_(None))
            )
        ).first()

    if row is None:
        raise NotFoundError("Unknown widget key")
    chatbot, cfg = row
    if chatbot.status != ChatbotStatus.active:
        raise PermissionDenied("This chatbot is not published")
    if cfg is not None and not cfg.is_enabled:
        raise PermissionDenied("This widget is disabled")

    greeting = (cfg.greeting if cfg and cfg.greeting else None) or chatbot.greeting or "Hi! How can I help you today?"
    return WidgetContext(
        chatbot_id=chatbot.id,
        company_id=chatbot.company_id,
        chatbot_name=chatbot.name,
        greeting=greeting,
        primary_color=(cfg.primary_color if cfg else None) or DEFAULT_PRIMARY,
        position=(cfg.position if cfg else None) or "bottom-right",
        suggested_prompts=(cfg.suggested_prompts if cfg else None) or [],
        lead_capture=(cfg.lead_capture if cfg else None) or {},
        locale=(cfg.locale if cfg else None) or "en",
        launcher_icon_url=cfg.launcher_icon_url if cfg else None,
        allowed_domains=(cfg.allowed_domains if cfg else None) or [],
        show_branding=True,
    )


def _host(value: str | None) -> str | None:
    if not value:
        return None
    try:
        netloc = urlparse(value).netloc or value
        return netloc.split(":")[0].lower().lstrip(".")
    except ValueError:
        return None


def origin_allowed(allowed_domains: list[str], origin: str | None, referer: str | None) -> bool:
    """Empty allowlist => allow all. Otherwise the Origin/Referer host must match
    an allowed domain (suffix match so sub.example.com matches example.com)."""
    if not allowed_domains:
        return True
    host = _host(origin) or _host(referer)
    if not host:
        return False
    for raw in allowed_domains:
        dom = _host(raw) or raw.lower().lstrip(".")
        if host == dom or host.endswith("." + dom):
            return True
    return False


async def capture_lead(
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    name: str | None,
    email: str | None,
    phone: str | None,
    fields: dict | None,
) -> uuid.UUID:
    # Route through the lead service so the widget capture also logs a timeline
    # activity, meters usage, and enforces the lead quota.
    from app.services import lead_service

    async with tenant_session(company_id) as db:  # type: AsyncSession
        lead = await lead_service.create_lead(
            db, company_id=company_id, chatbot_id=chatbot_id, conversation_id=conversation_id,
            name=name, email=email, phone=phone, source="widget", metadata=fields or {},
        )
        return lead.id
