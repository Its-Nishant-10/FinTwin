"""Thin wrapper around the Anthropic client — OWNER: Member 4.

One place decides whether the LLM is in play, which model and effort it runs
at, and how API failures surface. Callers get either a response or
LLMUnavailable; they never see SDK exceptions, so every caller can fall back
to its deterministic path with one `except`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

# Server-side refusal fallback: if a safety classifier declines, the API
# re-runs the request on Anthropic's recommended fallback model in the same
# call. Supported on the Claude Opus 5 / Fable 5 families.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5")


class LLMUnavailable(Exception):
    """The LLM could not produce a usable answer; use the deterministic path."""


def available() -> bool:
    settings = get_settings()
    return settings.agent_use_llm and bool(settings.anthropic_api_key)


@lru_cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key, timeout=60.0)


def create(*, output_format: dict[str, Any] | None = None, **kwargs: Any):
    """messages.create with FinTwin's defaults. Raises LLMUnavailable on any failure."""
    if not available():
        raise LLMUnavailable("no API key configured")

    settings = get_settings()
    output_config: dict[str, Any] = {"effort": settings.llm_effort}
    if output_format is not None:
        output_config["format"] = output_format

    extra: dict[str, Any] = {}
    if settings.llm_model.startswith(_FALLBACK_MODELS):
        extra = {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

    kwargs.setdefault("max_tokens", settings.llm_max_tokens)
    try:
        response = _client().beta.messages.create(
            model=settings.llm_model,
            output_config=output_config,
            **extra,
            **kwargs,
        )
    except anthropic.AuthenticationError as exc:
        log.error("Anthropic API key rejected: %s", exc)
        raise LLMUnavailable("API key rejected") from exc
    except anthropic.RateLimitError as exc:
        log.warning("Anthropic rate limit hit: %s", exc)
        raise LLMUnavailable("rate limited") from exc
    except anthropic.APIStatusError as exc:
        log.error("Anthropic API error %s: %s", exc.status_code, exc)
        raise LLMUnavailable(f"API error {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:
        log.warning("Could not reach the Anthropic API: %s", exc)
        raise LLMUnavailable("could not reach the API") from exc

    if response.stop_reason == "refusal":
        raise LLMUnavailable("the model declined the request")
    if response.stop_reason == "max_tokens":
        raise LLMUnavailable("the response was cut off")
    return response


def text_of(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text").strip()
