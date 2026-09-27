from typing import Any

from ..config import LLMSettings
from ..types import LLMMessage, LLMResponse, LLMTool
from .base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, settings: LLMSettings) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai package to use the LLM layer.") from exc

        kwargs: dict[str, Any] = {"api_key": settings.api_key}
        if settings.base_url:
            kwargs["base_url"] = settings.base_url

        self.settings = settings
        self.client = OpenAI(**kwargs)

    def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        tools: list[LLMTool] | None = None,
    ) -> LLMResponse:
        formatted_messages = [{"role": "system", "content": system_prompt}]
        formatted_messages.extend(
            {"role": message.role, "content": message.content} for message in messages
        )

        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": formatted_messages,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
        }

        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        tool_calls = [
            tool_call.model_dump()
            for tool_call in (message.tool_calls or [])
        ]

        return LLMResponse(
            content=message.content or "",
            model=self.settings.model,
            raw=response,
            tool_calls=tool_calls,
        )
