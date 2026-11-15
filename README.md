# TrueMetric

TrueMetric answers plain-English questions about e-commerce order data (the public Olist
dataset). A question is first matched against a small catalogue of hand-verified metrics;
when one fits, the app runs that metric's fixed SQL with bound parameters, so the language
model never writes the SQL. Only when no metric fits does the model write its own query,
and that query must pass a validator and run under a read-only, time-limited database
role. Every answer carries an audit trail built by code, and an eval measures how often
the full system is right compared with free-form text-to-SQL alone.

The free-form path's shape (generate → validate → execute → retry) and the
result-comparison eval method follow the approach of
[TourQuery](https://github.com/DefKd911/TourQuery). No code is taken from it.
