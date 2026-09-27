from functools import lru_cache

from .config import LLMSettings, get_llm_settings
from .guardrails import evaluate_assistant_response, evaluate_user_message
from .prompts import DEFAULT_SYSTEM_PROMPT
from .providers import LLMProvider, OpenAICompatibleProvider
from .tool_schemas import CUSTOMER_SUPPORT_TOOLS
from .types import LLMMessage, LLMResponse, LLMTool


class LLMService:
    def __init__(
        self,
        settings: LLMSettings,
        provider: LLMProvider,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        tools: list[LLMTool] | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools or []

    def chat(
        self,
        message: str,
        history: list[LLMMessage] | None = None,
        system_prompt: str | None = None,
        tools: list[LLMTool] | None = None,
    ) -> LLMResponse:
        user_guardrail = evaluate_user_message(message)
        if not user_guardrail.allowed:
            return LLMResponse(
                content=user_guardrail.safe_response or "",
                model=self.settings.model,
            )

        messages = history or []
        messages = [*messages, LLMMessage(role="user", content=message)]

        response = self.provider.generate(
            messages=messages,
            system_prompt=system_prompt or self.system_prompt,
            tools=self.tools if tools is None else tools,
        )

        assistant_guardrail = evaluate_assistant_response(response.content)
        if not assistant_guardrail.allowed:
            return LLMResponse(
                content=assistant_guardrail.safe_response or "",
                model=response.model,
                raw=response.raw,
                tool_calls=response.tool_calls,
            )

        return response


def _build_provider(settings: LLMSettings) -> LLMProvider:
    return OpenAICompatibleProvider(settings)


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_llm_settings()
    return LLMService(
        settings=settings,
        provider=_build_provider(settings),
        tools=CUSTOMER_SUPPORT_TOOLS,
    )
