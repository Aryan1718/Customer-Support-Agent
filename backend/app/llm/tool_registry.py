from collections.abc import Callable, Mapping
from typing import Any

from app.tools import OrderStatus, Refund, customerInformation, openTicket, updateOrder

from .tool_params import build_tool_params


ToolExecutor = Callable[..., Any]
ToolRegistry = Mapping[str, ToolExecutor]


DEFAULT_TOOL_REGISTRY: dict[str, ToolExecutor] = {
    "customerInformation": customerInformation,
    "openTicket": openTicket,
    "OrderStatus": OrderStatus,
    "updateOrder": updateOrder,
    "Refund": Refund,
}


def execute_tool(
    tool_name: str,
    collected_params: Mapping[str, Any],
    registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
) -> Any:
    executor = registry.get(tool_name)
    if executor is None:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool_params = build_tool_params(tool_name, collected_params)
    return executor(**tool_params)
