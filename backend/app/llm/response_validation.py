import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .service import LLMService


logger = logging.getLogger(__name__)

ValidationSeverity = Literal["none", "low", "medium", "high"]
ValidationStatus = Literal["allowed", "fallback", "warning"]

RESPONSE_VALIDATOR_SYSTEM_PROMPT = (
    "You are a strict customer-support response validator. Check whether the "
    "candidate assistant response is fully supported by the verified backend "
    "tool result. Return only JSON matching the requested schema. Mark high "
    "severity only for clear dangerous contradictions, invented successful "
    "actions, invented identifiers, or exposed internal/private data. If you "
    "are unsure, use low or medium severity, not high."
)


class ResponseValidationVerdict(BaseModel):
    valid: bool
    severity: ValidationSeverity
    reason: str = Field(min_length=1)
    fallback_response: str | None = None

    @model_validator(mode="after")
    def validate_verdict_consistency(self) -> "ResponseValidationVerdict":
        if self.valid and self.severity != "none":
            raise ValueError("valid verdicts must use severity 'none'")
        if not self.valid and self.severity == "none":
            raise ValueError("invalid verdicts must use low, medium, or high severity")
        if not self.valid and self.severity == "high" and not self.fallback_response:
            raise ValueError("high severity verdicts require a fallback_response")

        return self


class ValidatedResponse(BaseModel):
    content: str
    status: ValidationStatus
    verdict: ResponseValidationVerdict | None = None
    validation_error: str | None = None


def validate_tool_response(
    service: LLMService,
    *,
    original_user_message: str,
    tool_name: str,
    tool_params: dict[str, Any],
    tool_result: Any,
    candidate_response: str,
) -> ValidatedResponse:
    try:
        verdict = _get_validation_verdict(
            service=service,
            original_user_message=original_user_message,
            tool_name=tool_name,
            tool_params=tool_params,
            tool_result=tool_result,
            candidate_response=candidate_response,
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.warning("response_validation_failed_open: %s", exc)
        return ValidatedResponse(
            content=candidate_response,
            status="warning",
            validation_error=str(exc),
        )

    return apply_validation_decision(candidate_response, verdict)


def apply_validation_decision(
    candidate_response: str,
    verdict: ResponseValidationVerdict,
) -> ValidatedResponse:
    if verdict.valid:
        return ValidatedResponse(
            content=candidate_response,
            status="allowed",
            verdict=verdict,
        )

    if verdict.severity == "high" and verdict.fallback_response:
        return ValidatedResponse(
            content=verdict.fallback_response,
            status="fallback",
            verdict=verdict,
        )

    logger.warning(
        "response_validation_warning: severity=%s reason=%s",
        verdict.severity,
        verdict.reason,
    )
    return ValidatedResponse(
        content=candidate_response,
        status="warning",
        verdict=verdict,
    )


def _get_validation_verdict(
    service: LLMService,
    *,
    original_user_message: str,
    tool_name: str,
    tool_params: dict[str, Any],
    tool_result: Any,
    candidate_response: str,
) -> ResponseValidationVerdict:
    response = service.chat(
        message=_build_validation_message(
            original_user_message=original_user_message,
            tool_name=tool_name,
            tool_params=tool_params,
            tool_result=tool_result,
            candidate_response=candidate_response,
        ),
        system_prompt=RESPONSE_VALIDATOR_SYSTEM_PROMPT,
        tools=[],
    )
    verdict_payload = json.loads(response.content)
    return ResponseValidationVerdict(**verdict_payload)


def _build_validation_message(
    *,
    original_user_message: str,
    tool_name: str,
    tool_params: dict[str, Any],
    tool_result: Any,
    candidate_response: str,
) -> str:
    payload = {
        "original_user_message": original_user_message,
        "tool_name": tool_name,
        "tool_params": tool_params,
        "tool_result": tool_result,
        "candidate_response": candidate_response,
        "schema": {
            "valid": "boolean",
            "severity": "one of: none, low, medium, high",
            "reason": "non-empty string",
            "fallback_response": "string or null",
        },
        "decision_rules": [
            "valid=true only when the candidate response is supported by the tool result.",
            "severity=high only for clear dangerous contradictions or invented actions.",
            "If severity=high, provide a safe fallback_response grounded in the tool result.",
            "If unsure, return valid=false with low or medium severity.",
        ],
    }

    return (
        "Validate this candidate customer-support response against the verified "
        "tool result. Return only JSON.\n"
        f"{json.dumps(payload, default=str)}"
    )
