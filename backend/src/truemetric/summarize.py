"""The answer sentence: built by code for a single value, otherwise a short LLM summary."""

import logging
from typing import Any

from truemetric.audit import format_answer, format_headline
from truemetric.llm import LLMError, LLMRateLimited, invoke_text
from truemetric.metrics.catalog import Metric

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = "Here are the results."
MAX_SUMMARY_ROWS = 20

SUMMARY_PROMPT = """\
Answer the question in one or two sentences, using only numbers that appear in the result
rows below. Do not mention row limits, SQL or the database. Write plain text, without
Markdown formatting.

Question: {question}
What the rows contain: {context}
Columns: {columns}
Rows:
{rows}"""


def summarize(question: str, context: str | None, columns: list[str], rows: list[list]) -> str:
    """A short answer from up to 20 rows and what they contain; the fallback if the LLM fails."""
    shown_rows = "\n".join(
        " | ".join(str(value) for value in row) for row in rows[:MAX_SUMMARY_ROWS]
    )
    prompt = SUMMARY_PROMPT.format(
        question=question,
        context=context or "(not given)",
        columns=" | ".join(columns),
        rows=shown_rows or "(no rows)",
    )
    try:
        return invoke_text("Summary", [("human", prompt)]).strip() or FALLBACK_ANSWER
    except (LLMError, LLMRateLimited) as error:
        # A failed summary must not hide a query that worked.
        logger.warning("summary failed, using the fallback: %s", error)
        return FALLBACK_ANSWER


def write_answer(
    question: str,
    metric: Metric | None,
    metric_args: dict[str, Any] | None,
    explanation: str | None,
    columns: list[str],
    rows: list[list],
    use_llm: bool,
) -> tuple[str, str | None]:
    """The answer sentence and the headline (None unless the answer is one number)."""
    headline = format_headline(metric, columns, rows) if metric else None
    if headline is not None:
        # A single value needs no LLM: the answer is built by code from what ran.
        return format_answer(metric, metric_args, headline), headline
    if not use_llm:
        return FALLBACK_ANSWER, None
    # Tell the summary what the rows mean: the metric, or the generator's explanation.
    context = f"{metric.name}: {metric.definition}" if metric else explanation
    return summarize(question, context, columns, rows), None
