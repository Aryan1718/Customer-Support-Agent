import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import FastAPI

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class TelemetrySettings:
    enabled: bool
    service_name: str
    environment: str | None
    otlp_endpoint: str | None
    otlp_headers: str | None


def setup_telemetry(app: FastAPI) -> TelemetrySettings:
    settings = get_telemetry_settings()
    if not settings.enabled:
        logger.info("OpenTelemetry disabled. Set OTEL_ENABLED=true to enable tracing.")
        return settings

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning(
            "OpenTelemetry is enabled but packages are missing: %s",
            exc,
        )
        return settings

    try:
        resource_attributes = {SERVICE_NAME: settings.service_name}
        if settings.environment:
            resource_attributes[DEPLOYMENT_ENVIRONMENT] = settings.environment

        provider = TracerProvider(resource=Resource.create(resource_attributes))
        exporter_kwargs = {}
        if settings.otlp_endpoint:
            exporter_kwargs["endpoint"] = settings.otlp_endpoint
        if settings.otlp_headers:
            exporter_kwargs["headers"] = _parse_headers(settings.otlp_headers)

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs))
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info(
            "OpenTelemetry tracing enabled for service=%s endpoint=%s",
            settings.service_name,
            settings.otlp_endpoint or "default",
        )
    except Exception as exc:
        logger.warning("OpenTelemetry setup failed; continuing without tracing: %s", exc)

    return settings


def get_telemetry_settings() -> TelemetrySettings:
    load_dotenv()

    return TelemetrySettings(
        enabled=_env_flag("OTEL_ENABLED"),
        service_name=os.getenv("OTEL_SERVICE_NAME", "customer-support-agent-backend"),
        environment=os.getenv("OTEL_RESOURCE_ENVIRONMENT") or None,
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
        otlp_headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS") or None,
    )


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_headers(raw_headers: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for pair in raw_headers.split(","):
        if "=" not in pair:
            continue

        key, value = pair.split("=", 1)
        headers[key.strip()] = value.strip()

    return headers
