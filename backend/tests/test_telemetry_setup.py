from app.telemetry.setup import get_telemetry_settings


def test_get_telemetry_settings_defaults_to_disabled(monkeypatch):
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
