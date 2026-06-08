"""Website crawl endpoints (scoped to a company + chatbot)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import TenantContext, require_permission
from app.schemas import CrawlCreate, CrawlJobResponse
from app.services import chatbot_service, crawl_service
from app.workers.crawl_worker import pool

router = APIRouter(
    prefix="/companies/{company_id}/chatbots/{chatbot_id}/crawls",
    tags=["crawler"],
)


async def _ensure_chatbot(ctx: TenantContext, chatbot_id: uuid.UUID) -> None:
    await chatbot_service.get_chatbot(ctx.db, chatbot_id=chatbot_id)


@router.post("", response_model=CrawlJobResponse, status_code=status.HTTP_201_CREATED)
async def start_crawl(
    chatbot_id: uuid.UUID,
    body: CrawlCreate,
    ctx: TenantContext = Depends(require_permission("documents:create")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    job = await crawl_service.create_crawl_job(
        ctx.db,
        company_id=ctx.company.id,
        chatbot_id=chatbot_id,
        start_url=body.start_url,
        mode=body.mode,
        max_pages=body.max_pages,
        max_depth=body.max_depth,
        same_domain_only=body.same_domain_only,
    )
    pool.enqueue(job.id, ctx.company.id)
    return CrawlJobResponse.from_job(job)


@router.get("", response_model=list[CrawlJobResponse])
async def list_crawls(
    chatbot_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:read")),
):
    await _ensure_chatbot(ctx, chatbot_id)
    jobs = await crawl_service.list_jobs(ctx.db, chatbot_id=chatbot_id)
    return [CrawlJobResponse.from_job(j) for j in jobs]


@router.get("/{job_id}", response_model=CrawlJobResponse)
async def get_crawl(
    chatbot_id: uuid.UUID,
    job_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:read")),
):
    job = await crawl_service.get_job(ctx.db, job_id=job_id)
    return CrawlJobResponse.from_job(job)


@router.post("/{job_id}/cancel", response_model=CrawlJobResponse)
async def cancel_crawl(
    chatbot_id: uuid.UUID,
    job_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents:create")),
):
    job = await crawl_service.cancel_job(ctx.db, job_id=job_id)
    return CrawlJobResponse.from_job(job)
