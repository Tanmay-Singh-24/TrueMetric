"""One or two sentences answering the question, written from the result rows only."""

import logging

from orderlens.llm import LLMError, LLMRateLimited, invoke_text

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
