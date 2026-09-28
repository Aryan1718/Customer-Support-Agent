from app.llm.parameter_extraction import (
    detect_tool_from_text,
    extract_params_from_text,
    extract_params_from_tool_calls,
    extract_turn_parameters,
)


def test_extract_params_from_tool_calls_parses_json_arguments():
    extraction = extract_params_from_tool_calls(
        [
            {
                "function": {
                    "name": "Refund",
                    "arguments": '{"email": "maya.patel@example.test", "orderID": 42}',
                }
            }
        ]
    )

    assert extraction.tool_name == "Refund"
    assert extraction.params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_extract_params_from_tool_calls_ignores_invalid_arguments():
    extraction = extract_params_from_tool_calls(
        [{"function": {"name": "Refund", "arguments": "not-json"}}]
    )

    assert extraction.tool_name == "Refund"
    assert extraction.params == {}


def test_extract_params_from_text_finds_email_and_order_id():
    params = extract_params_from_text(
        "My email is maya.patel@example.test and order id is 42"
    )

    assert params == {
        "email": "maya.patel@example.test",
        "orderID": 42,
    }


def test_extract_params_from_text_uses_message_as_ticket_issue_for_open_ticket():
    params = extract_params_from_text("My package arrived damaged", "openTicket")

    assert params == {"issue": "My package arrived damaged"}


def test_detect_tool_from_text_uses_lightweight_keywords():
    assert detect_tool_from_text("I want a refund") == "Refund"
    assert detect_tool_from_text("Where is my order?") == "OrderStatus"


def test_extract_turn_parameters_prefers_tool_call_tool_and_latest_text_values():
    extraction = extract_turn_parameters(
        user_message="Use maya.patel@example.test and order id is 99",
        tool_calls=[
            {
                "function": {
                    "name": "Refund",
                    "arguments": '{"email": "old@example.test", "orderID": 42}',
                }
            }
        ],
    )

    assert extraction.tool_name == "Refund"
    assert extraction.params == {
        "email": "maya.patel@example.test",
        "orderID": 99,
    }
