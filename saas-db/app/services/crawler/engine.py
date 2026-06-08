"""Crawl orchestration.

Two modes:
  * ``crawl``   — breadth-first from a start URL, discovering internal links up
                  to max depth / max pages, scoped to the same site.
  * ``sitemap`` — fetch and parse sitemap.xml (or a sitemap index) and ingest the
                  listed pages (no link discovery).

For each fetched page: boilerplate is stripped, main content extracted, and the
cleaned text deduplicated by content hash (within the crawl and against existing
documents for the chatbot). Unique pages are written to storage as a document and
handed to the existing ingestion pipeline (chunk -> embed -> Qdrant). Job
counters/status are persisted per level; cancellation is honored between levels.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.enums import CrawlerStatus, DocumentSourceType, ProcessingStatus
from app.db.session import SessionFactory
from app.models.knowledge import CrawlerJob, Document
from app.services.crawler import fetcher, html_extract, sitemap, url_utils
from app.workers.ingest_worker import pool as ingest_pool

logger = get_logger("app.crawler.engine")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _set_guc(db: AsyncSession, company_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.current_company', :cid, true)"),
        {"cid": str(company_id)},
    )


async def _load_job(company_id, job_id) -> tuple | None:
    async with SessionFactory() as db:
        await _set_guc(db, company_id)
        job = (
            await db.execute(select(CrawlerJob).where(CrawlerJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            return None
        return (job.start_url, dict(job.config), job.chatbot_id, job.status)


async def _update_job(company_id, job_id, **fields) -> CrawlerStatus | None:
    async with SessionFactory() as db:
        await _set_guc(db, company_id)
        job = (
            await db.execute(select(CrawlerJob).where(CrawlerJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            return None
        for k, v in fields.items():
            setattr(job, k, v)
        status = job.status
        await db.commit()
        return status


async def _current_status(company_id, job_id) -> CrawlerStatus | None:
    async with SessionFactory() as db:
        await _set_guc(db, company_id)
        return (
            await db.execute(
                select(CrawlerJob.status).where(CrawlerJob.id == job_id)
            )
        ).scalar_one_or_none()


async def _store_page(
    *, company_id, chatbot_id, job_id, url, title, content
) -> uuid.UUID | None:
    """Persist a crawled page as a Document. Returns doc id, or None if duplicate."""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    async with SessionFactory() as db:
        await _set_guc(db, company_id)
        # Cross-crawl dedupe: skip if identical content already ingested here.
        dup = (
            await db.execute(
                select(Document.id).where(
                    Document.chatbot_id == chatbot_id,
                    Document.content_hash == content_hash,
                    Document.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if dup:
            return None

        document_id = uuid.uuid4()
        storage_key = f"{company_id}/{document_id}/page.txt"
        full_path = os.path.join(settings.STORAGE_DIR, storage_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        db.add(
            Document(
                id=document_id,
                company_id=company_id,
                chatbot_id=chatbot_id,
                crawler_job_id=job_id,
                source_type=DocumentSourceType.crawl,
                title=(title or url)[:1024],
                source_uri=url[:2048],
                storage_key=storage_key,
                mime_type="text/plain",
                file_size=len(content.encode("utf-8")),
                content_hash=content_hash,
                status=ProcessingStatus.pending,
                meta={"kind": "txt", "url": url, "crawler_job_id": str(job_id)},
            )
        )
        await db.commit()
        return document_id


async def _load_robots(client, start_url: str) -> RobotFileParser | None:
    if not settings.CRAWLER_RESPECT_ROBOTS:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    raw = await fetcher.fetch_raw(client, robots_url)
    if not raw:
        return None
    rp = RobotFileParser()
    rp.parse(raw.splitlines())
    return rp


def _allowed(rp: RobotFileParser | None, url: str) -> bool:
    if rp is None:
        return True
    try:
        return rp.can_fetch(settings.CRAWLER_USER_AGENT, url)
    except Exception:
        return True


async def _process_one(client, url, rp) -> dict:
    """Fetch + extract a single page (no DB writes). Safe for concurrent use."""
    if not _allowed(rp, url):
        return {"url": url, "ok": False, "error": "blocked by robots.txt", "skipped": True}
    res = await fetcher.fetch(client, url)
    if not res.ok or not res.text:
        return {"url": url, "ok": False, "error": res.error or "empty response"}
    if settings.CRAWLER_REQUEST_DELAY_SECONDS:
        await asyncio.sleep(settings.CRAWLER_REQUEST_DELAY_SECONDS)
    ex = html_extract.extract(res.text, res.url)
    return {
        "url": res.url,
        "ok": True,
        "title": ex.title,
        "text": ex.text,
        "links": ex.links,
    }


async def run(job_id: uuid.UUID, company_id: uuid.UUID) -> None:
    loaded = await _load_job(company_id, job_id)
    if loaded is None:
        logger.warning("Crawl job %s not found", job_id)
        return
    start_url, config, chatbot_id, _status = loaded

    mode = config.get("mode", "crawl")
    max_pages = int(config.get("max_pages", settings.CRAWLER_MAX_PAGES))
    max_depth = int(config.get("max_depth", settings.CRAWLER_MAX_DEPTH))
    same_domain_only = bool(config.get("same_domain_only", True))
    concurrency = max(1, min(settings.CRAWLER_CONCURRENCY, 8))

    await _update_job(
        company_id, job_id, status=CrawlerStatus.running, started_at=_now()
    )

    processed = failed = stored = 0
    visited: set[str] = set()
    content_hashes: set[str] = set()
    client = fetcher.make_client()

    try:
        rp = await _load_robots(client, start_url)
        sem = asyncio.Semaphore(concurrency)

        async def guarded(u):
            async with sem:
                return await _process_one(client, u, rp)

        # Build the initial frontier.
        if mode == "sitemap":
            sm_url = start_url
            if not sm_url.rstrip("/").endswith(".xml"):
                sm_url = start_url.rstrip("/") + "/sitemap.xml"
            seeds = await sitemap.collect_urls(client, sm_url, max_urls=max_pages)
            frontier = [(u, 0) for u in seeds]
            max_depth = 0  # listed pages only
        else:
            root = url_utils.normalize(start_url)
            if root is None:
                raise ValueError(f"Invalid start URL: {start_url}")
            frontier = [(root, 0)]

        for u, _ in frontier:
            visited.add(u)
        discovered = len(frontier)
        await _update_job(company_id, job_id, pages_discovered=discovered)

        depth = 0
        while frontier and processed + failed < max_pages:
            # Cancellation check between levels.
            if await _current_status(company_id, job_id) == CrawlerStatus.cancelled:
                logger.info("Crawl job %s cancelled", job_id)
                client_closed = True  # noqa: F841
                await client.aclose()
                return

            remaining = max_pages - (processed + failed)
            batch = frontier[:remaining]
            frontier = frontier[remaining:]

            results = await asyncio.gather(*(guarded(u) for u, _ in batch))
            batch_depths = {u: d for u, d in batch}

            next_frontier: list[tuple[str, int]] = []
            for r in results:
                if not r["ok"]:
                    if not r.get("skipped"):
                        failed += 1
                    continue
                processed += 1
                # Dedupe by content hash (within this crawl).
                chash = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
                if r["text"] and chash not in content_hashes:
                    content_hashes.add(chash)
                    doc_id = await _store_page(
                        company_id=company_id,
                        chatbot_id=chatbot_id,
                        job_id=job_id,
                        url=r["url"],
                        title=r.get("title"),
                        content=r["text"],
                    )
                    if doc_id is not None:
                        stored += 1
                        ingest_pool.enqueue(doc_id, company_id)

                # Discover links (crawl mode only).
                cur_depth = batch_depths.get(r["url"], depth)
                if mode == "crawl" and cur_depth < max_depth:
                    for link in r["links"]:
                        if link in visited or len(visited) >= max_pages:
                            continue
                        if same_domain_only and not url_utils.same_site(link, root):
                            continue
                        visited.add(link)
                        next_frontier.append((link, cur_depth + 1))

            discovered = len(visited)
            await _update_job(
                company_id,
                job_id,
                pages_discovered=discovered,
                pages_processed=processed,
                pages_failed=failed,
            )
            frontier.extend(next_frontier)
            depth += 1

        await client.aclose()
        final = await _current_status(company_id, job_id)
        if final != CrawlerStatus.cancelled:
            await _update_job(
                company_id,
                job_id,
                status=CrawlerStatus.completed,
                finished_at=_now(),
                pages_discovered=len(visited),
                pages_processed=processed,
                pages_failed=failed,
            )
        logger.info(
            "Crawl job %s done: discovered=%d processed=%d stored=%d failed=%d",
            job_id, len(visited), processed, stored, failed,
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await client.aclose()
        except Exception:
            pass
        await _update_job(
            company_id,
            job_id,
            status=CrawlerStatus.failed,
            error=str(exc)[:2000],
            finished_at=_now(),
        )
        logger.exception("Crawl job %s failed", job_id)
