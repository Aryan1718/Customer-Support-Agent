from collections.abc import Mapping, Sequence
from typing import Annotated
from typing import Any

from pydantic import ConfigDict, StringConstraints, TypeAdapter, create_model

from .tool_schemas import CUSTOMER_SUPPORT_TOOLS
from .types import LLMTool


ToolContext = Mapping[str, Any]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

PARAMETER_ALIASES: dict[str, tuple[str, ...]] = {
    "email": ("email", "Email", "customerEmail", "customer_email"),
    "Email": ("Email", "email", "customerEmail", "customer_email"),
    "customerEmail": ("customerEmail", "email", "Email", "customer_email"),
    "orderID": ("orderID", "OrderId", "orderId", "order_id"),
    "OrderId": ("OrderId", "orderID", "orderId", "order_id"),
}


def has_required_tool_params(
    tool_name: str,
    collected_context: ToolContext,
    tools: Sequence[LLMTool] = CUSTOMER_SUPPORT_TOOLS,
) -> bool:
    return not get_missing_tool_params(tool_name, collected_context, tools)


def get_missing_tool_params(
    tool_name: str,
    collected_context: ToolContext,
    tools: Sequence[LLMTool] = CUSTOMER_SUPPORT_TOOLS,
) -> list[str]:
    tool = _get_tool(tool_name, tools)

    return [
        parameter_name
        for parameter_name in _get_required_parameter_names(tool)
        if not _has_valid_parameter_value(tool, parameter_name, collected_context)
    ]


def build_tool_params(
    tool_name: str,
    collected_context: ToolContext,
    tools: Sequence[LLMTool] = CUSTOMER_SUPPORT_TOOLS,
) -> dict[str, Any]:
    tool = _get_tool(tool_name, tools)
    parameter_names = tool.parameters.get("properties", {}).keys()
    raw_params = {
        parameter_name: value
        for parameter_name in parameter_names
        if (value := _get_parameter_value(parameter_name, collected_context)) is not None
    }

    validated_params = _build_tool_params_model(tool)(**raw_params)
    return validated_params.model_dump(exclude_none=True)


def _get_tool(tool_name: str, tools: Sequence[LLMTool]) -> LLMTool:
    for tool in tools:
        if tool.name == tool_name:
            return tool

    raise ValueError(f"Unknown tool: {tool_name}")


def _get_required_parameter_names(tool: LLMTool) -> list[str]:
    required = tool.parameters.get("required", [])
    if not isinstance(required, list):
        return []

    return [parameter_name for parameter_name in required if isinstance(parameter_name, str)]


def _has_valid_parameter_value(
    tool: LLMTool,
    parameter_name: str,
    collected_context: ToolContext,
) -> bool:
    value = _get_parameter_value(parameter_name, collected_context)
    if value is None:
        return False

    parameter_schema = tool.parameters.get("properties", {}).get(parameter_name, {})
    if not isinstance(parameter_schema, dict):
        return True

    try:
        TypeAdapter(_get_parameter_type(parameter_schema)).validate_python(value)
    except ValueError:
        return False

    return True


def _get_parameter_value(parameter_name: str, collected_context: ToolContext) -> Any | None:
    for candidate_name in PARAMETER_ALIASES.get(parameter_name, (parameter_name,)):
        if candidate_name in collected_context:
            return collected_context[candidate_name]

    return None


def _build_tool_params_model(tool: LLMTool) -> type:
    required_parameter_names = set(_get_required_parameter_names(tool))
    properties = tool.parameters.get("properties", {})
    fields: dict[str, tuple[Any, Any]] = {}

    if not isinstance(properties, dict):
        properties = {}

    for parameter_name, parameter_schema in properties.items():
        if not isinstance(parameter_name, str) or not isinstance(parameter_schema, dict):
            continue

        parameter_type = _get_parameter_type(parameter_schema)
        default = ... if parameter_name in required_parameter_names else None
        if default is None:
            parameter_type = parameter_type | None

        fields[parameter_name] = (parameter_type, default)

    model_name = f"{tool.name}ToolParams"
    return create_model(
        model_name,
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def _get_parameter_type(parameter_schema: dict[str, Any]) -> Any:
    schema_type = parameter_schema.get("type")

    if schema_type == "string":
        return NonEmptyString
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list[Any]
    if schema_type == "object":
        return dict[str, Any]

    return Any
