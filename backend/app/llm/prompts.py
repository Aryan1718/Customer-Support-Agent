from importlib.resources import files


DEFAULT_SYSTEM_PROMPT_FILE = "customer_support_agent_system.md"


def load_prompt(filename: str) -> str:
    prompt_file = files("app.llm.prompt_assets").joinpath(filename)
    return prompt_file.read_text(encoding="utf-8").strip()


DEFAULT_SYSTEM_PROMPT = load_prompt(DEFAULT_SYSTEM_PROMPT_FILE)
