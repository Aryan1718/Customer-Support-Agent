import json
import logging

import pytest

from app.telemetry import (
    new_trace_context,
    record_agent_event,
    summarize_request,
    summarize_tool_selection,
    summarize_tool_calls,
)
from app.llm.tool_orchestrator import ToolTurnPlan
from app.session_store import ChatSession


def _session(**overrides):
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    values = {
        "session_id": "session-test",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(minutes=3),
    }
    values.update(overrides)
    return ChatSession(**values)


def test_new_trace_context_creates_distinct_ids():
    first = new_trace_context()
    second = new_trace_context()

    assert first.trace_id
    assert first.turn_id
    assert first != second


def test_record_agent_event_includes_trace_context(caplog):
    context = new_trace_context()
    payload = {
        "session_id": "session-test",
        "model": "test-model",
        "content_length": 0,
        "tool_calls": [],
    }

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        record_agent_event("llm_response_received", payload, context)

    record = caplog.records[0]
    emitted = json.loads(record.message.split(": ", 1)[1])

    assert "telemetry.llm_response_received" in record.message
    assert emitted["event_name"] == "llm_response_received"
    assert emitted["trace_id"] == context.trace_id
    assert emitted["turn_id"] == context.turn_id
    assert emitted["payload"] == payload


@pytest.mark.parametrize(
    ("event_name", "payload"),
    [
        ("unknown_event", {}),
        (
            "llm_response_received",
            {
                "session_id": "session-test",
                "model": "test-model",
                "content_length": -1,
                "tool_calls": [],
            },
        ),
        (
            "tool_planning_decision",
            {"planner_action": "no_tool"},
        ),
    ],
)
def test_record_agent_event_rejects_invalid_event_payloads(caplog, event_name, payload):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        record_agent_event(event_name, payload, new_trace_context())

    assert any("validation_failed" in record.message for record in caplog.records)
    assert not any(
        record.message.startswith(f"telemetry.{event_name}:")
        for record in caplog.records
    )


def test_summarize_request_keeps_message_and_counts_history():
    summary = summarize_request("Where is my order?", 2)

    assert summary == {
        "message": "Where is my order?",
        "message_length": 18,
        "history_count": 2,
    }


def test_summarize_tool_calls_keeps_function_name_and_arguments():
    summary = summarize_tool_calls(
        [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "openTicket",
                    "arguments": '{"customerEmail":"maya.patel@example.test"}',
                },
            }
        ]
    )

    assert summary == [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "openTicket",
                "arguments": '{"customerEmail":"maya.patel@example.test"}',
            },
        }
    ]


def test_summarize_tool_selection_identifies_llm_tool_call_source():
    plan = ToolTurnPlan(action="execute_tool", tool_name="openTicket")
    summary = summarize_tool_selection(
        _session(active_tool="Refund"),
        "Yes that would be much help",
        [{"function": {"name": "openTicket", "arguments": "{}"}}],
        plan,
    )

    assert summary == {
        "selected_by": "llm_tool_call",
        "llm_tool_name": "openTicket",
        "session_active_tool": "Refund",
        "keyword_tool_name": None,
        "final_tool_name": "openTicket",
        "planner_action": "execute_tool",
    }


def test_summarize_tool_selection_identifies_session_active_tool_source():
    plan = ToolTurnPlan(action="execute_tool", tool_name="openTicket")
    summary = summarize_tool_selection(
        _session(active_tool="openTicket"),
        "Yes that would be much help",
        [],
        plan,
    )

    assert summary["selected_by"] == "session_active_tool"
    assert summary["session_active_tool"] == "openTicket"
    assert summary["final_tool_name"] == "openTicket"
