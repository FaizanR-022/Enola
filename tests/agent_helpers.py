"""A scripted chat model so the gate can be tested without a network or a key.

It emits a fixed sequence of AI messages (tool calls included) and records how many
times it was asked, which is how the tests prove that a rejected run never goes
back to the model.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedModel(BaseChatModel):
    script: list[AIMessage]
    calls: int = 0
    received: list[list[Any]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        if self.calls >= len(self.script):
            raise AssertionError("ScriptedModel asked for more turns than scripted")
        message = self.script[self.calls]
        self.calls += 1
        self.received = [*self.received, list(messages)]
        return ChatResult(generations=[ChatGeneration(message=message)])


def ai_tool_call(name: str, args: dict[str, Any], call_id: str, text: str = "") -> AIMessage:
    return AIMessage(content=text, tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])
