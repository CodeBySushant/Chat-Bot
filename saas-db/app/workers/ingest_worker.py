"""In-process background worker pool for document ingestion.

An ``asyncio.Queue`` fed by the upload endpoint; N worker tasks drain it and run
the ingestion pipeline. Started/stopped in the app lifespan. For multi-process
production this is the seam to swap for a real broker (e.g. Redis/RQ, Celery,
arq) without changing the pipeline.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.services import ingestion

logger = get_logger("app.worker")


@dataclass
class IngestJob:
    document_id: uuid.UUID
    company_id: uuid.UUID


class IngestWorkerPool:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[IngestJob] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def _worker(self, n: int) -> None:
        logger.info("Ingest worker %d started", n)
        while True:
            job = await self._queue.get()
            try:
                await ingestion.process_document(job.document_id, job.company_id)
            except Exception:  # never let a bad job kill the worker
                logger.exception("Worker %d crashed on document %s", n, job.document_id)
            finally:
                self._queue.task_done()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i)) for i in range(settings.INGEST_WORKERS)
        ]
        logger.info("Started %d ingest workers", settings.INGEST_WORKERS)

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

    def enqueue(self, document_id: uuid.UUID, company_id: uuid.UUID) -> None:
        self._queue.put_nowait(IngestJob(document_id=document_id, company_id=company_id))

    async def join(self) -> None:
        """Block until the queue is drained (used by tests)."""
        await self._queue.join()


pool = IngestWorkerPool()
