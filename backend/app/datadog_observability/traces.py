import json
import logging
import os
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger("uvicorn.error")
_llmobs_enable_attempted = False


@dataclass(frozen=True)
class DatadogTraceSettings:
    enabled: bool
    llmobs_enabled: bool
    service_name: str
    environment: str | None
    ml_app: str | None
    site: str | None
    agentless_enabled: bool
    api_key_configured: bool


def get_datadog_trace_settings() -> DatadogTraceSettings:
    load_dotenv()

    llmobs_enabled = _env_flag("DD_LLMOBS_ENABLED")
    trace_enabled = not _env_flag("DD_TRACE_ENABLED", disabled_values=True)
    ml_app = os.getenv("DD_LLMOBS_ML_APP") or None

    return DatadogTraceSettings(
        enabled=trace_enabled and llmobs_enabled,
        llmobs_enabled=llmobs_enabled,
        service_name=os.getenv("DD_SERVICE", "customer-support-agent-backend"),
        environment=os.getenv("DD_ENV") or None,
        ml_app=ml_app,
        site=os.getenv("DD_SITE") or None,
        agentless_enabled=_env_flag("DD_LLMOBS_AGENTLESS_ENABLED"),
        api_key_configured=bool(os.getenv("DD_API_KEY")),
    )


@contextmanager
def start_datadog_workflow_span(
    name: str,
    trace_id: str,
    turn_id: str,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    settings = get_datadog_trace_settings()
    if not settings.enabled:
        with nullcontext():
            yield
        return

    llmobs = _import_llmobs()
    if llmobs is None:
        logger.warning("Datadog LLM Observability is enabled but ddtrace is missing.")
        with nullcontext():
            yield
        return
    _ensure_llmobs_enabled(llmobs, settings)

    span_attributes = {
        "agent.trace_id": trace_id,
        "agent.turn_id": turn_id,
        "service": settings.service_name,
        **_flatten_attributes(attributes or {}),
    }
    if settings.environment:
        span_attributes["env"] = settings.environment

    workflow_kwargs = {"name": name, "session_id": trace_id}
    if settings.ml_app:
        workflow_kwargs["ml_app"] = settings.ml_app

    try:
        workflow_span = llmobs.workflow(**workflow_kwargs)
        workflow_span.__enter__()
    except Exception as exc:
        logger.warning("Unable to start Datadog workflow span %s: %s", name, exc)
        with nullcontext():
            yield
        return

    try:
        _annotate_llmobs(tags=span_attributes)
        yield
    finally:
        try:
            workflow_span.__exit__(*sys.exc_info())
        except Exception as exc:
            logger.warning("Unable to close Datadog workflow span %s: %s", name, exc)


def record_datadog_event(
    event: str,
    payload: Mapping[str, Any],
    trace_id: str,
    turn_id: str,
) -> None:
    settings = get_datadog_trace_settings()
    if not settings.enabled:
        return

    tags = {
        "agent.event.name": event,
        "agent.trace_id": trace_id,
        "agent.turn_id": turn_id,
        f"agent.event.{event}": _json_dumps(payload),
    }
    _annotate_llmobs(tags=tags)
    _tag_current_apm_span(tags)


def _import_llmobs():
    try:
        from ddtrace.llmobs import LLMObs
    except ImportError:
        return None

    return LLMObs


def _ensure_llmobs_enabled(llmobs: Any, settings: DatadogTraceSettings) -> None:
    global _llmobs_enable_attempted

    if _llmobs_enable_attempted:
        return

    _llmobs_enable_attempted = True
    try:
        llmobs.enable(
            ml_app=settings.ml_app,
            api_key=os.getenv("DD_API_KEY") or None,
            site=settings.site,
            agentless_enabled=settings.agentless_enabled,
            env=settings.environment,
            service=settings.service_name,
        )
    except Exception as exc:
        logger.debug("Unable to enable Datadog LLMObs explicitly: %s", exc)


def _annotate_llmobs(tags: Mapping[str, Any]) -> None:
    llmobs = _import_llmobs()
    if llmobs is None:
        return

    try:
        llmobs.annotate(tags=_flatten_attributes(tags))
    except Exception as exc:
        logger.debug("Unable to annotate Datadog LLMObs span: %s", exc)


def _tag_current_apm_span(tags: Mapping[str, Any]) -> None:
    try:
        from ddtrace import tracer
    except ImportError:
        return

    span = tracer.current_span()
    if span is None:
        return

    for key, value in _flatten_attributes(tags).items():
        span.set_tag(key, value)


def _env_flag(name: str, disabled_values: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if disabled_values:
        return value in {"0", "false", "no", "off"}

    return value in {"1", "true", "yes", "on"}


def _flatten_attributes(payload: Mapping[str, Any]) -> dict[str, str | int | float | bool]:
    attributes: dict[str, str | int | float | bool] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            attributes[key] = value
            continue

        attributes[key] = _json_dumps(value)

    return attributes


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        return str(value)
