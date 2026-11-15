"""The HTTP API: /health, /catalog and /ask."""

import json
import logging
import time
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from orderlens.audit import Audit
from orderlens.config import settings
from orderlens.graph import ask
from orderlens.metrics.catalog import METRICS
from orderlens.ratelimit import RateLimiter, allow_request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="OrderLens")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_day)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    metric_id: str | None = None  # set when the user picks an option from a clarify question


class ClarifyOption(BaseModel):
    metric_id: str
    name: str
    definition: str


class AskResponse(BaseModel):
    status: Literal["answered", "clarify", "refused", "failed"]
    answer: str
    headline: str | None
    columns: list[str]
    rows: list[list[Any]]
    audit: Audit | None
    options: list[ClarifyOption]


class CatalogMetric(BaseModel):
    id: str
    name: str
    definition: str
    args: list[str]
    example: str


def client_ip(request: Request) -> str:
    """The caller's IP: the first address in X-Forwarded-For (set by Render's proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def json_value(value: object) -> object:
    """Numbers as JSON numbers and dates as ISO text, so the frontend can show them."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the server is up."""
    return {"status": "ok"}


@app.get("/catalog")
def catalog() -> list[CatalogMetric]:
    """The ten verified metrics, for the example questions on the page."""
    return [
        CatalogMetric(
            id=metric.id,
            name=metric.name,
            definition=metric.definition,
            args=sorted(metric.args),
            example=metric.example,
        )
        for metric in METRICS
    ]


@app.post("/ask")
def ask_question(body: AskRequest, request: Request) -> AskResponse:
    """Answer one question, within the rate limit."""
    if not allow_request(limiter, client_ip(request), time.time()):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute.")
    result = ask(body.question, metric_id=body.metric_id)
    # One JSON line per request, with the audit trail; `failure` stays in the logs only.
    log_line = {
        "question": body.question,
        "metric_id": body.metric_id,
        "status": result["status"],
        "audit": result["audit"],
        "failure": result["failure"],
    }
    logger.info(json.dumps(log_line, default=str, ensure_ascii=False))
    rows = [[json_value(value) for value in row] for row in result["rows"]]
    return AskResponse(
        status=result["status"],
        answer=result["answer"],
        headline=result["headline"],
        columns=result["columns"],
        rows=rows,
        audit=result["audit"],
        options=result["options"],
    )
