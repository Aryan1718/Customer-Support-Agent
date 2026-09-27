import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMSettings:
    model: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int = 1000
    base_url: str | None = None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to .env.")

    return value


def _required_api_key() -> str:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set. Add your provider API key to .env.")

    return api_key


@lru_cache
def get_llm_settings() -> LLMSettings:
    load_dotenv()

    return LLMSettings(
        model=_required_env("LLM_MODEL").strip(),
        api_key=_required_api_key(),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
        base_url=os.getenv("LLM_BASE_URL") or None,
    )
