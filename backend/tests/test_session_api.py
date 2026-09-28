from dataclasses import dataclass

from fastapi.testclient import TestClient

import app.main as main
from app.llm import LLMResponse
from app.session_store import InMemorySessionStore


@dataclass
class FakeLLMService:
    def chat(self, *args, **kwargs) -> LLMResponse:
        return LLMResponse(content="What is your order ID?", model="test-model")


def test_create_session_endpoint_returns_session_id(monkeypatch):
    monkeypatch.setattr(main, "session_store", InMemorySessionStore())
    client = TestClient(main.app)

    response = client.post("/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["expires_at"]


def test_llm_chat_returns_and_stores_active_session_id(monkeypatch):
    store = InMemorySessionStore()
    session = store.create_session()
    monkeypatch.setattr(main, "session_store", store)
    monkeypatch.setattr(main, "get_llm_service", lambda: FakeLLMService())
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
    assert body["content"] == "What is your order ID?"

    stored_session = store.get_session(session.session_id)
    assert stored_session is not None
    assert len(stored_session.conversations) == 1
    assert stored_session.conversations[0].user_input == "I want a refund"
    assert stored_session.conversations[0].llm_response == "What is your order ID?"
