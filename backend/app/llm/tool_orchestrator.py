from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.session_store import ChatSession, InMemorySessionStore

from .follow_up_prompts import build_follow_up_prompt
from .parameter_extraction import extract_turn_parameters
from .tool_params import build_tool_params, get_missing_tool_params
from .tool_registry import ToolRegistry, execute_tool


ToolTurnAction = Literal["no_tool", "ask_follow_up", "execute_tool"]


class ToolTurnPlan(BaseModel):
    action: ToolTurnAction
    tool_name: str | None = None
    collected_params: dict[str, Any] = Field(default_factory=dict)
    missing_params: list[str] = Field(default_factory=list)
    tool_params: dict[str, Any] = Field(default_factory=dict)
    follow_up_prompt: str | None = None


def plan_tool_turn(
    session: ChatSession,
    user_message: str,
    tool_calls: Sequence[Mapping[str, Any]] | None = None,
) -> ToolTurnPlan:
    extraction = extract_turn_parameters(
        user_message=user_message,
        tool_calls=tool_calls,
        active_tool=session.active_tool,
    )
    tool_name = extraction.tool_name or session.active_tool
    collected_params = {**session.collected_params, **extraction.params}

    if tool_name is None:
        return ToolTurnPlan(action="no_tool", collected_params=collected_params)

    missing_params = get_missing_tool_params(tool_name, collected_params)
    if missing_params:
        return ToolTurnPlan(
            action="ask_follow_up",
            tool_name=tool_name,
            collected_params=collected_params,
            missing_params=missing_params,
            follow_up_prompt=build_follow_up_prompt(missing_params),
        )

    return ToolTurnPlan(
        action="execute_tool",
        tool_name=tool_name,
        collected_params=collected_params,
        tool_params=build_tool_params(tool_name, collected_params),
    )


def execute_tool_plan(
    plan: ToolTurnPlan,
    registry: ToolRegistry,
) -> Any:
    if plan.action != "execute_tool" or plan.tool_name is None:
        raise ValueError("Tool plan is not ready for execution.")

    return execute_tool(plan.tool_name, plan.collected_params, registry)


def apply_tool_plan_to_session(
    store: InMemorySessionStore,
    session_id: str,
    plan: ToolTurnPlan,
) -> ChatSession:
    session = store.update_context(
        session_id,
        collected_params=plan.collected_params,
    )

    if plan.action == "ask_follow_up":
        return store.update_tool_state(
            session.session_id,
            active_tool=plan.tool_name,
            last_missing_params=plan.missing_params,
        )

    if plan.action == "execute_tool":
        return store.update_tool_state(
            session.session_id,
            active_tool=None,
        )

    return session
