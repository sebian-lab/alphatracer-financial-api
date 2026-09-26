"""
OpenTelemetry Tracing Integration with Jaeger.
Exports distributed traces via standard OTLP HTTP/gRPC to Jaeger (:4318 / :4317).
"""
import os
import logging

logger = logging.getLogger(__name__)


def setup_telemetry(app):
    """Instruments FastAPI application with OpenTelemetry targeting Jaeger."""
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    enable_tracing = os.getenv("ENABLE_TRACING", "true").lower() in ("true", "1")

    if not enable_tracing:
        logger.info("OpenTelemetry tracing is disabled (ENABLE_TRACING=false).")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({"service.name": "alphatracer-api"})
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        )
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        logger.info(f"OpenTelemetry tracing successfully enabled -> {otlp_endpoint}")
    except ImportError:
        logger.info(
            "OpenTelemetry SDK not present in environment; tracing will be active in container."
        )
