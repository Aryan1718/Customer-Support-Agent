from collections.abc import Sequence


PARAMETER_FOLLOW_UP_PROMPTS: dict[str, str] = {
    "email": "What email address is on the account?",
    "Email": "What email address is on the account?",
    "customerEmail": "What email address is on the account?",
    "orderID": "What is the order ID?",
    "OrderId": "What is the order ID?",
    "issue": "What issue should I add to the support ticket?",
}


def build_follow_up_prompt(missing_params: Sequence[str]) -> str:
    prompts = [
        PARAMETER_FOLLOW_UP_PROMPTS.get(param, f"Please provide {param}.")
        for param in missing_params
    ]

    if not prompts:
        return ""
    if len(prompts) == 1:
        return prompts[0]
    if len(prompts) == 2:
        return f"{prompts[0]} Also, {prompts[1][0].lower()}{prompts[1][1:]}"

    first_prompts = ", ".join(prompts[:-1])
    final_prompt = prompts[-1]
    return f"{first_prompts}, and {final_prompt[0].lower()}{final_prompt[1:]}"
