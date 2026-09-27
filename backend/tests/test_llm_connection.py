import os

import pytest
from dotenv import load_dotenv

from app.llm.service import get_llm_service


REQUIRED_LLM_ENV_VARS = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")

load_dotenv()


def _missing_llm_env_vars() -> list[str]:
    return [name for name in REQUIRED_LLM_ENV_VARS if not os.getenv(name)]


@pytest.mark.live
def test_llm_connection_returns_response() -> None:
    missing_env_vars = _missing_llm_env_vars()
    if missing_env_vars:
        pytest.skip(
            "Set these env vars to run the live LLM connection test: "
            + ", ".join(missing_env_vars)
        )

    get_llm_service.cache_clear()
    service = get_llm_service()

    response = service.chat(
        message="Reply with exactly: connection-ok",
        system_prompt=(
            "You are a connection test. Reply with exactly the requested text "
            "and no extra words."
        ),
        tools=[],
    )

    assert response.model == os.environ["LLM_MODEL"]
    assert response.content.strip()
