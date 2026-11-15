"""API tests with ask() replaced by a stub: no LLM and no database."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from orderlens import api
from orderlens.ratelimit import RateLimiter

client = TestClient(api.app)

AUDIT = {
    "path": "metric",
    "metric_id": "merchandise_revenue",
    "metric_name": "Merchandise revenue",
    "definition": "Total item price of valid orders placed in the date range.",
    "parameters": {"start_date": "2018-01-01", "end_date": "2018-12-31"},
    "notes": ["Item prices only; freight excluded"],
    "sql": "SELECT ...",
    "check": "Verified metric template",
    "attempts": 1,
    "row_count": 1,
    "duration_ms": 120,
    "model": "openai/gpt-oss-120b",
}
ANSWERED = {
    "status": "answered",
    "answer": "Merchandise revenue, 2018-01-01 – 2018-12-31: R$ 7,341,182.41",
    "headline": "R$ 7,341,182.41",
    "columns": ["revenue", "orders"],
    "rows": [[Decimal("7341182.41"), 53531]],
    "audit": AUDIT,
    "options": [],
    "failure": None,
}
CLARIFY = {
    "status": "clarify",
    "answer": "Do you mean: Top categories by revenue, or Top categories by units sold?",
    "headline": None,
    "columns": [],
    "rows": [],
    "audit": None,
    "options": [
        {"metric_id": "top_categories_by_revenue", "name": "Top categories by revenue",
         "definition": "Product categories ranked by merchandise revenue."},
        {"metric_id": "top_categories_by_units", "name": "Top categories by units sold",
         "definition": "Product categories ranked by number of units sold."},
    ],
    "failure": None,
}  # fmt: skip


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test its own rate limiter with the default limits."""
    monkeypatch.setattr(api, "limiter", RateLimiter(per_minute=10, per_day=300))


def stub_ask(monkeypatch: pytest.MonkeyPatch, result: dict) -> None:
    """Make /ask return this result instead of running the graph."""
    monkeypatch.setattr(api, "ask", lambda question, metric_id=None: result)


def test_health_reports_ok() -> None:
    response = client.get("/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_catalog_lists_the_ten_metrics() -> None:
    metrics = client.get("/catalog").json()
    assert len(metrics) == 10
    assert metrics[0]["args"] == ["category", "end_date", "start_date", "state"]


def test_a_normal_answer_returns_numbers_and_the_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_ask(monkeypatch, ANSWERED)
    body = client.post("/ask", json={"question": "What was our revenue in 2018?"}).json()
    assert body["rows"] == [[7341182.41, 53531]]
    assert body["audit"]["check"] == "Verified metric template"


def test_the_failure_details_are_not_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_ask(monkeypatch, ANSWERED)
    body = client.post("/ask", json={"question": "What was our revenue in 2018?"}).json()
    assert "failure" not in body


def test_a_clarify_response_lists_the_options(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_ask(monkeypatch, CLARIFY)
    body = client.post("/ask", json={"question": "Which category performs best?"}).json()
    assert body["status"] == "clarify"
    assert [option["metric_id"] for option in body["options"]] == [
        "top_categories_by_revenue",
        "top_categories_by_units",
    ]


def test_an_over_long_question_is_rejected() -> None:
    response = client.post("/ask", json={"question": "x" * 301})
    assert response.status_code == 422


def test_an_empty_question_is_rejected() -> None:
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_the_eleventh_request_in_a_minute_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_ask(monkeypatch, ANSWERED)
    codes = [
        client.post("/ask", json={"question": "Revenue in 2018?"}).status_code for _ in range(11)
    ]
    assert codes == [200] * 10 + [429]


def test_cors_allows_the_local_frontend() -> None:
    response = client.options(
        "/ask",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_blocks_other_origins() -> None:
    response = client.options(
        "/ask",
        headers={"Origin": "https://example.com", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
