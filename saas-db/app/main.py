"""FastAPI application factory and entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.metrics import setup_metrics
from app.core.tracing import setup_tracing
from app.api.health import router as health_router
from app.db.session import dispose_engines
from app.middleware.context import RequestContextMiddleware
from app.services import vector_store
from app.workers.crawl_worker import pool as crawl_pool
from app.workers.ingest_worker import pool as ingest_pool

configure_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (env=%s)", settings.PROJECT_NAME, settings.ENV)
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    await vector_store.ensure_collection()
    ingest_pool.start()
    crawl_pool.start()
    yield
    await crawl_pool.stop()
    await ingest_pool.stop()
    from app.services.ai import close_providers

    await close_providers()
    vector_store.close()
    await dispose_engines()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Widget endpoints must be callable from any embedding site. Auth is by
    # Bearer token (dashboard) or public key (widget), never cookies, so a
    # wildcard origin without credentials is safe; the widget additionally
    # enforces its own per-chatbot domain allowlist at the application layer.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    if settings.METRICS_ENABLED:
        setup_metrics(app)

    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(health_router)  # /healthz /readyz /startupz

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "service": settings.PROJECT_NAME}

    setup_tracing(app)
    return app


app = create_app()
