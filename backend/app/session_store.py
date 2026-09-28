from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import Lock
from typing import Any, Callable

from pydantic import BaseModel, Field


DEFAULT_SESSION_TTL_SECONDS = 180


class ConversationTurn(BaseModel):
    user_input: str
    llm_response: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatSession(BaseModel):
    session_id: str
    customer_id: int | None = None
    customer_email: str | None = None
    orders: list[dict[str, Any]] = Field(default_factory=list)
    collected_params: dict[str, Any] = Field(default_factory=dict)
    conversations: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class InMemorySessionStore:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)
        self._now = now or (lambda: datetime.now(UTC))
        self._sessions: dict[str, ChatSession] = {}
        self._lock = Lock()

    def create_session(self) -> ChatSession:
        with self._lock:
            self._delete_expired_sessions()
            return self._create_session()

    def get_session(self, session_id: str) -> ChatSession | None:
        with self._lock:
            self._delete_expired_sessions()
            session = self._sessions.get(session_id)
            if session is None:
                return None

            return session.model_copy(deep=True)

    def get_or_create_session(self, session_id: str | None = None) -> ChatSession:
        with self._lock:
            self._delete_expired_sessions()
            if session_id:
                session = self._sessions.get(session_id)
                if session is not None:
                    self._touch_session(session)
                    return session.model_copy(deep=True)

            return self._create_session()

    def append_conversation(
        self,
        session_id: str,
        user_input: str,
        llm_response: str,
    ) -> ChatSession:
        with self._lock:
            self._delete_expired_sessions()
            session = self._require_session(session_id)
            session.conversations.append(
                ConversationTurn(
                    user_input=user_input,
                    llm_response=llm_response,
                    created_at=self._now(),
                )
            )
            self._touch_session(session)
            return session.model_copy(deep=True)

    def update_context(
        self,
        session_id: str,
        *,
        customer_id: int | None = None,
        customer_email: str | None = None,
        orders: list[dict[str, Any]] | None = None,
        collected_params: dict[str, Any] | None = None,
    ) -> ChatSession:
        with self._lock:
            self._delete_expired_sessions()
            session = self._require_session(session_id)

            if customer_id is not None:
                session.customer_id = customer_id
            if customer_email is not None:
                session.customer_email = customer_email
            if orders is not None:
                session.orders = orders
            if collected_params is not None:
                session.collected_params.update(collected_params)

            self._touch_session(session)
            return session.model_copy(deep=True)

    def delete_expired_sessions(self) -> int:
        with self._lock:
            return self._delete_expired_sessions()

    def _create_session(self) -> ChatSession:
        now = self._now()
        session_id = self._generate_session_id()
        while session_id in self._sessions:
            session_id = self._generate_session_id()

        session = ChatSession(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            expires_at=now + self.ttl,
        )
        self._sessions[session_id] = session
        return session.model_copy(deep=True)

    def _touch_session(self, session: ChatSession) -> None:
        now = self._now()
        session.updated_at = now
        session.expires_at = now + self.ttl

    def _delete_expired_sessions(self) -> int:
        now = self._now()
        expired_session_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired_session_ids:
            del self._sessions[session_id]

        return len(expired_session_ids)

    def _require_session(self, session_id: str) -> ChatSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown or expired session: {session_id}")

        return session

    def _generate_session_id(self) -> str:
        return token_urlsafe(32)


session_store = InMemorySessionStore()
