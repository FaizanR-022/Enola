"""Run and resume agent threads. This is the only place that invokes the graph."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import enola.agent.tools  # noqa: F401  (registers the application tools)
from enola.agent.checkpoint import open_checkpointer
from enola.agent.graph import build_graph
from enola.agent.models import (
    ModelRole,
    make_chat_model,
    model_available,
    model_id_for,
    no_key_message,
)
from enola.agent.registry import ToolRegistry
from enola.agent.registry import registry as app_registry
from enola.core.enums import ApprovalState, ChatSource
from enola.core.errors import AgentUnavailableError, ConflictError, InvalidInputError, NotFoundError
from enola.core.logging import bind_context, get_logger
from enola.core.models.infra import ApprovalRequest

log = get_logger(__name__)

MAIN_THREAD = "main"


@dataclass
class ChatMessage:
    role: str  # "you" | "enola" | "tool"
    text: str
    tool_name: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RunResult:
    run_id: str
    thread_id: str
    messages: list[ChatMessage]
    held_approval_id: int | None
    aborted: bool
    source: ChatSource = ChatSource.TEXT


def make_model(model_name: str | None = None) -> BaseChatModel:
    """The chat loop's model. Kept as a module function so tests can monkeypatch it."""
    return make_chat_model(ModelRole.AGENT, model_name=model_name)


class UnavailableModel(BaseChatModel):
    """Stands in when there is no API key so an approved Held action can still finish
    its run: the tool executes, then this closes the turn with an honest note instead
    of leaving the checkpoint dangling. New conversations are refused up front."""

    @property
    def _llm_type(self) -> str:
        return "unavailable"

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> Any:
        from langchain_core.outputs import ChatGeneration, ChatResult

        text = f"Done. I carried out the approved action, but I cannot write a reply: {no_key_message()}"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self


def to_chat_messages(messages: list[AnyMessage]) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append(ChatMessage(role="you", text=str(m.content)))
        elif isinstance(m, AIMessage):
            text = m.content if isinstance(m.content, str) else " ".join(p.get("text", "") for p in m.content if isinstance(p, dict))
            out.append(ChatMessage(role="enola", text=text.strip(), tool_calls=[{"name": c["name"], "args": c["args"]} for c in m.tool_calls]))
        elif isinstance(m, ToolMessage):
            out.append(ChatMessage(role="tool", text=str(m.content), tool_name=m.name))
    return out


class AgentService:
    """Synchronous on purpose: a run returns when it finishes or when it is Held."""

    def __init__(self, db: Session, *, model: BaseChatModel | None = None, registry: ToolRegistry | None = None, database_url: str | None = None) -> None:
        self.db = db
        self._model = model
        self.registry = registry or app_registry
        # The graph opens its own sessions and checkpointer connection; they must hit
        # the same database as the session we were handed, never a configured default.
        bind = db.get_bind()
        engine = bind if isinstance(bind, Engine) else bind.engine
        self.database_url = database_url or engine.url.render_as_string(hide_password=False)

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            self._model = make_model() if model_available() else UnavailableModel()
        return self._model

    def run(self, *, text: str, thread_id: str = MAIN_THREAD, scope: str = "everything", source: ChatSource = ChatSource.TEXT) -> RunResult:
        if self._model is None and not model_available():
            raise AgentUnavailableError(no_key_message())
        pending = self.db.scalar(
            select(ApprovalRequest.id).where(ApprovalRequest.thread_id == thread_id, ApprovalRequest.state == ApprovalState.HELD)
        )
        if pending is not None:
            # The rest of the job stays parked. Nothing runs on this thread while a Held
            # action sits there, and a new turn must not silently supersede its checkpoint.
            raise ConflictError("Something is Held on this thread. Decide it in Approvals first.", details={"approval_id": pending})
        run_id = uuid.uuid4().hex[:12]
        with bind_context(run_id=run_id, thread_id=thread_id):
            log.info("run_start", scope=scope, source=str(source))
            result = self._invoke(
                {"messages": [HumanMessage(content=text)], "run_id": run_id, "thread_id": thread_id, "scope": scope, "aborted": False},
                thread_id=thread_id,
                run_id=run_id,
            )
            result.source = source
            return result

    def decide(self, approval_id: int, *, approve: bool, args: dict[str, Any] | None = None, note: str = "") -> RunResult:
        """Resolve a Held request and resume its run from the checkpoint."""
        row = self.db.get(ApprovalRequest, approval_id)
        if row is None:
            raise NotFoundError(f"Approval {approval_id} not found")
        if row.state != ApprovalState.HELD:
            raise InvalidInputError(f"Approval {approval_id} is already {row.state.value}.")
        row.state = ApprovalState.APPROVED if approve else ApprovalState.REJECTED
        row.resolved_at = datetime.now(UTC)
        row.resolution_note = note
        if approve and args is not None:
            row.args = args
        self.db.commit()
        decision = {"decision": "approved" if approve else "rejected", "args": row.args, "note": note}
        with bind_context(run_id=row.run_id, thread_id=row.thread_id):
            log.info("run_resume", approval_id=approval_id, decision=decision["decision"])
            return self._invoke(Command(resume=decision), thread_id=row.thread_id, run_id=row.run_id)

    def history(self, thread_id: str = MAIN_THREAD) -> list[ChatMessage]:
        with open_checkpointer(self.database_url) as saver:
            graph = build_graph(model=_NullModel(), registry=self.registry, checkpointer=saver, database_url=self.database_url)
            snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        messages = snapshot.values.get("messages", []) if snapshot.values else []
        return to_chat_messages(list(messages))

    def _invoke(self, payload: Any, *, thread_id: str, run_id: str) -> RunResult:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        with open_checkpointer(self.database_url) as saver:
            graph = build_graph(model=self.model, registry=self.registry, checkpointer=saver, database_url=self.database_url, model_id=model_id_for(ModelRole.AGENT))
            result = graph.invoke(payload, config=config)
            snapshot = graph.get_state(config)
        held_id: int | None = None
        for intr in result.get("__interrupt__", []):
            value = intr.value if isinstance(intr.value, dict) else {}
            raw_id = value.get("approval_id")
            held_id = int(raw_id) if raw_id is not None else None
        if held_id is not None:
            checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
            row = self.db.get(ApprovalRequest, held_id)
            if row is not None and checkpoint_id:
                row.checkpoint_id = str(checkpoint_id)
                self.db.commit()
            log.info("run_held", approval_id=held_id, checkpoint_id=checkpoint_id)
        else:
            log.info("run_end", aborted=bool(result.get("aborted")))
        return RunResult(
            run_id=run_id,
            thread_id=thread_id,
            messages=to_chat_messages(list(result.get("messages", []))),
            held_approval_id=held_id,
            aborted=bool(result.get("aborted")),
        )


class _NullModel(BaseChatModel):
    """Used only to build a graph for reading state; it never generates."""

    @property
    def _llm_type(self) -> str:
        return "null"

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> Any:
        raise RuntimeError("_NullModel cannot generate")

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self
