"""Ask one question from the terminal: print status, headline, answer, table and audit.

Usage:
  uv run --env-file .env python scripts/ask.py "What was our revenue in 2018?"
  uv run --env-file .env python scripts/ask.py "Which category performs best?" \\
      --metric-id top_categories_by_units
"""

import argparse
import json
import logging

from terminal import print_table

from truemetric.graph import ask

MAX_ROWS_SHOWN = 20


def parse_arguments() -> argparse.Namespace:
    """Read the question and the optional settings of ask()."""
    parser = argparse.ArgumentParser(description="Ask TrueMetric one question.")
    parser.add_argument("question")
    parser.add_argument("--metric-id", help="the metric chosen from a clarify question")
    parser.add_argument("--mode", choices=["full", "freeform_only"], default="full")
    parser.add_argument("--no-summarize", action="store_true", help="skip the summary call")
    return parser.parse_args()


def main() -> None:
    """Run ask() once and print the response, logging each LLM call's tokens."""
    arguments = parse_arguments()
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(f"question: {arguments.question}")
    result = ask(
        arguments.question,
        metric_id=arguments.metric_id,
        mode=arguments.mode,
        summarize=not arguments.no_summarize,
    )
    print(f"status:   {result['status']}")
    print(f"headline: {result['headline']}")
    print(f"answer:   {result['answer']}")
    for option in result["options"]:
        print(f"  option: {option['metric_id']} ({option['name']})")
    if result["columns"]:
        print()
        print_table(result["columns"], result["rows"][:MAX_ROWS_SHOWN])
    if result["audit"]:
        print("\naudit:")
        print(json.dumps(result["audit"], indent=2))


if __name__ == "__main__":
    main()
