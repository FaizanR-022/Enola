"""The four mandatory approval-gate tests. This is the Phase 2 gate.

They run the real graph against the real Postgres checkpointer with a scripted model,
so what is being tested is the mechanism, not a stub that returns success.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.agent.registry import ToolRegistry
from enola.agent.service import AgentService
from enola.agent.tools import probes
from enola.core.enums import ActivityKind, ApprovalState, Risk
from enola.core.errors import ConflictError
from enola.core.models import ActivityLog, ApprovalRequest
from tests.agent_helpers import ScriptedModel, ai_tool_call
from tests.conftest import TEST_URL


@pytest.fixture
def probe_registry() -> ToolRegistry:
    """A fresh registry holding the two probe tools, registered the same way as in production."""
    reg = ToolRegistry()
    reg.tool(risk=Risk.SAFE)(probes.echo_probe)
    reg.tool(risk=Risk.EXTERNAL, kind_label="probe · outbound")(probes.send_probe)
    return reg


@pytest.fixture(autouse=True)
def clear_sent() -> Iterator[None]:
    probes.SENT.clear()
    yield
    probes.SENT.clear()


def service(db: Session, model: ScriptedModel, registry: ToolRegistry) -> AgentService:
    return AgentService(db, model=model, registry=registry, database_url=TEST_URL)


def test_external_tool_halts(db: Session, probe_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("send_probe", {"to": "ayesha@kestrellabs.io", "message": "Following up on the take-home."}, "call_1", text="Nudging after 48h of silence, per your rule."),
        AIMessage(content="Sent."),
    ])
    result = service(db, model, probe_registry).run(text="Follow up with Ayesha.", thread_id="t-halt")

    assert result.held_approval_id is not None
    row = db.get(ApprovalRequest, result.held_approval_id)
    assert row is not None
    assert row.state == ApprovalState.HELD
    assert row.tool_name == "send_probe"
    assert row.risk == Risk.EXTERNAL
    assert row.args == {"to": "ayesha@kestrellabs.io", "message": "Following up on the take-home."}
    assert "48h" in row.rationale
    assert row.checkpoint_id, "the Held row must point at the checkpoint it will resume from"
    # The side effect did not happen, and the model was not asked again.
    assert probes.SENT == []
    assert model.calls == 1
    held_log = db.scalars(select(ActivityLog).where(ActivityLog.kind == ActivityKind.HELD)).all()
    assert len(held_log) == 1 and held_log[0].run_id == result.run_id


def test_resume_preserves_context(db: Session, probe_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("send_probe", {"to": "ayesha@kestrellabs.io", "message": "Following up."}, "call_1", text="Because of your 48h rule."),
        AIMessage(content="Done — sent and logged."),
    ])
    svc = service(db, model, probe_registry)
    first = svc.run(text="Follow up with Ayesha about the take-home.", thread_id="t-resume")
    assert first.held_approval_id is not None and probes.SENT == []

    resumed = svc.decide(first.held_approval_id, approve=True, note="ok")

    # The side effect happened exactly once, with the original arguments.
    assert probes.SENT == [{"to": "ayesha@kestrellabs.io", "message": "Following up."}]
    assert resumed.held_approval_id is None and resumed.aborted is False
    # The original conversation is intact: human turn, the tool call, its result, the final answer.
    history = svc.history("t-resume")
    assert [m.role for m in history] == ["you", "enola", "tool", "enola"]
    assert history[0].text == "Follow up with Ayesha about the take-home."
    assert history[1].tool_calls == [{"name": "send_probe", "args": {"to": "ayesha@kestrellabs.io", "message": "Following up."}}]
    assert history[2].text == "sent to ayesha@kestrellabs.io"
    assert history[3].text == "Done — sent and logged."
    assert model.calls == 2
    row = db.get(ApprovalRequest, first.held_approval_id)
    assert row is not None and row.state == ApprovalState.APPROVED and row.resolved_at is not None
    kinds = [a.kind for a in db.scalars(select(ActivityLog).where(ActivityLog.run_id == first.run_id).order_by(ActivityLog.id)).all() if a.kind != ActivityKind.MODEL_CALL]
    assert kinds == [ActivityKind.HELD, ActivityKind.APPROVED]


def test_resume_with_edited_args_uses_the_edit(db: Session, probe_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("send_probe", {"to": "ayesha@kestrellabs.io", "message": "Draft one."}, "call_1"),
        AIMessage(content="Sent the edited version."),
    ])
    svc = service(db, model, probe_registry)
    first = svc.run(text="Follow up.", thread_id="t-edit")
    assert first.held_approval_id is not None
    svc.decide(first.held_approval_id, approve=True, args={"to": "ayesha@kestrellabs.io", "message": "Draft two, shorter."})
    assert probes.SENT == [{"to": "ayesha@kestrellabs.io", "message": "Draft two, shorter."}]
    row = db.get(ApprovalRequest, first.held_approval_id)
    assert row is not None and row.args["message"] == "Draft two, shorter."


def test_reject_aborts_cleanly(db: Session, probe_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("send_probe", {"to": "ayesha@kestrellabs.io", "message": "Following up."}, "call_1"),
        AIMessage(content="This must never be produced: the run should end on rejection."),
    ])
    svc = service(db, model, probe_registry)
    first = svc.run(text="Follow up.", thread_id="t-reject")
    assert first.held_approval_id is not None

    result = svc.decide(first.held_approval_id, approve=False, note="Too soon; she said early next week.")

    assert probes.SENT == []
    assert result.aborted is True and result.held_approval_id is None
    assert model.calls == 1, "a rejected run must not go back to the model"
    row = db.get(ApprovalRequest, first.held_approval_id)
    assert row is not None
    assert row.state == ApprovalState.REJECTED
    assert row.resolved_at is not None and row.resolution_note == "Too soon; she said early next week."
    history = svc.history("t-reject")
    assert [m.role for m in history] == ["you", "enola", "tool"]
    assert history[-1].text.startswith("The owner rejected this action.")
    kinds = [a.kind for a in db.scalars(select(ActivityLog).where(ActivityLog.run_id == first.run_id).order_by(ActivityLog.id)).all() if a.kind != ActivityKind.MODEL_CALL]
    assert kinds == [ActivityKind.HELD, ActivityKind.REJECTED]
    # No partial writes: only the two activity rows (plus model-call logging) and the one approval row exist for this run.
    assert db.scalar(select(ApprovalRequest.id).where(ApprovalRequest.run_id == first.run_id, ApprovalRequest.id != row.id)) is None
    # Deciding twice is refused.
    with pytest.raises(Exception, match="already rejected"):
        svc.decide(first.held_approval_id, approve=True)


def test_unclassified_tool_defaults_to_gated(db: Session) -> None:
    reg = ToolRegistry()
    seen: list[str] = []

    @reg.tool()  # no risk given, on purpose
    def mystery(value: str) -> str:
        """A tool someone added in a hurry without saying how risky it is."""
        seen.append(value)
        return "ran"

    spec = reg.get("mystery")
    assert spec.risk == Risk.UNCLASSIFIED
    assert spec.gated is True
    assert reg.is_gated("mystery") is True
    assert reg.is_gated("never_registered") is True

    model = ScriptedModel(script=[ai_tool_call("mystery", {"value": "x"}, "call_1"), AIMessage(content="ok")])
    result = service(db, model, reg).run(text="Run the mystery tool.", thread_id="t-unclassified")
    assert result.held_approval_id is not None
    row = db.get(ApprovalRequest, result.held_approval_id)
    assert row is not None and row.state == ApprovalState.HELD and row.risk == Risk.UNCLASSIFIED
    assert seen == []


def test_safe_tool_runs_freely_and_write_local_is_logged(db: Session, probe_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[
        ai_tool_call("echo_probe", {"text": "ping"}, "call_1"),
        AIMessage(content="pong"),
    ])
    result = service(db, model, probe_registry).run(text="echo ping", thread_id="t-safe")
    assert result.held_approval_id is None and result.aborted is False
    assert [m.text for m in result.messages if m.role == "tool"] == ["echo: ping"]
    assert db.scalar(select(ApprovalRequest.id)) is None


def test_new_turn_is_refused_while_held(db: Session, probe_registry: ToolRegistry) -> None:
    model = ScriptedModel(script=[ai_tool_call("send_probe", {"to": "a@b.c", "message": "x"}, "call_1"), AIMessage(content="ok")])
    svc = service(db, model, probe_registry)
    first = svc.run(text="Send it.", thread_id="t-parked")
    assert first.held_approval_id is not None
    with pytest.raises(ConflictError):
        svc.run(text="Actually, also do this.", thread_id="t-parked")
    assert model.calls == 1
