"""The agent loop's guard against repeating itself.

A weaker model will sometimes call the same read tool two or three times in one turn.
The owner sees Enola answering the same question over and over, which is the single
loudest way it stops feeling like an assistant.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from enola.agent.registry import ToolRegistry
from enola.agent.service import AgentService
from enola.core.enums import Risk
from tests.agent_helpers import ScriptedModel, ai_tool_call
from tests.conftest import TEST_URL

CALLS: list[str] = []


@pytest.fixture(autouse=True)
def clear_calls() -> None:
    CALLS.clear()


@pytest.fixture
def counting_registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.tool(risk=Risk.SAFE)
    def list_things(window: int = 7) -> str:
        """List things in a window."""
        CALLS.append(f"window={window}")
        return "thing one\nthing two"

    return reg


def service(db: Session, model: ScriptedModel, reg: ToolRegistry) -> AgentService:
    return AgentService(db, model=model, registry=reg, database_url=TEST_URL)


def test_an_identical_repeat_does_not_run_the_tool_again(db: Session, counting_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("list_things", {"window": 7}, "c1"),
        ai_tool_call("list_things", {"window": 7}, "c2"),  # the same question again
        AIMessage(content="Nothing's due today."),
    ])
    result = service(db, model, counting_registry).run(text="What's on today?", thread_id="loop-1")

    assert CALLS == ["window=7"], "the tool ran twice for one question"
    # The model still gets an answer back, so the turn completes rather than stalling.
    tool_texts = [m.text for m in result.messages if m.role == "tool"]
    assert len(tool_texts) == 2
    assert "already called" in tool_texts[1] and "do not call it again" in tool_texts[1]
    assert "thing one" in tool_texts[1], "the earlier result must be handed back, not withheld"
    assert result.messages[-1].text == "Nothing's due today."


def test_different_arguments_are_not_treated_as_a_repeat(db: Session, counting_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("list_things", {"window": 7}, "c1"),
        ai_tool_call("list_things", {"window": 30}, "c2"),  # a genuinely different question
        AIMessage(content="Two windows checked."),
    ])
    service(db, model, counting_registry).run(text="Check this week and this month.", thread_id="loop-2")
    assert CALLS == ["window=7", "window=30"]
