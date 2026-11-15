"""Checks LLM-written SQL before it runs.

A query runs only if every part of it is on an allowlist:
  1. shape     - one statement, and every query block in it is a plain SELECT;
  2. tables    - only the seven schema tables, or CTEs the query defines;
  3. functions - only the functions listed in ALLOWED_FUNCTIONS;
  4. columns   - only columns that exist in schema.sql.
Then a row limit is applied. Anything else raises UnsafeSQL, whose message says what is
allowed, so the free-form path's one retry has what it needs to fix the query.

Allowlists, not blocklists: a blocklist only stops what someone thought of, while here
anything new or unexpected is rejected by default. The read-only database role and the
5-second timeout are separate layers behind this one.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, TokenError
from sqlglot.optimizer.qualify import qualify

from truemetric.schema import TABLE_COLUMNS

MAX_ROWS = 200

# The only kinds of query block allowed anywhere in a query: a SELECT, or a UNION,
# INTERSECT or EXCEPT of SELECTs. An INSERT/UPDATE/DELETE hidden in a CTE, or a raw
# command, is simply not on the list.
QUERY_BLOCKS = (exp.Select, exp.SetOperation)

# Keys are sqlglot node types, values the Postgres name used in messages. A function
# sqlglot does not recognise becomes exp.Anonymous (pg_sleep, dblink, table_to_xml, ...),
# which is not a key, so it is rejected without anyone having to list it.
ALLOWED_FUNCTIONS = {
    exp.Count: "COUNT",
    exp.Sum: "SUM",
    exp.Avg: "AVG",
    exp.Min: "MIN",
    exp.Max: "MAX",
    exp.Coalesce: "COALESCE",
    exp.Nullif: "NULLIF",
    exp.Round: "ROUND",
    exp.Cast: "CAST",
    exp.Case: "CASE",
    exp.If: "CASE",  # sqlglot stores each WHEN branch of a CASE as an If node
    exp.TimestampTrunc: "DATE_TRUNC",  # date_trunc on a timestamp
    exp.DateTrunc: "DATE_TRUNC",  # date_trunc on a date
    # Added after the first eval run: DATE(x) is the function form of CAST(x AS DATE), and
    # the baseline used it three times; rejecting it cost a retry each time.
    exp.Date: "DATE",
    exp.Extract: "EXTRACT",
    exp.Lower: "LOWER",
    exp.Upper: "UPPER",
    exp.RowNumber: "ROW_NUMBER",
    exp.Rank: "RANK",
    exp.DenseRank: "DENSE_RANK",
    exp.Exists: "EXISTS",
}
ALLOWED_FUNCTION_NAMES = ", ".join(sorted(set(ALLOWED_FUNCTIONS.values())))
ALLOWED_TABLE_NAMES = ", ".join(sorted(TABLE_COLUMNS))


class UnsafeSQL(Exception):
    """Generated SQL that must not be run."""


def parse(sql: str) -> exp.Expression:
    """The single statement in the text, parsed as Postgres."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except (ParseError, TokenError) as error:
        raise UnsafeSQL(f"the SQL does not parse: {error}") from None
    if len(statements) != 1:
        raise UnsafeSQL(f"send one statement only (this has {len(statements)})")
    return statements[0]


def check_shape(statement: exp.Expression) -> None:
    """The query and every CTE and subquery in it must be a plain SELECT."""
    blocks = [statement]
    blocks += [cte.this for cte in statement.find_all(exp.CTE)]
    blocks += [subquery.this for subquery in statement.find_all(exp.Subquery)]
    for block in blocks:
        if not isinstance(block, QUERY_BLOCKS):
            raise UnsafeSQL(f"only SELECT queries can run, and this contains {block.key.upper()}")
    for select in statement.find_all(exp.Select):
        # A SELECT can still write (SELECT ... INTO creates a table) or lock rows.
        if select.args.get("into") or select.args.get("locks"):
            raise UnsafeSQL("a SELECT may not create a table (INTO) or lock rows (FOR UPDATE)")


def check_tables(statement: exp.Expression) -> None:
    """Every table must be one of the seven, or a CTE defined in the query."""
    defined_here = {cte.alias_or_name for cte in statement.find_all(exp.CTE)}
    for table in statement.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            continue  # a function used as a table, e.g. FROM dblink(...): check_functions decides
        if table.db or table.catalog:
            raise UnsafeSQL(f"use bare table names; {table.sql()} names a schema")
        if table.name not in TABLE_COLUMNS and table.name not in defined_here:
            raise UnsafeSQL(f"{table.name} is not a table. Tables: {ALLOWED_TABLE_NAMES}")


def check_functions(statement: exp.Expression) -> None:
    """Every function must be on ALLOWED_FUNCTIONS."""
    for function in statement.find_all(exp.Func):
        # AND and OR are operators, but sqlglot models them as function nodes.
        if isinstance(function, exp.Connector) or type(function) in ALLOWED_FUNCTIONS:
            continue
        # sqlglot's own names differ from Postgres (TO_CHAR is TIME_TO_STR), so the name
        # is taken from the node written back out as Postgres SQL.
        name = function.sql(dialect="postgres").split("(")[0]
        raise UnsafeSQL(f"{name} is not an allowed function. Functions: {ALLOWED_FUNCTION_NAMES}")


def check_columns(statement: exp.Expression) -> None:
    """Every column must exist in the table or CTE it is read from."""
    try:
        qualify(
            statement.copy(),
            schema=TABLE_COLUMNS,
            dialect="postgres",
            validate_qualify_columns=True,
        )
    except OptimizeError as error:
        raise UnsafeSQL(f"a column does not exist: {error}") from None


def with_row_limit(statement: exp.Expression) -> exp.Expression:
    """At most MAX_ROWS rows, without ever raising a smaller limit."""
    limit = statement.args.get("limit")
    if limit is None:
        return statement.limit(MAX_ROWS)
    count = limit.expression
    if isinstance(count, exp.Literal) and count.is_int:
        return statement.limit(min(int(count.this), MAX_ROWS))
    # A limit that is not a plain number (LIMIT 5::int, LIMIT ALL) could be either side
    # of MAX_ROWS, so keep it and put an outer limit around the whole query.
    return exp.select("*").from_(statement.subquery("limited")).limit(MAX_ROWS)


def validate_sql(sql: str) -> str:
    """The query exactly as it will run, with a row limit; raises UnsafeSQL otherwise."""
    statement = parse(sql)
    check_shape(statement)
    check_tables(statement)
    check_functions(statement)
    check_columns(statement)
    # What runs is regenerated from the checked tree, so what runs is what was checked.
    return with_row_limit(statement).sql(dialect="postgres")
