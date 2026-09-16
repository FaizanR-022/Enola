"""The agent state machine.

    START → agent → gate → gate → … → agent → … → END

`agent` asks the model. If it wants tools, `gate` handles them one call per step,
consulting the registry before executing anything. A gated call writes an
approval_request row with state Held and then calls `interrupt()`; the run resumes
from the Postgres checkpoint when the owner decides. Rejection ends the run.

Handling one tool call per `gate` step matters: LangGraph re-runs a node from its
start after an interrupt, so a node that executed several calls before pausing
would execute the earlier ones twice on resume.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from sqlalchemy import select

from enola.agent.context import ToolContext, tool_context
from enola.agent.memory.profile import active_facts
from enola.agent.prompts import build_system_prompt
from enola.agent.registry import ToolRegistry, ToolSpec
from enola.core.config import get_settings
from enola.core.db import get_sessionmaker
from enola.core.enums import ActivityKind, ApprovalState, Risk
from enola.core.errors import RegistryError
from enola.core.logging import get_logger
from enola.core.models.infra import ApprovalRequest
from enola.core.services.activity import record_activity

log = get_logger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    run_id: str
    thread_id: str
    scope: str
    # Set when the owner rejects a Held call; the run ends without going back to the model.
    aborted: bool


class Decision(TypedDict, total=False):
    decision: Literal["approved", "rejected"]
    args: dict[str, Any]
    note: str


def _pending_tool_call(messages: list[AnyMessage]) -> dict[str, Any] | None:
    """The first tool call in the last AI message that has no ToolMessage yet."""
    last_ai: AIMessage | None = None
    answered: set[str] = set()
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            answered.add(str(message.tool_call_id))
        elif isinstance(message, AIMessage):
            last_ai = message
            break
    if last_ai is None:
        return None
    for call in last_ai.tool_calls:
        if call["id"] not in answered:
            return dict(call)
    return None


def _preview(spec: ToolSpec, args: dict[str, Any]) -> str:
    if spec.name == "send_email":
        return f"to: {args.get('to', '')}\nsubject: {args.get('subject', '')}\n\n{args.get('body', '')}"
    return json.dumps(args, indent=2, ensure_ascii=False, default=str)


def _rationale(message: AIMessage) -> str:
    text = message.content if isinstance(message.content, str) else " ".join(
        part.get("text", "") for part in message.content if isinstance(part, dict)
    )
    return text.strip()


def build_graph(
    *,
    model: BaseChatModel,
    registry: ToolRegistry,
    checkpointer: BaseCheckpointSaver[Any],
    database_url: str | None = None,
) -> CompiledStateGraph[AgentState, Any, Any, Any]:
    settings = get_settings()
    sessions = get_sessionmaker(database_url)
    bound = model.bind_tools(registry.langchain_tools())

    def agent(state: AgentState) -> dict[str, Any]:
        with sessions() as db:
            facts = active_facts(db)
        system = build_system_prompt(
            owner_name=settings.owner_name,
            timezone=settings.timezone,
            facts=list(facts),
            scope=state["scope"],
            today=datetime.now(UTC).strftime("%A %d %B %Y"),
        )
        response = bound.invoke([SystemMessage(content=system), *state["messages"]])
        return {"messages": [response]}

    def gate(state: AgentState) -> dict[str, Any]:
        call = _pending_tool_call(state["messages"])
        if call is None:
            return {}
        name, call_id, raw_args = str(call["name"]), str(call["id"]), dict(call["args"])
        run_id, thread_id = state["run_id"], state["thread_id"]
        last_ai = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))

        try:
            spec = registry.get(name)
        except RegistryError as exc:
            with sessions() as db:
                record_activity(db, kind=ActivityKind.TOOL_CALL, summary=f"Refused unknown tool {name}", run_id=run_id, thread_id=thread_id, tool_name=name)
                db.commit()
            return {"messages": [ToolMessage(content=f"Refused: {exc.message}", tool_call_id=call_id)]}

        args = raw_args
        if spec.gated:
            # Get-or-create is what makes this safe to re-run after the interrupt.
            with sessions() as db:
                row = db.scalar(select(ApprovalRequest).where(ApprovalRequest.thread_id == thread_id, ApprovalRequest.tool_call_id == call_id))
                if row is None:
                    row = ApprovalRequest(
                        thread_id=thread_id,
                        run_id=run_id,
                        tool_call_id=call_id,
                        tool_name=name,
                        args=raw_args,
                        rationale=_rationale(last_ai),
                        risk=spec.risk,
                        state=ApprovalState.HELD,
                        payload_preview=_preview(spec, raw_args),
                        job_label=f"chat · {spec.kind_label}",
                        step_labels=["read context", "draft", "your approval", "act + log"],
                        step_index=2,
                    )
                    db.add(row)
                    record_activity(db, kind=ActivityKind.HELD, summary=f"Held: {spec.kind_label} — waiting on you", run_id=run_id, thread_id=thread_id, tool_name=name, risk=spec.risk)
                    db.commit()
                    log.info("tool_held", tool=name, run_id=run_id, thread_id=thread_id, risk=spec.risk.value)
                approval_id = row.id
            decision: Decision = interrupt(
                {"approval_id": approval_id, "tool": name, "risk": spec.risk.value, "args": raw_args, "rationale": _rationale(last_ai)}
            )
            note = str(decision.get("note", ""))
            if decision.get("decision") != "approved":
                with sessions() as db:
                    record_activity(db, kind=ActivityKind.REJECTED, summary=f"Rejected: {spec.kind_label}" + (f" — {note}" if note else ""), run_id=run_id, thread_id=thread_id, tool_name=name, risk=spec.risk)
                    db.commit()
                log.info("tool_rejected", tool=name, run_id=run_id)
                return {
                    "messages": [ToolMessage(content=f"The owner rejected this action." + (f" Reason: {note}" if note else ""), tool_call_id=call_id)],
                    "aborted": True,
                }
            args = dict(decision.get("args") or raw_args)

        try:
            valid = spec.validate_args(args)
        except Exception as exc:  # pydantic validation
            return {"messages": [ToolMessage(content=f"Invalid arguments for {name}: {exc}", tool_call_id=call_id)]}

        with sessions() as db:
            ctx = ToolContext(db=db, run_id=run_id, thread_id=thread_id, scope=state["scope"])
            try:
                with tool_context(ctx):
                    result = spec.fn(**valid)
            except Exception as exc:
                db.rollback()
                log.warning("tool_failed", tool=name, run_id=run_id, error=str(exc))
                return {"messages": [ToolMessage(content=f"{name} failed: {exc}", tool_call_id=call_id)]}
            if spec.gated:
                record_activity(db, kind=ActivityKind.APPROVED, summary=f"Approved and done: {spec.kind_label} — {str(result)[:160]}", run_id=run_id, thread_id=thread_id, tool_name=name, risk=spec.risk, detail={"args": valid})
            elif spec.risk == Risk.WRITE_LOCAL:
                record_activity(db, kind=ActivityKind.TOOL_CALL, summary=str(result)[:200], run_id=run_id, thread_id=thread_id, tool_name=name, risk=spec.risk, detail={"args": valid})
            db.commit()
        log.info("tool_done", tool=name, run_id=run_id, risk=spec.risk.value)
        return {"messages": [ToolMessage(content=str(result), tool_call_id=call_id)]}

    def after_agent(state: AgentState) -> str:
        return "gate" if _pending_tool_call(state["messages"]) else END

    def after_gate(state: AgentState) -> str:
        if state.get("aborted"):
            return END
        return "gate" if _pending_tool_call(state["messages"]) else "agent"

    graph: StateGraph[AgentState, Any, Any, Any] = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("gate", gate)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", after_agent)
    graph.add_conditional_edges("gate", after_gate)
    return graph.compile(checkpointer=checkpointer)
