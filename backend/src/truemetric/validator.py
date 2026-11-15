"""Checks LLM-written SQL before it runs: one read-only SELECT over known tables, columns
and functions, with a row limit. Anything else raises UnsafeSQL."""

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, TokenError
from sqlglot.optimizer.qualify import qualify

from truemetric.schema import TABLE_COLUMNS

MAX_ROWS = 200

# An allowlist, not a blocklist: a blocklist only stops the functions someone thought
# of. Keys are sqlglot node types, values the Postgres name shown in error messages. A
# function sqlglot does not recognise becomes exp.Anonymous (pg_sleep, dblink,
# table_to_xml, ...) and is therefore never allowed.
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

# Nodes that write, change the schema, lock rows or run raw commands. Most can only
# appear at the top level, which the SELECT check already stops, but Postgres allows
# INSERT/UPDATE/DELETE inside a CTE, and SELECT ... INTO creates a table.
WRITE_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Grant,
    exp.Command,
    exp.Into,
    exp.Lock,
)


class UnsafeSQL(Exception):
    """Generated SQL that must not be run."""


def parse_one_statement(sql: str) -> exp.Expression:
    """Parse the text as Postgres and require exactly one statement."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except (ParseError, TokenError) as error:
        raise UnsafeSQL(f"could not parse the SQL: {error}") from None
    if len(statements) != 1:
        raise UnsafeSQL(f"expected exactly one statement, got {len(statements)}")
    return statements[0]


def check_is_select(statement: exp.Expression) -> None:
    """Allow a SELECT, a CTE ending in a SELECT, or a UNION/INTERSECT/EXCEPT of them."""
    if not isinstance(statement, exp.Select | exp.SetOperation):
        raise UnsafeSQL("only SELECT queries are allowed")


def check_read_only(statement: exp.Expression) -> None:
    """Reject any write, schema change, row lock or raw command anywhere in the query."""
    found = statement.find(*WRITE_NODES)
    if found is not None:
        raise UnsafeSQL(f"not a read-only query: contains {type(found).__name__}")


def check_tables(statement: exp.Expression) -> None:
    """Allow only the seven schema tables and CTEs defined in the query itself."""
    cte_names = {cte.alias_or_name for cte in statement.find_all(exp.CTE)}
    for table in statement.find_all(exp.Table):
        if table.db or table.catalog:
            raise UnsafeSQL(f"schema-qualified table names are not allowed: {table.sql()}")
        if table.name not in TABLE_COLUMNS and table.name not in cte_names:
            raise UnsafeSQL(f"unknown table: {table.sql(dialect='postgres')}")


def check_functions(statement: exp.Expression) -> None:
    """Allow only the functions on ALLOWED_FUNCTIONS."""
    for function in statement.find_all(exp.Func):
        # AND and OR are operators, but sqlglot models them as function nodes.
        if isinstance(function, exp.Connector):
            continue
        if type(function) not in ALLOWED_FUNCTIONS:
            # sqlglot's own names differ from Postgres (TO_CHAR is TIME_TO_STR), so the
            # name is taken from the node written back out as Postgres SQL.
            name = function.sql(dialect="postgres").split("(")[0]
            raise UnsafeSQL(
                f"function not allowed: {name}. Allowed functions: {ALLOWED_FUNCTION_NAMES}"
            )


def check_columns(statement: exp.Expression) -> None:
    """Require every column to exist in the table or CTE it is read from."""
    try:
        qualify(
            statement.copy(),
            schema=TABLE_COLUMNS,
            dialect="postgres",
            validate_qualify_columns=True,
        )
    except OptimizeError as error:
        raise UnsafeSQL(f"column check failed: {error}") from None


def with_row_limit(statement: exp.Expression) -> exp.Expression:
    """Make sure at most MAX_ROWS rows come back, without ever raising a smaller limit."""
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
    """The query exactly as it will run, with a row limit; raises UnsafeSQL if unsafe."""
    statement = parse_one_statement(sql)
    check_is_select(statement)
    check_read_only(statement)
    check_tables(statement)
    check_functions(statement)
    check_columns(statement)
    # The SQL that runs is generated from the checked tree, so what runs is what was checked.
    return with_row_limit(statement).sql(dialect="postgres")
