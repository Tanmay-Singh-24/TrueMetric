import pytest

from orderlens import summarize as summarize_module
from orderlens.llm import LLMRateLimited
from orderlens.summarize import FALLBACK_ANSWER, summarize


def test_a_failed_summary_falls_back_to_a_fixed_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    def rate_limited(label: str, messages: list) -> str:
        raise LLMRateLimited("429")

    monkeypatch.setattr(summarize_module, "invoke_text", rate_limited)
    assert summarize("How many sellers?", ["sellers"], [[3095]]) == FALLBACK_ANSWER
