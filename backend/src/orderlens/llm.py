"""The only module that knows the LLM provider: it creates the Groq chat model and calls it."""

import logging
from typing import Any

from groq import APIError, BadRequestError, RateLimitError
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from pydantic import BaseModel

from orderlens.config import settings

logger = logging.getLogger(__name__)

# gpt-oss reasons before it answers, and those reasoning tokens count against the free
# tier's 8,000 tokens a minute. "low" keeps that cost down.
REASONING_EFFORT = "low"

# Groq's error codes for malformed structured output. These get exactly one retry.
RETRYABLE_ERROR_CODES = {"tool_use_failed", "json_validate_failed"}


class LLMRateLimited(Exception):
    """Groq refused the call because a rate limit (per minute or per day) was reached."""


class LLMError(Exception):
    """The LLM call failed for any other reason."""


def chat_model() -> ChatGroq:
    """The configured Groq model at temperature 0."""
    # max_retries=0 turns off the Groq client's own retries, which would otherwise
    # retry rate-limit (429) errors; the only retry is the one in invoke_with_retry.
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


def invoke_with_retry(model: Runnable, messages: list) -> Any:
    """Call the model, retrying once on malformed output; turn Groq errors into ours."""
    for attempt in (1, 2):
        try:
            return model.invoke(messages)
        except RateLimitError as error:
            raise LLMRateLimited(str(error)) from error
        except BadRequestError as error:
            if attempt == 2 or groq_error_code(error) not in RETRYABLE_ERROR_CODES:
                raise LLMError(str(error)) from error
            logger.warning("retrying once after Groq error %s", groq_error_code(error))
        except APIError as error:
            raise LLMError(str(error)) from error


def log_usage(label: str, reply: AIMessage) -> None:
    """Log how many tokens one call used, to plan around Groq's rate limits."""
    usage = reply.usage_metadata or {}
    logger.info(
        "%s call: %s input + %s output = %s tokens",
        label,
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    )


def invoke_structured[OutputT: BaseModel](output_type: type[OutputT], messages: list) -> OutputT:
    """Ask the model for an instance of output_type (Groq strict structured output)."""
    # include_raw keeps the raw reply so its token usage can be logged.
    model = chat_model().with_structured_output(
        output_type, method="json_schema", strict=True, include_raw=True
    )
    result = invoke_with_retry(model, messages)
    log_usage(output_type.__name__, result["raw"])
    if result["parsing_error"] is not None:
        raise LLMError(f"could not read the model's reply: {result['parsing_error']}")
    return result["parsed"]


def invoke_text(label: str, messages: list) -> str:
    """Ask the model for plain text."""
    reply = invoke_with_retry(chat_model(), messages)
    log_usage(label, reply)
    return reply.content
