from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from app.llm import LLMResponse
from app.llm.response_validation import (
    ResponseValidationVerdict,
    apply_validation_decision,
    validate_tool_response,
)


@dataclass
class FakeLLMService:
    response_content: str
    calls: list[dict] = field(default_factory=list)

    def chat(self, *args, **kwargs) -> LLMResponse:
        self.calls.append({"args": args, "kwargs": kwargs})
        return LLMResponse(content=self.response_content, model="test-model")


def test_response_validation_verdict_requires_consistent_valid_state():
    with pytest.raises(ValidationError):
        ResponseValidationVerdict(
            valid=True,
            severity="low",
            reason="Looks mostly fine.",
        )


def test_response_validation_verdict_requires_fallback_for_high_severity():
    with pytest.raises(ValidationError):
        ResponseValidationVerdict(
            valid=False,
            severity="high",
            reason="Contradicts tool result.",
        )


def test_apply_validation_decision_allows_valid_response():
    verdict = ResponseValidationVerdict(
        valid=True,
        severity="none",
        reason="Supported by the tool result.",
    )

    result = apply_validation_decision("Original response", verdict)

    assert result.status == "allowed"
    assert result.content == "Original response"


def test_apply_validation_decision_uses_fallback_for_high_severity():
    verdict = ResponseValidationVerdict(
        valid=False,
        severity="high",
        reason="Says refund approved when tool requires human approval.",
        fallback_response="Your refund request needs human approval.",
    )

    result = apply_validation_decision("Your refund is approved.", verdict)

    assert result.status == "fallback"
    assert result.content == "Your refund request needs human approval."


def test_apply_validation_decision_keeps_response_for_low_severity_warning():
    verdict = ResponseValidationVerdict(
        valid=False,
        severity="low",
        reason="Could be more complete.",
    )

    result = apply_validation_decision("Original response", verdict)

    assert result.status == "warning"
    assert result.content == "Original response"


def test_validate_tool_response_parses_validator_json_and_disables_tools():
    service = FakeLLMService(
        response_content=(
            '{"valid": true, "severity": "none", '
            '"reason": "Supported.", "fallback_response": null}'
        )
    )

    result = validate_tool_response(
        service,
        original_user_message="order id is 42",
        tool_name="Refund",
        tool_params={"email": "maya.patel@example.test", "orderID": 42},
        tool_result="Human Approval",
        candidate_response="Your refund request needs human approval.",
    )

    assert result.status == "allowed"
    assert result.content == "Your refund request needs human approval."
    assert service.calls[0]["kwargs"]["tools"] == []
    assert "Human Approval" in service.calls[0]["kwargs"]["message"]


def test_validate_tool_response_fails_open_for_invalid_validator_json():
    service = FakeLLMService(response_content="not-json")

    result = validate_tool_response(
        service,
        original_user_message="order id is 42",
        tool_name="Refund",
        tool_params={"email": "maya.patel@example.test", "orderID": 42},
        tool_result="Human Approval",
        candidate_response="Your refund request needs human approval.",
    )

    assert result.status == "warning"
    assert result.content == "Your refund request needs human approval."
    assert result.validation_error
