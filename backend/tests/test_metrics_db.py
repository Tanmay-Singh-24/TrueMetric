"""Every metric's SQL against the values scripts/reference_values.py computed in Python."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from truemetric.audit import format_headline
from truemetric.metrics.registry import get_metric, run_metric, validate_args

pytestmark = pytest.mark.db

REFERENCE = json.loads((Path(__file__).parent / "reference_values.json").read_text())
CASES = REFERENCE["metric_cases"]
TOLERANCE = Decimal("0.01")


def same_value(actual: object, expected: object) -> bool:
    """Compare a database value with its JSON reference, by the database value's type."""
    # psycopg returns numeric columns as Decimal; the JSON stores them as exact strings,
    # so both sides are Decimals and no float rounding enters the comparison.
    if isinstance(actual, Decimal):
        return abs(actual - Decimal(expected)) <= TOLERANCE
    if isinstance(actual, date):
        return actual.isoformat() == expected
    return actual == expected


@pytest.mark.parametrize("case", CASES, ids=[case["label"] for case in CASES])
def test_metric_sql_matches_reference(case: dict) -> None:
    metric = get_metric(case["metric_id"])
    columns, rows = run_metric(metric, validate_args(metric, case["args"]))
    assert columns == case["columns"]
    assert len(rows) == len(case["rows"])
    for position, (actual_row, expected_row) in enumerate(zip(rows, case["rows"], strict=True)):
        matches = [
            same_value(actual, expected)
            for actual, expected in zip(actual_row, expected_row, strict=True)
        ]
        assert all(matches), f"row {position}: SQL {actual_row}, reference {expected_row}"


def test_headline_for_revenue_in_2018() -> None:
    metric = get_metric("merchandise_revenue")
    args = validate_args(metric, {"start_date": "2018-01-01", "end_date": "2018-12-31"})
    columns, rows = run_metric(metric, args)
    assert format_headline(metric, columns, rows) == "R$ 7,341,182.41"
