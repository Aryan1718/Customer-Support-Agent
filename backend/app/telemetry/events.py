import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.llm.parameter_extraction import detect_tool_from_text
from app.llm.tool_orchestrator import ToolTurnPlan
from app.session_store import ChatSession

from .schemas import validate_observation_event

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    turn_id: str


def new_trace_context() -> TraceContext:
    return TraceContext(trace_id=uuid4().hex, turn_id=uuid4().hex)


@contextmanager
def start_agent_span(
    name: str,
    context: TraceContext,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    tracer = _get_tracer()
    if tracer is None:
        with nullcontext():
            yield
        return

    span_attributes = {
        "agent.trace_id": context.trace_id,
        "agent.turn_id": context.turn_id,
        **_flatten_attributes(attributes or {}),
    }
    with tracer.start_as_current_span(name, attributes=span_attributes):
        yield


def record_agent_event(
    event: str,
    payload: Mapping[str, Any],
    context: TraceContext,
) -> None:
    try:
        observation = validate_observation_event(
            event_name=event,
            trace_fields=asdict(context),
            payload=dict(payload),
        )
    except (KeyError, ValidationError) as exc:
        logger.error("telemetry.%s.validation_failed: %s", event, exc)
        return

    event_payload = observation.model_dump(mode="json")
    logger.info(
        "telemetry.%s: %s",
        event,
        json.dumps(event_payload, default=str, sort_keys=True),
    )
    _record_span_event(event, event_payload)


def summarize_session(session: ChatSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "active_tool": session.active_tool,
        "last_missing_params": session.last_missing_params,
        "collected_params": session.collected_params,
        "conversation_count": len(session.conversations),
        "expires_at": session.expires_at,
    }


def summarize_plan(plan: ToolTurnPlan) -> dict[str, Any]:
    return {
        "action": plan.action,
        "tool_name": plan.tool_name,
        "missing_params": plan.missing_params,
        "collected_params": plan.collected_params,
        "tool_params": plan.tool_params,
        "follow_up_prompt": plan.follow_up_prompt,
    }


def summarize_tool_selection(
    session: ChatSession,
    message: str,
    tool_calls: Sequence[Mapping[str, Any]] | None,
    plan: ToolTurnPlan,
) -> dict[str, Any]:
    llm_tool_name = _first_tool_call_name(tool_calls)
    keyword_tool_name = detect_tool_from_text(message)
    source = "none"

    if llm_tool_name:
        source = "llm_tool_call"
    elif session.active_tool:
        source = "session_active_tool"
    elif keyword_tool_name:
        source = "keyword_detection"

    return {
        "selected_by": source,
        "llm_tool_name": llm_tool_name,
        "session_active_tool": session.active_tool,
        "keyword_tool_name": keyword_tool_name,
        "final_tool_name": plan.tool_name,
        "planner_action": plan.action,
    }


def summarize_request(message: str, history_count: int) -> dict[str, Any]:
    return {
        "message": message,
        "message_length": len(message),
        "history_count": history_count,
    }


def summarize_tool_calls(
    tool_calls: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for tool_call in tool_calls or []:
        function_payload = tool_call.get("function")
        if not isinstance(function_payload, Mapping):
            summaries.append({"type": tool_call.get("type"), "function": None})
            continue

        summaries.append(
            {
                "type": tool_call.get("type"),
                "id": tool_call.get("id"),
                "function": {
                    "name": function_payload.get("name"),
                    "arguments": function_payload.get("arguments"),
                },
            }
        )

    return summaries


def _record_span_event(event: str, payload: Mapping[str, Any]) -> None:
    trace = _import_trace_api()
    if trace is None:
        return

    span = trace.get_current_span()
    if not span or not span.is_recording():
        return

    span.add_event(f"agent.{event}", attributes=_flatten_attributes(payload))


def _get_tracer():
    trace = _import_trace_api()
    if trace is None:
        return None

    return trace.get_tracer("customer_support_agent.telemetry")


def _import_trace_api():
    try:
        from opentelemetry import trace
    except ImportError:
        return None

    return trace


def _flatten_attributes(payload: Mapping[str, Any]) -> dict[str, str | int | float | bool]:
    attributes: dict[str, str | int | float | bool] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            attributes[key] = value
            continue

        try:
            attributes[key] = json.dumps(value, default=str, sort_keys=True)
        except TypeError:
            logger.debug("Unable to serialize telemetry attribute %s", key)
            attributes[key] = str(value)

    return attributes


def _first_tool_call_name(
    tool_calls: Sequence[Mapping[str, Any]] | None,
) -> str | None:
    for tool_call in tool_calls or []:
        function_payload = tool_call.get("function")
        if not isinstance(function_payload, Mapping):
            continue

        tool_name = function_payload.get("name")
        if isinstance(tool_name, str) and tool_name:
            return tool_name

    return None
