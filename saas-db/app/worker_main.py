"""Worker process entrypoint (separate container from the API).

Runs the durable job pool, the ingest/crawl pools, and a lightweight scheduler
that enqueues recurring maintenance jobs. Handles SIGTERM/SIGINT for graceful
shutdown so in-flight jobs finish before exit.
"""
from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.tracing import setup_tracing
from app.db.session import dispose_engines
from app.services.jobs import queue
from app.workers.crawl_worker import pool as crawl_pool
from app.workers.ingest_worker import pool as ingest_pool
from app.workers.job_worker import pool as job_pool

configure_logging()
logger = get_logger("app.worker")


async def scheduler(stop: asyncio.Event) -> None:
    """Enqueue recurring jobs (dedupe_key keeps them idempotent per period)."""
    while not stop.is_set():
        now = datetime.now(timezone.utc)
        day = now.date().isoformat()
        await queue.enqueue("cleanup", {"retain_days": 90}, dedupe_key=f"cleanup:{day}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=3600)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    setup_tracing(None)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    ingest_pool.start()
    crawl_pool.start()
    job_pool.start()
    sched = asyncio.create_task(scheduler(stop))
    logger.info("Worker started (env=%s, job_workers=%s)", settings.ENVIRONMENT, settings.JOB_WORKERS)

    await stop.wait()
    logger.info("Shutting down workers...")
    sched.cancel()
    await job_pool.stop()
    await crawl_pool.stop()
    await ingest_pool.stop()
    await dispose_engines()
    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
