from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ObservationEventName = Literal[
    "chat_turn_started",
    "llm_response_received",
    "tool_planning_decision",
    "session_after_plan_applied",
    "tool_execution_started",
    "tool_execution_finished",
    "tool_response_validated",
    "chat_turn_stored",
]

ToolTurnAction = Literal["no_tool", "ask_follow_up", "execute_tool"]
ToolSelectionSource = Literal[
    "llm_tool_call",
    "session_active_tool",
    "keyword_detection",
    "none",
]


class StrictObservationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TraceFields(StrictObservationModel):
    trace_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)


class RequestSummary(StrictObservationModel):
    message: str
    message_length: int = Field(ge=0)
    history_count: int = Field(ge=0)


class SessionSummary(StrictObservationModel):
    session_id: str
    active_tool: str | None = None
    last_missing_params: list[str]
    collected_params: dict[str, Any]
    conversation_count: int = Field(ge=0)
    expires_at: Any


class ToolCallFunctionSummary(StrictObservationModel):
    name: str | None = None
    arguments: Any | None = None


class ToolCallSummary(StrictObservationModel):
    type: Any | None = None
    id: Any | None = None
    function: ToolCallFunctionSummary | None = None


class ToolTurnPlanSummary(StrictObservationModel):
    action: ToolTurnAction
    tool_name: str | None = None
    missing_params: list[str]
    collected_params: dict[str, Any]
    tool_params: dict[str, Any]
    follow_up_prompt: str | None = None


class ToolSelectionSummary(StrictObservationModel):
    selected_by: ToolSelectionSource
    llm_tool_name: str | None = None
    session_active_tool: str | None = None
    keyword_tool_name: str | None = None
    final_tool_name: str | None = None
    planner_action: ToolTurnAction


class ChatTurnStartedPayload(StrictObservationModel):
    session: SessionSummary
    request: RequestSummary


class LLMResponseReceivedPayload(StrictObservationModel):
    session_id: str
    model: str
    content_length: int = Field(ge=0)
    tool_calls: list[ToolCallSummary]


class ToolPlanningDecisionPayload(StrictObservationModel):
    session_before_plan: SessionSummary
    request: RequestSummary
    llm_tool_calls: list[ToolCallSummary]
    tool_selection: ToolSelectionSummary
    plan: ToolTurnPlanSummary


class SessionAfterPlanAppliedPayload(StrictObservationModel):
    session: SessionSummary
    plan_action: ToolTurnAction
    plan_tool_name: str | None = None


class ToolExecutionStartedPayload(StrictObservationModel):
    session_id: str
    tool_name: str | None = None
    tool_params: dict[str, Any]
    collected_params: dict[str, Any]


class ToolExecutionFinishedPayload(StrictObservationModel):
    session_id: str
    tool_name: str | None = None
    tool_result: Any


class ToolResponseValidatedPayload(StrictObservationModel):
    session_id: str
    tool_name: str | None = None
    candidate_content_length: int = Field(ge=0)
    validated_content_length: int = Field(ge=0)


class ChatTurnStoredPayload(StrictObservationModel):
    session: SessionSummary
    final_content_length: int = Field(ge=0)


ObservationPayload = (
    ChatTurnStartedPayload
    | LLMResponseReceivedPayload
    | ToolPlanningDecisionPayload
    | SessionAfterPlanAppliedPayload
    | ToolExecutionStartedPayload
    | ToolExecutionFinishedPayload
    | ToolResponseValidatedPayload
    | ChatTurnStoredPayload
)

PAYLOAD_MODELS: dict[ObservationEventName, type[ObservationPayload]] = {
    "chat_turn_started": ChatTurnStartedPayload,
    "llm_response_received": LLMResponseReceivedPayload,
    "tool_planning_decision": ToolPlanningDecisionPayload,
    "session_after_plan_applied": SessionAfterPlanAppliedPayload,
    "tool_execution_started": ToolExecutionStartedPayload,
    "tool_execution_finished": ToolExecutionFinishedPayload,
    "tool_response_validated": ToolResponseValidatedPayload,
    "chat_turn_stored": ChatTurnStoredPayload,
}


class ObservationEvent(StrictObservationModel):
    event_name: ObservationEventName
    trace_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    payload: ObservationPayload


def validate_observation_event(
    event_name: str,
    trace_fields: dict[str, str],
    payload: dict[str, Any],
) -> ObservationEvent:
    payload_model = PAYLOAD_MODELS[event_name]  # type: ignore[index]
    validated_payload = payload_model(**payload)

    return ObservationEvent(
        event_name=event_name,
        **trace_fields,
        payload=validated_payload,
    )
