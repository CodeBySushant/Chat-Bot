"""Background worker pool for crawl jobs (separate queue from ingestion)."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.services.crawler import engine

logger = get_logger("app.crawlworker")


@dataclass
class CrawlJobMsg:
    job_id: uuid.UUID
    company_id: uuid.UUID


class CrawlWorkerPool:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[CrawlJobMsg] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def _worker(self, n: int) -> None:
        logger.info("Crawl worker %d started", n)
        while True:
            msg = await self._queue.get()
            try:
                await engine.run(msg.job_id, msg.company_id)
            except Exception:
                logger.exception("Crawl worker %d crashed on job %s", n, msg.job_id)
            finally:
                self._queue.task_done()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i)) for i in range(settings.CRAWL_WORKERS)
        ]
        logger.info("Started %d crawl workers", settings.CRAWL_WORKERS)

    async def stop(self) -> None:
        for t in self._workers:
            t.cancel()
        for t in self._workers:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        self._running = False

    def enqueue(self, job_id: uuid.UUID, company_id: uuid.UUID) -> None:
        self._queue.put_nowait(CrawlJobMsg(job_id=job_id, company_id=company_id))

    async def join(self) -> None:
        await self._queue.join()


pool = CrawlWorkerPool()
