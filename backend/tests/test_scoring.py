from datetime import date, datetime
from decimal import Decimal

from evals.scoring import results_match, score

GOLD = [["health_beauty", Decimal("1255695.13")], ["watches_gifts", Decimal("1198185.21")]]


def test_equal_results_match() -> None:
    assert results_match(GOLD, [list(row) for row in GOLD])


def test_extra_columns_are_allowed() -> None:
    result = [["health_beauty", Decimal("1255695.13"), 9634], ["watches_gifts", 1198185.21, 5970]]
    assert results_match(GOLD, result)


def test_row_order_does_not_matter() -> None:
    assert results_match(GOLD, [GOLD[1], GOLD[0]])


def test_column_names_and_order_do_not_matter() -> None:
    assert results_match(GOLD, [[row[1], row[0]] for row in GOLD])


def test_a_number_within_one_cent_matches() -> None:
    assert results_match([[Decimal("4.09")]], [[4.0864]])


def test_a_number_off_by_more_than_one_cent_does_not_match() -> None:
    assert not results_match([[Decimal("137.42")]], [[Decimal("137.44")]])


def test_a_missing_row_does_not_match() -> None:
    assert not results_match(GOLD, [GOLD[0]])


def test_an_extra_row_does_not_match() -> None:
    assert not results_match(GOLD, [*GOLD, ["bed_bath_table", Decimal("1035964.06")]])


def test_text_is_compared_ignoring_case() -> None:
    assert results_match([["credit_card"]], [["CREDIT_CARD"]])


def test_timestamps_are_compared_by_day() -> None:
    assert results_match([[datetime(2017, 1, 1, 0, 0)]], [[date(2017, 1, 1)]])


def test_a_number_never_matches_text() -> None:
    assert not results_match([[Decimal("3.04")]], [["3.04"]])


METRIC_QUESTION = {"category": "metric", "expected_metric": "merchandise_revenue"}


def answered(rows: list[list], path: str, metric_id: str | None) -> dict:
    """A minimal answered response."""
    return {"status": "answered", "rows": rows, "audit": {"path": path, "metric_id": metric_id}}


def test_a_clarify_question_passes_on_status_alone() -> None:
    response = {"status": "clarify", "rows": []}
    assert score({"category": "ambiguous"}, response, None, "full") == (True, None)


def test_a_failed_run_keeps_its_failure_reason() -> None:
    response = {"status": "failed", "failure": {"reason": "validation_failed"}}
    assert score(METRIC_QUESTION, response, [[1]], "baseline") == (False, "validation_failed")


def test_the_wrong_metric_is_a_wrong_route() -> None:
    response = answered([[2]], "metric", "order_count")
    assert score(METRIC_QUESTION, response, [[1]], "full") == (False, "wrong_route")


def test_the_right_metric_with_the_wrong_result_is_wrong_args() -> None:
    response = answered([[2]], "metric", "merchandise_revenue")
    assert score(METRIC_QUESTION, response, [[1]], "full") == (False, "wrong_args")


def test_a_wrong_freeform_result_is_wrong_result() -> None:
    response = answered([[2]], "freeform", None)
    assert score(METRIC_QUESTION, response, [[1]], "baseline") == (False, "wrong_result")
