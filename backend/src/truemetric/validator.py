"""Checks LLM-written SQL before it runs.

The SQL is parsed into a tree, and it runs only if every part of the tree is on an
allowlist:
  1. shape   - one statement, and it is a SELECT (or a UNION, INTERSECT or EXCEPT);
  2. syntax  - every node in the tree is plain query syntax or an allowed function;
  3. types   - a CAST converts only to a plain value type;
  4. tables  - every table is one of the seven, or a CTE the name refers to at that point;
  5. columns - every column exists in schema.sql.
Then a row limit is applied. Anything else raises UnsafeSQL, whose message says what is
allowed, so the free-form path's one retry has what it needs to fix the query.

Allowlists, not blocklists: a blocklist only stops what someone thought of, while here
anything new or unexpected is rejected by default. tests/test_validator_attacks.py tries
to get past these checks. The read-only database role and the 5-second timeout are
separate layers behind this one.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, TokenError
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.qualify import qualify

from truemetric.schema import TABLE_COLUMNS

MAX_ROWS = 200

# The statement itself must be one of these: a SELECT, or a UNION, INTERSECT or EXCEPT.
QUERY_BLOCKS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# Every kind of node a query may contain apart from functions. Anything sqlglot builds
# that is not listed - an INSERT inside a CTE, FOR UPDATE, INTO, OPERATOR(...), a field
# selection like (o).name, a $1 placeholder - is rejected without anyone having to list it.
ALLOWED_SYNTAX = (
    *QUERY_BLOCKS,
    # clauses
    exp.With,
    exp.CTE,
    exp.Subquery,
    exp.From,
    exp.Join,
    exp.Where,
    exp.Group,
    exp.Having,
    exp.Order,
    exp.Ordered,
    exp.Limit,
    exp.Offset,
    exp.Distinct,
    exp.Window,
    exp.WindowSpec,
    exp.Filter,
    # names and values
    exp.Table,
    exp.TableAlias,
    exp.Column,
    exp.Identifier,
    exp.Star,
    exp.Alias,
    exp.Literal,
    exp.Boolean,
    exp.Null,
    exp.Interval,
    exp.Var,  # a keyword argument, e.g. YEAR in EXTRACT(YEAR FROM ...)
    exp.DataType,  # the target of a CAST; check_types decides which types
    exp.DataTypeParam,
    exp.Paren,
    # operators
    exp.And,
    exp.Or,
    exp.Not,
    exp.EQ,
    exp.NEQ,
    exp.GT,
    exp.GTE,
    exp.LT,
    exp.LTE,
    exp.Is,
    exp.In,
    exp.Between,
    exp.Like,
    exp.ILike,
    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
    exp.Mod,
    exp.Neg,
    exp.DPipe,  # || string concatenation
)

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

# The types a CAST may convert to. Converting to a type runs that type's input function,
# and types such as regclass or regproc look names up in the system catalog, so only
# plain value types are listed.
ALLOWED_TYPES = {
    exp.DataType.Type.DATE: "DATE",
    exp.DataType.Type.TIMESTAMP: "TIMESTAMP",
    exp.DataType.Type.TIMESTAMPTZ: "TIMESTAMPTZ",
    exp.DataType.Type.INT: "INT",
    exp.DataType.Type.BIGINT: "BIGINT",
    exp.DataType.Type.DECIMAL: "NUMERIC",
    exp.DataType.Type.DOUBLE: "DOUBLE PRECISION",
    exp.DataType.Type.TEXT: "TEXT",
    exp.DataType.Type.VARCHAR: "VARCHAR",
}

ALLOWED_FUNCTION_NAMES = ", ".join(sorted(set(ALLOWED_FUNCTIONS.values())))
ALLOWED_TYPE_NAMES = ", ".join(sorted(ALLOWED_TYPES.values()))
ALLOWED_TABLE_NAMES = ", ".join(sorted(TABLE_COLUMNS))


class UnsafeSQL(Exception):
    """Generated SQL that must not be run."""


def parse(sql: str) -> exp.Expression:
    """The single statement in the text, parsed as Postgres, with names as Postgres reads them."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except (ParseError, TokenError) as error:
        raise UnsafeSQL(f"the SQL does not parse: {error}") from None
    if len(statements) != 1:
        raise UnsafeSQL(f"send one statement only (this has {len(statements)})")
    # Postgres lower-cases unquoted names and keeps quoted ones exactly, so Pg_Roles means
    # pg_roles but "Pg_Roles" does not. Doing the same here means every name below is
    # compared the way Postgres will resolve it.
    return normalize_identifiers(statements[0], dialect="postgres")


def check_shape(statement: exp.Expression) -> None:
    """The statement must be a SELECT, or a UNION, INTERSECT or EXCEPT of SELECTs."""
    if not isinstance(statement, QUERY_BLOCKS):
        raise UnsafeSQL(f"only SELECT queries can run, not {statement.key.upper()}")


def check_syntax(statement: exp.Expression) -> None:
    """Every node in the tree must be allowed syntax or an allowed function."""
    for node in statement.walk():
        # Exact types, not isinstance: a subclass of an allowed node is a different thing.
        if type(node) in ALLOWED_SYNTAX or type(node) in ALLOWED_FUNCTIONS:
            continue
        if isinstance(node, exp.Func):
            # sqlglot's own names differ from Postgres (TO_CHAR is TIME_TO_STR), so the
            # name is taken from the node written back out as Postgres SQL.
            name = node.sql(dialect="postgres").split("(")[0]
            raise UnsafeSQL(
                f"{name} is not an allowed function. Functions: {ALLOWED_FUNCTION_NAMES}"
            )
        raise UnsafeSQL(f"this syntax is not allowed: {node.sql(dialect='postgres')}")


def check_types(statement: exp.Expression) -> None:
    """Every CAST must convert to a type on ALLOWED_TYPES."""
    for data_type in statement.find_all(exp.DataType):
        if data_type.this not in ALLOWED_TYPES:
            name = data_type.sql(dialect="postgres")
            raise UnsafeSQL(f"{name} is not an allowed type. Types: {ALLOWED_TYPE_NAMES}")


def top_level_ctes(statement: exp.Expression) -> list[exp.CTE]:
    """The CTEs in the WITH clause that starts the query."""
    with_clause = statement.args.get("with_")
    # A WITH inside a subquery, or a RECURSIVE one, would make the rule in check_tables
    # more complicated; generated queries never need either.
    for found in statement.find_all(exp.With):
        if found is not with_clause:
            raise UnsafeSQL("WITH may only start the query, not appear inside a subquery")
    if with_clause is None:
        return []
    if with_clause.args.get("recursive"):
        raise UnsafeSQL("WITH RECURSIVE is not allowed")
    return with_clause.expressions


def check_tables(statement: exp.Expression) -> None:
    """Every table must be one of the seven, or a CTE that the name refers to there."""
    ctes = top_level_ctes(statement)
    cte_names = [cte.alias_or_name for cte in ctes]
    for table in statement.find_all(exp.Table):
        if table.db or table.catalog:
            raise UnsafeSQL(f"use bare table names; {table.sql()} names a schema")
        # Postgres's rule without RECURSIVE: the main query can read every CTE, but a CTE
        # can read only the CTEs listed before it. Any other name is looked up as a real
        # table, so it must be one of the seven.
        enclosing = table.find_ancestor(exp.CTE)
        visible = cte_names[: ctes.index(enclosing)] if enclosing else cte_names
        if table.name not in TABLE_COLUMNS and table.name not in visible:
            raise UnsafeSQL(f"{table.name} is not a table. Tables: {ALLOWED_TABLE_NAMES}")


def check_columns(statement: exp.Expression) -> None:
    """Every column must exist in the table or CTE it is read from."""
    # qualify() does not look inside the ORDER BY, LIMIT or OFFSET of a UNION, INTERSECT
    # or EXCEPT (the attack tests found this), so a subquery there would go unchecked.
    for set_operation in statement.find_all(exp.Union, exp.Intersect, exp.Except):
        for clause in ("order", "limit", "offset"):
            part = set_operation.args.get(clause)
            if part is not None and part.find(exp.Select):
                raise UnsafeSQL(
                    "a subquery may not appear in the ORDER BY, LIMIT or OFFSET "
                    "of a UNION, INTERSECT or EXCEPT"
                )
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
    # A limit that is not a plain number (LIMIT 5::int) could be either side of MAX_ROWS,
    # so keep it and put an outer limit around the whole query.
    return exp.select("*").from_(statement.subquery("limited")).limit(MAX_ROWS)


def validate_sql(sql: str) -> str:
    """The query exactly as it will run, with a row limit; raises UnsafeSQL otherwise."""
    try:
        statement = parse(sql)
        check_shape(statement)
        check_syntax(statement)
        check_types(statement)
        check_tables(statement)
        check_columns(statement)
        # What runs is regenerated from the checked tree, so what runs is what was checked.
        # Comments are left out, so nothing can hide in how a comment is read.
        return with_row_limit(statement).sql(dialect="postgres", comments=False)
    except RecursionError:
        # sqlglot reads and writes SQL recursively, so a query nested about a hundred
        # levels deep goes past Python's recursion limit. Nothing has run at that point.
        raise UnsafeSQL("the query is nested too deeply") from None
