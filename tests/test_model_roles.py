"""Phase 1 (iteration 1): model roles resolve independently, the cache prefix is
stable and marked, and every call lands in activity_log with its model and usage."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.agent.models import ModelRole, model_id_for, usage_of
from enola.agent.prompts.system import STABLE, build_system_blocks, stable_block
from enola.agent.registry import ToolRegistry
from enola.agent.service import AgentService
from enola.agent.tools import probes
from enola.agent.utility import utility_complete
from enola.core.config import get_settings
from enola.core.enums import ActivityKind, Risk
from enola.core.models import ActivityLog
from tests.agent_helpers import ScriptedModel, ai_tool_call
from tests.conftest import TEST_URL


def test_roles_resolve_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "default_model", "claude-haiku-4-5")
    monkeypatch.setattr(settings, "agent_model", None)
    monkeypatch.setattr(settings, "utility_model", None)
    assert model_id_for(ModelRole.AGENT, settings) == "claude-haiku-4-5"
    assert model_id_for(ModelRole.UTILITY, settings) == "claude-haiku-4-5"
    # Raising the chat loop alone leaves utility work where it was.
    monkeypatch.setattr(settings, "agent_model", "claude-sonnet-5")
    assert model_id_for(ModelRole.AGENT, settings) == "claude-sonnet-5"
    assert model_id_for(ModelRole.UTILITY, settings) == "claude-haiku-4-5"


def test_stable_prefix_has_no_volatile_content() -> None:
    blocks = build_system_blocks(owner_name="Faizan", timezone="Asia/Karachi", facts=["Prefers async teams"], scope="course:42", today="Thursday 17 September 2026")
    assert blocks[0]["cacheable"] is True
    assert "cache_control" not in blocks[0]
    assert blocks[0]["text"] == STABLE
    assert "cache_control" not in blocks[1]
    for volatile in ("Faizan", "Asia/Karachi", "Prefers async teams", "17 September", "course:42"):
        assert volatile not in blocks[0]["text"]
        assert volatile in blocks[1]["text"]
    assert stable_block() == blocks[0]
    # Haiku 4.5 needs a 4096-token prefix to cache at all; tools add ~1.5K, so the
    # stable text must carry the rest. Roughly 3.4 chars per token.
    assert len(STABLE) > 3.4 * 3000


def test_agent_call_is_logged_with_model_and_cache_usage(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "anthropic")  # the cache_control shape is Anthropic's
    monkeypatch.setattr(settings, "agent_model", "claude-sonnet-5")
    reply = AIMessage(
        content="pong",
        usage_metadata={"input_tokens": 5200, "output_tokens": 40, "total_tokens": 5240, "input_token_details": {"cache_read": 4900, "cache_creation": 0}},
        response_metadata={"model": "claude-sonnet-5"},
    )
    model = ScriptedModel(script=[ai_tool_call("echo_probe", {"text": "ping"}, "c1"), reply])
    reg = ToolRegistry()
    reg.tool(risk=Risk.SAFE)(probes.echo_probe)
    AgentService(db, model=model, registry=reg, database_url=TEST_URL).run(text="echo ping", thread_id="t-usage")

    # The system message reached the model as blocks, stable one first with the marker.
    system = model.received[0][0]
    assert isinstance(system, SystemMessage) and isinstance(system.content, list)
    assert system.content[0]["cache_control"] == {"type": "ephemeral"}
    assert system.content[0]["text"] == STABLE

    calls = db.scalars(select(ActivityLog).where(ActivityLog.kind == ActivityKind.MODEL_CALL).order_by(ActivityLog.id)).all()
    assert len(calls) == 2
    assert all(c.detail["role"] == "agent" for c in calls)
    assert calls[1].detail["model"] == "claude-sonnet-5"
    assert calls[1].detail["cache_read"] == 4900 and calls[1].detail["input_tokens"] == 5200
    assert "cache read 4900" in calls[1].summary


def test_utility_call_uses_its_own_role(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "anthropic")  # the cache_control shape is Anthropic's
    monkeypatch.setattr(settings, "agent_model", "claude-sonnet-5")
    monkeypatch.setattr(settings, "utility_model", None)
    monkeypatch.setattr(settings, "default_model", "claude-haiku-4-5")
    model = ScriptedModel(script=[AIMessage(content="Three things need you today.")])
    text = utility_complete(db, instructions="Summarise in one line.", text="held: 1, due: 2", purpose="brief", model=model)
    assert text == "Three things need you today."
    system = model.received[0][0]
    assert isinstance(system, SystemMessage) and system.content[0]["cache_control"] == {"type": "ephemeral"}
    row = db.scalar(select(ActivityLog).where(ActivityLog.kind == ActivityKind.MODEL_CALL))
    assert row is not None and row.detail["role"] == "utility" and row.detail["model"] == "claude-haiku-4-5"


def test_usage_of_handles_missing_metadata() -> None:
    assert usage_of(AIMessage(content="x")) == {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_creation": 0}


def test_provider_defaults_and_system_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    from enola.agent.models import system_message

    settings = get_settings()
    for name in ("default_model", "agent_model", "utility_model"):
        monkeypatch.setattr(settings, name, None)
    blocks = build_system_blocks(owner_name="F", timezone="Asia/Karachi", facts=[], scope="everything", today="Thu")

    monkeypatch.setattr(settings, "model_provider", "google")
    # Both roles run on flash-lite. gemini-3.5-flash allows 5 requests a minute on the
    # free tier and one chat turn spends several, so the agent loop was unusable there.
    assert model_id_for(ModelRole.AGENT, settings) == "gemini-3.5-flash-lite"
    assert model_id_for(ModelRole.UTILITY, settings) == "gemini-3.5-flash-lite"
    rendered = system_message(blocks, settings)
    assert isinstance(rendered.content, str) and rendered.content.startswith(STABLE) and "cache_control" not in rendered.content

    monkeypatch.setattr(settings, "model_provider", "anthropic")
    assert model_id_for(ModelRole.AGENT, settings) == "claude-haiku-4-5"
    rendered = system_message(blocks, settings)
    assert isinstance(rendered.content, list) and rendered.content[0]["cache_control"] == {"type": "ephemeral"}
    assert "cacheable" not in rendered.content[0] and "cache_control" not in rendered.content[1]


def test_every_tool_converts_for_gemini() -> None:
    """Gemini is stricter about tool schemas; a tool that fails to convert would break the gate."""
    from langchain_google_genai._function_utils import convert_to_genai_function_declarations

    import enola.agent.tools  # noqa: F401
    from enola.agent.registry import registry

    tools = registry.langchain_tools()
    declared = convert_to_genai_function_declarations(tools)
    assert sum(len(t.function_declarations or []) for t in declared) == len(tools)


def test_empty_and_rate_limited_replies_fail_gracefully() -> None:
    from enola.agent.models import invoke_checked
    from enola.core.errors import AgentUnavailableError

    empty = ScriptedModel(script=[AIMessage(content="", response_metadata={"finish_reason": "SAFETY"})])
    with pytest.raises(AgentUnavailableError, match="SAFETY"):
        invoke_checked(empty, [])

    class Limited(ScriptedModel):
        def _generate(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    with pytest.raises(AgentUnavailableError, match="rate limited or busy"):
        invoke_checked(Limited(script=[]), [])


def test_prompt_contains_no_liftable_example_data() -> None:
    """Regression: the prompt's examples used the seed data's own names, and a weak model
    reported them as the owner's records — naming a course and a quiz that did not exist
    in an empty database. Examples must be placeholders nothing can be lifted from.
    """
    import re

    from enola.agent.prompts.system import STABLE

    # Course-code shapes, and the seed's proper nouns.
    assert not re.search(r"\b[A-Z]{2,3}\d{3,4}\b", STABLE), "a course-code-shaped string is liftable as a real course"
    for name in ("Hamza", "Usman", "Ayesha", "Bilal", "Kestrel", "Turing", "Areeba", "Naveed", "Milestone 2", "Quiz 2"):
        assert name not in STABLE, f"{name!r} in the prompt reads as one of the owner's records"
    # And the rule that makes the placeholders mean something.
    assert "Nothing\nin them is a record." in STABLE or "Nothing in them is a record." in STABLE.replace("\n", " ")
