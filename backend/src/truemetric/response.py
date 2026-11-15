"""The response ask() returns (ARCHITECTURE.md section 6.7), built from the graph's final
state. The audit trail is built here, by code, from what actually ran."""

from collections.abc import Mapping
from typing import Any

from truemetric.audit import Audit, build_audit
from truemetric.config import settings
from truemetric.metrics.registry import get_metric


def make_response(status: str, answer: str, **fields: object) -> dict:
    """A response with empty defaults for every field not given."""
    # `failure` (reason, detail, last SQL) is for the eval and the logs; the API leaves it
    # out of what it returns.
    empty = {
        "headline": None,
        "columns": [],
        "rows": [],
        "audit": None,
        "options": [],
        "failure": None,
    }
    return {"status": status, "answer": answer, **empty, **fields}


def failure(reason: str, error: Exception) -> dict:
    """The failure details of a run that an exception ended."""
    return {"reason": reason, "detail": str(error), "sql": None}


def audit_from_state(state: Mapping[str, Any], duration_ms: int) -> Audit:
    """The audit trail of an answered question."""
    row_count = len(state["rows"])
    if "metric_args" in state:
        metric = get_metric(state["decision"].metric_id)
        args = state["metric_args"]
        return build_audit(metric, args, state["sql"], row_count, duration_ms, settings.groq_model)
    return build_audit(
        None,
        {},
        state["sql"],
        row_count,
        duration_ms,
        settings.groq_model,
        explanation=state.get("explanation"),
        attempts=state["attempts"],
    )


def response_from_state(state: Mapping[str, Any], duration_ms: int) -> dict:
    """The response for the graph's final state."""
    if state["status"] != "answered":
        return make_response(
            state["status"],
            state["answer"],
            options=state.get("options", []),
            failure=state.get("failure"),
        )
    audit = audit_from_state(state, duration_ms)
    return make_response(
        "answered",
        state["answer"],
        headline=state["headline"],
        columns=state["columns"],
        rows=state["rows"],
        audit=audit.model_dump(),
    )
