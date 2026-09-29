import logging
import json
from typing import Any
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from database import check_connection

from .llm import (
    DEFAULT_TOOL_REGISTRY,
    LLMMessage,
    ToolTurnPlan,
    apply_tool_plan_to_session,
    execute_tool_plan,
    get_llm_service,
    plan_tool_turn,
    validate_tool_response,
)
from .session_store import ChatSession, session_store

logger = logging.getLogger(__name__)
SESSION_HISTORY_TURN_LIMIT = 6

TOOL_RESULT_SYSTEM_PROMPT = (
    "You write concise customer support responses from verified backend tool results. "
    "Use only the provided tool result and context. Do not invent order statuses, "
    "refund approvals, ticket IDs, or actions that are not in the tool result."
)

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
        history=_build_llm_history(session, request.history),
    )
    plan = plan_tool_turn(
        session=session,
        user_message=request.message,
        tool_calls=response.tool_calls,
    )
    session = apply_tool_plan_to_session(session_store, session.session_id, plan)
    final_response = response
    final_content = response.content

    if plan.action == "ask_follow_up":
        final_content = plan.follow_up_prompt or response.content
    elif plan.action == "execute_tool":
        tool_result = execute_tool_plan(plan, DEFAULT_TOOL_REGISTRY)
        final_response = service.chat(
            message=_build_tool_result_message(
                user_message=request.message,
                plan=plan,
                tool_result=tool_result,
            ),
            history=_build_llm_history(session, []),
            system_prompt=TOOL_RESULT_SYSTEM_PROMPT,
            tools=[],
        )
        final_content = final_response.content
        validated_response = validate_tool_response(
            service=service,
            original_user_message=request.message,
            tool_name=plan.tool_name or "",
            tool_params=plan.tool_params,
            tool_result=tool_result,
            candidate_response=final_content,
        )
        final_content = validated_response.content

    session = session_store.append_conversation(
        session_id=session.session_id,
        user_input=request.message,
        llm_response=final_content,
    )
    _log_session("chat_turn_stored", session)

    return {
        "session_id": session.session_id,
        "content": final_content,
        "model": final_response.model,
        "tool_calls": response.tool_calls,
    }


def _session_response(session: ChatSession) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "expires_at": session.expires_at,
    }


def _build_llm_history(
    session: ChatSession,
    request_history: list[ChatMessage],
) -> list[LLMMessage]:
    if session.conversations:
        messages: list[LLMMessage] = []
        for conversation in session.conversations[-SESSION_HISTORY_TURN_LIMIT:]:
            messages.append(LLMMessage(role="user", content=conversation.user_input))
            messages.append(
                LLMMessage(role="assistant", content=conversation.llm_response)
            )

        return messages

    return [
        LLMMessage(role=message.role, content=message.content)
        for message in request_history
    ]


def _build_tool_result_message(
    user_message: str,
    plan: ToolTurnPlan,
    tool_result: Any,
) -> str:
    payload = {
        "original_user_message": user_message,
        "tool_name": plan.tool_name,
        "tool_params": plan.tool_params,
        "tool_result": tool_result,
    }

    return (
        "Generate a customer-facing response for this verified tool result.\n"
        f"{json.dumps(payload, default=str)}"
    )


def _log_session(event: str, session: ChatSession) -> None:
    logger.info(
        "session_%s: %s",
        event,
        session.model_dump(mode="json"),
    )
