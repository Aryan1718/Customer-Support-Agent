from app.llm.follow_up_prompts import build_follow_up_prompt


def test_build_follow_up_prompt_for_single_missing_param():
    assert build_follow_up_prompt(["orderID"]) == "What is the order ID?"


def test_build_follow_up_prompt_for_multiple_missing_params():
    assert build_follow_up_prompt(["email", "orderID"]) == (
        "What email address is on the account? Also, what is the order ID?"
    )


def test_build_follow_up_prompt_falls_back_for_unknown_param():
    assert build_follow_up_prompt(["postalCode"]) == "Please provide postalCode."
