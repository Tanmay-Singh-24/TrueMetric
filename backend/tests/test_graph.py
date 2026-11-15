"""ask() end to end through the graph, with the LLM calls replaced by fakes."""

import pytest

from orderlens import graph
from orderlens.freeform import GeneratedSQL
from orderlens.llm import LLMError, LLMRateLimited
from orderlens.router import RouterDecision


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


def fake_router(monkeypatch: pytest.MonkeyPatch, result: RouterDecision) -> None:
    """Make the router return this decision instead of calling the LLM."""
    monkeypatch.setattr(graph, "route_question", lambda question, forced_metric_id=None: result)


def forbid_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if anything reaches the database."""

    def no_query(*args: object) -> None:
        raise AssertionError("a query was executed")

    monkeypatch.setattr(graph, "run_query", no_query)
    monkeypatch.setattr(graph, "run_metric", no_query)


def fake_generator(monkeypatch: pytest.MonkeyPatch, sqls: list[str]) -> list[tuple]:
    """Make generate_sql return these SQL strings in turn; return the calls it received."""
    calls = []

    def generate(question: str, previous_sql: str | None, error: str | None) -> GeneratedSQL:
        calls.append((previous_sql, error))
        return GeneratedSQL(sql=sqls[len(calls) - 1], cannot_answer=None, explanation="test")

    monkeypatch.setattr(graph, "generate_sql", generate)
    return calls


def test_clarify_returns_the_catalogue_options(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = ["top_categories_by_revenue", "top_categories_by_units"]
    fake_router(monkeypatch, decision(route="clarify", candidates=candidates))
    forbid_queries(monkeypatch)
    result = graph.ask("Which category performs best?")
    assert result["status"] == "clarify"
    assert [option["metric_id"] for option in result["options"]] == candidates


def test_refuse_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_router(monkeypatch, decision(route="refuse"))
    forbid_queries(monkeypatch)
    result = graph.ask("Delete all canceled orders")
    assert (result["status"], result["audit"]) == ("refused", None)


def test_the_retry_goes_through_the_validator_too(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_generator(monkeypatch, ["DELETE FROM orders", "DROP TABLE orders"])
    forbid_queries(monkeypatch)
    result = graph.ask("Remove old orders", mode="freeform_only")
    assert result["status"] == "failed"
    assert len(calls) == 2


def test_the_retry_is_shown_the_failed_sql_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_generator(monkeypatch, ["SELECT nope FROM sellers", "DROP TABLE orders"])
    forbid_queries(monkeypatch)
    graph.ask("How many sellers?", mode="freeform_only")
    previous_sql, error = calls[1]
    assert previous_sql == "SELECT nope FROM sellers"
    assert "column check failed" in error


def test_a_rate_limit_gives_the_daily_limit_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def rate_limited(question: str, forced_metric_id: str | None = None) -> None:
        raise LLMRateLimited("429")

    monkeypatch.setattr(graph, "route_question", rate_limited)
    result = graph.ask("What was our revenue in 2018?")
    assert result == graph.response("failed", graph.DAILY_LIMIT_ANSWER)


def test_another_llm_error_gives_a_plain_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(question: str, forced_metric_id: str | None = None) -> None:
        raise LLMError("500")

    monkeypatch.setattr(graph, "route_question", broken)
    result = graph.ask("What was our revenue in 2018?")
    assert result == graph.response("failed", graph.LLM_FAILED_ANSWER)


@pytest.mark.db
def test_a_metric_decision_produces_a_full_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    year_2018 = {"start_date": "2018-01-01", "end_date": "2018-12-31"}
    fake_router(monkeypatch, decision(metric_id="merchandise_revenue", **year_2018))
    result = graph.ask("What was our revenue in 2018?", summarize=False)
    audit = result["audit"]
    assert result["headline"] == "R$ 7,341,182.41"
    assert result["answer"] == "Merchandise revenue, 2018-01-01 – 2018-12-31: R$ 7,341,182.41"
    assert (audit["path"], audit["check"], audit["attempts"]) == (
        "metric",
        "Verified metric template",
        1,
    )
    assert audit["parameters"] == {"start_date": "2018-01-01", "end_date": "2018-12-31"}
    assert audit["notes"] == [
        "Item prices only; freight excluded",
        "Excludes canceled and unavailable orders",
        "Dated by purchase time",
    ]
    assert "%(start_date)s" in audit["sql"]


@pytest.mark.db
def test_a_freeform_answer_after_one_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_generator(monkeypatch, ["SELECT nope FROM sellers", "SELECT COUNT(*) FROM sellers"])
    result = graph.ask("How many sellers?", mode="freeform_only", summarize=False)
    assert result["rows"] == [[3095]]
    assert (result["audit"]["path"], result["audit"]["attempts"]) == ("freeform", 2)


@pytest.mark.db
def test_a_single_value_answer_makes_no_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_summary(*args: object) -> None:
        raise AssertionError("the summary LLM was called")

    fake_router(monkeypatch, decision(metric_id="order_count", state="RJ"))
    monkeypatch.setattr(graph, "summarize", no_summary)
    result = graph.ask("How many orders came from RJ?", summarize=True)
    assert result["answer"].startswith("Number of orders, 2016-09-04 – 2018-10-17, state RJ: ")


@pytest.mark.db
def test_a_table_metric_summary_is_told_the_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    contexts = []

    def capture(question: str, context: str, columns: list, rows: list) -> str:
        contexts.append(context)
        return "summary"

    fake_router(monkeypatch, decision(metric_id="top_categories_by_units", top_n=3))
    monkeypatch.setattr(graph, "summarize", capture)
    graph.ask("Which category performs best?", summarize=True)
    assert contexts == [
        "Top categories by units sold: Product categories ranked by number of units sold."
    ]
