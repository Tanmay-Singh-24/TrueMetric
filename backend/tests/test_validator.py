import re

import pytest

from truemetric.db import run_query
from truemetric.metrics.catalog import METRICS, Metric
from truemetric.metrics.registry import metric_sql
from truemetric.validator import MAX_ROWS, UnsafeSQL, validate_sql

ACCEPTED = {
    "plain select": "SELECT seller_id, seller_state FROM sellers",
    "join": (
        "SELECT c.customer_state, COUNT(*) AS orders FROM orders o "
        "JOIN customers c ON c.customer_id = o.customer_id GROUP BY c.customer_state"
    ),
    "cte": (
        "WITH per_state AS (SELECT seller_state, COUNT(*) AS sellers FROM sellers "
        "GROUP BY seller_state) SELECT seller_state, sellers FROM per_state WHERE sellers > 10"
    ),
    "subquery": (
        "SELECT order_id FROM orders WHERE customer_id IN "
        "(SELECT customer_id FROM customers WHERE customer_state = 'SP')"
    ),
    "union": "SELECT customer_state AS state FROM customers UNION SELECT seller_state FROM sellers",
    "window function": (
        "SELECT category, RANK() OVER (ORDER BY COUNT(*) DESC) AS position "
        "FROM products GROUP BY category"
    ),
    "trailing semicolon": "SELECT COUNT(*) FROM orders;",
    "date function": "SELECT DATE(order_purchase_timestamp) AS day FROM orders",
}

# Each rejected query names a word the error message must contain, so the test shows
# which check stopped it.
REJECTED = {
    "incomplete sql": ("SELECT * FROM orders WHERE (", "parse"),
    "unterminated string": ("SELECT 'oops", "parse"),
    "plain english": ("show me everything", "only SELECT"),
    "two statements": ("SELECT * FROM orders; DROP TABLE orders", "one statement"),
    "insert": ("INSERT INTO sellers VALUES ('x', 'y', 'SP')", "only SELECT"),
    "update": ("UPDATE orders SET order_status = 'delivered'", "only SELECT"),
    "delete": ("DELETE FROM orders", "only SELECT"),
    "drop": ("DROP TABLE orders", "only SELECT"),
    "delete inside a cte": (
        "WITH gone AS (DELETE FROM orders RETURNING order_id) SELECT order_id FROM gone",
        "not allowed: DELETE",
    ),
    "update inside a cte": (
        "WITH changed AS (UPDATE orders SET order_status = 'x' RETURNING 1) SELECT * FROM changed",
        "not allowed: UPDATE",
    ),
    "select into": ("SELECT * INTO orders_copy FROM orders", "INTO"),
    "for update": ("SELECT * FROM orders FOR UPDATE", "FOR UPDATE"),
    "for share inside a subquery": (
        "SELECT * FROM (SELECT * FROM orders FOR SHARE) AS locked",
        "FOR SHARE",
    ),
    "unknown table": ("SELECT * FROM users", "is not a table"),
    "pg_catalog.pg_roles": ("SELECT rolname FROM pg_catalog.pg_roles", "bare table names"),
    "information_schema.tables": (
        "SELECT table_name FROM information_schema.tables",
        "bare table names",
    ),
    "unknown column": ("SELECT seller_name FROM sellers", "column does not exist"),
    "pg_sleep": ("SELECT pg_sleep(7)", "function"),
    "schema-qualified pg_sleep": ("SELECT pg_catalog.pg_sleep(7)", "not allowed"),
    "table_to_xml": ("SELECT table_to_xml('orders', true, false, '')", "function"),
    "query_to_xml": ("SELECT query_to_xml('SELECT * FROM orders', true, false, '')", "function"),
    "dblink": ("SELECT * FROM dblink('host=example.com', 'SELECT 1') AS t(x int)", "DBLINK"),
    "current_setting": ("SELECT current_setting('statement_timeout')", "function"),
    "version": ("SELECT version()", "function"),
}

EXAMPLE_LITERALS = {
    "start_date": "'2017-01-01'",
    "end_date": "'2017-12-31'",
    "state": "'SP'",
    "category": "'health_beauty'",
    "top_n": "5",
}


def with_literals(sql: str) -> str:
    """Replace each psycopg placeholder with an example literal value."""
    return re.sub(r"%\((\w+)\)s", lambda match: EXAMPLE_LITERALS[match.group(1)], sql)


@pytest.mark.parametrize("sql", ACCEPTED.values(), ids=ACCEPTED.keys())
def test_accepts(sql: str) -> None:
    validate_sql(sql)


@pytest.mark.parametrize("metric", METRICS, ids=lambda metric: metric.id)
def test_accepts_every_metric_sql_file(metric: Metric) -> None:
    validate_sql(with_literals(metric_sql(metric)))


@pytest.mark.parametrize(("sql", "reason"), REJECTED.values(), ids=REJECTED.keys())
def test_rejects(sql: str, reason: str) -> None:
    with pytest.raises(UnsafeSQL, match=reason):
        validate_sql(sql)


def test_adds_a_limit_when_missing() -> None:
    assert validate_sql("SELECT seller_id FROM sellers").endswith(f"LIMIT {MAX_ROWS}")


def test_lowers_a_limit_above_the_maximum() -> None:
    assert validate_sql("SELECT seller_id FROM sellers LIMIT 5000").endswith(f"LIMIT {MAX_ROWS}")


def test_keeps_a_smaller_limit() -> None:
    assert validate_sql("SELECT seller_id FROM sellers LIMIT 5").endswith("LIMIT 5")


def test_limits_the_whole_union() -> None:
    sql = "SELECT customer_state FROM customers UNION SELECT seller_state FROM sellers"
    assert validate_sql(sql).endswith(f"LIMIT {MAX_ROWS}")


def test_a_limit_inside_a_subquery_does_not_count_as_the_top_level_limit() -> None:
    sql = "SELECT order_id FROM (SELECT order_id FROM orders LIMIT 5) AS recent"
    assert validate_sql(sql).endswith(f"LIMIT {MAX_ROWS}")


@pytest.mark.db
@pytest.mark.parametrize("metric", METRICS, ids=lambda metric: metric.id)
def test_validated_sql_returns_the_same_rows_as_the_original(metric: Metric) -> None:
    # The validator regenerates the SQL from its parse tree, so this checks that the
    # regenerated text means exactly what the original meant.
    original = with_literals(metric_sql(metric))
    assert run_query(validate_sql(original)) == run_query(original)


def test_a_limit_that_is_not_a_plain_number_is_kept_inside_an_outer_limit() -> None:
    result = validate_sql("SELECT seller_id FROM sellers LIMIT 5::int")
    assert "LIMIT CAST(5 AS INT)" in result
    assert result.endswith(f"LIMIT {MAX_ROWS}")


def test_a_rejected_function_is_named_in_postgres_spelling_with_the_allowed_list() -> None:
    sql = "SELECT TO_CHAR(order_purchase_timestamp, 'YYYY') FROM orders"
    with pytest.raises(UnsafeSQL) as caught:
        validate_sql(sql)
    message = str(caught.value)
    assert message.startswith("TO_CHAR is not an allowed function.")
    assert "Functions: AVG, CASE, CAST, COALESCE, COUNT, DATE, DATE_TRUNC" in message


def test_a_rejected_table_is_answered_with_the_tables_that_exist() -> None:
    with pytest.raises(UnsafeSQL) as caught:
        validate_sql("SELECT * FROM users")
    assert (
        "Tables: customers, order_items, order_payments, order_reviews, orders, products, sellers"
        in str(caught.value)
    )
