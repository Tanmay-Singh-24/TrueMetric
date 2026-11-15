from datetime import date
from decimal import Decimal

import pytest

from truemetric.audit import build_audit, format_answer, format_headline
from truemetric.metrics.registry import get_metric


@pytest.mark.parametrize(
    ("metric_id", "value", "expected"),
    [
        ("merchandise_revenue", Decimal("7341182.41"), "R$ 7,341,182.41"),
        ("repeat_customer_rate", Decimal("3.04"), "3.04%"),
        ("order_count", 98207, "98,207"),
        ("average_review_score", Decimal("4.09"), "4.09 / 5"),
    ],
    ids=["brl", "percent", "count", "score"],
)
def test_headline_formats_each_unit(metric_id: str, value: object, expected: str) -> None:
    metric = get_metric(metric_id)
    columns = ["other_column", metric.value_column]
    assert format_headline(metric, columns, [[0, value]]) == expected


def test_no_headline_for_more_than_one_row() -> None:
    rows = [[Decimal("1.00"), 1], [Decimal("2.00"), 2]]
    assert format_headline(get_metric("merchandise_revenue"), ["revenue", "orders"], rows) is None


def test_no_headline_for_a_table_metric_even_with_one_row() -> None:
    columns = ["category", "revenue", "units"]
    rows = [["health_beauty", Decimal("1255695.13"), 9634]]
    assert format_headline(get_metric("top_categories_by_revenue"), columns, rows) is None


def test_no_headline_when_the_value_is_null() -> None:
    # Average order value over a range with no orders divides by NULLIF(0, 0) and gives NULL.
    columns = ["average_order_value", "orders"]
    assert format_headline(get_metric("average_order_value"), columns, [[None, 0]]) is None


def test_metric_audit_shows_resolved_parameters_and_notes() -> None:
    metric = get_metric("merchandise_revenue")
    parameters = {
        "start_date": date(2016, 9, 4),
        "end_date": date(2018, 10, 17),
        "state": "SP",
        "category": None,
    }
    audit = build_audit(metric, parameters, "SELECT 1", 1, 12, "test-model")
    assert audit.path == "metric"
    assert audit.check == "Verified metric template"
    assert audit.parameters == {"start_date": "2016-09-04", "end_date": "2018-10-17", "state": "SP"}
    assert audit.notes == list(metric.notes)


def test_freeform_audit_uses_the_explanation_and_counts_attempts() -> None:
    audit = build_audit(
        None, {}, "SELECT 1", 1, 12, "test-model", explanation="Counts sellers.", attempts=2
    )
    assert audit.path == "freeform"
    assert audit.definition == "Counts sellers."
    assert audit.attempts == 2


def test_single_value_answer_names_the_metric_period_and_value() -> None:
    parameters = {"start_date": date(2018, 1, 1), "end_date": date(2018, 12, 31), "state": None}
    answer = format_answer(get_metric("order_count"), parameters, "53,532")
    assert answer == "Number of orders, 2018-01-01 – 2018-12-31: 53,532"


def test_single_value_answer_includes_state_and_category_filters() -> None:
    parameters = {
        "start_date": date(2017, 1, 1),
        "end_date": date(2017, 12, 31),
        "state": "SP",
        "category": "health_beauty",
    }
    answer = format_answer(get_metric("merchandise_revenue"), parameters, "R$ 1.00")
    assert answer == (
        "Merchandise revenue, 2017-01-01 – 2017-12-31, state SP, category health_beauty: R$ 1.00"
    )
