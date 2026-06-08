"""Lead management: capture, manual create, update, assign, notes, timeline,
search/filter, export, analytics. Every mutation logs an activity and meters usage."""
from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.enums import ActorType, LeadStatus
from app.models.chat import Lead
from app.models.crm import LeadActivity, LeadNote
from app.repositories import leads_repo
from app.services import usage_service


async def _activity(db, *, company_id, lead_id, activity_type, description=None,
                    actor_user_id=None, data=None):
    db.add(LeadActivity(
        company_id=company_id, lead_id=lead_id,
        actor_type=ActorType.user if actor_user_id else ActorType.system,
        actor_user_id=actor_user_id, activity_type=activity_type,
        description=description, data=data or {},
    ))


async def create_lead(
    db: AsyncSession, *, company_id: uuid.UUID, chatbot_id: uuid.UUID,
    name=None, email=None, phone=None, company=None, source="manual",
    conversation_id=None, tags=None, metadata=None, actor_user_id=None,
) -> Lead:
    await usage_service.check_quota(db, company_id=company_id, metric="leads", requested=1)
    lead = Lead(
        company_id=company_id, chatbot_id=chatbot_id, conversation_id=conversation_id,
        name=name, email=email, phone=phone, company=company, source=source,
        status=LeadStatus.new, tags=tags or [], metadata_=metadata or {},
    )
    db.add(lead)
    await db.flush()
    await _activity(db, company_id=company_id, lead_id=lead.id, activity_type="created",
                    description=f"Lead created via {source}", actor_user_id=actor_user_id)
    await usage_service.record_usage(db, company_id=company_id, metric="leads",
                                     chatbot_id=chatbot_id)
    await db.commit()
    return lead


async def update_lead(
    db: AsyncSession, *, company_id: uuid.UUID, lead_id: uuid.UUID,
    changes: dict, actor_user_id=None,
) -> Lead:
    lead = await leads_repo.get(db, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    if "status" in changes and changes["status"]:
        old = lead.status.value
        lead.status = LeadStatus(changes["status"])
        await _activity(db, company_id=company_id, lead_id=lead.id, activity_type="status_changed",
                        description=f"{old} -> {lead.status.value}", actor_user_id=actor_user_id,
                        data={"from": old, "to": lead.status.value})
    for f in ("name", "email", "phone", "company", "tags"):
        if f in changes and changes[f] is not None:
            setattr(lead, f, changes[f])
    if "metadata" in changes and changes["metadata"] is not None:
        lead.metadata_ = changes["metadata"]
    await db.commit()
    return lead


async def assign_lead(
    db: AsyncSession, *, company_id: uuid.UUID, lead_id: uuid.UUID,
    assignee_id: uuid.UUID | None, actor_user_id=None,
) -> Lead:
    lead = await leads_repo.get(db, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    lead.assigned_to = assignee_id
    await _activity(db, company_id=company_id, lead_id=lead.id, activity_type="assigned",
                    description=f"Assigned to {assignee_id}", actor_user_id=actor_user_id,
                    data={"assignee": str(assignee_id) if assignee_id else None})
    await db.commit()
    return lead


async def add_note(
    db: AsyncSession, *, company_id: uuid.UUID, lead_id: uuid.UUID, body: str, author_id=None,
) -> LeadNote:
    lead = await leads_repo.get(db, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    note = LeadNote(company_id=company_id, lead_id=lead_id, author_id=author_id, body=body)
    db.add(note)
    await _activity(db, company_id=company_id, lead_id=lead_id, activity_type="note_added",
                    description=body[:120], actor_user_id=author_id)
    await db.commit()
    return note


async def timeline(db: AsyncSession, *, lead_id: uuid.UUID) -> list[LeadActivity]:
    return await leads_repo.activities_for(db, lead_id)


async def list_leads(db: AsyncSession, **kw):
    return await leads_repo.search(db, **kw)


async def export_csv(db: AsyncSession) -> str:
    rows, _ = await leads_repo.search(
        db, status=None, assigned_to=None, chatbot_id=None, q=None, limit=10000, offset=0
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "email", "phone", "company", "status", "source", "assigned_to", "captured_at"])
    for l in rows:
        w.writerow([l.id, l.name or "", l.email or "", l.phone or "", l.company or "",
                    l.status.value, l.source or "", l.assigned_to or "", l.captured_at.isoformat()])
    return buf.getvalue()


async def analytics(db: AsyncSession) -> dict:
    counts = await leads_repo.status_counts(db)
    total = sum(counts.values())
    won = counts.get("won", 0) + counts.get("converted", 0)
    return {
        "total": total,
        "by_status": counts,
        "won": won,
        "conversion_rate": round(won / total, 4) if total else 0.0,
    }
