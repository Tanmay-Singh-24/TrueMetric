# TrueMetric — Study notes

## Phase 0 — Scaffold

**What was built:**
- A git repository, and a `backend/` Python package named `truemetric` (managed with `uv`,
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
  creates indexes and the `truemetric_readonly` role, then prints the facts to check.
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

## Phase 2 — Metric layer

**What was built:**
- `scripts/reference_values.py`: the ten metrics computed a second time in plain Python
  from the raw CSVs (no SQL, no database), written to `tests/reference_values.json`.
- Ten static `.sql` files copied from METRICS.md; `catalog.py` (a tuple of ten `Metric`
  dataclasses); `registry.py` (`get_metric`, `validate_args`, `run_metric`).
- `audit.py` (`build_audit`, `format_headline`) and `scripts/run_metric.py`.

**Why it is built this way:**
- Two independent implementations, Python and SQL, must agree. A bug would have to be
  made the same way twice to slip through. The Python version was written and checked
  against METRICS.md before any SQL existed.
- The SQL text never changes; only bound values do. Optional filters are written as
  `(%(state)s::text IS NULL OR ...)`, so there is no string building to inject into.
- `validate_args` treats `None` as "not given" (the router fills every field), rejects
  anything the metric cannot do exactly, and fills in the data window when dates are
  missing, so the audit trail always shows a concrete range.
- Money stays `Decimal` from the database to the comparison. The JSON stores values as
  exact strings, so the tests never compare floats.
- `Metric` lives in `catalog.py`, not `registry.py`: the registry imports the catalogue,
  so defining the dataclass there would make the two modules import each other.
- The headline number is formatted by code (`R$ 7,341,182.41`), never by the LLM.

**What went wrong:**
- Running the full test suite without `--env-file .env` leaves `DATABASE_URL` empty, and
  the database tests wait for a connection instead of failing. Run `pytest -m "not db"`
  when there is no database.

**Likely interview questions:**
- *How do you know the metric SQL is right?* The same definitions are computed in plain
  Python from the raw files, and a test compares every metric for all data, 2017 and
  2018 plus three filtered cases. All 33 cases match, row by row.
- *Why not let the LLM fill values into the SQL text?* The SQL is a fixed file and values
  are bound parameters, so the database never treats a value as SQL. That removes SQL
  injection on this path entirely.
- *What does `AVG(price)` get wrong for average order value?* It averages item prices,
  not orders. The metric divides revenue by the number of distinct orders, which gives
  137.42 for all data.
- *Why cast every placeholder (`%(state)s::text`)?* psycopg 3 sends values separately
  from the SQL, and a NULL with no cast has no type, so Postgres cannot plan
  `NULL IS NULL OR ...`.

## Phase 3 — Free-form path

**What was built:**
- `validator.py`: `validate_sql()` with the seven checks (one statement, SELECT only, no
  writes anywhere, known tables, allowlisted functions, known columns, row limit).
- `llm.py` (the only place that creates the Groq model, with one retry for malformed
  structured output) and `freeform.py` (prompt, `GeneratedSQL`, `generate_sql()`).
- `scripts/try_freeform.py`: generate → validate → execute with one retry, from the
  terminal.

**Why it is built this way:**
- Functions are checked against an allowlist of sqlglot node types. Anything sqlglot
  does not recognise (`pg_sleep`, `dblink`, `table_to_xml`) is an unknown function and is
  rejected without anyone having to think of it first.
- Columns are checked with sqlglot's `qualify` against the map parsed from `schema.sql`,
  so the validator and the database cannot disagree about what exists.
- The SQL that runs is regenerated from the checked parse tree: what runs is exactly
  what was checked. A database test confirms every metric gives the same rows after the
  round trip.
- Both attempts go through the same `validate_sql`; the retry only changes what the LLM
  is shown (the failed SQL and the error).
- Groq's strict structured output constrains the reply to the `GeneratedSQL` schema.
  `llm.py` turns off the Groq client's own retries so a 429 is never retried.
- The free-form prompt holds the schema text and the business definitions, taken from
  the catalogue so they cannot drift from the metrics. Nothing else yet.

**What went wrong:**
- `llama-3.3-70b-versatile`, the model in the design, was shut down by Groq on
  16 Aug 2026. Switched to `openai/gpt-oss-120b` with reasoning effort "low".
- The row-limit check turned `LIMIT 5::int` into `LIMIT 200`: a cast is not a plain
  number, and the first version replaced any limit it could not read. The database
  round-trip test caught it on the three top-N metrics. Fix: a limit that is not a plain
  number is kept, and the whole query is wrapped in `SELECT * FROM (...) LIMIT 200`, so a
  smaller limit is never raised.
- sqlglot models `AND`, `OR` and `CASE ... WHEN` branches as function nodes, and renames
  some functions (`date_trunc` → `TimestampTrunc`). Inspecting the parse trees first
  shaped the allowlist and the decision to skip `AND`/`OR`.

**Likely interview questions:**
- *Why an allowlist and not a blocklist?* A blocklist only stops the functions someone
  thought of; Postgres has thousands. With an allowlist, a new dangerous function is
  rejected by default.
- *If the validator has a bug, what still protects the data?* The app connects as a role
  with only `SELECT` on seven tables, and every statement is cancelled after five
  seconds. The validator is one of three independent layers.
- *How does the retry work?* If validation or execution fails, the LLM is called once
  more with the failed SQL and the error message. The new SQL goes through exactly the
  same checks; after a second failure the question fails.
- *How many tokens does a free-form call cost?* About 1,500–1,650 tokens, almost all of
  it the prompt (schema plus definitions, about 1,440 tokens). At 8,000 tokens a minute
  that is about five calls a minute.

## Phase 4 — Router and graph

**What was built:**
- `router.py`: `RouterDecision`, the router prompt, `route_question()`, `check_decision()`
  and `build_clarification()`. `summarize.py`: the summary call with a fixed fallback.
- `graph.py`: the nine LangGraph nodes, the edges of the flow diagram, and `ask()`, the
  one entry point. `scripts/ask.py` runs it from the terminal.
- `llm.py` now turns Groq errors into `LLMRateLimited` and `LLMError`, so no other module
  imports the provider.

**Why it is built this way:**
- The router must extract every filter the question mentions, even ones the chosen
  metric does not accept. Code then decides: "repeat rate in SP" carries `state=SP`,
  `validate_args` rejects it for `repeat_customer_rate`, and the question goes to
  free-form instead of being answered for all of Brazil.
- The clarifying question and its options are built by code from the catalogue, so the
  options are always real metrics. Picking one resends the question with `metric_id`,
  and code fixes the route to that metric: no conversation is stored.
- Nodes are thin and call plain functions, so the router checks, clarification and audit
  are tested with fake decisions and no LLM. Only `graph.py` imports LangGraph.
- LLM and connection errors are exceptions that end the run in `ask()`: a 429 gives the
  "daily limit" message, anything else a plain failure. Only bad SQL or a timeout gets
  the graph's one retry. A failed summary falls back to "Here are the results."
- The headline and the audit are built by code in `ask()` from the final state.

**What went wrong:**
- Mid-phase, the Mac's DNS stopped resolving the Neon host while public DNS still did.
  Database checks ran with `PGHOSTADDR` set to the public-DNS address for those commands
  only; nothing in the code or `.env` changed.
- The summary does not know which metric produced the rows. After the user chose "Top
  categories by units sold", it still named the revenue leader. Reported for review.

**Likely interview questions:**
- *What stops the router from answering a question it cannot answer exactly?*
  `check_decision`: an unknown metric, a filter the metric does not accept, or an invalid
  value sends the question to free-form. The rule is "fall back rather than guess".
- *How is ambiguity handled without a confidence score?* The router may return `clarify`
  with two or three candidate metrics; code checks they exist and writes the question
  from their names. A confidence score from an LLM is not calibrated; a list of
  candidates is observable and testable.
- *Why does a 429 not get retried?* The free tier's limit is per minute and per day, so
  retrying at once only wastes a request. The user gets a clear message instead.
- *What does one question cost in tokens?* About 1,800–2,000 on the metric path and
  about 3,400–3,500 on the free-form path, with the summary. The router prompt alone is
  about 1,450 input tokens.

## Phase 5 — Evaluation

**What was built:**
- `evals/questions.yaml`: 36 questions (20 metric, 8 free-form, 4 ambiguous, 4 refuse)
  with gold SQL, committed before either configuration ran.
- `evals/scoring.py` (compare result rows, not SQL), `evals/run_eval.py` (`--config`,
  `--ids`, `--resume`, `--check-gold`, `--report`), and `evals/REPORT.md`.

**Why it is built this way:**
- Scoring compares values, not column names: each gold value must appear in a different
  cell of a result row, numbers within 0.01, text ignoring case, timestamps by day. So
  `SUM(price) AS revenue_brl` and `AS revenue` both count as right.
- Gold SQL for metric questions is written differently from the templates and checked
  against the Python reference values, so a shared mistake would have to be made twice.
- The baseline gets the same definitions and synonyms as the router, so the comparison
  measures SQL, not knowledge of the definitions.
- The runner saves after every question, paces itself by the tokens each question used
  (6,000 a minute, under Groq's 8,000), and never scores rate-limit or outage failures.
- `ask()` returns a `failure` object (reason, error, last SQL) so the report can tell a
  validator rejection from a SQL error; the API leaves it out.

**What went wrong:**
- The result was much smaller than hoped: full 27/28, baseline 26/28 on the head-to-head
  questions. The one difference (m08) came from the router knowing the category names,
  not from the baseline writing worse SQL; the row-multiplication trap did not catch it.
- The validator rejected `DATE(x)`, a normal Postgres function, on three baseline first
  attempts. It was added to the allowlist and the affected questions were re-run in both
  configurations; the pass/fail results did not change.
- The results file kept only the final attempt, so the first-attempt errors were read
  from the LangSmith traces.

**Likely interview questions:**
- *Did the metric layer help?* In this run, by one question out of 28, within run-to-run
  variation. The model avoided the row-multiplication trap when the prompt warned it, so
  the honest claim is that the metric layer makes those mistakes impossible, not that the
  baseline made many of them.
- *Why compare results instead of SQL text?* Many different queries are correct. What
  matters is whether the numbers match the definition, so the eval runs both and compares
  rows, with a 0.01 tolerance for money and rates.
- *How did you keep the eval honest?* The questions and gold SQL were committed before
  any run; nothing was changed afterwards; the one allowlist change has a stated reason
  and was re-run on both sides; every number in the report comes from the results files.
- *What would you do next?* Run each question several times to measure variation, give
  the free-form prompt the category names, and add harder questions where definitions
  matter more (for example customers counted by person, not by order).

## Phase 6 — API

**What was built:**
- `api.py`: `GET /health`, `GET /catalog`, `POST /ask` with Pydantic request and response
  models, CORS limited to `CORS_ORIGINS`, and one JSON log line per request with the audit.
- `ratelimit.py`: 10 requests a minute per IP and 300 a day in total, in memory.
- `backend/Dockerfile` (`python:3.12-slim`, `uv sync --frozen --no-dev`, uvicorn on `$PORT`).

**Why it is built this way:**
- The request model caps the question at 300 characters, so FastAPI rejects longer ones
  with a 422 before any LLM call. Only `/ask` is rate-limited: it is the only endpoint
  that costs tokens, and the page calls `/health` while the server wakes up.
- The limiter is a dataclass of counters plus one plain function. Fixed windows (a new
  minute or a new UTC day resets the count) are simple to explain and test; a lock is
  needed because FastAPI runs plain `def` endpoints in a thread pool.
- The response model is the API contract: anything not in it (the internal `failure`
  details) is never sent. Decimals become JSON numbers for display.
- The Docker image copies `pyproject.toml` and `uv.lock` before the code, so dependencies
  stay cached between builds, and it installs exactly the locked versions.

**What went wrong:**
- Docker is not installed on the build machine, so the image was not built locally; the
  same checks ran against `uvicorn` directly. Render builds the image in Phase 8.

**Likely interview questions:**
- *What happens if someone sends 1,000 requests?* After 10 in a minute from one IP they
  get HTTP 429, and after 300 in a day from everyone together the demo stops answering.
  The counter is in memory and keyed by `X-Forwarded-For`, which a client can spoof;
  that is acceptable for a free demo and stated in the README.
- *Why plain `def` endpoints and not `async def`?* The work is a blocking database query
  and blocking LLM calls; FastAPI runs `def` endpoints in a thread pool, so the server
  still handles several requests at once without async code.
- *How does CORS protect the API?* The browser only lets pages from the listed origins
  read responses. It does not stop scripts or curl, which is why the rate limit and the
  read-only database role exist.

## Phase 7 — Frontend

**What was built:**
- A one-page Vite + React + TypeScript app in `frontend/`: `App.tsx` holds the state;
  `AskBox`, `ExampleQuestions`, `AnswerCard`, `ClarifyOptions`, `ResultTable` and
  `AuditPanel` each draw one part; `api.ts` makes the three calls; `types.ts` mirrors the
  API's response models; one `styles.css`, with light and dark colours.

**Why it is built this way:**
- Plain `useState` and one `useEffect`: the page has a handful of values (server ready,
  catalogue, question, result, error, loading), so a state library would add nothing.
- On load the page calls `/health` every 3 seconds until it answers, showing "Waking the
  server…", because Render's free tier sleeps when idle. Then it loads `/catalog` and
  turns each metric's example into a clickable chip.
- A clarify option resends the same question with that `metric_id`; the server stores no
  conversation, so the page only has to remember the last question.
- The audit panel shows what ran: the metric and its definition (or "Free-form query"),
  the date range and filters, the notes, which check was applied, the time taken, and the
  SQL in a collapsible block. The headline number comes from the server, formatted by code.
- `VITE_API_URL` is the only setting; there are no keys in the frontend.

**What went wrong:**
- The LLM summary used Markdown (`**bed_bath_table**`), which showed as raw asterisks.
  The summary prompt now asks for plain text.

**Likely interview questions:**
- *Why is there no conversation history in the page?* The design is stateless: each
  question is answered on its own, and a clarification resends the question with the
  chosen metric. Nothing has to be stored on the server.
- *How does the page handle the 429 rate limit?* `api.ts` turns an HTTP 429 into a
  friendly message asking the user to wait a moment; refusals and failures show the
  server's own answer with a hint to rephrase.
- *How is the result table kept usable on a phone?* The table sits in a container that
  scrolls sideways on its own, so the page itself never scrolls horizontally; at 375 px
  the page width equals the screen width.

## Phase 8 — CI and README (the parts that need no accounts)

**What was built:**
- `.github/workflows/ci.yml`: on every push, ruff and the tests that need no database for
  the backend, and `tsc` and the build for the frontend.
- The README: what the project is, the honest evaluation result, the row-multiplication
  example, the flow, the safety layers, the data decisions, how to run it, known limits.
- Before this phase: the free-form prompt got the category names (the eval's one gap),
  and the project was renamed from OrderLens to TrueMetric, including the database role.

**Why it is built this way:**
- CI installs exact versions from `uv.lock` and `package-lock.json` (`uv sync --frozen`,
  `npm ci`), so a passing build means the locked versions work.
- CI runs only the tests that need no database or LLM: it has no secrets, and LLM
  behaviour is measured by the eval, not by unit tests.
- The README leads with what the eval measured: accuracy tied with free-form SQL, and the
  real gains are clarification, code-built numbers, the audit trail and verified
  definitions. No accuracy improvement is claimed.
- Renaming a Postgres role keeps its grants, settings and SCRAM password, because those
  belong to the role's internal id, not its name.

**What went wrong:**
- After the role rename, `DATABASE_URL` in `.env` still named the old user. Tests and the
  screenshot ran with the username swapped in memory until the `.env` is updated.
- The first `git push` failed every time with a TLS "bad record mac" error, even for a
  single small commit, while ordinary requests to GitHub worked. The Mac was on a phone
  hotspot, which was corrupting the upload; the push went through from another network.
- Live checks on the deployed site passed: a metric answer, a clarify question and its
  option, a free-form answer, and a request from another origin blocked by CORS.

**Likely interview questions:**
- *So did the project work?* The safety and verification parts did: no wrong metric ran,
  ambiguity got a clarifying question, and every number is traceable. The accuracy gain I
  expected did not show up, because the model followed the prompt's warning about the
  join trap; I report that rather than tune the questions.
- *What does CI check, and what does it not?* Formatting, lint, the validator, scoring,
  router checks, API and rate-limit tests, and the frontend build. It does not touch the
  database or the LLM; those are covered by the database tests run locally and the eval.
- *How did you rename the database user without downtime?* `ALTER ROLE ... RENAME TO`
  keeps the password and permissions; only the connection string's username changes.

## Frontend redesign — pixel art and interaction

**What was built:**
- A dithered pixel-art hero (`art/skyline.ts`): the skyline is the real monthly revenue,
  Jan 2017 – Aug 2018, from `reference_values.json`. Bars rise on load, clouds drift,
  hovering shows the month's figure, clicking asks that month's revenue question.
- A halftone "How it works" (`art/halftone.ts`): dots morph from a fork (routing) to a
  database (verified code) to a magnifying glass (the audit) as the steps scroll past.
- An interactive join trap (toggle: payment blocks multiply, totals count from
  R$ 15.74M to R$ 20.16M), a ticker of real metric values, rolling-digit facts, a pixel
  loader and stepped reveals.

**Why it is built this way:**
- Ordered (Bayer) dithering compares each pixel's shade with a fixed 4×4 pattern, which
  turns gradients into the pixel texture of old printers. The scene is drawn at about a
  quarter of screen resolution into an `ImageData` buffer and scaled up with
  `image-rendering: pixelated`, so every art pixel is a crisp square and drawing stays cheap.
- Each halftone shape is a signed distance function (negative inside); a dot's size is how
  far inside the shape its centre is, and blending two shapes' sizes morphs one into the
  other. The morph is centred on each step boundary, so the picture is half-way through
  changing exactly when the heading switches.
- The art uses only real numbers: the skyline, the tooltip and the ticker match what the
  verified metrics return (clicking November 2017 answers R$ 1,003,862.14, the bar's value).
- Still React's rules: `useState` and `useEffect` only. Canvas elements are captured with
  `ref={setCanvas}` into state; drawing lives in plain functions that return a stop
  function, which the effect uses as its cleanup. Loops pause off-screen, colours come from
  CSS variables (so dark mode works), and reduced-motion users get still frames.

**What went wrong:**
- Hover used `event.offsetX`, which is unreliable when the page is scaled: the tooltip
  showed April 2017 over November's bar. Now the column is computed from `clientX` and the
  canvas's on-screen rectangle.
- The first morph finished each new shape before its step began, so the picture ran ahead of
  the heading. Centring the morph on the step boundary fixed it.

**Likely interview questions:**
- *Why draw at low resolution instead of full size?* A 1280-pixel-wide hero is drawn as 320
  art pixels, so each frame touches about 30,000 pixels instead of half a million, and the
  pixel look comes for free from scaling up without smoothing.
- *How do you keep the animation from wasting battery?* An IntersectionObserver pauses the
  loop when the canvas is off-screen, frames are capped at 30 a second, and users who ask
  for reduced motion get one still frame.
- *Is the decoration honest?* Yes: every number on the page, including the art, comes from
  the same reference values the tests check, and clicking a bar asks the real question.

## Landing page — clouds, theme switch, logo

**What was built:**
- `art/clouds.ts`: dithered clouds behind the headline that gather around the search bar,
  a sun by day or a crescent moon and twinkling stars by night, and a pointer "wind" that
  clears a gap in the clouds. Clicking the sun or moon switches the theme.
- A light/dark switch in the header (`ThemeToggle`, `theme.ts`). The new theme is revealed
  in a stepped circle growing from the switch, and the choice is remembered.
- A Space Grotesk wordmark with a pixel equaliser mark; headline words that drop in and hop
  on hover; a placeholder that types real example questions; chips that pop in.

**Why it is built this way:**
- The theme is one attribute, `<html data-theme>`. The CSS colours and all three canvases
  follow it, so nothing has to pass theme state around in React. A tiny script in
  `index.html` sets it before the first paint (saved choice, else the system setting),
  which avoids a flash of the wrong theme.
- The canvases read their colours from CSS variables and redraw when a MutationObserver
  sees `data-theme` change; that is how the sun becomes a moon.
- The reveal uses the browser's View Transitions API where it exists; elsewhere the theme
  simply switches. Reduced-motion visitors get no reveal and still skies.
- Cloud pixels are transparent where there is no cloud, so the page colour shows through
  and the sky works on both themes. The cloud density is weighted by distance to the search
  bar (measured from the page each frame), so the bar always sits in the clouds.

**What went wrong:**
- At 1200 px the sun sat on the end of the headline; it moved up and further right.
- On phones the taller header (with the switch) covered the pinned "How it works" bar;
  its sticky offset moved from 58 px to 70 px.

**Likely interview questions:**
- *How does the page avoid a flash of the wrong theme?* An inline script in the head sets
  `data-theme` before anything paints; React then reads the attribute instead of guessing.
- *How does the wind work?* Each frame, the cloud density near the pointer is reduced by a
  Gaussian bump; the bump's position eases towards the pointer, so the gap trails behind
  it like moving air.
