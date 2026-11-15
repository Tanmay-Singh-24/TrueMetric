"""The only module that knows the LLM provider: it creates the Groq chat model and calls it."""

import logging

from groq import BadRequestError
from langchain_groq import ChatGroq
from pydantic import BaseModel

from orderlens.config import settings

logger = logging.getLogger(__name__)

# gpt-oss reasons before it answers, and those reasoning tokens count against the free
# tier's 8,000 tokens a minute. "low" keeps that cost down.
REASONING_EFFORT = "low"

# Groq's error codes for malformed structured output. These get exactly one retry.
RETRYABLE_ERROR_CODES = {"tool_use_failed", "json_validate_failed"}


def chat_model() -> ChatGroq:
    """The configured Groq model at temperature 0."""
    # max_retries=0 turns off the Groq client's own retries, which would otherwise
    # retry rate-limit (429) errors; the only retry is the one in invoke_structured.
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
        reasoning_effort=REASONING_EFFORT,
        max_retries=0,
    )


def groq_error_code(error: BadRequestError) -> str | None:
    """The machine-readable code in Groq's error body, e.g. 'tool_use_failed'."""
    body = error.body if isinstance(error.body, dict) else {}
    return body.get("error", {}).get("code")


def invoke_structured[OutputT: BaseModel](output_type: type[OutputT], messages: list) -> OutputT:
    """Ask the model for an instance of output_type; retry once on malformed output."""
    # Strict json_schema: Groq constrains the output to the model's JSON schema.
    # include_raw keeps the raw reply so its token usage can be logged.
    model = chat_model().with_structured_output(
        output_type, method="json_schema", strict=True, include_raw=True
    )
    try:
        result = model.invoke(messages)
    except BadRequestError as error:
        if groq_error_code(error) not in RETRYABLE_ERROR_CODES:
            raise
        logger.warning("retrying once after Groq error %s", groq_error_code(error))
        result = model.invoke(messages)
    usage = result["raw"].usage_metadata or {}
    logger.info(
        "%s call: %s input + %s output = %s tokens",
        output_type.__name__,
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    )
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    return result["parsed"]
