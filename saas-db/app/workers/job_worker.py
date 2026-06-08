"""DB-polling job worker pool. Claims jobs atomically, runs the registered
handler, and completes or fails (retry/dead-letter) accordingly.

`run_once` executes a single claim+run (used by tests and by the scheduler tick);
the pool runs `run_once` in a loop across N workers.
"""
from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.services.jobs import queue
from app.services.jobs.registry import TASKS
import app.services.jobs.tasks  # noqa: F401  (registers handlers)

logger = get_logger("app.jobs.worker")


async def run_once(worker_id: str = "w0") -> str | None:
    """Claim and run one job. Returns the resulting status, or None if idle."""
    job = await queue.claim_one(worker_id)
    if job is None:
        return None
    handler = TASKS.get(job.task)
    if handler is None:
        await queue.fail(job, f"no handler for task '{job.task}'")
        return "retry"
    try:
        await handler(job.payload)
    except Exception as exc:  # noqa: BLE001
        outcome = await queue.fail(job, repr(exc))
        logger.warning("job %s (%s) failed: %s -> %s", job.id, job.task, exc, outcome)
        return outcome
    await queue.complete(job.id)
    return "succeeded"


class JobWorkerPool:
    def __init__(self, workers: int | None = None, poll_interval: float = 1.0):
        self._n = workers or getattr(settings, "JOB_WORKERS", 2)
        self._poll = poll_interval
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    async def _loop(self, wid: str):
        while not self._stop.is_set():
            try:
                result = await run_once(wid)
                if result is None:
                    await asyncio.sleep(self._poll)
            except Exception:  # noqa: BLE001
                logger.exception("worker %s crashed; continuing", wid)
                await asyncio.sleep(self._poll)

    def start(self):
        self._stop.clear()
        self._tasks = [asyncio.create_task(self._loop(f"w{i}")) for i in range(self._n)]
        logger.info("Started %d job workers", self._n)

    async def stop(self):
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks.clear()


pool = JobWorkerPool()
