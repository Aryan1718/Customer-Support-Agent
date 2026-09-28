import logging
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from database import check_connection

from .llm import LLMMessage, get_llm_service
from .session_store import ChatSession, session_store

logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Support Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Customer Support Agent API is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/db")
async def database_health() -> dict[str, str]:
    try:
        check_connection()
    except (RuntimeError, SQLAlchemyError) as exc:
        return {"status": "unhealthy", "detail": str(exc)}

    return {"status": "healthy"}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


@app.post("/sessions")
async def create_session() -> dict[str, object]:
    session = session_store.create_session()
    _log_session("created", session)

    return _session_response(session)


@app.get("/health/llm")
async def llm_health() -> dict[str, str]:
    try:
        service = get_llm_service()
    except RuntimeError as exc:
        return {"status": "unhealthy", "detail": str(exc)}

    return {
        "status": "healthy",
        "model": service.settings.model,
    }


@app.post("/llm/chat")
async def llm_chat(request: ChatRequest) -> dict[str, object]:
    session = session_store.get_or_create_session(request.session_id)
    service = get_llm_service()
    response = service.chat(
        message=request.message,
        history=[
            LLMMessage(role=message.role, content=message.content)
            for message in request.history
        ],
    )
    session = session_store.append_conversation(
        session_id=session.session_id,
        user_input=request.message,
        llm_response=response.content,
    )
    _log_session("chat_turn_stored", session)

    return {
        "session_id": session.session_id,
        "content": response.content,
        "model": response.model,
        "tool_calls": response.tool_calls,
    }


def _session_response(session: ChatSession) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "expires_at": session.expires_at,
    }


def _log_session(event: str, session: ChatSession) -> None:
    logger.info(
        "session_%s: %s",
        event,
        session.model_dump(mode="json"),
    )
