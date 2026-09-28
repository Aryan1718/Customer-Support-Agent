from datetime import UTC, datetime, timedelta

import pytest

from app.llm.tool_orchestrator import (
    apply_tool_plan_to_session,
    execute_tool_plan,
    plan_tool_turn,
)
from app.session_store import ChatSession, InMemorySessionStore


def _session(**overrides):
    now = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
    values = {
        "session_id": "session-test",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(minutes=3),
    }
    values.update(overrides)
    return ChatSession(**values)


def test_plan_tool_turn_returns_no_tool_when_no_intent_is_detected():
    plan = plan_tool_turn(_session(), "Hello there")

    assert plan.action == "no_tool"
    assert plan.tool_name is None


def test_plan_tool_turn_asks_for_missing_params_for_new_refund_intent():
    plan = plan_tool_turn(_session(), "I want a refund")

    assert plan.action == "ask_follow_up"
    assert plan.tool_name == "Refund"
    assert plan.missing_params == ["email", "orderID"]
    assert plan.follow_up_prompt == (
        "What email address is on the account? Also, what is the order ID?"
    )


def test_plan_tool_turn_uses_active_tool_when_follow_up_message_has_only_params():
    session = _session(
        active_tool="Refund",
        collected_params={"email": "maya.patel@example.test"},
        last_missing_params=["orderID"],
    )

    plan = plan_tool_turn(session, "order id is 42")

    assert plan.action == "execute_tool"
    assert plan.tool_name == "Refund"
    assert plan.collected_params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }
    assert plan.tool_params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_plan_tool_turn_uses_latest_explicit_user_value_when_conflicting():
    session = _session(
        active_tool="Refund",
        collected_params={
            "email": "old@example.test",
            "orderID": 42,
        },
    )

    plan = plan_tool_turn(session, "Actually use maya.patel@example.test order id is 99")

    assert plan.action == "execute_tool"
    assert plan.tool_params == {
        "email": "maya.patel@example.test",
        "orderID": 99,
    }


def test_plan_tool_turn_accepts_llm_tool_call_arguments():
    plan = plan_tool_turn(
        _session(),
        "Refund this order",
        tool_calls=[
            {
                "function": {
                    "name": "Refund",
                    "arguments": '{"email": "maya.patel@example.test", "orderID": "42"}',
                }
            }
        ],
    )

    assert plan.action == "execute_tool"
    assert plan.tool_params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_execute_tool_plan_calls_registry_when_plan_is_ready():
    plan = plan_tool_turn(
        _session(),
        "Refund order id is 42 for maya.patel@example.test",
    )

    result = execute_tool_plan(
        plan,
        registry={"Refund": lambda email, orderID: {"email": email, "orderID": orderID}},
    )

    assert result == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_execute_tool_plan_rejects_plan_that_is_not_ready():
    plan = plan_tool_turn(_session(), "I want a refund")

    with pytest.raises(ValueError, match="not ready"):
        execute_tool_plan(plan, registry={})


def test_apply_tool_plan_to_session_stores_active_tool_for_follow_up():
    store = InMemorySessionStore()
    session = store.create_session()
    plan = plan_tool_turn(session, "I want a refund")

    updated_session = apply_tool_plan_to_session(store, session.session_id, plan)

    assert updated_session.active_tool == "Refund"
    assert updated_session.last_missing_params == ["email", "orderID"]
    assert updated_session.collected_params == {}


def test_apply_tool_plan_to_session_clears_active_tool_after_ready_plan():
    store = InMemorySessionStore()
    session = store.create_session()
    store.update_tool_state(
        session.session_id,
        active_tool="Refund",
        last_missing_params=["orderID"],
    )
    store.update_context(
        session.session_id,
        collected_params={"email": "maya.patel@example.test"},
    )
    active_session = store.get_session(session.session_id)
    assert active_session is not None

    plan = plan_tool_turn(active_session, "order id is 42")
    updated_session = apply_tool_plan_to_session(store, session.session_id, plan)

    assert updated_session.active_tool is None
    assert updated_session.last_missing_params == []
    assert updated_session.collected_params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }
