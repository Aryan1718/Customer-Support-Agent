from abc import ABC, abstractmethod

from ..types import LLMMessage, LLMResponse, LLMTool


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        tools: list[LLMTool] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError
