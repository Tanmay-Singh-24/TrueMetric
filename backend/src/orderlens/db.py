"""The only module that opens database connections. Always the read-only role."""

from functools import cache
from typing import Any

from psycopg_pool import ConnectionPool

from orderlens.config import settings


@cache
def get_pool() -> ConnectionPool:
    """Open the connection pool on DATABASE_URL the first time it is needed."""
    # Neon suspends an idle database and drops its connections, so each connection is
    # checked before it is handed out instead of failing on the first query after a pause.
    return ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=4,
        check=ConnectionPool.check_connection,
        open=True,
    )


def run_query(sql: str, params: dict[str, Any] | None = None) -> tuple[list[str], list[list]]:
    """Run one query and return its column names and rows."""
    with get_pool().connection() as conn:
        cursor = conn.execute(sql, params)
        columns = [column.name for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
    return columns, rows
