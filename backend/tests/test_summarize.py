import pytest

from orderlens import summarize as summarize_module
from orderlens.llm import LLMRateLimited
from orderlens.summarize import FALLBACK_ANSWER, summarize


def test_the_prompt_says_what_the_rows_contain(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = []

    def capture(label: str, messages: list) -> str:
        prompts.append(messages[0][1])
        return "Bed, bath and table sold the most units."

    monkeypatch.setattr(summarize_module, "invoke_text", capture)
    context = "Top categories by units sold: Product categories ranked by number of units sold."
    summarize("Which category performs best?", context, ["category", "units"], [["x", 1]])
    assert f"What the rows contain: {context}" in prompts[0]


def test_a_failed_summary_falls_back_to_a_fixed_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    def rate_limited(label: str, messages: list) -> str:
        raise LLMRateLimited("429")

    monkeypatch.setattr(summarize_module, "invoke_text", rate_limited)
    assert (
        summarize("How many sellers?", "Counts sellers.", ["sellers"], [[3095]]) == FALLBACK_ANSWER
    )
