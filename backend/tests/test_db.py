import time

import psycopg.errors
import pytest

from truemetric.db import run_query
from truemetric.lookups import known_categories, known_states

pytestmark = pytest.mark.db


def test_select_returns_columns_and_rows() -> None:
    columns, rows = run_query("SELECT COUNT(*) AS orders FROM orders")
    assert (columns, rows) == (["orders"], [[99441]])


def test_read_only_role_cannot_delete() -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        run_query("DELETE FROM orders")


def test_statement_timeout_cancels_long_queries() -> None:
    started = time.monotonic()
    with pytest.raises(psycopg.errors.QueryCanceled):
        run_query("SELECT pg_sleep(7)")
    assert time.monotonic() - started < 6.5


def test_known_states_has_27_codes() -> None:
    assert len(known_states()) == 27


def test_known_categories_has_74_names() -> None:
    assert len(known_categories()) == 74
