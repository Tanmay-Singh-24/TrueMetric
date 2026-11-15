"""Values the router and argument checks need to know: states and categories in the data."""

from functools import cache

from orderlens.db import run_query


@cache
def known_states() -> frozenset[str]:
    """The two-letter customer state codes in the data, read once."""
    _, rows = run_query("SELECT DISTINCT customer_state FROM customers")
    return frozenset(row[0] for row in rows)


@cache
def known_categories() -> frozenset[str]:
    """The product category names in the data, including 'unknown', read once."""
    _, rows = run_query("SELECT DISTINCT category FROM products")
    return frozenset(row[0] for row in rows)
