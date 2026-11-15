"""The audit trail and the headline number, both built by code from what actually ran."""

from typing import Any, Literal

from pydantic import BaseModel

from truemetric.metrics.catalog import Metric

HEADLINE_FORMATS = {
    "brl": "R$ {:,.2f}",
    "percent": "{:.2f}%",
    "count": "{:,}",
    "score": "{:.2f} / 5",
}


class Audit(BaseModel):
    path: Literal["metric", "freeform"]
    metric_id: str | None
    metric_name: str | None
    definition: str | None  # the metric definition, or the generator's explanation
    parameters: dict[str, str]  # resolved values, including defaulted dates
    notes: list[str]
    sql: str  # exactly what was executed
    check: str
    attempts: int
    row_count: int
    duration_ms: int
    model: str


def build_audit(
    metric: Metric | None,
    parameters: dict[str, Any],
    sql: str,
    row_count: int,
    duration_ms: int,
    model: str,
    explanation: str | None = None,
    attempts: int = 1,
) -> Audit:
    """Describe what ran: a metric with its bound values, or validated generated SQL."""
    if metric is not None:
        return Audit(
            path="metric",
            metric_id=metric.id,
            metric_name=metric.name,
            definition=metric.definition,
            # Filters left as None (all states, all categories) were not applied.
            parameters={
                name: str(value) for name, value in parameters.items() if value is not None
            },
            notes=list(metric.notes),
            sql=sql,
            check="Verified metric template",
            attempts=1,
            row_count=row_count,
            duration_ms=duration_ms,
            model=model,
        )
    return Audit(
        path="freeform",
        metric_id=None,
        metric_name=None,
        definition=explanation,
        parameters={},
        notes=[],
        sql=sql,
        check="Validated generated SQL",
        attempts=attempts,
        row_count=row_count,
        duration_ms=duration_ms,
        model=model,
    )


def format_answer(metric: Metric, parameters: dict[str, Any], headline: str) -> str:
    """The answer for a single-value metric, built by code: name, period, filters, value."""
    parts = [metric.name, f"{parameters['start_date']} – {parameters['end_date']}"]
    if parameters.get("state"):
        parts.append(f"state {parameters['state']}")
    if parameters.get("category"):
        parts.append(f"category {parameters['category']}")
    return f"{', '.join(parts)}: {headline}"


def format_headline(metric: Metric, columns: list[str], rows: list[list]) -> str | None:
    """The metric's single value formatted for display, or None if there is no single value."""
    if metric.value_column is None or len(rows) != 1:
        return None
    value = rows[0][columns.index(metric.value_column)]
    if value is None:
        return None
    return HEADLINE_FORMATS[metric.unit].format(value)
