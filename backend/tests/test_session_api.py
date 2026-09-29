from dataclasses import dataclass, field

from fastapi.testclient import TestClient

import app.main as main
from app.llm import LLMResponse
from app.session_store import InMemorySessionStore


@dataclass
class FakeLLMService:
    responses: list[LLMResponse] = field(
        default_factory=lambda: [
            LLMResponse(content="I can help with that.", model="test-model")
        ]
    )
    calls: list[dict] = field(default_factory=list)

    def chat(self, *args, **kwargs) -> LLMResponse:
        self.calls.append({"args": args, "kwargs": kwargs})
        if self.responses:
            return self.responses.pop(0)

        return LLMResponse(content="I can help with that.", model="test-model")


def test_create_session_endpoint_returns_session_id(monkeypatch):
    monkeypatch.setattr(main, "session_store", InMemorySessionStore())
    client = TestClient(main.app)

    response = client.post("/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["expires_at"]


def test_llm_chat_asks_follow_up_and_stores_active_tool(monkeypatch):
    store = InMemorySessionStore()
    session = store.create_session()
    service = FakeLLMService()
    monkeypatch.setattr(main, "session_store", store)
    monkeypatch.setattr(main, "get_llm_service", lambda: service)
    client = TestClient(main.app)

    response = client.post(
        "/llm/chat",
        json={
            "session_id": session.session_id,
            "message": "I want a refund",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session.session_id
    assert body["content"] == (
        "What email address is on the account? Also, what is the order ID?"
    )

    stored_session = store.get_session(session.session_id)
    assert stored_session is not None
    assert stored_session.active_tool == "Refund"
    assert stored_session.last_missing_params == ["email", "orderID"]
    assert len(stored_session.conversations) == 1
    assert stored_session.conversations[0].user_input == "I want a refund"
    assert stored_session.conversations[0].llm_response == (
        "What email address is on the account? Also, what is the order ID?"
    )
    assert len(service.calls) == 1


def test_llm_chat_executes_ready_tool_and_uses_llm_to_format_result(monkeypatch):
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
    service = FakeLLMService(
        responses=[
            LLMResponse(content="", model="test-model"),
            LLMResponse(
                content="Your refund request needs human approval.",
                model="test-model",
            ),
            LLMResponse(
                content=(
                    '{"valid": true, "severity": "none", '
                    '"reason": "Supported.", "fallback_response": null}'
                ),
                model="test-model",
            ),
        ]
    )
    monkeypatch.setattr(main, "session_store", store)
    monkeypatch.setattr(main, "get_llm_service", lambda: service)
    monkeypatch.setattr(
        main,
        "DEFAULT_TOOL_REGISTRY",
        {"Refund": lambda email, orderID: "Human Approval"},
    )
    client = TestClient(main.app)

    response = client.post(
        "/llm/chat",
        json={
            "session_id": session.session_id,
            "message": "order id is 42",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session.session_id
    assert body["content"] == "Your refund request needs human approval."

    stored_session = store.get_session(session.session_id)
    assert stored_session is not None
    assert stored_session.active_tool is None
    assert stored_session.last_missing_params == []
    assert stored_session.collected_params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }
    assert stored_session.conversations[0].llm_response == (
        "Your refund request needs human approval."
    )
    assert len(service.calls) == 3
    assert service.calls[1]["kwargs"]["tools"] == []
    assert "Human Approval" in service.calls[1]["kwargs"]["message"]
    assert service.calls[2]["kwargs"]["tools"] == []
    assert "candidate_response" in service.calls[2]["kwargs"]["message"]


def test_llm_chat_uses_validation_fallback_for_high_severity_contradiction(monkeypatch):
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
    service = FakeLLMService(
        responses=[
            LLMResponse(content="", model="test-model"),
            LLMResponse(content="Your refund is approved.", model="test-model"),
            LLMResponse(
                content=(
                    '{"valid": false, "severity": "high", '
                    '"reason": "Contradicts Human Approval.", '
                    '"fallback_response": "Your refund request needs human approval."}'
                ),
                model="test-model",
            ),
        ]
    )
    monkeypatch.setattr(main, "session_store", store)
    monkeypatch.setattr(main, "get_llm_service", lambda: service)
    monkeypatch.setattr(
        main,
        "DEFAULT_TOOL_REGISTRY",
        {"Refund": lambda email, orderID: "Human Approval"},
    )
    client = TestClient(main.app)

    response = client.post(
        "/llm/chat",
        json={
            "session_id": session.session_id,
            "message": "order id is 42",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Your refund request needs human approval."

    stored_session = store.get_session(session.session_id)
    assert stored_session is not None
    assert stored_session.conversations[0].llm_response == (
        "Your refund request needs human approval."
    )
    assert len(service.calls) == 3


def test_llm_chat_stream_returns_sse_events_and_stores_conversation(monkeypatch):
    store = InMemorySessionStore()
    session = store.create_session()
    service = FakeLLMService(
        responses=[LLMResponse(content="I can help with that.", model="test-model")]
    )
    monkeypatch.setattr(main, "session_store", store)
    monkeypatch.setattr(main, "get_llm_service", lambda: service)
    client = TestClient(main.app)

    with client.stream(
        "POST",
        "/llm/chat/stream",
        json={
            "session_id": session.session_id,
            "message": "Hello",
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: status\ndata: {"stage": "received"}' in body
    assert 'event: status\ndata: {"stage": "loading_session"}' in body
    assert 'event: status\ndata: {"stage": "calling_llm"}' in body
    assert 'event: status\ndata: {"stage": "planning"}' in body
    assert 'event: status\ndata: {"stage": "finalizing"}' in body
    assert 'event: status\ndata: {"stage": "storing_conversation"}' in body
    assert "event: metadata" in body
    assert f'"session_id": "{session.session_id}"' in body
    assert 'event: content\ndata: {"delta": "I ' in body
    assert "event: done" in body
    assert '"content": "I can help with that."' in body

    stored_session = store.get_session(session.session_id)
    assert stored_session is not None
    assert stored_session.conversations[0].llm_response == "I can help with that."
