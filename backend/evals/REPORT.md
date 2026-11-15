# OrderLens — Evaluation report

Run on 2026-11-15 with `openai/gpt-oss-120b` on Groq (reasoning effort "low",
temperature 0), one run per configuration. Every number below comes from
`evals/results/*.json` in this repository, printed by
`uv run python -m evals.run_eval --report`.

## The question

On the same questions, how much more often is the full system (router, verified metrics,
free-form fallback) right than free-form SQL alone?

## Method

- **Questions** (`questions.yaml`): 36 in four categories: 20 `metric` (two per metric,
  with different filters and business wording), 8 `freeform` (no metric covers them; f01–f03
  tempt a join of `order_items` and `order_payments`), 4 `ambiguous` (should get a
  clarifying question) and 4 `refuse` (a delete, an update, an off-topic question and a
  prompt injection). They and their gold SQL were committed (`c3f805c`) before either
  configuration was run. No question or gold query was changed afterwards.
- **Gold SQL** is written independently of the metric templates (subqueries, `IN`,
  per-order totals). `--check-gold` ran all 28 gold queries: every one runs, passes the
  validator, and the 13 that have a reference value agree with `reference_values.json`.
  As an extra check, the other 7 metric gold queries agree with the metric templates run
  with the same filters, and the three trap questions give a different answer if items
  and payments are joined (f02: R$ 2,391,104.87 correct, R$ 6,744,803.54 with the join).
- **Configurations**: `baseline` is `mode="freeform_only"`: every question goes straight to
  the SQL generator, whose prompt holds the schema and all the business definitions and
  synonyms. `full` is the router, the metric layer and the same free-form fallback.
  Summaries were off in both (they are not scored).
- **Scoring** (`scoring.py`) compares results, not SQL: same number of rows, and every
  gold row matches a different result row on all gold values (numbers within 0.01, text
  ignoring case, timestamps by day; extra columns allowed). `ambiguous` and `refuse`
  questions pass on status alone (`clarify`, `refused`).
- **Head to head** counts only `metric` and `freeform` questions: the baseline has no
  router, so it cannot produce `clarify`, and refusals are reported separately.

## Results

| Category | baseline | full |
|---|---|---|
| metric | 19/20 (95%) | 20/20 (100%) |
| freeform | 7/8 (88%) | 7/8 (88%) |
| **head to head (metric + freeform)** | 26/28 (93%) | 27/28 (96%) |
| ambiguous (reported separately) | 0/4 (0%) | 3/4 (75%) |
| refuse (reported separately) | 4/4 (100%) | 4/4 (100%) |

**The full system was right on one more question than the baseline: 27 of 28 against
26 of 28.** That is a smaller difference than the project set out to show, and with one
run per configuration, one question is within run-to-run variation.

> **Note added after the run.** On accuracy the head-to-head is effectively a tie. The one
> gap (m08) came from a prompt difference: the router's prompt listed the category names
> and the free-form prompt did not. Because the full system's own free-form fallback had
> the same gap, the category names were added to the free-form prompt after this run, as
> a product fix. The numbers above are as measured, before that fix; the next run will
> measure its effect.

### Where the difference came from

- **m08** ("monthly revenue from watches and gifts, first half of 2018") is the only
  question one configuration passed and the other failed. The baseline guessed the
  category names, `p.category IN ('watches', 'gifts')`, and got no rows. The router's
  prompt lists the 74 category names, so it chose `monthly_revenue` with
  `category = watches_gifts`. The win came from the router knowing the category names, not
  from the baseline writing worse SQL. The free-form prompt does not list them; adding
  that list would be a general change, not made here because it would be a prompt change
  made after seeing an eval failure (left for review).
- **The row-multiplication trap did not catch the baseline.** On f01–f03 it never joined
  items and payments; the glossary line "never join order_items and order_payments" was
  enough for this model. The failure the metric layer was designed to prevent did not
  happen in this run.
- **The free-form category** goes through the same generator in both configurations, so
  any difference there is run-to-run noise. Here both failed the same question (f03) in
  the same way.

## Router choices on metric questions (full)

| id | expected metric | chosen | passed |
|---|---|---|---|
| m01 | merchandise_revenue | merchandise_revenue | True |
| m02 | merchandise_revenue | freeform | True |
| m03 | order_count | order_count | True |
| m04 | order_count | order_count | True |
| m05 | average_order_value | average_order_value | True |
| m06 | average_order_value | average_order_value | True |
| m07 | monthly_revenue | monthly_revenue | True |
| m08 | monthly_revenue | monthly_revenue | True |
| m09 | top_categories_by_revenue | top_categories_by_revenue | True |
| m10 | top_categories_by_revenue | top_categories_by_revenue | True |
| m11 | top_categories_by_units | top_categories_by_units | True |
| m12 | top_categories_by_units | top_categories_by_units | True |
| m13 | revenue_by_state | revenue_by_state | True |
| m14 | revenue_by_state | revenue_by_state | True |
| m15 | repeat_customer_rate | repeat_customer_rate | True |
| m16 | repeat_customer_rate | repeat_customer_rate | True |
| m17 | late_delivery_rate | late_delivery_rate | True |
| m18 | late_delivery_rate | late_delivery_rate | True |
| m19 | average_review_score | average_review_score | True |
| m20 | average_review_score | average_review_score | True |

19 of 20 took the expected metric. On **m02** ("revenue from São Paulo customers in
2018") the router chose `revenue_by_state` with `state = SP`; that metric has no state
filter, so `check_decision` sent the question to free-form instead of answering for all
states (LangSmith trace: "sent to freeform: revenue_by_state does not accept: state").
The free-form SQL was correct. This is the "fall back rather than guess" rule working.

## Every failure

| config | id | category | reason | what happened |
|---|---|---|---|---|
| baseline | m08 | metric | wrong_result | Guessed category names `'watches', 'gifts'`; the real name is `watches_gifts`; 0 rows |
| baseline | f03 | freeform | wrong_result | Treated "delivered" as "has a delivery date", which also counts 6 canceled orders: 164.16 instead of 164.18 |
| baseline | a01–a04 | ambiguous | wrong_route | The baseline cannot ask for clarification; it answered each with one interpretation |
| full | f03 | freeform | wrong_result | The same generator, the same mistake as the baseline: 164.16 instead of 164.18 |
| full | a03 | ambiguous | wrong_route | "How much business did we do in 2017?" was answered as merchandise revenue instead of asking revenue or order count |

f03 is not ambiguous: the gold value (status `delivered`) equals what the metrics' own
late-delivery rule gives (status `delivered` and a delivery date), so the question and its
gold query were kept.

No question failed with `validation_failed` or `execution_error` in either run.

## Refuse questions

- **Full**: all four refused by the router; no SQL was generated or run.
- **Baseline**: all four refused by the generator (`cannot_answer`, which goes to the
  refuse node); no SQL was generated, so nothing reached the validator or the database.
- **Nothing was written**: after both runs, the row counts of all seven tables are the
  Phase 1 values (orders 99,441; order_items 112,650; order_payments 103,886;
  order_reviews 99,224; customers 99,441; products 32,951; sellers 3,095), and the status
  counts are unchanged (canceled 625, delivered 96,478). The order r02 asked to update
  was already `delivered`, so its status alone proves nothing; the read-only role (which
  has only `SELECT`) is what makes a write impossible.

## Validator

- **One normal function was blocked.** In the first run, the baseline's first attempt on
  m17, m18 and a04 used `DATE(x)`, which was not on the allowlist. All three recovered on
  the retry, so no question was lost, but each cost about 2,000 extra tokens. `DATE(x)` is
  the function form of `CAST(x AS DATE)` with no side effects, so it was added to the
  allowlist, and both configurations were re-run on m17, m18 and a04. The pass/fail
  results did not change; baseline m17 and m18 now pass on the first attempt.
- **The other retries were the model's own errors**, which Postgres also rejects:
  baseline m05 wrote `GROUP BY 1` on an aggregate; the re-run of baseline a04 referred to
  `rs.avg_review_score` from the wrong subquery.

## Tokens and time

Final results (after the `DATE` re-run). Time is time spent answering, without the pauses
the runner adds to stay under the token limit.

| config | questions | total tokens | tokens per question | total seconds | seconds per question |
|---|---|---|---|---|---|
| baseline | 36 | 70,604 | 1,961 | 69.0 | 1.9 |
| full | 36 | 74,601 | 2,072 | 79.4 | 2.2 |

First run, before `DATE` was allowed (`*.first_run.json`): baseline 74,997 tokens and
70.1 s; full 74,603 tokens and 79.5 s. Wall-clock time with pacing: baseline 12 min 46 s,
full 12 min 40 s.

The two cost about the same: a metric question costs the full system one router call
(about 1,600 tokens) where the baseline makes one generator call (about 1,800), but a
free-form question costs the full system a router call plus a generator call (about 3,400).

## Changes made during this phase

- **Prompt (before any run):** the free-form glossary now includes each metric's synonyms
  (for example "sales" for merchandise revenue), because the router already knew them and
  the baseline should know the same business vocabulary.
- **Prompt (after the runs):** none.
- **Allowlist (after the first run):** `DATE`, with the reason above; affected questions
  re-run in both configurations.
- **Questions and gold SQL:** none changed.

## What this evaluation does and does not show

- On the metric path the SQL is fixed, so that path can only fail by choosing the wrong
  metric or the wrong arguments; the free-form path can also fail by writing wrong SQL.
  That difference is the project's claim. In this run the full system made no metric-path
  mistakes (20/20 on metric questions), but the baseline failed only one of the same
  questions, and that failure was a guessed category name rather than wrong SQL logic.
- "Correct" means "matches the definitions in METRICS.md". The definitions are choices
  (for example, revenue excludes freight), and both configurations were given them.
- The difference is small and is reported as it came out. The question set was not
  changed to widen it.
- The baseline has no clarify step, so `ambiguous` questions are reported separately and
  left out of the head-to-head number; `refuse` questions are also reported separately.
- One run per configuration: the model's output varies between runs, so a difference of
  one question is within noise. Running each question several times would measure that.
- 36 questions written by the person who built the metrics may be phrased in ways the
  router handles well.

## Raw results

- `results/baseline.json`, `results/full.json`: final results, one record per question
  (route, chosen metric, SQL, error, first rows, tokens, seconds).
- `results/baseline.first_run.json`, `results/full.first_run.json`: the first run, before
  `DATE` was added to the allowlist.
