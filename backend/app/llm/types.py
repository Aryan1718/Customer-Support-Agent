from dataclasses import dataclass, field
from typing import Any, Literal

LLMRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str


@dataclass(frozen=True)
class LLMTool:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    raw: Any | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
