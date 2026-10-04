import sys
import types

from fastapi import FastAPI

from app.telemetry.setup import get_telemetry_settings, setup_telemetry


def test_get_telemetry_settings_defaults_to_disabled(monkeypatch):
    monkeypatch.setattr("app.telemetry.setup.load_dotenv", lambda: None)
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_RESOURCE_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)

    settings = get_telemetry_settings()

    assert settings.enabled is False
    assert settings.service_name == "customer-support-agent-backend"
    assert settings.environment is None
    assert settings.otlp_endpoint is None
    assert settings.otlp_headers is None


def test_get_telemetry_settings_reads_otel_env(monkeypatch):
    monkeypatch.setattr("app.telemetry.setup.load_dotenv", lambda: None)
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "support-api")
    monkeypatch.setenv("OTEL_RESOURCE_ENVIRONMENT", "local")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otel.example/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Bearer token")

    settings = get_telemetry_settings()

    assert settings.enabled is True
    assert settings.service_name == "support-api"
    assert settings.environment == "local"
    assert settings.otlp_endpoint == "https://otel.example/v1/traces"
    assert settings.otlp_headers == "Authorization=Bearer token"


def test_setup_telemetry_failure_does_not_break_startup(monkeypatch):
    monkeypatch.setattr("app.telemetry.setup.load_dotenv", lambda: None)
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "not-a-valid-endpoint")

    _install_fake_otel_modules(monkeypatch)

    class BrokenExporter:
        def __init__(self, **kwargs):
            raise RuntimeError("exporter setup failed")

    sys.modules[
        "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    ].OTLPSpanExporter = BrokenExporter

    settings = setup_telemetry(FastAPI())

    assert settings.enabled is True


def _install_fake_otel_modules(monkeypatch):
    trace_module = types.ModuleType("opentelemetry.trace")
    trace_module.set_tracer_provider = lambda provider: None

    opentelemetry_module = types.ModuleType("opentelemetry")
    opentelemetry_module.trace = trace_module

    exporter_module = types.ModuleType(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    )
    exporter_module.OTLPSpanExporter = object

    fastapi_instrumentation_module = types.ModuleType(
        "opentelemetry.instrumentation.fastapi"
    )

    class FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app):
            return None

    fastapi_instrumentation_module.FastAPIInstrumentor = FakeFastAPIInstrumentor

    resources_module = types.ModuleType("opentelemetry.sdk.resources")
    resources_module.DEPLOYMENT_ENVIRONMENT = "deployment.environment"
    resources_module.SERVICE_NAME = "service.name"

    class FakeResource:
        @staticmethod
        def create(attributes):
            return attributes

    resources_module.Resource = FakeResource

    sdk_trace_module = types.ModuleType("opentelemetry.sdk.trace")

    class FakeTracerProvider:
        def __init__(self, resource):
            self.resource = resource

        def add_span_processor(self, processor):
            return None

    sdk_trace_module.TracerProvider = FakeTracerProvider

    sdk_trace_export_module = types.ModuleType("opentelemetry.sdk.trace.export")

    class FakeBatchSpanProcessor:
        def __init__(self, exporter):
            self.exporter = exporter

    sdk_trace_export_module.BatchSpanProcessor = FakeBatchSpanProcessor

    modules = {
        "opentelemetry": opentelemetry_module,
        "opentelemetry.trace": trace_module,
        "opentelemetry.exporter.otlp.proto.http.trace_exporter": exporter_module,
        "opentelemetry.instrumentation.fastapi": fastapi_instrumentation_module,
        "opentelemetry.sdk.resources": resources_module,
        "opentelemetry.sdk.trace": sdk_trace_module,
        "opentelemetry.sdk.trace.export": sdk_trace_export_module,
    }

    for module_name, module in modules.items():
        monkeypatch.setitem(sys.modules, module_name, module)
