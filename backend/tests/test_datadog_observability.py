from app.datadog_observability.traces import (
    DatadogTraceSettings,
    get_datadog_trace_settings,
    start_datadog_workflow_span,
)
from app.telemetry.events import TraceContext, start_agent_span


def test_get_datadog_trace_settings_defaults_to_disabled(monkeypatch):
    monkeypatch.setattr("app.datadog_observability.traces.load_dotenv", lambda: None)
    monkeypatch.delenv("DD_LLMOBS_ENABLED", raising=False)
    monkeypatch.delenv("DD_TRACE_ENABLED", raising=False)
    monkeypatch.delenv("DD_SERVICE", raising=False)
    monkeypatch.delenv("DD_ENV", raising=False)
    monkeypatch.delenv("DD_LLMOBS_ML_APP", raising=False)
    monkeypatch.delenv("DD_SITE", raising=False)
    monkeypatch.delenv("DD_LLMOBS_AGENTLESS_ENABLED", raising=False)
    monkeypatch.delenv("DD_API_KEY", raising=False)

    settings = get_datadog_trace_settings()

    assert settings.enabled is False
    assert settings.llmobs_enabled is False
    assert settings.service_name == "customer-support-agent-backend"
    assert settings.environment is None
    assert settings.ml_app is None
    assert settings.site is None
    assert settings.agentless_enabled is False
    assert settings.api_key_configured is False


def test_get_datadog_trace_settings_reads_datadog_env(monkeypatch):
    monkeypatch.setattr("app.datadog_observability.traces.load_dotenv", lambda: None)
    monkeypatch.setenv("DD_LLMOBS_ENABLED", "1")
    monkeypatch.setenv("DD_SERVICE", "support-api")
    monkeypatch.setenv("DD_ENV", "local")
    monkeypatch.setenv("DD_LLMOBS_ML_APP", "support-agent")
    monkeypatch.setenv("DD_SITE", "datadoghq.com")
    monkeypatch.setenv("DD_LLMOBS_AGENTLESS_ENABLED", "true")
    monkeypatch.setenv("DD_API_KEY", "test-key")

    settings = get_datadog_trace_settings()

    assert settings.enabled is True
    assert settings.llmobs_enabled is True
    assert settings.service_name == "support-api"
    assert settings.environment == "local"
    assert settings.ml_app == "support-agent"
    assert settings.site == "datadoghq.com"
    assert settings.agentless_enabled is True
    assert settings.api_key_configured is True


def test_start_agent_span_uses_datadog_when_otel_tracer_is_missing(monkeypatch):
    calls = []

    def fake_datadog_span(name, trace_id, turn_id, attributes=None):
        class FakeSpan:
            def __enter__(self):
                calls.append((name, trace_id, turn_id, attributes))

            def __exit__(self, exc_type, exc, traceback):
                calls.append("closed")

        return FakeSpan()

    monkeypatch.setattr("app.telemetry.events._get_tracer", lambda: None)
    monkeypatch.setattr(
        "app.telemetry.events.start_datadog_workflow_span",
        fake_datadog_span,
    )

    context = TraceContext(trace_id="trace-1", turn_id="turn-1")
    with start_agent_span("agent.chat_turn", context, {"agent.streaming": False}):
        calls.append("inside")

    assert calls == [
        (
            "agent.chat_turn",
            "trace-1",
            "turn-1",
            {"agent.streaming": False},
        ),
        "inside",
        "closed",
    ]


def test_datadog_span_close_failure_does_not_break_request(monkeypatch):
    class FakeLLMObs:
        @staticmethod
        def enable(**kwargs):
            return None

        @staticmethod
        def workflow(**kwargs):
            class FakeWorkflowSpan:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    raise RuntimeError("datadog close failed")

            return FakeWorkflowSpan()

        @staticmethod
        def annotate(tags):
            return None

    monkeypatch.setattr(
        "app.datadog_observability.traces.get_datadog_trace_settings",
        lambda: DatadogTraceSettings(
            enabled=True,
            llmobs_enabled=True,
            service_name="support-api",
            environment="test",
            ml_app="support-agent",
            site="datadoghq.com",
            agentless_enabled=True,
            api_key_configured=True,
        ),
    )
    monkeypatch.setattr(
        "app.datadog_observability.traces._import_llmobs",
        lambda: FakeLLMObs,
    )

    with start_datadog_workflow_span("agent.chat_turn", "trace-1", "turn-1"):
        pass


def test_datadog_workflow_enables_llmobs_agentless(monkeypatch):
    enable_calls = []

    class FakeLLMObs:
        @staticmethod
        def enable(**kwargs):
            enable_calls.append(kwargs)

        @staticmethod
        def workflow(**kwargs):
            class FakeWorkflowSpan:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return None

            return FakeWorkflowSpan()

        @staticmethod
        def annotate(tags):
            return None

    monkeypatch.setattr("app.datadog_observability.traces._llmobs_enable_attempted", False)
    monkeypatch.setenv("DD_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.datadog_observability.traces.get_datadog_trace_settings",
        lambda: DatadogTraceSettings(
            enabled=True,
            llmobs_enabled=True,
            service_name="support-api",
            environment="test",
            ml_app="support-agent",
            site="datadoghq.com",
            agentless_enabled=True,
            api_key_configured=True,
        ),
    )
    monkeypatch.setattr(
        "app.datadog_observability.traces._import_llmobs",
        lambda: FakeLLMObs,
    )

    with start_datadog_workflow_span("agent.chat_turn", "trace-1", "turn-1"):
        pass

    assert enable_calls == [
        {
            "ml_app": "support-agent",
            "api_key": "test-key",
            "site": "datadoghq.com",
            "agentless_enabled": True,
            "env": "test",
            "service": "support-api",
        }
    ]
