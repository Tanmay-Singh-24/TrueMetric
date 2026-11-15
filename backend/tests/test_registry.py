import re
from datetime import date

import pytest

from truemetric.metrics import registry
from truemetric.metrics.catalog import METRICS
from truemetric.metrics.registry import InvalidArgs, get_metric, metric_sql, validate_args


@pytest.fixture(autouse=True)
def known_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the database lookups, so these tests run without a database."""
    monkeypatch.setattr(registry, "known_states", lambda: frozenset({"SP", "RJ"}))
    monkeypatch.setattr(
        registry, "known_categories", lambda: frozenset({"health_beauty", "unknown"})
    )


@pytest.mark.parametrize("metric", METRICS, ids=lambda metric: metric.id)
def test_every_metric_has_a_sql_file(metric: registry.Metric) -> None:
    assert (registry.SQL_DIR / f"{metric.id}.sql").is_file()


def test_every_sql_file_belongs_to_a_metric() -> None:
    file_names = {path.stem for path in registry.SQL_DIR.glob("*.sql")}
    assert file_names == {metric.id for metric in METRICS}


@pytest.mark.parametrize("metric", METRICS, ids=lambda metric: metric.id)
def test_sql_placeholders_are_exactly_the_declared_arguments(metric: registry.Metric) -> None:
    placeholders = set(re.findall(r"%\((\w+)\)s", metric_sql(metric)))
    assert placeholders == metric.args


def test_unknown_metric_id_gives_none() -> None:
    assert get_metric("profit_margin") is None


def test_missing_arguments_get_defaults() -> None:
    args = validate_args(get_metric("top_categories_by_revenue"), {})
    assert args == {
        "start_date": date(2016, 9, 4),
        "end_date": date(2018, 10, 17),
        "state": None,
        "top_n": 10,
    }


def test_none_values_count_as_not_given() -> None:
    # The router fills every argument field, using None for the ones it did not extract.
    raw_args = {"start_date": "2018-01-01", "end_date": "2018-12-31", "state": None, "top_n": None}
    args = validate_args(get_metric("repeat_customer_rate"), raw_args)
    assert args == {"start_date": date(2018, 1, 1), "end_date": date(2018, 12, 31)}


def test_state_is_upper_cased() -> None:
    assert validate_args(get_metric("order_count"), {"state": "sp"})["state"] == "SP"


@pytest.mark.parametrize(
    ("metric_id", "raw_args"),
    [
        ("repeat_customer_rate", {"state": "SP"}),
        ("merchandise_revenue", {"state": "XX"}),
        ("merchandise_revenue", {"category": "spaceships"}),
        ("merchandise_revenue", {"start_date": "2018-12-31", "end_date": "2018-01-01"}),
        ("merchandise_revenue", {"start_date": "31/12/2018"}),
        ("top_categories_by_revenue", {"top_n": 0}),
        ("top_categories_by_revenue", {"top_n": 51}),
    ],
    ids=[
        "unsupported argument",
        "unknown state",
        "unknown category",
        "reversed dates",
        "unparseable date",
        "top_n too small",
        "top_n too large",
    ],
)
def test_validate_args_rejects(metric_id: str, raw_args: dict) -> None:
    with pytest.raises(InvalidArgs):
        validate_args(get_metric(metric_id), raw_args)
