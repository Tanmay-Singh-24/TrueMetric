"""check_decision and build_clarification, with hand-made router decisions (no LLM)."""

import pytest

from orderlens.metrics import registry
from orderlens.router import RouterDecision, build_clarification, check_decision


@pytest.fixture(autouse=True)
def known_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the database lookups, so these tests run without a database."""
    monkeypatch.setattr(registry, "known_states", lambda: frozenset({"SP", "RJ"}))
    monkeypatch.setattr(registry, "known_categories", lambda: frozenset({"health_beauty"}))


def decision(**fields: object) -> RouterDecision:
    """A router decision with empty filters, overridden by the given fields."""
    defaults = {
        "route": "metric",
        "metric_id": None,
        "candidates": [],
        "start_date": None,
        "end_date": None,
        "state": None,
        "category": None,
        "top_n": None,
        "reason": "test",
    }
    return RouterDecision(**{**defaults, **fields})


def test_a_metric_decision_that_can_run_is_kept() -> None:
    original = decision(metric_id="merchandise_revenue", state="SP")
    assert check_decision(original) == original


def test_an_unknown_metric_goes_to_freeform() -> None:
    checked = check_decision(decision(metric_id="profit_margin"))
    assert (checked.route, checked.metric_id) == ("freeform", None)


def test_a_filter_the_metric_does_not_accept_goes_to_freeform() -> None:
    # "What is the repeat rate in SP?": repeat_customer_rate has no state filter.
    checked = check_decision(decision(metric_id="repeat_customer_rate", state="SP"))
    assert checked.route == "freeform"


def test_an_invalid_filter_value_goes_to_freeform() -> None:
    checked = check_decision(decision(metric_id="order_count", state="XX"))
    assert checked.route == "freeform"


def test_the_reason_for_going_to_freeform_is_recorded() -> None:
    checked = check_decision(decision(metric_id="repeat_customer_rate", state="SP"))
    assert "does not accept: state" in checked.reason


def test_clarify_with_two_known_candidates_is_kept() -> None:
    candidates = ["top_categories_by_revenue", "top_categories_by_units"]
    checked = check_decision(decision(route="clarify", candidates=candidates))
    assert (checked.route, checked.candidates) == ("clarify", candidates)


def test_clarify_with_one_known_candidate_becomes_that_metric() -> None:
    candidates = ["top_categories_by_units", "best_sellers"]
    checked = check_decision(decision(route="clarify", candidates=candidates))
    assert (checked.route, checked.metric_id) == ("metric", "top_categories_by_units")


def test_clarify_with_no_known_candidates_goes_to_freeform() -> None:
    checked = check_decision(decision(route="clarify", candidates=["best_sellers"]))
    assert checked.route == "freeform"


def test_clarify_that_becomes_a_metric_still_has_its_filters_checked() -> None:
    candidates = ["repeat_customer_rate", "unknown_metric"]
    checked = check_decision(decision(route="clarify", candidates=candidates, state="SP"))
    assert checked.route == "freeform"


def test_clarification_is_built_from_the_catalogue() -> None:
    question, options = build_clarification(
        ["top_categories_by_revenue", "top_categories_by_units"]
    )
    assert question == "Do you mean: Top categories by revenue, or Top categories by units sold?"
    assert [option["metric_id"] for option in options] == [
        "top_categories_by_revenue",
        "top_categories_by_units",
    ]


def test_clarification_options_carry_the_catalogue_definitions() -> None:
    _, options = build_clarification(["order_count", "average_order_value"])
    assert options[0] == {
        "metric_id": "order_count",
        "name": "Number of orders",
        "definition": "Number of valid orders placed in the date range.",
    }
