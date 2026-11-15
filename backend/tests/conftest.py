import pytest

from truemetric.config import settings

NO_DATABASE_REASON = "DATABASE_URL is empty; run `uv run --env-file .env pytest` to include it"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked db when there is no database to connect to."""
    # Without this, an empty DATABASE_URL makes the pool wait for a connection, so
    # plain `pytest` would hang instead of reporting anything.
    if settings.database_url:
        return
    skip_database = pytest.mark.skip(reason=NO_DATABASE_REASON)
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip_database)
