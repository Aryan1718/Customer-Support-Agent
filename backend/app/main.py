import logging
import json
import re
import asyncio
from queue import Empty, Queue
from typing import Any
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
from .observability import (
    emit_observation,
    new_trace_context,
    summarize_plan,
    summarize_request,
    summarize_session,
    summarize_tool_selection,
    summarize_tool_calls,
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


class ChatResponse(BaseModel):
    session_id: str
    content: str
    model: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ChatPipelineResult(BaseModel):
    response: ChatResponse
    session: ChatSession


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
    response = _handle_chat_request(request)

    return response.model_dump()


@app.post("/llm/chat/stream")
async def llm_chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream_chat_response(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _handle_chat_request(request: ChatRequest) -> ChatResponse:
    return _run_chat_pipeline(request).response


def _run_chat_pipeline(
    request: ChatRequest,
    emit_status: Any | None = None,
) -> ChatPipelineResult:
    trace_context = new_trace_context()
    _emit_status(emit_status, "loading_session")
    session = session_store.get_or_create_session(request.session_id)
    emit_observation(
        "chat_turn_started",
        {
            "session": summarize_session(session),
            "request": summarize_request(request.message, len(request.history)),
        },
        trace_context,
    )
    _emit_status(emit_status, "calling_llm")
    service = get_llm_service()
    response = service.chat(
        message=request.message,
        history=_build_llm_history(session, request.history),
    )
    emit_observation(
        "llm_response_received",
        {
            "session_id": session.session_id,
            "model": response.model,
            "content_length": len(response.content),
            "tool_calls": summarize_tool_calls(response.tool_calls),
        },
        trace_context,
    )
    _emit_status(emit_status, "planning")
    plan = plan_tool_turn(
        session=session,
        user_message=request.message,
        tool_calls=response.tool_calls,
    )
    emit_observation(
        "tool_planning_decision",
        {
            "session_before_plan": summarize_session(session),
            "request": summarize_request(request.message, len(request.history)),
            "llm_tool_calls": summarize_tool_calls(response.tool_calls),
            "tool_selection": summarize_tool_selection(
                session,
                request.message,
                response.tool_calls,
                plan,
            ),
            "plan": summarize_plan(plan),
        },
        trace_context,
    )
    session = apply_tool_plan_to_session(session_store, session.session_id, plan)
    emit_observation(
        "session_after_plan_applied",
        {
            "session": summarize_session(session),
            "plan_action": plan.action,
            "plan_tool_name": plan.tool_name,
        },
        trace_context,
    )
    final_response = response
    final_content = response.content

    if plan.action == "ask_follow_up":
        _emit_status(
            emit_status,
            "collecting_missing_information",
            {"missing_params": plan.missing_params},
        )
        final_content = plan.follow_up_prompt or response.content
    elif plan.action == "execute_tool":
        _emit_status(
            emit_status,
            "executing_tool",
            {"tool_name": plan.tool_name, "tool_params": plan.tool_params},
        )
        emit_observation(
            "tool_execution_started",
            {
                "session_id": session.session_id,
                "tool_name": plan.tool_name,
                "tool_params": plan.tool_params,
                "collected_params": plan.collected_params,
            },
            trace_context,
        )
        tool_result = execute_tool_plan(plan, DEFAULT_TOOL_REGISTRY)
        emit_observation(
            "tool_execution_finished",
            {
                "session_id": session.session_id,
                "tool_name": plan.tool_name,
                "tool_result": tool_result,
            },
            trace_context,
        )
        _emit_status(
            emit_status,
            "generating_tool_response",
            {"tool_name": plan.tool_name},
        )
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
        _emit_status(
            emit_status,
            "validating_response",
            {"tool_name": plan.tool_name},
        )
        validated_response = validate_tool_response(
            service=service,
            original_user_message=request.message,
            tool_name=plan.tool_name or "",
            tool_params=plan.tool_params,
            tool_result=tool_result,
            candidate_response=final_content,
        )
        emit_observation(
            "tool_response_validated",
            {
                "session_id": session.session_id,
                "tool_name": plan.tool_name,
                "candidate_content_length": len(final_response.content),
                "validated_content_length": len(validated_response.content),
            },
            trace_context,
        )
        final_content = validated_response.content
    else:
        _emit_status(emit_status, "finalizing")

    _emit_status(emit_status, "storing_conversation")
    session = session_store.append_conversation(
        session_id=session.session_id,
        user_input=request.message,
        llm_response=final_content,
    )
    emit_observation(
        "chat_turn_stored",
        {
            "session": summarize_session(session),
            "final_content_length": len(final_content),
        },
        trace_context,
    )
    _log_session("chat_turn_stored", session)

    return ChatPipelineResult(
        response=ChatResponse(
            session_id=session.session_id,
            content=final_content,
            model=final_response.model,
            tool_calls=response.tool_calls,
        ),
        session=session,
    )


async def _stream_chat_response(request: ChatRequest) -> AsyncIterator[str]:
    status_queue: Queue[str | ChatPipelineResult | BaseException] = Queue()

    def capture_status(stage: str, detail: dict[str, Any] | None = None) -> None:
        status_queue.put(_format_status_event(stage, detail))

    yield _format_status_event("received")

    async def run_pipeline() -> None:
        try:
            result = await asyncio.to_thread(
                _run_chat_pipeline,
                request,
                capture_status,
            )
        except BaseException as exc:
            status_queue.put(exc)
        else:
            status_queue.put(result)

    pipeline_task = asyncio.create_task(run_pipeline())
    pipeline_result: ChatPipelineResult | None = None

    while pipeline_result is None:
        try:
            event = status_queue.get_nowait()
        except Empty:
            if pipeline_task.done():
                await pipeline_task
            await asyncio.sleep(0.01)
            continue

        if isinstance(event, ChatPipelineResult):
            pipeline_result = event
        elif isinstance(event, BaseException):
            raise event
        else:
            yield event

    await pipeline_task

    response = pipeline_result.response
    yield _format_stream_event(
        "metadata",
        {
            "session_id": response.session_id,
            "model": response.model,
            "tool_calls": response.tool_calls,
        },
    )

    for chunk in _split_stream_chunks(response.content):
        yield _format_stream_event("content", {"delta": chunk})

    yield _format_stream_event(
        "done",
        {
            "session_id": response.session_id,
            "content": response.content,
            "model": response.model,
            "tool_calls": response.tool_calls,
        },
    )


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


def _split_stream_chunks(content: str) -> list[str]:
    return re.findall(r"\S+\s*", content) or [""]


def _format_stream_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _format_status_event(stage: str, detail: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"stage": stage}
    if detail:
        payload["detail"] = detail

    return _format_stream_event("status", payload)


def _emit_status(
    emit_status: Any | None,
    stage: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if emit_status is not None:
        emit_status(stage, detail)


def _log_session(event: str, session: ChatSession) -> None:
    logger.info(
        "session_%s: %s",
        event,
        session.model_dump(mode="json"),
    )
