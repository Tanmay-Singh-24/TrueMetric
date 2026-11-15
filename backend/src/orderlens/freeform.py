"""The free-form path's generator: the LLM writes one SELECT when no metric fits."""

from pydantic import BaseModel

from orderlens.llm import invoke_structured
from orderlens.metrics.catalog import METRICS
from orderlens.schema import SCHEMA_SQL


class GeneratedSQL(BaseModel):
    sql: str | None  # one SELECT statement
    cannot_answer: str | None  # set instead of sql when the data cannot answer the question
    explanation: str  # one sentence on what the query computes


# The shared definitions from docs/METRICS.md. The metric definitions follow them, taken
# from the catalogue, so the free-form path knows the same business rules as the metrics.
SHARED_DEFINITIONS = """\
- Valid order: order_status NOT IN ('canceled', 'unavailable').
- Order date: order_purchase_timestamp.
- Date ranges include both ends, by calendar day: >= start_date and < end_date + 1 day.
- Customer: customer_unique_id, never customer_id (customer_id is new for every order).
- Unit: one row in order_items.
- Revenue: sum of order_items.price. Freight is excluded.
- Currency: Brazilian real (BRL).
- Never join order_items and order_payments in one query: both have many rows per order."""

METRIC_DEFINITIONS = "\n".join(
    f"- {metric.name} (also called {', '.join(metric.synonyms)}): {metric.definition} "
    f"({'; '.join(metric.notes)}.)"
    for metric in METRICS
)

SYSTEM_PROMPT = f"""\
You write one PostgreSQL SELECT statement that answers a question about an online store's
orders in Brazil, placed between 2016-09-04 and 2018-10-17.

Database schema:
{SCHEMA_SQL}
Business definitions:
{SHARED_DEFINITIONS}
{METRIC_DEFINITIONS}

Return one SELECT statement in `sql`. If this data cannot answer the question, set `sql`
to null and say why in `cannot_answer`. In `explanation`, say in one sentence what the
query computes."""

RETRY_PROMPT = """\
Your previous query failed. Write a corrected query.

Previous query:
{previous_sql}

Error:
{error}"""


def generate_sql(
    question: str, previous_sql: str | None = None, error: str | None = None
) -> GeneratedSQL:
    """Ask the LLM for SQL answering the question; on a retry, show it what failed."""
    messages = [("system", SYSTEM_PROMPT), ("human", question)]
    if previous_sql is not None:
        messages.append(("human", RETRY_PROMPT.format(previous_sql=previous_sql, error=error)))
    return invoke_structured(GeneratedSQL, messages)
