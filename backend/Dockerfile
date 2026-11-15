FROM python:3.12-slim

# uv installs exactly the versions in uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so this layer is cached until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# The app, and sql/schema.sql, which the prompts and the validator read.
COPY src ./src
COPY sql ./sql
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Render sets $PORT; 8000 is the local default.
CMD ["sh", "-c", "uvicorn orderlens.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
