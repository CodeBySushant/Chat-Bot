"""Crawl-job lifecycle on top of the tenant session."""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.core.logging import get_logger
from app.db.enums import CrawlerStatus
from app.models.knowledge import CrawlerJob

logger = get_logger("app.crawl")

_ACTIVE = (CrawlerStatus.queued, CrawlerStatus.running)


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationFailed("start_url must be an absolute http(s) URL")
    return url


async def create_crawl_job(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    start_url: str,
    mode: str,
    max_pages: int,
    max_depth: int,
    same_domain_only: bool,
) -> CrawlerJob:
    _validate_url(start_url)

    # One active crawl per (chatbot, start_url) to avoid duplicate concurrent runs.
    dup = (
        await db.execute(
            select(CrawlerJob.id).where(
                CrawlerJob.chatbot_id == chatbot_id,
                CrawlerJob.start_url == start_url,
                CrawlerJob.status.in_(_ACTIVE),
                CrawlerJob.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise ConflictError("An active crawl for this URL already exists")

    job = CrawlerJob(
        company_id=company_id,
        chatbot_id=chatbot_id,
        start_url=start_url,
        status=CrawlerStatus.queued,
        config={
            "mode": mode,
            "max_pages": min(max_pages, settings.CRAWLER_MAX_PAGES * 10),
            "max_depth": max_depth,
            "same_domain_only": same_domain_only,
        },
    )
    db.add(job)
    await db.commit()
    logger.info("Created crawl job %s for %s", job.id, start_url)
    return job


async def list_jobs(db: AsyncSession, *, chatbot_id: uuid.UUID) -> list[CrawlerJob]:
    return list(
        (
            await db.execute(
                select(CrawlerJob)
                .where(
                    CrawlerJob.chatbot_id == chatbot_id,
                    CrawlerJob.deleted_at.is_(None),
                )
                .order_by(CrawlerJob.created_at.desc())
            )
        ).scalars()
    )


async def get_job(db: AsyncSession, *, job_id: uuid.UUID) -> CrawlerJob:
    job = (
        await db.execute(
            select(CrawlerJob).where(
                CrawlerJob.id == job_id, CrawlerJob.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Crawl job not found")
    return job


async def cancel_job(db: AsyncSession, *, job_id: uuid.UUID) -> CrawlerJob:
    job = await get_job(db, job_id=job_id)
    if job.status in _ACTIVE:
        job.status = CrawlerStatus.cancelled
        await db.commit()
    return job
