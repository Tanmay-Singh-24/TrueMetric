"""Tries to get untrusted SQL past the validator.

1. Hand-written attacks, grouped by the trick they use. Each names a word the rejection
   message must contain, so the test shows which check stopped it.
2. A generator that hides each dangerous query inside every wrapper, every pair of
   wrappers, and ten of the same wrapper, and checks none gets through. The same
   wrappers around a safe query must be accepted, so each rejection is caused by the
   dangerous query and not by the wrapper.

Passing shows that every trick tried here is stopped. It cannot show that no other trick
exists, which is why the validator accepts only what it lists and why the read-only role
and the timeout sit behind it.
"""

import pytest

from truemetric.validator import UnsafeSQL, validate_sql

ATTACKS = {
    # nested subqueries and CTEs
    "nesting: catalog table four subqueries deep": (
        "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM pg_roles) AS a) AS b) AS c",
        "pg_roles is not a table",
    ),
    "nesting: catalog table in a LATERAL subquery": (
        "SELECT * FROM orders AS o, LATERAL (SELECT * FROM pg_roles) AS r",
        "not allowed: LATERAL",
    ),
    "nesting: DELETE in a CTE three levels down": (
        "WITH a AS (WITH b AS (WITH c AS (DELETE FROM orders RETURNING order_id) "
        "SELECT * FROM c) SELECT * FROM b) SELECT * FROM a",
        "not allowed: DELETE",
    ),
    "nesting: DELETE in a MATERIALIZED CTE": (
        "WITH x AS MATERIALIZED (DELETE FROM orders RETURNING order_id) SELECT * FROM x",
        "not allowed: DELETE",
    ),
    "nesting: WITH inside a subquery": (
        "SELECT * FROM (WITH s AS (SELECT seller_id FROM sellers) SELECT * FROM s) AS w",
        "WITH may only start",
    ),
    "nesting: WITH RECURSIVE": (
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT n FROM r",
        "RECURSIVE",
    ),
    # which name means which CTE
    "cte scope: a CTE name read outside the subquery that defines it": (
        "SELECT * FROM (WITH pg_roles AS (SELECT 1 AS x) SELECT * FROM pg_roles) AS w, pg_roles",
        "WITH may only start",
    ),
    "cte scope: a CTE that reads its own name": (
        "WITH pg_roles AS (SELECT * FROM pg_roles) SELECT * FROM pg_roles",
        "pg_roles is not a table",
    ),
    "cte scope: a CTE that reads a CTE defined after it": (
        "WITH a AS (SELECT * FROM pg_authid), pg_authid AS (SELECT 1 AS x) SELECT * FROM a",
        "pg_authid is not a table",
    ),
    "cte scope: a quoted CTE name read without quotes": (
        'WITH "Pg_Roles" AS (SELECT 1 AS x) SELECT * FROM Pg_Roles',
        "pg_roles is not a table",
    ),
    # UNION, INTERSECT and EXCEPT
    "set operations: UNION with a catalog table": (
        "SELECT seller_id FROM sellers UNION SELECT rolname FROM pg_roles",
        "pg_roles is not a table",
    ),
    "set operations: INTERSECT with a catalog view": (
        "SELECT seller_id FROM sellers INTERSECT SELECT usename FROM pg_user",
        "pg_user is not a table",
    ),
    "set operations: EXCEPT with a function": (
        "SELECT seller_id FROM sellers EXCEPT SELECT pg_sleep(1)::text",
        "PG_SLEEP is not an allowed function",
    ),
    "set operations: subquery in the ORDER BY of a UNION": (
        "SELECT seller_id FROM sellers UNION SELECT seller_id FROM sellers "
        "ORDER BY (SELECT COUNT(rolpassword) FROM sellers)",
        "ORDER BY, LIMIT or OFFSET",
    ),
    "set operations: subquery in the LIMIT of an INTERSECT": (
        "SELECT seller_id FROM sellers INTERSECT SELECT seller_id FROM sellers "
        "LIMIT (SELECT COUNT(rolpassword) FROM sellers)",
        "ORDER BY, LIMIT or OFFSET",
    ),
    "set operations: subquery in the OFFSET of an EXCEPT": (
        "SELECT seller_id FROM sellers EXCEPT SELECT seller_id FROM sellers "
        "OFFSET (SELECT COUNT(rolpassword) FROM sellers)",
        "ORDER BY, LIMIT or OFFSET",
    ),
    "set operations: bracketed UNION branch": (
        "(SELECT seller_id FROM sellers) UNION ALL (SELECT current_setting('server_version'))",
        "CURRENT_SETTING is not an allowed function",
    ),
    # schema-qualified and quoted identifiers
    "identifiers: schema-qualified table": ("SELECT * FROM pg_catalog.pg_roles", "names a schema"),
    "identifiers: quoted schema-qualified table": (
        'SELECT * FROM "pg_catalog"."pg_authid"',
        "names a schema",
    ),
    "identifiers: public schema": ("SELECT * FROM public.orders", "names a schema"),
    "identifiers: three-part name": ("SELECT * FROM neondb.public.orders", "names a schema"),
    "identifiers: quoted catalog table": ('SELECT * FROM "pg_roles"', "pg_roles is not a table"),
    "identifiers: upper-case catalog table": (
        "SELECT * FROM PG_SHADOW",
        "pg_shadow is not a table",
    ),
    "identifiers: quoted name in the wrong case": (
        'SELECT * FROM "Orders"',
        "Orders is not a table",
    ),
    "identifiers: unicode-escaped name": ('SELECT * FROM U&"pg_roles"', "parse"),
    # aliases and ambiguous columns
    "columns: alias named after a catalog table": (
        "SELECT pg_roles.rolname FROM orders AS pg_roles",
        "column does not exist",
    ),
    "columns: catalog column": ("SELECT rolpassword FROM orders", "column does not exist"),
    "columns: system column": ("SELECT xmin FROM orders", "column does not exist"),
    "columns: ambiguous column": (
        "SELECT order_id FROM orders AS o JOIN order_items AS i ON i.order_id = o.order_id",
        "could not be resolved",
    ),
    # Postgres reads o.to_json, with no such column, as the function call to_json(o).
    "columns: function called as a column": (
        "SELECT o.to_json FROM orders AS o",
        "column does not exist",
    ),
    "columns: function called on a whole row": (
        "SELECT (o).to_json FROM orders AS o",
        "not allowed",
    ),
    # SELECT * and qualified wildcards
    "wildcards: qualified wildcard of a table not in the query": (
        "SELECT pg_roles.* FROM orders",
        "column does not exist",
    ),
    "wildcards: SELECT * across a catalog table": (
        "SELECT * FROM orders, pg_shadow",
        "pg_shadow is not a table",
    ),
    # dangerous functions, in every position
    "functions: in ORDER BY": ("SELECT * FROM orders ORDER BY pg_sleep(1)", "PG_SLEEP"),
    "functions: in JOIN ON": (
        "SELECT * FROM orders AS o JOIN customers AS c ON pg_sleep(1) IS NULL",
        "PG_SLEEP",
    ),
    "functions: in GROUP BY": ("SELECT COUNT(*) FROM orders GROUP BY pg_sleep(0.1)", "PG_SLEEP"),
    "functions: in FILTER": (
        "SELECT COUNT(*) FILTER (WHERE pg_sleep(1) IS NULL) FROM orders",
        "PG_SLEEP",
    ),
    "functions: in a window": (
        "SELECT SUM(price) OVER (ORDER BY pg_sleep(0.1)) FROM order_items",
        "PG_SLEEP",
    ),
    "functions: inside an allowed function": ("SELECT COUNT(pg_sleep(1)) FROM orders", "PG_SLEEP"),
    "functions: quoted name": ('SELECT "pg_sleep"(1)', "is not an allowed function"),
    "functions: schema-qualified name": ("SELECT pg_catalog.pg_sleep(1)", "not allowed"),
    "functions: used as a table": ("SELECT * FROM pg_sleep(5)", "PG_SLEEP"),
    "functions: set-returning, used as a table": (
        "SELECT * FROM generate_series(1, 1000000000) AS g",
        "GENERATE_SERIES",
    ),
    "functions: file read": ("SELECT pg_read_file('/etc/passwd')", "PG_READ_FILE"),
    "functions: large object import": ("SELECT lo_import('/etc/passwd')", "LO_IMPORT"),
    "functions: settings change": (
        "SELECT set_config('statement_timeout', '0', false)",
        "SET_CONFIG",
    ),
    "functions: session user": ("SELECT current_user", "CURRENT_USER"),
    "functions: server address": ("SELECT inet_server_addr()", "INET_SERVER_ADDR"),
    # Casting a name to regclass or regproc looks it up in the system catalog. sqlglot
    # builds these as their own node type, so the syntax check stops them first.
    "casts: to regclass": ("SELECT 'pg_authid'::regclass", "not allowed: REGCLASS"),
    "casts: CAST AS regproc": ("SELECT CAST('pg_sleep' AS regproc)", "not allowed: REGPROC"),
    "casts: chained catalog casts": ("SELECT 'pg_catalog'::regnamespace::oid", "not allowed"),
    "casts: to xml": ("SELECT order_id::xml FROM orders", "XML is not an allowed type"),
    "casts: to an array": ("SELECT '{1,2}'::int[]", "is not an allowed type"),
    # PostgreSQL-specific statements and syntax
    "postgres: SET": ("SET search_path TO pg_catalog", "only SELECT"),
    "postgres: SET ROLE": ("SET ROLE neondb_owner", "only SELECT"),
    "postgres: RESET": ("RESET ALL", "only SELECT"),
    "postgres: SHOW": ("SHOW ALL", "only SELECT"),
    "postgres: EXPLAIN ANALYZE": ("EXPLAIN ANALYZE DELETE FROM orders", "only SELECT"),
    "postgres: COPY": ("COPY orders TO STDOUT", "only SELECT"),
    "postgres: DO block": ("DO $$ BEGIN DELETE FROM orders; END $$", "only SELECT"),
    "postgres: PREPARE": ("PREPARE p AS SELECT 1", "only SELECT"),
    "postgres: EXECUTE": ("EXECUTE p", "only SELECT"),
    "postgres: NOTIFY": ("NOTIFY chan", "only SELECT"),
    "postgres: BEGIN": ("BEGIN", "only SELECT"),
    "postgres: CREATE TABLE AS": ("CREATE TEMP TABLE t AS SELECT 1", "only SELECT"),
    "postgres: VALUES": ("VALUES (1)", "only SELECT"),
    "postgres: SELECT INTO a temporary table": (
        "SELECT * INTO TEMP t FROM orders",
        "not allowed: INTO",
    ),
    "postgres: FOR NO KEY UPDATE": (
        "SELECT * FROM orders FOR NO KEY UPDATE",
        "not allowed: FOR NO KEY UPDATE",
    ),
    "postgres: FOR KEY SHARE": ("SELECT * FROM orders FOR KEY SHARE", "not allowed: FOR KEY SHARE"),
    "postgres: second statement after a comment": (
        "SELECT 1; -- harmless\nDROP TABLE orders",
        "one statement",
    ),
    "postgres: OPERATOR()": ("SELECT 1 OPERATOR(pg_catalog.+) 1", "not allowed"),
    "postgres: positional parameter": ("SELECT $1", "not allowed: \\$1"),
    "postgres: TABLESAMPLE": ("SELECT * FROM orders TABLESAMPLE SYSTEM (1)", "not allowed"),
    "postgres: FETCH FIRST": ("SELECT * FROM orders FETCH FIRST 100000 ROWS ONLY", "not allowed"),
    "postgres: dollar-quoted string": ("SELECT $q$ it's $q$ AS s", "not allowed"),
}

# Odd but harmless: each is accepted, and this is exactly what runs.
HARMLESS = {
    "a semicolon inside a string stays data": (
        "SELECT 'a;DROP TABLE orders' AS s",
        "SELECT 'a;DROP TABLE orders' AS s LIMIT 200",
    ),
    "comments are not sent to the database": (
        "SELECT seller_id FROM sellers -- */ , pg_sleep(5) /*",
        "SELECT seller_id FROM sellers LIMIT 200",
    ),
    "unquoted names are lower-cased, as Postgres does": (
        "SELECT * FROM ORDERS",
        "SELECT * FROM orders LIMIT 200",
    ),
    "a CTE may reuse a table's name": (
        "WITH orders AS (SELECT * FROM orders) SELECT COUNT(*) FROM orders",
        "WITH orders AS (SELECT * FROM orders) SELECT COUNT(*) FROM orders LIMIT 200",
    ),
}


@pytest.mark.parametrize(("sql", "reason"), ATTACKS.values(), ids=ATTACKS.keys())
def test_rejects_the_attack(sql: str, reason: str) -> None:
    with pytest.raises(UnsafeSQL, match=reason):
        validate_sql(sql)


@pytest.mark.parametrize(("sql", "expected"), HARMLESS.values(), ids=HARMLESS.keys())
def test_accepts_the_harmless_oddity_as_it_will_run(sql: str, expected: str) -> None:
    assert validate_sql(sql) == expected


def test_a_query_nested_past_the_parsers_limit_is_rejected_cleanly() -> None:
    sql = "SELECT seller_id FROM sellers"
    for _ in range(300):
        sql = f"SELECT seller_id FROM ({sql}) AS hidden"
    with pytest.raises(UnsafeSQL, match="nested too deeply"):
        validate_sql(sql)


# Each returns one column, x, so it fits inside any wrapper below.
DANGEROUS = {
    "catalog table": "SELECT rolname AS x FROM pg_roles",
    "schema-qualified catalog table": "SELECT relname AS x FROM pg_catalog.pg_class",
    "quoted catalog table": 'SELECT usename AS x FROM "pg_user"',
    "upper-case catalog table": "SELECT passwd AS x FROM PG_SHADOW",
    "information_schema": "SELECT table_name AS x FROM information_schema.tables",
    "pg_sleep": "SELECT pg_sleep(1) AS x",
    "schema-qualified pg_sleep": "SELECT pg_catalog.pg_sleep(1) AS x",
    "pg_sleep as a table": "SELECT x FROM pg_sleep(1) AS x",
    "file read": "SELECT pg_read_file('/etc/passwd') AS x",
    "settings change": "SELECT set_config('statement_timeout', '0', false) AS x",
    "catalog lookup by cast": "SELECT 'pg_authid'::regclass AS x",
    "function lookup by cast": "SELECT CAST('pg_sleep' AS regproc) AS x",
    "operator call": "SELECT 1 OPERATOR(pg_catalog.+) 1 AS x",
    "row lock": "SELECT seller_id AS x FROM sellers FOR UPDATE",
    "function on a whole row": "SELECT (s).to_json AS x FROM sellers AS s",
    "unknown column": "SELECT rolpassword AS x FROM sellers",
}
SAFE = "SELECT seller_id AS x FROM sellers"

# Each hides a one-column query, {}, somewhere inside another one-column query.
WRAPPERS = {
    "FROM subquery": "SELECT x FROM ({}) AS hidden",
    "JOIN": (
        "SELECT s.seller_id AS x FROM sellers AS s JOIN ({}) AS hidden ON hidden.x = s.seller_id"
    ),
    "JOIN ON": "SELECT s.seller_id AS x FROM sellers AS s JOIN sellers AS t ON EXISTS ({})",
    "scalar subquery": "SELECT ({}) AS x",
    "IN": "SELECT seller_id AS x FROM sellers WHERE seller_id IN ({})",
    "EXISTS": "SELECT seller_id AS x FROM sellers WHERE EXISTS ({})",
    "CASE": "SELECT CASE WHEN EXISTS ({}) THEN 'yes' ELSE 'no' END AS x",
    "ORDER BY": "SELECT seller_id AS x FROM sellers ORDER BY ({})",
    "HAVING": (
        "SELECT seller_state AS x FROM sellers GROUP BY seller_state "
        "HAVING COUNT(*) > (SELECT COUNT(*) FROM ({}) AS hidden)"
    ),
    "FILTER": "SELECT COUNT(*) FILTER (WHERE seller_id IN ({})) AS x FROM sellers",
    "window": "SELECT RANK() OVER (ORDER BY ({})) AS x FROM sellers",
    "LIMIT": "SELECT seller_id AS x FROM sellers LIMIT ({})",
    "OFFSET": "SELECT seller_id AS x FROM sellers OFFSET ({})",
    # Brackets keep a hidden query's own ORDER BY or LIMIT inside its branch.
    "UNION": "SELECT seller_id AS x FROM sellers UNION ({})",
    "INTERSECT": "SELECT seller_id AS x FROM sellers INTERSECT ({})",
    "EXCEPT": "SELECT seller_id AS x FROM sellers EXCEPT ({})",
    "first branch of UNION ALL": "({}) UNION ALL (SELECT seller_id AS x FROM sellers)",
}

# A WITH may only start a query, so these go around everything else.
OUTER_WRAPPERS = {
    "nothing": "{}",
    "CTE": "WITH hidden AS ({}) SELECT x FROM hidden",
    "first of three CTEs": (
        "WITH c1 AS ({}), c2 AS (SELECT x FROM c1), c3 AS (SELECT x FROM c2) SELECT x FROM c3"
    ),
}


def nested(query: str, wrapper: str, depth: int) -> str:
    """The query inside the same wrapper `depth` times."""
    for _ in range(depth):
        query = wrapper.format(query)
    return query


def hidings(query: str) -> list[str]:
    """The query inside every wrapper, every pair of wrappers and ten of each wrapper,
    each of those also inside every outer wrapper."""
    inner = [query]
    for first in WRAPPERS.values():
        inner.append(first.format(query))
        inner += [second.format(first.format(query)) for second in WRAPPERS.values()]
        inner.append(nested(query, first, 10))
    return [outer.format(sql) for outer in OUTER_WRAPPERS.values() for sql in inner]


def is_accepted(sql: str) -> bool:
    """Whether the validator lets the query run."""
    try:
        validate_sql(sql)
    except UnsafeSQL:
        return False
    return True


def test_every_hiding_place_accepts_a_safe_query() -> None:
    assert [sql for sql in hidings(SAFE) if not is_accepted(sql)] == []


@pytest.mark.parametrize("payload", DANGEROUS.values(), ids=DANGEROUS.keys())
def test_no_hiding_place_lets_a_dangerous_query_through(payload: str) -> None:
    assert [sql for sql in hidings(payload) if is_accepted(sql)] == []
