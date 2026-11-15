"""Run the evaluation: each question through one configuration, scored against gold SQL.

Usage, from backend/:
  uv run --env-file .env python -m evals.run_eval --check-gold
  uv run --env-file .env python -m evals.run_eval --config baseline
  uv run --env-file .env python -m evals.run_eval --config full --resume
  uv run --env-file .env python -m evals.run_eval --config full --ids m07,f06
  uv run python -m evals.run_eval --report

Summaries are always off: they cost tokens and are not scored.
"""

import argparse
import json
import logging
import re
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import yaml

from evals.scoring import results_match, score
from orderlens.db import run_query
from orderlens.graph import ask
from orderlens.validator import UnsafeSQL, validate_sql

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVAL_DIR / "questions.yaml"
RESULTS_DIR = EVAL_DIR / "results"
REFERENCE_PATH = EVAL_DIR.parent / "tests" / "reference_values.json"
MODES = {"baseline": "freeform_only", "full": "full"}
# Groq's free tier allows 8,000 tokens a minute; pacing to 6,000 leaves room for other calls.
TOKENS_PER_MINUTE = 6000
UNSCORED_FAILURES = {"rate_limited", "llm_error", "database_error"}
MAX_TRIES = 3
BACKOFF_SECONDS = 60
CATEGORIES = ("metric", "freeform", "ambiguous", "refuse")

# Token counts of the LLM calls for the current question, read from orderlens.llm's logs.
call_tokens: list[int] = []


def count_tokens(record: logging.LogRecord) -> bool:
    """Logging filter: note each LLM call's token count, and let the record through."""
    call_tokens.append(getattr(record, "total_tokens", 0))
    return True


def load_questions(ids: list[str] | None = None) -> list[dict]:
    """The questions from questions.yaml, optionally only the given ids."""
    questions = yaml.safe_load(QUESTIONS_PATH.read_text())
    return [question for question in questions if ids is None or question["id"] in ids]


def results_path(config: str) -> Path:
    return RESULTS_DIR / f"{config}.json"


def load_results(config: str) -> dict[str, dict]:
    """The saved results of one configuration, keyed by question id."""
    path = results_path(config)
    return json.loads(path.read_text()) if path.exists() else {}


def save_results(config: str, results: dict[str, dict]) -> None:
    """Write the results file; called after every question so a stopped run loses nothing."""
    RESULTS_DIR.mkdir(exist_ok=True)
    text = json.dumps(results, indent=1, ensure_ascii=False, default=str)
    results_path(config).write_text(text + "\n")


def run_question(question: dict, config: str) -> tuple[dict | None, int, float]:
    """Ask one question; retry rate limits and outages, which are never scored."""
    for attempt in range(1, MAX_TRIES + 1):
        call_tokens.clear()
        started = time.perf_counter()
        response = ask(question["question"], mode=MODES[config], summarize=False)
        seconds = time.perf_counter() - started
        reason = (response["failure"] or {}).get("reason")
        if reason not in UNSCORED_FAILURES:
            return response, sum(call_tokens), seconds
        print(f"    {reason} on try {attempt} of {MAX_TRIES}; waiting {BACKOFF_SECONDS}s")
        time.sleep(BACKOFF_SECONDS)
    return None, 0, 0.0


def make_record(question: dict, config: str, response: dict, tokens: int, seconds: float) -> dict:
    """Score one response and keep what the report needs."""
    gold_rows = run_query(question["gold_sql"])[1] if "gold_sql" in question else None
    passed, reason = score(question, response, gold_rows, config)
    audit = response["audit"] or {}
    failure = response["failure"] or {}
    return {
        "category": question["category"],
        "question": question["question"],
        "status": response["status"],
        "route": audit.get("path") or response["status"],
        "metric_id": audit.get("metric_id"),
        "expected_metric": question.get("expected_metric"),
        "passed": passed,
        "reason": reason,
        "attempts": audit.get("attempts"),
        "sql": audit.get("sql") or failure.get("sql"),
        "error": failure.get("detail"),
        "answer": response["answer"],
        "row_count": len(response["rows"]),
        "rows": response["rows"][:10],
        "tokens": tokens,
        "seconds": round(seconds, 1),
    }


def run_config(config: str, ids: list[str] | None, resume: bool) -> None:
    """Run every selected question through one configuration, saving after each."""
    results = load_results(config)
    for question in load_questions(ids):
        if resume and question["id"] in results:
            continue
        print(f"{config} {question['id']}: {question['question']}")
        response, tokens, seconds = run_question(question, config)
        if response is None:
            print("Stopped: the LLM is still unavailable. Run again later with --resume.")
            return
        record = make_record(question, config, response, tokens, seconds)
        results[question["id"]] = record
        save_results(config, results)
        verdict = "pass" if record["passed"] else f"FAIL ({record['reason']})"
        print(f"    {verdict} via {record['route']}, {tokens} tokens, {seconds:.1f}s")
        # Wait long enough that this question's tokens fit in the per-minute limit.
        time.sleep(max(0.0, tokens / TOKENS_PER_MINUTE * 60 - seconds))


def reference_value(value: object) -> object:
    """reference_values.json stores decimals and dates as strings; turn them back."""
    if isinstance(value, str) and re.fullmatch(r"-?\d+\.\d+", value):
        return Decimal(value)
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    return value


def gold_problems(question: dict, references: dict[str, dict]) -> list[str]:
    """Everything wrong with one gold query: it fails, the validator rejects it, or it
    disagrees with the reference value."""
    try:
        _, rows = run_query(question["gold_sql"])
    except psycopg.Error as error:
        return [f"does not run: {error}"]
    problems = []
    try:
        validate_sql(question["gold_sql"])
    except UnsafeSQL as error:
        problems.append(f"the validator rejects it: {error}")
    if "reference" in question:
        case = references[question["reference"]]
        expected = [[reference_value(value) for value in row] for row in case["rows"]]
        if not results_match(rows, expected):
            problems.append(f"disagrees with reference {question['reference']!r}: {rows}")
    return problems


def check_gold() -> bool:
    """Run every gold query (no LLM calls) and report any problem."""
    cases = json.loads(REFERENCE_PATH.read_text())["metric_cases"]
    references = {case["label"]: case for case in cases}
    all_good = True
    for question in load_questions():
        if "gold_sql" not in question:
            continue
        problems = gold_problems(question, references)
        checked = "matches reference" if "reference" in question else "runs"
        print(f"{question['id']}: {'; '.join(problems) if problems else 'ok, ' + checked}")
        all_good = all_good and not problems
    print("all gold queries ok" if all_good else "SOME GOLD QUERIES HAVE PROBLEMS")
    return all_good


def pass_rate(records: list[dict]) -> str:
    """'passed/total (percent)' for a list of records."""
    if not records:
        return "—"
    passed = sum(record["passed"] for record in records)
    return f"{passed}/{len(records)} ({100 * passed / len(records):.0f}%)"


def print_results_table(results: dict[str, dict[str, dict]]) -> None:
    """Pass rates per category and head to head, one column per configuration."""
    configs = list(results)
    print("| Category | " + " | ".join(configs) + " |")
    print("|---|" + "---|" * len(configs))
    rows = [(category, (category,)) for category in CATEGORIES]
    rows.insert(2, ("**head to head (metric + freeform)**", ("metric", "freeform")))
    for label, categories in rows:
        cells = [
            pass_rate([r for r in results[config].values() if r["category"] in categories])
            for config in configs
        ]
        print(f"| {label} | " + " | ".join(cells) + " |")


def print_router_choices(full: dict[str, dict]) -> None:
    """For metric questions on the full system: the metric expected and the one chosen."""
    print("| id | expected metric | chosen | passed |")
    print("|---|---|---|---|")
    for question_id, record in full.items():
        if record["category"] == "metric":
            chosen = record["metric_id"] or record["route"]
            print(
                f"| {question_id} | {record['expected_metric']} | {chosen} | {record['passed']} |"
            )


def print_failures(results: dict[str, dict[str, dict]]) -> None:
    """Every failed question with its reason and error."""
    print("| config | id | category | reason | route | detail |")
    print("|---|---|---|---|---|---|")
    for config, records in results.items():
        for question_id, record in records.items():
            if not record["passed"]:
                detail = (record["error"] or "").replace("|", "/").replace("\n", " ")[:160]
                print(
                    f"| {config} | {question_id} | {record['category']} | {record['reason']} "
                    f"| {record['route']} | {detail} |"
                )


def print_costs(results: dict[str, dict[str, dict]]) -> None:
    """Tokens and time per configuration (time spent answering, not pausing)."""
    print(
        "| config | questions | total tokens | tokens per question "
        "| total seconds | seconds per question |"
    )
    print("|---|---|---|---|---|---|")
    for config, records in results.items():
        count = len(records)
        tokens = sum(record["tokens"] for record in records.values())
        seconds = sum(record["seconds"] for record in records.values())
        print(
            f"| {config} | {count} | {tokens:,} | {tokens / count:,.0f} "
            f"| {seconds:,.1f} | {seconds / count:.1f} |"
        )


def report() -> None:
    """Print the report tables from the saved results, in Markdown."""
    results = {config: load_results(config) for config in MODES if results_path(config).exists()}
    print("## Results\n")
    print_results_table(results)
    if "full" in results:
        print("\n## Router choices on metric questions (full)\n")
        print_router_choices(results["full"])
    print("\n## Failures\n")
    print_failures(results)
    print("\n## Tokens and time\n")
    print_costs(results)


def main() -> None:
    """Parse the command line and run the chosen action."""
    parser = argparse.ArgumentParser(description="Run the OrderLens evaluation.")
    parser.add_argument("--config", choices=list(MODES))
    parser.add_argument("--ids", help="comma-separated question ids to run")
    parser.add_argument("--resume", action="store_true", help="skip questions already saved")
    parser.add_argument("--check-gold", action="store_true", help="check gold SQL; no LLM")
    parser.add_argument("--report", action="store_true", help="print the report tables")
    arguments = parser.parse_args()
    if arguments.check_gold:
        raise SystemExit(0 if check_gold() else 1)
    if arguments.report:
        report()
        return
    if arguments.config is None:
        parser.error("choose --config, --check-gold or --report")
    llm_logger = logging.getLogger("orderlens.llm")
    llm_logger.setLevel(logging.INFO)
    llm_logger.addFilter(count_tokens)
    ids = arguments.ids.split(",") if arguments.ids else None
    run_config(arguments.config, ids, arguments.resume)


if __name__ == "__main__":
    main()
