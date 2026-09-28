import pytest
from pydantic import ValidationError

from app.llm.tool_registry import execute_tool


def test_execute_tool_validates_and_calls_registered_executor():
    calls = []

    def refund(email: str, orderID: int) -> bool:
        calls.append({"email": email, "orderID": orderID})
        return True

    result = execute_tool(
        "Refund",
        {"email": "maya.patel@example.test", "orderID": "42"},
        registry={"Refund": refund},
    )

    assert result is True
    assert calls == [{"email": "maya.patel@example.test", "orderID": 42}]


def test_execute_tool_rejects_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        execute_tool("missingTool", {}, registry={})


def test_execute_tool_rejects_invalid_params_before_calling_executor():
    calls = []

    def refund(email: str, orderID: int) -> bool:
        calls.append({"email": email, "orderID": orderID})
        return True

    with pytest.raises(ValidationError):
        execute_tool(
            "Refund",
            {"email": "maya.patel@example.test", "orderID": "not-valid"},
            registry={"Refund": refund},
        )

    assert calls == []
