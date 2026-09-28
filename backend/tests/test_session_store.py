from datetime import UTC, datetime, timedelta

import pytest

from app.session_store import InMemorySessionStore


class Clock:
    def __init__(self) -> None:
        self.current_time = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current_time

    def advance(self, seconds: int) -> None:
        self.current_time += timedelta(seconds=seconds)


def test_create_session_returns_unique_backend_generated_sessions():
    store = InMemorySessionStore()

    first_session = store.create_session()
    second_session = store.create_session()

    assert first_session.session_id
    assert second_session.session_id
    assert first_session.session_id != second_session.session_id


def test_get_or_create_session_returns_existing_session_and_refreshes_ttl():
    clock = Clock()
    store = InMemorySessionStore(ttl_seconds=180, now=clock.now)
    session = store.create_session()

    clock.advance(60)
    refreshed_session = store.get_or_create_session(session.session_id)

    assert refreshed_session.session_id == session.session_id
    assert refreshed_session.updated_at == clock.now()
    assert refreshed_session.expires_at == clock.now() + timedelta(seconds=180)


def test_get_or_create_session_replaces_missing_or_expired_session():
    clock = Clock()
    store = InMemorySessionStore(ttl_seconds=180, now=clock.now)
    session = store.create_session()

    clock.advance(181)
    new_session = store.get_or_create_session(session.session_id)

    assert new_session.session_id != session.session_id
    assert store.get_session(session.session_id) is None


def test_append_conversation_stores_user_input_and_llm_response():
    clock = Clock()
    store = InMemorySessionStore(now=clock.now)
    session = store.create_session()

    updated_session = store.append_conversation(
        session_id=session.session_id,
        user_input="I want a refund",
        llm_response="What is your order ID?",
    )

    assert len(updated_session.conversations) == 1
    assert updated_session.conversations[0].user_input == "I want a refund"
    assert updated_session.conversations[0].llm_response == "What is your order ID?"


def test_update_context_stores_customer_order_and_collected_params():
    store = InMemorySessionStore()
    session = store.create_session()

    updated_session = store.update_context(
        session.session_id,
        customer_id=123,
        customer_email="maya.patel@example.test",
        orders=[{"orderId": 42, "status": "delivered"}],
        collected_params={"email": "maya.patel@example.test"},
    )
    updated_session = store.update_context(
        updated_session.session_id,
        collected_params={"orderID": 42},
    )

    assert updated_session.customer_id == 123
    assert updated_session.customer_email == "maya.patel@example.test"
    assert updated_session.orders == [{"orderId": 42, "status": "delivered"}]
    assert updated_session.collected_params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_lazy_cleanup_runs_when_store_is_used():
    clock = Clock()
    store = InMemorySessionStore(ttl_seconds=180, now=clock.now)
    expired_session = store.create_session()

    clock.advance(181)
    active_session = store.create_session()

    assert store.get_session(expired_session.session_id) is None
    assert store.get_session(active_session.session_id) is not None


def test_append_conversation_rejects_expired_session():
    clock = Clock()
    store = InMemorySessionStore(ttl_seconds=180, now=clock.now)
    session = store.create_session()

    clock.advance(181)

    with pytest.raises(KeyError, match="Unknown or expired session"):
        store.append_conversation(
            session_id=session.session_id,
            user_input="Hello?",
            llm_response="Hi",
        )
