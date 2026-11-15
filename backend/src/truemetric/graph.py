"""LangGraph wiring for one question, and ask(), the only entry point.

Every node is thin: it calls a plain function from another module and returns the state
fields it changed, so all logic is testable without LangGraph. Building the response from
the final state is response.py's job.
"""

import logging
import time
from typing import Literal, TypedDict

import psycopg
from langgraph.graph import END, START, StateGraph

from truemetric.db import run_query
from truemetric.freeform import generate_sql
from truemetric.llm import LLMError, LLMRateLimited
from truemetric.metrics.registry import get_metric, metric_sql, run_metric, validate_args
from truemetric.response import failure, make_response, response_from_state
from truemetric.router import (
    RouterDecision,
    build_clarification,
    check_decision,
    filter_args,
    route_question,
)
from truemetric.summarize import write_answer
from truemetric.validator import UnsafeSQL, validate_sql

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
REFUSED_ANSWER = "I can only answer questions that read this store's order data."
FAILED_ANSWER = "Sorry, I couldn't build a working query for that question."
DAILY_LIMIT_ANSWER = "The demo has reached today's free AI limit. Please try again tomorrow."
LLM_FAILED_ANSWER = "Sorry, the AI service failed while answering. Please try again."
DATABASE_FAILED_ANSWER = "Sorry, the database could not be reached. Please try again."

# Errors a rewritten query might fix: bad SQL, bad values, or the 5-second timeout.
# Connection errors are not here; they end the run in ask().
RETRYABLE_SQL_ERRORS = (psycopg.ProgrammingError, psycopg.DataError, psycopg.errors.QueryCanceled)


class State(TypedDict, total=False):
    question: str
    forced_metric_id: str | None
    mode: Literal["full", "freeform_only"]  # freeform_only is the eval baseline
    summarize: bool  # False in evals to save tokens
    decision: RouterDecision
    metric_args: dict
    sql: str | None
    explanation: str | None
    cannot_answer: str | None  # the generator's reason when the data cannot answer
    error: str | None
    failure_reason: Literal["validation_failed", "execution_error"] | None
    failure: dict | None  # reason, detail and last SQL of a failed run
    attempts: int
    columns: list[str]
    rows: list[list]
    status: Literal["answered", "clarify", "refused", "failed"]
    answer: str
    headline: str | None  # formatted by code, never by the LLM
    options: list[dict]


def route_node(state: State) -> dict:
    decision = route_question(state["question"], state.get("forced_metric_id"))
    return {"decision": check_decision(decision)}


def run_metric_node(state: State) -> dict:
    metric = get_metric(state["decision"].metric_id)
    args = validate_args(metric, filter_args(state["decision"]))
    columns, rows = run_metric(metric, args)
    return {"metric_args": args, "sql": metric_sql(metric), "columns": columns, "rows": rows}


def generate_sql_node(state: State) -> dict:
    # On the second attempt, state holds the first attempt's SQL and its error.
    generated = generate_sql(state["question"], state.get("sql"), state.get("error"))
    return {
        "attempts": state["attempts"] + 1,
        "sql": generated.sql,
        "explanation": generated.explanation,
        "cannot_answer": generated.cannot_answer,
        "error": None,
    }


def validate_sql_node(state: State) -> dict:
    try:
        return {"sql": validate_sql(state["sql"])}
    except UnsafeSQL as error:
        return {
            "error": f"rejected by the validator: {error}",
            "failure_reason": "validation_failed",
        }


def execute_sql_node(state: State) -> dict:
    try:
        columns, rows = run_query(state["sql"])
    except RETRYABLE_SQL_ERRORS as error:
        return {
            "error": f"the database rejected the query: {str(error).strip()}",
            "failure_reason": "execution_error",
        }
    return {"columns": columns, "rows": rows}


def summarize_node(state: State) -> dict:
    metric = get_metric(state["decision"].metric_id) if "metric_args" in state else None
    answer, headline = write_answer(
        state["question"],
        metric,
        state.get("metric_args"),
        state.get("explanation"),
        state["columns"],
        state["rows"],
        use_llm=state["summarize"],
    )
    return {"status": "answered", "answer": answer, "headline": headline}


def clarify_node(state: State) -> dict:
    answer, options = build_clarification(state["decision"].candidates)
    return {"status": "clarify", "answer": answer, "options": options}


def refuse_node(state: State) -> dict:
    if state.get("cannot_answer"):
        return {
            "status": "refused",
            "answer": f"This data cannot answer that: {state['cannot_answer']}",
        }
    return {"status": "refused", "answer": REFUSED_ANSWER}


def fail_node(state: State) -> dict:
    failure = {"reason": state["failure_reason"], "detail": state["error"], "sql": state["sql"]}
    return {"status": "failed", "answer": FAILED_ANSWER, "failure": failure}


def start_at(state: State) -> Literal["route", "generate_sql"]:
    return "generate_sql" if state["mode"] == "freeform_only" else "route"


def after_route(state: State) -> Literal["run_metric", "clarify", "generate_sql", "refuse"]:
    next_node = {
        "metric": "run_metric",
        "clarify": "clarify",
        "freeform": "generate_sql",
        "refuse": "refuse",
    }
    return next_node[state["decision"].route]


def after_generate(state: State) -> Literal["validate_sql", "refuse"]:
    return "refuse" if state["sql"] is None else "validate_sql"


def retry_or_fail(state: State) -> Literal["generate_sql", "fail"]:
    return "generate_sql" if state["attempts"] < MAX_ATTEMPTS else "fail"


def after_validate(state: State) -> Literal["execute_sql", "generate_sql", "fail"]:
    return "execute_sql" if state.get("error") is None else retry_or_fail(state)


def after_execute(state: State) -> Literal["summarize", "generate_sql", "fail"]:
    return "summarize" if state.get("error") is None else retry_or_fail(state)


def build_graph() -> StateGraph:
    """Wire the nine nodes exactly as the flow diagram in ARCHITECTURE.md section 2."""
    graph = StateGraph(State)
    graph.add_node("route", route_node)
    graph.add_node("run_metric", run_metric_node)
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("validate_sql", validate_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("refuse", refuse_node)
    graph.add_node("fail", fail_node)
    graph.add_conditional_edges(START, start_at)
    graph.add_conditional_edges("route", after_route)
    graph.add_edge("run_metric", "summarize")
    graph.add_conditional_edges("generate_sql", after_generate)
    graph.add_conditional_edges("validate_sql", after_validate)
    graph.add_conditional_edges("execute_sql", after_execute)
    for last_node in ("summarize", "clarify", "refuse", "fail"):
        graph.add_edge(last_node, END)
    return graph.compile()


GRAPH = build_graph()


def ask(
    question: str,
    metric_id: str | None = None,
    mode: Literal["full", "freeform_only"] = "full",
    summarize: bool = True,
) -> dict:
    """Answer one question. The API, the eval and scripts/ask.py all call this."""
    started = time.perf_counter()
    initial = {
        "question": question,
        "forced_metric_id": metric_id,
        "mode": mode,
        "summarize": summarize,
        "attempts": 0,
    }
    # LLM and connection errors are not retried by the graph: they end the run here.
    try:
        state = GRAPH.invoke(initial)
    except LLMRateLimited as error:
        logger.warning("Groq rate limit reached")
        return make_response("failed", DAILY_LIMIT_ANSWER, failure=failure("rate_limited", error))
    except LLMError as error:
        logger.exception("LLM call failed")
        return make_response("failed", LLM_FAILED_ANSWER, failure=failure("llm_error", error))
    except psycopg.OperationalError as error:
        logger.exception("database error")
        return make_response(
            "failed", DATABASE_FAILED_ANSWER, failure=failure("database_error", error)
        )
    duration_ms = round((time.perf_counter() - started) * 1000)
    return response_from_state(state, duration_ms)
