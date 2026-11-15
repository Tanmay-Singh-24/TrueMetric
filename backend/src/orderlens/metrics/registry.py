"""Find a metric, check its arguments, and run its fixed SQL with bound values."""

from datetime import date
from pathlib import Path
from typing import Any

from orderlens.db import run_query
from orderlens.lookups import known_categories, known_states
from orderlens.metrics.catalog import METRICS, Metric

SQL_DIR = Path(__file__).parent / "sql"
DATA_START = date(2016, 9, 4)
DATA_END = date(2018, 10, 17)
DEFAULT_TOP_N = 10
MAX_TOP_N = 50

METRICS_BY_ID = {metric.id: metric for metric in METRICS}


class InvalidArgs(Exception):
    """The arguments cannot be used to run the metric exactly as asked."""


def get_metric(metric_id: str) -> Metric | None:
    """The metric with this id, or None if there is none."""
    return METRICS_BY_ID.get(metric_id)


def metric_sql(metric: Metric) -> str:
    """The metric's fixed SQL, read from its .sql file."""
    return (SQL_DIR / f"{metric.id}.sql").read_text()


def parse_date(value: date | str | None, default: date, name: str) -> date:
    """A date given as a date or an ISO string; the default when it is missing."""
    if value is None:
        return default
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidArgs(f"{name} is not a date: {value!r}") from None


def check_state(value: str | None) -> str | None:
    """An upper-cased state code that exists in the data, or None for all states."""
    if value is None:
        return None
    state = value.strip().upper()
    if state not in known_states():
        raise InvalidArgs(f"unknown state: {value!r}")
    return state


def check_category(value: str | None) -> str | None:
    """A category name that exists in the data, or None for all categories."""
    if value is None:
        return None
    category = value.strip().lower()
    if category not in known_categories():
        raise InvalidArgs(f"unknown category: {value!r}")
    return category


def check_top_n(value: int) -> int:
    """A whole number of rows to return, from 1 to MAX_TOP_N."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TOP_N:
        raise InvalidArgs(f"top_n must be a whole number from 1 to {MAX_TOP_N}: {value!r}")
    return value


def validate_args(metric: Metric, raw_args: dict[str, Any]) -> dict[str, Any]:
    """The metric's arguments, checked and with defaults filled in; raises InvalidArgs."""
    given = {name: value for name, value in raw_args.items() if value is not None}
    unsupported = set(given) - metric.args
    if unsupported:
        raise InvalidArgs(f"{metric.id} does not accept: {', '.join(sorted(unsupported))}")
    # Every metric takes a date range; missing ends default to the data window so the
    # audit trail always shows a concrete range.
    args: dict[str, Any] = {
        "start_date": parse_date(given.get("start_date"), DATA_START, "start_date"),
        "end_date": parse_date(given.get("end_date"), DATA_END, "end_date"),
    }
    if args["start_date"] > args["end_date"]:
        raise InvalidArgs("start_date is after end_date")
    if "state" in metric.args:
        args["state"] = check_state(given.get("state"))
    if "category" in metric.args:
        args["category"] = check_category(given.get("category"))
    if "top_n" in metric.args:
        args["top_n"] = check_top_n(given.get("top_n", DEFAULT_TOP_N))
    return args


def run_metric(metric: Metric, args: dict[str, Any]) -> tuple[list[str], list[list]]:
    """Run the metric's SQL with the checked arguments bound as parameters."""
    return run_query(metric_sql(metric), args)
