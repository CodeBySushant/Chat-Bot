"""Prometheus metrics: HTTP request instrumentation + domain instruments.

Exposes /metrics (text exposition) and a middleware that records request count
and latency labelled by method, templated route, and status class. Domain code
(AI providers, workers, queue) imports the module-level instruments directly.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from starlette.middleware.base import BaseHTTPMiddleware

# A dedicated registry so multiprocess (gunicorn/uvicorn workers) can aggregate
# via PROMETHEUS_MULTIPROC_DIR when set; otherwise the default in-process registry.
REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests",
    ["method", "route", "status"], registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=REGISTRY,
)
HTTP_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "In-flight HTTP requests",
    ["method"], registry=REGISTRY, multiprocess_mode="livesum",
)

# --- Domain instruments (imported by services/workers) ---
AI_REQUESTS = Counter(
    "ai_provider_requests_total", "AI provider calls",
    ["provider", "model", "outcome"], registry=REGISTRY,
)
AI_LATENCY = Histogram(
    "ai_provider_latency_seconds", "AI provider latency",
    ["provider", "model"], registry=REGISTRY,
)
AI_TOKENS = Counter(
    "ai_tokens_total", "AI tokens consumed", ["provider", "kind"], registry=REGISTRY,
)
JOBS_PROCESSED = Counter(
    "jobs_processed_total", "Background jobs processed",
    ["task", "outcome"], registry=REGISTRY,
)
JOB_DURATION = Histogram(
    "job_duration_seconds", "Background job duration", ["task"], registry=REGISTRY,
)
QUEUE_DEPTH = Gauge(
    "job_queue_depth", "Jobs by status", ["status"], registry=REGISTRY,
    multiprocess_mode="liveall",
)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        method = request.method
        HTTP_IN_PROGRESS.labels(method).inc()
        start = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = _route_template(request)
            HTTP_LATENCY.labels(method, route).observe(elapsed)
            HTTP_REQUESTS.labels(method, route, status).inc()
            HTTP_IN_PROGRESS.labels(method).dec()


def setup_metrics(app: FastAPI) -> None:
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        import os
        if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            data = generate_latest(registry)
        else:
            data = generate_latest(REGISTRY)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
