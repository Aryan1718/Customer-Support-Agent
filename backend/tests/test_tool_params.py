import pytest
from pydantic import ValidationError

from app.llm import (
    build_tool_params,
    get_missing_tool_params,
    has_required_tool_params,
)


def test_has_required_tool_params_returns_true_when_refund_context_is_complete():
    collected_context = {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }

    assert has_required_tool_params("Refund", collected_context) is True


def test_has_required_tool_params_returns_false_when_required_value_is_missing():
    collected_context = {"email": "maya.patel@example.test"}

    assert has_required_tool_params("Refund", collected_context) is False


def test_get_missing_tool_params_returns_exact_tool_parameter_names():
    collected_context = {"email": "maya.patel@example.test"}

    assert get_missing_tool_params("Refund", collected_context) == ["orderID"]


def test_blank_strings_count_as_missing_required_parameters():
    collected_context = {
        "customerEmail": "maya.patel@example.test",
        "issue": "   ",
    }

    assert get_missing_tool_params("openTicket", collected_context) == ["issue"]


def test_invalid_required_type_counts_as_missing_parameter():
    collected_context = {
        "email": "maya.patel@example.test",
        "orderID": "not-an-order-id",
    }

    assert has_required_tool_params("Refund", collected_context) is False
    assert get_missing_tool_params("Refund", collected_context) == ["orderID"]


def test_build_tool_params_returns_exact_refund_tool_shape():
    collected_context = {
        "email": "maya.patel@example.test",
        "orderID": 42,
        "issue": "Damaged item",
    }

    assert build_tool_params("Refund", collected_context) == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_build_tool_params_coerces_valid_integer_strings():
    collected_context = {
        "email": "maya.patel@example.test",
        "orderID": "42",
    }

    assert build_tool_params("Refund", collected_context) == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_build_tool_params_validates_required_parameter_types():
    collected_context = {
        "email": "maya.patel@example.test",
        "orderID": "not-an-order-id",
    }

    with pytest.raises(ValidationError):
        build_tool_params("Refund", collected_context)


def test_build_tool_params_supports_common_aliases_for_mixed_tool_names():
    collected_context = {
        "email": "maya.patel@example.test",
        "order_id": 42,
    }

    assert build_tool_params("updateOrder", collected_context) == {
        "Email": "maya.patel@example.test",
        "OrderId": 42,
    }


def test_exact_parameter_value_wins_over_alias_value():
    collected_context = {
        "Email": "exact@example.test",
        "email": "alias@example.test",
        "OrderId": 42,
        "order_id": 999,
    }

    assert build_tool_params("updateOrder", collected_context) == {
        "Email": "exact@example.test",
        "OrderId": 42,
    }


def test_unknown_tool_raises_value_error():
    with pytest.raises(ValueError, match="Unknown tool"):
        get_missing_tool_params("missingTool", {})
