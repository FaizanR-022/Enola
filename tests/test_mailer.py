"""Outbound mail.

Sending is now real, so these tests are about the things that would be worst if they
were wrong: a message that never left being recorded as sent, and a reply that silently
starts a new conversation instead of continuing one.

Nothing here touches a live SMTP server — conftest blanks the host for every test, and
the transport is stubbed besides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.agent.registry import ToolRegistry
from enola.agent.service import AgentService
from enola.agent.tools import records
from enola.core import mailer
from enola.core.config import get_settings
from enola.core.enums import ApprovalState, InteractionKind, Risk
from enola.core.errors import InvalidInputError
from enola.core.mailer import MailNotConfigured, send_mail, valid_address
from enola.core.models import ApprovalRequest, Interaction
from enola.core.schemas.people import PersonCreate
from enola.core.services.people import PersonService
from tests.agent_helpers import ScriptedModel, ai_tool_call
from tests.conftest import TEST_URL


@dataclass
class FakeSMTP:
    """Records what would have gone out, and can be told to fail like a real server."""

    sent: list[dict[str, Any]] = field(default_factory=list)
    explode: bool = False

    def __call__(self, *, to: str, subject: str, body: str, in_reply_to: str = "", settings: Any = None) -> str:
        if self.explode:
            raise MailNotConfigured("no transport")
        self.sent.append({"to": to, "subject": subject, "body": body, "in_reply_to": in_reply_to})
        return "<fake-message-id@enola>"


def registry_with_send() -> ToolRegistry:
    reg = ToolRegistry()
    reg.tool(risk=Risk.EXTERNAL, kind_label="email · outbound")(records.send_email)
    return reg


def run_send(db: Session, args: dict[str, Any], *, thread: str) -> tuple[AgentService, int]:
    model = ScriptedModel(script=[ai_tool_call("send_email", args, "call_1", text="Drafted."), AIMessage(content="Done.")])
    svc = AgentService(db, model=model, registry=registry_with_send(), database_url=TEST_URL)
    result = svc.run(text="Reply to her.", thread_id=thread)
    assert result.held_approval_id is not None, "an outbound email must always be Held first"
    return svc, result.held_approval_id


def test_valid_address() -> None:
    assert valid_address("ayesha@kestrellabs.io")
    assert valid_address("Ayesha Tariq <ayesha@kestrellabs.io>")
    assert not valid_address("")
    assert not valid_address("ayesha")
    assert not valid_address("ayesha@localhost")


def test_send_mail_refuses_without_a_transport() -> None:
    with pytest.raises(MailNotConfigured):
        send_mail(to="a@b.co", subject="x", body="y")


def test_approving_actually_sends(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    smtp = FakeSMTP()
    monkeypatch.setattr(records, "send_mail", smtp)
    person = PersonService(db).create(PersonCreate(name="Ayesha Tariq", email="ayesha@kestrellabs.io"))
    db.commit()

    svc, approval_id = run_send(
        db,
        {"to": "ayesha@kestrellabs.io", "subject": "Re: take-home", "body": "Sending tonight.", "reply_to_message_id": "<abc@mail.gmail.com>"},
        thread="send-1",
    )
    assert smtp.sent == [], "nothing may leave before approval"

    svc.decide(approval_id, approve=True)

    assert len(smtp.sent) == 1
    sent = smtp.sent[0]
    assert sent["to"] == "ayesha@kestrellabs.io" and sent["subject"] == "Re: take-home"
    # Threaded, so it continues the conversation rather than starting a new one.
    assert sent["in_reply_to"] == "<abc@mail.gmail.com>"
    # And the send is recorded against the person.
    interactions = db.scalars(select(Interaction).where(Interaction.person_id == person.id)).all()
    assert [i.kind for i in interactions] == [InteractionKind.EMAIL]


def test_rejecting_sends_nothing(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    smtp = FakeSMTP()
    monkeypatch.setattr(records, "send_mail", smtp)
    svc, approval_id = run_send(db, {"to": "ayesha@kestrellabs.io", "subject": "No", "body": "No"}, thread="send-2")
    svc.decide(approval_id, approve=False, note="too soon")
    assert smtp.sent == []
    row = db.get(ApprovalRequest, approval_id)
    assert row is not None and row.state == ApprovalState.REJECTED


def test_a_failed_send_is_not_recorded_as_a_reply(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worst failure mode: the owner believes they replied and they did not."""
    smtp = FakeSMTP(explode=True)
    monkeypatch.setattr(records, "send_mail", smtp)
    person = PersonService(db).create(PersonCreate(name="Ayesha Tariq", email="ayesha@kestrellabs.io"))
    db.commit()

    svc, approval_id = run_send(db, {"to": "ayesha@kestrellabs.io", "subject": "Re: take-home", "body": "Hi"}, thread="send-3")
    # The graph turns a tool failure into a tool result rather than crashing the run,
    # which is right — but the failure must not leave a trail that looks like success.
    svc.decide(approval_id, approve=True)

    assert db.scalars(select(Interaction).where(Interaction.person_id == person.id)).all() == [], (
        "an interaction was logged for a message that never left"
    )
    tool_messages = [m.text for m in svc.history("send-3") if m.role == "tool"]
    assert tool_messages and "no transport" in " ".join(tool_messages).lower(), (
        "the failure must be visible in the transcript, not swallowed"
    )
    assert not any("sent to" in t.lower() for t in tool_messages)


def test_send_refuses_a_malformed_address(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "me@example.test")
    with pytest.raises(InvalidInputError):
        send_mail(to="not-an-address", subject="x", body="y", settings=settings)


def test_outbox_waits_rather_than_failing_without_a_transport(db: Session) -> None:
    """A queued notification must stay queued when there is no transport, not fail."""
    from enola.core.enums import NotificationChannel, NotificationKind, NotificationState
    from enola.workers.outbox import deliver_due, enqueue

    enqueue(db, kind=NotificationKind.TASK_DUE, title="t", body="b", dedupe_key="k", channels=(NotificationChannel.EMAIL,))
    db.commit()
    counts = deliver_due(db)
    assert counts["waiting"] == 1 and counts["failed"] == 0 and counts["sent"] == 0
    row = db.scalars(select(mailer_notification())).first()
    assert row is not None and row.state is NotificationState.QUEUED


def mailer_notification() -> Any:
    from enola.core.models.infra import Notification

    return Notification
