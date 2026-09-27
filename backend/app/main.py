from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from database import check_connection

from .llm import LLMMessage, get_llm_service

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
    history: list[ChatMessage] = Field(default_factory=list)


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
    service = get_llm_service()
    response = service.chat(
        message=request.message,
        history=[
            LLMMessage(role=message.role, content=message.content)
            for message in request.history
        ],
    )

    return {
        "content": response.content,
        "model": response.model,
        "tool_calls": response.tool_calls,
    }
