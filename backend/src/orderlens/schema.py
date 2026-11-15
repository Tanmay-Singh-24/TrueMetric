"""The database schema, read from sql/schema.sql: raw text for prompts, parsed for checks."""

from pathlib import Path

import sqlglot
from sqlglot import exp

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

# Shown to the LLM word for word, comments included: they explain the data traps.
SCHEMA_SQL = SCHEMA_PATH.read_text()


def parse_tables(schema_sql: str) -> dict[str, dict[str, str]]:
    """Map each CREATE TABLE in the text to its columns and their SQL types."""
    tables = {}
    for statement in sqlglot.parse(schema_sql, read="postgres"):
        table_name = statement.find(exp.Table).name
        tables[table_name] = {
            column.name: column.args["kind"].sql(dialect="postgres").lower()
            for column in statement.find_all(exp.ColumnDef)
        }
    return tables


TABLE_COLUMNS = parse_tables(SCHEMA_SQL)
