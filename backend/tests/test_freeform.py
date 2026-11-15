import pytest

from orderlens import freeform
from orderlens.freeform import system_prompt


def test_the_prompt_lists_the_category_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(freeform, "known_categories", lambda: frozenset({"watches_gifts", "toys"}))
    assert "exactly as stored: toys, watches_gifts" in system_prompt()


def test_the_prompt_holds_the_schema_and_definitions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(freeform, "known_categories", lambda: frozenset({"toys"}))
    prompt = system_prompt()
    assert "CREATE TABLE order_payments" in prompt
    assert "Customer: customer_unique_id, never customer_id" in prompt
