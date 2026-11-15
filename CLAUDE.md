# TrueMetric — rules for the builder

You are implementing a project that has already been designed. The design is in:

1. `docs/ARCHITECTURE.md` — what to build and why
2. `docs/METRICS.md` — the ten metric definitions, their SQL and reference values
3. `docs/BUILD_PLAN.md` — the order to build in, with checks for each phase

Read all three before writing any code.

## Who this is for

Tanmay will present this project in placement interviews and must be able to explain
every file. That is the test for every choice you make: **could he explain this line to
an interviewer in one sentence?** If not, write it more plainly. Simple and obvious beats
clever, short or "production-grade".

## How to work

- Build one phase at a time, in order. Do not start the next phase until told to.
- A phase is done when every check in BUILD_PLAN.md has been run and passes. Show the
  real output. Never say a check passed without running it.
- At the end of each phase:
  1. commit;
  2. add a section to `docs/STUDY_NOTES.md` (format below);
  3. report what was built, the check results, and anything that differed from the docs;
  4. stop and wait for review.
- **The docs are the specification.** If something in them is wrong, unclear or
  impossible, stop and ask. Do not improvise around it and do not quietly change the
  design. Small implementation details the docs leave open are yours to decide; note
  each one in the phase report.
- Never change a metric definition, a reference value, or the eval questions to make a
  check pass. A mismatch is a finding: report it.
- Do not build anything listed as out of scope, and do not add a dependency that is not
  in the stack table, without asking.

## Code rules

- **Small modules, one job each.** Follow the layout in ARCHITECTURE.md section 5.
- **Plain functions.** Classes only for data (`dataclass`, Pydantic models, `TypedDict`).
  No inheritance, no metaclasses, no custom decorators, no dependency-injection
  frameworks, no plugin or registry patterns beyond the metric tuple.
- **No `async`.** FastAPI endpoints are plain `def`.
- **No speculative generality.** No provider abstraction, no config options nobody
  asked for, no helper used only once that hides three clear lines.
- Functions stay short (about 40 lines at most) and do one thing.
- Type hints on every function signature.
- One docstring line per public function saying what it does. Comments explain *why*,
  never *what*. No commented-out code, no TODOs left behind.
- Names are full words: `start_date`, not `sd`.
- Prompts live as module-level constants next to the function that uses them.
- All settings come from `config.py`. No `os.environ` anywhere else.
- Only `db.py` opens database connections. Only `llm.py` creates the chat model. Only
  `graph.py` imports LangGraph.
- SQL on the metric path is never built from strings. Values are always bound
  parameters.
- Errors: a few specific exceptions (`InvalidArgs`, `UnsafeSQL`). No bare `except`. Catch
  an exception only where something useful is done with it.
- Logging uses the standard library. No `print` outside `scripts/`.
- Frontend: function components, `useState`/`useEffect` only, no state library, no UI
  kit, one CSS file.
- `ruff check` and `ruff format` clean before every commit.

## Tests

- `pytest`. Tests that need the database are marked `db`; tests that need the LLM are
  not written as unit tests at all — LLM behaviour is measured by the eval.
- Test behaviour, not implementation. One clear assertion per idea.
- Do not write tests that only restate the code.

## Git

- One commit per phase at minimum, more if a phase has natural steps.
- Plain messages in the imperative: "Add metric registry and ten metric queries".
- **No `Co-Authored-By` trailer and no "Generated with" line.** Tanmay is the sole
  author.
- Never commit `.env`, the CSV files, or any credential. Check `git status` before each
  commit.

## Secrets and safety

- The app uses only the read-only database URL. The owner URL is used by
  `scripts/setup_db.py` and nothing else.
- No secret is ever logged, returned by the API, or placed in frontend code.
- Do not create accounts, enter credentials, or deploy on your own. Prepare the steps
  and walk Tanmay through them.

## Honest reporting

- Every number in the README and the eval report comes from a run in this repository.
  No estimated, rounded-up or expected figures.
- If the eval shows the metric layer helps less than hoped, the report says so.

## `docs/STUDY_NOTES.md`

One section per phase, written for Tanmay to revise from. Keep each to about ten bullets:

```markdown
## Phase N — <name>

**What was built:** two or three bullets.

**Why it is built this way:** the decisions made in this phase, each with its reason.

**What went wrong:** real bugs or surprises hit during the phase and how they were fixed.
Leave this out if nothing did; never invent one.

**Likely interview questions:** three or four, each with a two-sentence answer.
```
