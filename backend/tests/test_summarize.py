from datetime import date

import pytest

from truemetric import summarize as summarize_module
from truemetric.llm import LLMRateLimited
from truemetric.metrics.registry import get_metric
from truemetric.summarize import FALLBACK_ANSWER, summarize, write_answer


def capture_prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the LLM with a fake that records each prompt; return the list it fills."""
    prompts = []

    def fake_llm(label: str, messages: list) -> str:
        prompts.append(messages[0][1])
        return "A summary."

    monkeypatch.setattr(summarize_module, "invoke_text", fake_llm)
    return prompts


def forbid_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if the LLM is called."""

    def no_llm(label: str, messages: list) -> str:
        raise AssertionError("the LLM was called")

    monkeypatch.setattr(summarize_module, "invoke_text", no_llm)


def test_the_prompt_says_what_the_rows_contain(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = capture_prompts(monkeypatch)
    context = "Top categories by units sold: Product categories ranked by number of units sold."
    summarize("Which category performs best?", context, ["category", "units"], [["x", 1]])
    assert f"What the rows contain: {context}" in prompts[0]


def test_a_failed_summary_falls_back_to_a_fixed_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    def rate_limited(label: str, messages: list) -> str:
        raise LLMRateLimited("429")

    monkeypatch.setattr(summarize_module, "invoke_text", rate_limited)
    answer = summarize("How many sellers?", "Counts sellers.", ["sellers"], [[3095]])
    assert answer == FALLBACK_ANSWER


def test_a_single_value_is_answered_by_code(monkeypatch: pytest.MonkeyPatch) -> None:
    forbid_llm(monkeypatch)
    metric = get_metric("order_count")
    args = {"start_date": date(2018, 1, 1), "end_date": date(2018, 12, 31), "state": None}
    answer, headline = write_answer(
        "Orders in 2018?", metric, args, None, ["orders"], [[53532]], True
    )
    assert (answer, headline) == ("Number of orders, 2018-01-01 – 2018-12-31: 53,532", "53,532")


def test_without_the_llm_a_table_gets_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    forbid_llm(monkeypatch)
    metric = get_metric("top_categories_by_units")
    answer, headline = write_answer("Top?", metric, {}, None, ["category"], [["toys"]], False)
    assert (answer, headline) == (FALLBACK_ANSWER, None)


def test_a_table_summary_is_told_what_the_metric_is(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = capture_prompts(monkeypatch)
    metric = get_metric("top_categories_by_units")
    write_answer("Best category?", metric, {}, None, ["category"], [["toys"]], True)
    assert "What the rows contain: Top categories by units sold:" in prompts[0]


def test_a_freeform_summary_is_told_the_explanation(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = capture_prompts(monkeypatch)
    explanation = "Counts sellers per state."
    write_answer("Sellers per state?", None, None, explanation, ["state"], [["SP"]], True)
    assert f"What the rows contain: {explanation}" in prompts[0]
