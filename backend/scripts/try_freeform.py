"""Try the free-form path from the terminal: generate SQL, validate it, run it, retry once.

Usage:
  uv run --env-file .env python scripts/try_freeform.py "How many sellers are in each state?"
  uv run --env-file .env python scripts/try_freeform.py "..." --first-sql "SELECT ..."

--first-sql stands in for the LLM's first attempt, to show a bad first attempt being
corrected on the retry. Both attempts go through exactly the same validator.
"""

import argparse
import logging

import psycopg
from terminal import print_table

from orderlens.db import run_query
from orderlens.freeform import GeneratedSQL, generate_sql
from orderlens.validator import UnsafeSQL, validate_sql

MAX_ATTEMPTS = 2


def next_attempt(
    question: str, attempt: int, previous_sql: str | None, error: str | None, first_sql: str | None
) -> GeneratedSQL:
    """The SQL for this attempt: the forced first SQL if given, otherwise the LLM's."""
    if attempt == 1 and first_sql is not None:
        return GeneratedSQL(sql=first_sql, cannot_answer=None, explanation="(forced first attempt)")
    return generate_sql(question, previous_sql, error)


def run_freeform(question: str, first_sql: str | None) -> None:
    """Run generate, validate and execute, with one retry on a validation or SQL error."""
    previous_sql = error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        generated = next_attempt(question, attempt, previous_sql, error, first_sql)
        if generated.sql is None:
            print(f"cannot answer: {generated.cannot_answer}")
            return
        print(f"\nattempt {attempt} SQL:\n{generated.sql}")
        try:
            safe_sql = validate_sql(generated.sql)
            columns, rows = run_query(safe_sql)
        except (UnsafeSQL, psycopg.Error) as caught:
            previous_sql, error = generated.sql, str(caught).strip()
            print(f"attempt {attempt} failed: {error}")
            continue
        print(f"\nexplanation: {generated.explanation}")
        print(f"executed SQL: {safe_sql}\n")
        print_table(columns, rows)
        return
    print(f"\nfailed after {MAX_ATTEMPTS} attempts")


def main() -> None:
    """Read the question and run the free-form path once, logging each LLM call's tokens."""
    parser = argparse.ArgumentParser(description="Try the free-form SQL path.")
    parser.add_argument("question")
    parser.add_argument("--first-sql", help="use this SQL instead of the LLM's first attempt")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(f"question: {arguments.question}")
    run_freeform(arguments.question, arguments.first_sql)


if __name__ == "__main__":
    main()
