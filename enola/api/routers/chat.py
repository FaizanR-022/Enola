from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from enola.agent.registry import registry
from enola.agent.service import MAIN_THREAD, AgentService, RunResult
from enola.agent.speech import spoken_text_for
from enola.api.deps import CurrentSession, DbSession
from enola.core.enums import ChatSource, Risk

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageRead(BaseModel):
    role: str
    text: str
    tool_name: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class RunRead(BaseModel):
    run_id: str
    thread_id: str
    messages: list[ChatMessageRead]
    held_approval_id: int | None
    aborted: bool
    source: ChatSource
    spoken_text: str


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    thread_id: str = MAIN_THREAD
    scope: str = "everything"
    source: ChatSource = ChatSource.TEXT


class ToolInfo(BaseModel):
    name: str
    description: str
    risk: Risk
    gated: bool


def run_read(result: RunResult) -> RunRead:
    return RunRead(
        run_id=result.run_id,
        thread_id=result.thread_id,
        messages=[ChatMessageRead(role=m.role, text=m.text, tool_name=m.tool_name, tool_calls=m.tool_calls) for m in result.messages],
        held_approval_id=result.held_approval_id,
        aborted=result.aborted,
        source=result.source,
        spoken_text=spoken_text_for(result.messages, held=result.held_approval_id is not None, aborted=result.aborted),
    )


@router.post("", response_model=RunRead, operation_id="chat_send")
def send(body: ChatRequest, db: DbSession, _: CurrentSession) -> RunRead:
    return run_read(AgentService(db).run(text=body.text, thread_id=body.thread_id, scope=body.scope, source=body.source))


@router.get("/tools", response_model=list[ToolInfo], operation_id="chat_tools")
def tools(_: CurrentSession) -> list[ToolInfo]:
    return [ToolInfo(name=s.name, description=s.description, risk=s.risk, gated=s.gated) for s in registry.all()]


@router.get("/{thread_id}", response_model=list[ChatMessageRead], operation_id="chat_history")
def history(thread_id: str, db: DbSession, _: CurrentSession) -> list[ChatMessageRead]:
    return [ChatMessageRead(role=m.role, text=m.text, tool_name=m.tool_name, tool_calls=m.tool_calls) for m in AgentService(db).history(thread_id)]


@router.delete("/{thread_id}", status_code=204, operation_id="chat_clear")
def clear(thread_id: str, db: DbSession, _: CurrentSession) -> Response:
    """Forget a conversation. Refused while a Held action is parked on it."""
    AgentService(db).clear(thread_id)
    return Response(status_code=204)
