import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field


EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
ORDER_ID_PATTERN = re.compile(
    r"\b(?:order\s*(?:id|number|#)?|orderid)\s*(?:is|:|#)?\s*(\d+)\b",
    re.IGNORECASE,
)

TOOL_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Refund", ("refund", "return my money", "money back")),
    ("updateOrder", ("update order", "change order", "modify order")),
    ("OrderStatus", ("order status", "track order", "where is my order", "my orders")),
    ("openTicket", ("open ticket", "create ticket", "file ticket", "support ticket")),
    ("customerInformation", ("account", "profile", "customer information")),
)


class ParameterExtraction(BaseModel):
    tool_name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


def extract_turn_parameters(
    user_message: str,
    tool_calls: Sequence[Mapping[str, Any]] | None = None,
    active_tool: str | None = None,
) -> ParameterExtraction:
    extraction = extract_params_from_tool_calls(tool_calls or [])
    text_params = extract_params_from_text(user_message, extraction.tool_name or active_tool)

    return ParameterExtraction(
        tool_name=extraction.tool_name or active_tool or detect_tool_from_text(user_message),
        params={**extraction.params, **text_params},
    )


def extract_params_from_tool_calls(
    tool_calls: Sequence[Mapping[str, Any]],
) -> ParameterExtraction:
    for tool_call in tool_calls:
        function_payload = tool_call.get("function")
        if not isinstance(function_payload, Mapping):
            continue

        tool_name = function_payload.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            continue

        return ParameterExtraction(
            tool_name=tool_name,
            params=_parse_arguments(function_payload.get("arguments")),
        )

    return ParameterExtraction()


def extract_params_from_text(
    user_message: str,
    tool_name: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    email_match = EMAIL_PATTERN.search(user_message)
    if email_match:
        params["email"] = email_match.group(0)

    order_id_match = ORDER_ID_PATTERN.search(user_message)
    if order_id_match:
        params["orderID"] = int(order_id_match.group(1))

    if tool_name == "openTicket" and user_message.strip():
        params["issue"] = user_message.strip()

    return params


def detect_tool_from_text(user_message: str) -> str | None:
    normalized_message = user_message.lower()

    for tool_name, keywords in TOOL_KEYWORDS:
        if any(keyword in normalized_message for keyword in keywords):
            return tool_name

    return None


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, Mapping):
        return dict(arguments)

    if not isinstance(arguments, str) or not arguments.strip():
        return {}

    try:
        parsed_arguments = json.loads(arguments)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed_arguments, Mapping):
        return dict(parsed_arguments)

    return {}
