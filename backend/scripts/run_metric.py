"""Run one verified metric from the terminal: print its headline, table and audit trail.

Usage:
  uv run --env-file .env python scripts/run_metric.py merchandise_revenue \\
      --start 2018-01-01 --end 2018-12-31 --state SP
"""

import argparse
import time

from orderlens.audit import build_audit, format_headline
from orderlens.metrics.catalog import METRICS
from orderlens.metrics.registry import (
    InvalidArgs,
    get_metric,
    metric_sql,
    run_metric,
    validate_args,
)


def parse_arguments() -> argparse.Namespace:
    """Read the metric id and its optional arguments from the command line."""
    parser = argparse.ArgumentParser(description="Run one verified metric.")
    parser.add_argument("metric_id", choices=[metric.id for metric in METRICS])
    parser.add_argument("--start", dest="start_date", help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end", dest="end_date", help="YYYY-MM-DD, inclusive")
    parser.add_argument("--state", help="two-letter customer state, e.g. SP")
    parser.add_argument("--category", help="product category, e.g. health_beauty")
    parser.add_argument("--top-n", dest="top_n", type=int, help="rows for ranked metrics")
    return parser.parse_args()


def print_table(columns: list[str], rows: list[list]) -> None:
    """Print rows under their column names, each column right-aligned."""
    lines = [columns, *rows]
    widths = [max(len(str(line[index])) for line in lines) for index in range(len(columns))]
    for line in lines:
        print("  ".join(str(value).rjust(width) for value, width in zip(line, widths, strict=True)))


def main() -> None:
    """Validate the arguments, run the metric and print the result."""
    arguments = vars(parse_arguments())
    metric = get_metric(arguments.pop("metric_id"))
    try:
        args = validate_args(metric, arguments)
    except InvalidArgs as error:
        raise SystemExit(f"invalid arguments: {error}") from None
    started = time.perf_counter()
    columns, rows = run_metric(metric, args)
    duration_ms = round((time.perf_counter() - started) * 1000)
    print(f"headline: {format_headline(metric, columns, rows)}\n")
    print_table(columns, rows)
    audit = build_audit(
        metric=metric,
        parameters=args,
        sql=metric_sql(metric),
        row_count=len(rows),
        duration_ms=duration_ms,
        model="none (run from the terminal)",
    )
    print("\naudit:")
    print(audit.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
