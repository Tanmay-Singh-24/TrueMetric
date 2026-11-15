# OrderLens — Study notes

## Phase 0 — Scaffold

**What was built:**
- A git repository, and a `backend/` Python package named `orderlens` (managed with `uv`,
  `src/` layout, pinned to Python 3.12).
- `config.py`: one frozen `Settings` dataclass filled from environment variables, plus
  `.env.example` listing every variable.
- A FastAPI app with only `GET /health`, one test for it, `ruff` and `pytest` configured.

**Why it is built this way:**
- `src/` layout: tests import the installed package, not files that happen to sit next to
  them, so a missing file fails in tests instead of only in production.
- Settings are read from real environment variables only. Render sets them in production;
  locally `uv run --env-file .env ...` loads `.env` into the environment. No extra
  library is needed, and LangSmith (which reads its variables straight from the
  environment) sees the same values as the app.
- One `settings` object in `config.py` is the only place that touches `os.environ`, so
  every setting the app uses is listed in one file.
- Dependencies are added in the phase that first needs them, so each commit shows why a
  package arrived.

**What went wrong:**
- `readme = "../README.md"` in `pyproject.toml` broke the package build: the build only
  sees files inside `backend/`. Removed the line; the README lives at the repository root.

**Likely interview questions:**
- *Why a dataclass and not pydantic-settings?* Eight values read from the environment
  need no library. A frozen dataclass makes the settings read-only after start-up.
- *Why is `/health` there?* Render's free tier sleeps when idle; the frontend calls
  `/health` first to wake the server and show a "waking up" message until it answers.
- *Why `uv`?* It resolves and locks dependencies quickly and writes `uv.lock`, so the
  Docker image installs exactly the versions tested locally.
