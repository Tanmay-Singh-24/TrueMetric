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

## Phase 1 — Data

**What was built:**
- `sql/schema.sql` (the seven tables, with the comments the LLM will read) and
  `sql/indexes.sql`; `scripts/download_data.py` fetches the eight CSVs.
- `scripts/setup_db.py`: drops and recreates the tables, loads the CSVs with `COPY`,
  creates indexes and the `orderlens_readonly` role, then prints the facts to check.
- `db.py` (`run_query()` over a small read-only pool), `schema.py` (parses `schema.sql`
  into `{table: {column: type}}`), `lookups.py` (`known_states()`, `known_categories()`).

**Why it is built this way:**
- Python's `csv` module picks columns, turns empty strings into NULL and resolves the
  category; `COPY` then streams the rows in. `COPY` is far faster than 300k `INSERT`s.
- The whole setup is one transaction: if anything fails, the old data stays, so the
  script is always safe to rerun.
- The read-only role gets `SELECT` on the seven tables and nothing else, plus
  `statement_timeout = 5s` set on the role itself, so no client can forget to set it.
- `schema.py` parses `schema.sql` with sqlglot instead of asking the database what
  tables exist, so the database, the prompt and the validator share one source.
- The pool checks each connection before use, because Neon suspends an idle database and
  closes its connections.
- Lookups are read once and cached with `functools.cache`: states and categories never
  change while the app runs.

**What went wrong:**
- The download failed with `CERTIFICATE_VERIFY_FAILED`: the python.org build of Python
  has no CA certificates until its "Install Certificates" step is run. Rebuilt the local
  virtualenv on Homebrew's Python 3.12 instead of turning off verification.
- Two Portuguese categories (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`)
  have no English translation. As designed, they keep their Portuguese name; that is why
  there are 74 categories (71 English, 2 Portuguese, `unknown`).

**Likely interview questions:**
- *What stops the app from deleting data?* The app only holds the read-only role, which
  has `SELECT` and nothing else. The test suite checks that `DELETE FROM orders` fails
  with "permission denied".
- *What stops a runaway query?* `statement_timeout = 5s` on the role. A test runs
  `pg_sleep(7)` and checks it is cancelled after about five seconds.
- *Why is `customer_unique_id` a trap?* `customer_id` is new for every order, so there
  are 99,441 of them but only 96,096 real people. Counting customers by `customer_id`
  overcounts, and the repeat rate comes out as zero.
- *Why not load with pandas?* The standard `csv` module and `COPY` are enough for seven
  files, and pandas would be a large dependency used once.
