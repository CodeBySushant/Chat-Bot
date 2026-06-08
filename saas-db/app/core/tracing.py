"""Optional OpenTelemetry tracing.

Disabled by default (OTEL_ENABLED=false) so the app boots without the OTEL
packages installed. When enabled, configures an OTLP exporter and instruments
FastAPI, SQLAlchemy, and httpx. The worker process calls setup_tracing(None) to
get the same provider for span export without HTTP instrumentation.

Install in the image only when tracing is used:
  opentelemetry-sdk opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-instrumentation-sqlalchemy \
  opentelemetry-instrumentation-httpx
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.tracing")
_configured = False


def setup_tracing(app=None) -> None:
    global _configured
    if not settings.OTEL_ENABLED or _configured:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError:
        logger.warning("OTEL_ENABLED but opentelemetry packages are not installed; skipping")
        return

    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME,
        "deployment.environment": settings.ENVIRONMENT,
    })
    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(settings.OTEL_TRACES_SAMPLER_RATIO),
    )
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from app.db.session import engine, admin_engine
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        SQLAlchemyInstrumentor().instrument(engine=admin_engine.sync_engine)
    except Exception:  # noqa: BLE001
        logger.warning("SQLAlchemy instrumentation failed", exc_info=True)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        logger.warning("httpx instrumentation failed", exc_info=True)
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz,startupz,metrics")
        except Exception:  # noqa: BLE001
            logger.warning("FastAPI instrumentation failed", exc_info=True)

    _configured = True
    logger.info("OpenTelemetry tracing enabled -> %s", settings.OTEL_EXPORTER_OTLP_ENDPOINT)
