"""Which model serves which job, and a record of every call.

Two roles, each its own environment variable, both falling back to one default.
A dict and a lookup: not a routing framework. Every call writes an
`activity_log` row of kind MODEL_CALL carrying the model id and the token usage,
including cache reads, so spend is visible rather than assumed.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.runnables import Runnable
from sqlalchemy.orm import Session

from enola.agent.prompts.system import CACHEABLE
from enola.core.config import Settings, get_settings
from enola.core.enums import ActivityKind
from enola.core.errors import AgentUnavailableError
from enola.core.logging import get_logger
from enola.core.services.activity import record_activity

log = get_logger(__name__)

CACHE_CONTROL: dict[str, str] = {"type": "ephemeral"}

KEY_VARIABLE = {"anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY"}


# What each role runs on when nothing is configured. Free-tier Gemini: flash for the
# chat loop (best tool calling), flash-lite for high-volume utility work.
PROVIDER_DEFAULTS: dict[str, dict[ModelRole, str]] = {}


def _api_key(settings: Settings) -> str:
    return settings.anthropic_api_key if settings.model_provider == "anthropic" else settings.google_api_key


def no_key_message(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return f"{KEY_VARIABLE[settings.model_provider]} is not set, so Enola cannot think yet."


class ModelRole(StrEnum):
    AGENT = "agent"  # the chat loop: tools, judgement, the owner's voice
    UTILITY = "utility"  # brief prose, classification, scoring, summaries


PROVIDER_DEFAULTS.update(
    {
        # flash-lite for both roles. Measured on the free tier: gemini-3.5-flash allows
        # 5 requests a minute, and one chat turn spends two to four of them on tool
        # calls — so the agent loop was rate-limited almost immediately. flash-lite ran
        # 14 requests in 11 seconds without complaint and calls tools correctly.
        # If the agent loop ever needs more reasoning, raise this one alone.
        "google": {ModelRole.AGENT: "gemini-3.5-flash-lite", ModelRole.UTILITY: "gemini-3.5-flash-lite"},
        "anthropic": {ModelRole.AGENT: "claude-haiku-4-5", ModelRole.UTILITY: "claude-haiku-4-5"},
    }
)


def model_id_for(role: ModelRole, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    configured = {ModelRole.AGENT: settings.agent_model, ModelRole.UTILITY: settings.utility_model}
    return configured[role] or settings.default_model or PROVIDER_DEFAULTS[settings.model_provider][role]


def model_available(settings: Settings | None = None) -> bool:
    return bool(_api_key(settings or get_settings()))


def make_chat_model(role: ModelRole, settings: Settings | None = None, *, model_name: str | None = None) -> BaseChatModel:
    settings = settings or get_settings()
    if not _api_key(settings):
        raise AgentUnavailableError(no_key_message(settings))
    model = model_name or model_id_for(role, settings)
    if settings.model_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # 429s are routine on the free tier's 10 RPM: retry with backoff before giving up.
        # Thinking stays on for the chat loop; utility work is prose and classification,
        # where it only costs tokens and latency.
        thinking: dict[str, Any] = {"thinking_level": "minimal"} if role is ModelRole.UTILITY else {}
        # Two retries, not five. The free tier's per-minute quota is small, and the
        # client retries a 429 the same way it retries a transient 503 — so a generous
        # retry count spends six requests of quota failing to make one call, which makes
        # the exhaustion worse. Fail quickly and let the caller try again.
        return ChatGoogleGenerativeAI(
            model=model, google_api_key=settings.google_api_key, max_output_tokens=4096, timeout=120, max_retries=2, **thinking
        )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, api_key=settings.anthropic_api_key, max_tokens=4096, timeout=120)


def _is_rate_limit(exc: Exception) -> bool:
    """A 429 or a 503 "high demand": both clear up on their own, so both read as "try again"."""
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = f"{type(exc).__name__} {exc}"
    markers = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "RateLimit", "ResourceExhausted", "Overloaded")
    return status in (429, 503) or any(m in text for m in markers)


def _text_of(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    return " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict)).strip()


def invoke_checked(model: Runnable[Any, Any], messages: Sequence[BaseMessage]) -> AIMessage:
    """Call the model; turn a rate limit or an empty reply into AgentUnavailableError.

    An empty reply (a safety block, say) must never look like a finished turn, and a
    429 that outlasted the client's retries should read as advice, not a stack trace."""
    try:
        response = model.invoke(list(messages))
    except Exception as exc:
        if _is_rate_limit(exc):
            log.warning("model_rate_limited", error=str(exc)[:200])
            raise AgentUnavailableError("The model is rate limited or busy right now. Try again in a moment.") from exc
        raise
    if not isinstance(response, AIMessage):
        raise AgentUnavailableError("The model returned an unexpected reply.")
    if not response.tool_calls and not _text_of(response):
        reason = (response.response_metadata or {}).get("finish_reason") or "unknown"
        log.warning("model_empty_response", finish_reason=str(reason))
        raise AgentUnavailableError(f"The model returned no answer (finish reason: {reason}). Try rephrasing.")
    return response


def system_message(blocks: Sequence[dict[str, Any]], settings: Settings | None = None) -> SystemMessage:
    """Render neutral system blocks for the selected provider.

    Anthropic takes a list of content blocks and a cache breakpoint on the stable
    prefix. Gemini takes a plain string, and caches implicitly."""
    settings = settings or get_settings()
    if settings.model_provider == "google":
        return SystemMessage(content="\n\n".join(str(b["text"]) for b in blocks))
    content: list[str | dict[Any, Any]] = []
    for block in blocks:
        rendered = {k: v for k, v in block.items() if k != CACHEABLE}
        if block.get(CACHEABLE):
            rendered["cache_control"] = dict(CACHE_CONTROL)
        content.append(rendered)
    return SystemMessage(content=content)


def usage_of(message: AIMessage) -> dict[str, int]:
    """Token usage from a response, cache reads included. Zeros when absent."""
    usage: Any = message.usage_metadata or {}
    details: Any = usage.get("input_token_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "cache_read": int(details.get("cache_read") or 0),
        "cache_creation": int(details.get("cache_creation") or 0),
    }


def record_model_call(
    db: Session,
    *,
    role: ModelRole,
    model_id: str,
    message: AIMessage,
    run_id: str | None,
    thread_id: str | None,
    purpose: str,
) -> None:
    usage = usage_of(message)
    response_model = str((message.response_metadata or {}).get("model") or (message.response_metadata or {}).get("model_name") or model_id)
    record_activity(
        db,
        kind=ActivityKind.MODEL_CALL,
        summary=f"{role.value} · {response_model} · in {usage['input_tokens']} (cache read {usage['cache_read']}) · out {usage['output_tokens']}",
        run_id=run_id,
        thread_id=thread_id,
        tool_name=purpose,
        detail={"role": role.value, "model": response_model, **usage},
    )
    log.info("model_call", role=role.value, model=response_model, purpose=purpose, **usage)
