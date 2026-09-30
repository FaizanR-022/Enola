"""Phase 5 gate: a backdated task, a backdated contact cadence and a due assessment each
produce a notification that surfaces in the brief and the in-app badge. Plus the
dedupe and outbox rules that keep the worker from nagging."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.enums import (
    AssessmentKind,
    NotificationChannel,
    NotificationKind,
    NotificationState,
)
from enola.core.models import Notification
from enola.core.schemas.academics import AssessmentCreate, CourseCreate
from enola.core.schemas.people import InteractionCreate, PersonCreate
from enola.core.schemas.tasks import TaskCreate
from enola.core.services.academics import AssessmentService, CourseService
from enola.core.services.people import InteractionService, PersonService
from enola.core.services.tasks import TaskService
from enola.workers.jobs import daily_brief, due_reminders, followup_nudges
from enola.workers.outbox import deliver_due, enqueue

NOW = datetime.now(UTC)


def _seed_backdated(db: Session) -> tuple[int, int, int]:
    task = TaskService(db).create(TaskCreate(title="Send Areeba the poster money", due_at=NOW - timedelta(days=2)))
    person = PersonService(db).create(PersonCreate(name="Sana Iqbal", role="Engineering manager", cadence_days=30))
    InteractionService(db).create(InteractionCreate(person_id=person.id, summary="Coffee after her lecture", occurred_at=NOW - timedelta(days=63)))
    course = CourseService(db).create(CourseCreate(code="CS3006", name="Parallel and Distributed Computing"))
    assessment = AssessmentService(db).create(AssessmentCreate(course_id=course.id, kind=AssessmentKind.ASSIGNMENT, title="Assignment 3 — Raft", due_at=NOW + timedelta(hours=6)))
    db.commit()
    assert assessment.task_id is not None
    return task.id, person.id, assessment.task_id


def test_reminders_nudges_and_brief(db: Session, client: TestClient) -> None:
    task_id, person_id, assessment_task_id = _seed_backdated(db)

    assert due_reminders(db)["queued"] == 4  # two tasks × two channels
    assert followup_nudges(db)["queued"] == 2  # one cold person × two channels
    db.commit()

    kinds = {(n.kind, n.entity_id) for n in db.scalars(select(Notification).where(Notification.channel == NotificationChannel.IN_APP)).all()}
    assert (NotificationKind.TASK_DUE, task_id) in kinds
    assert (NotificationKind.ACADEMIC_DEADLINE, assessment_task_id) in kinds
    assert (NotificationKind.CONTACT_COLD, person_id) in kinds

    # Running the jobs again the same day queues nothing new.
    assert due_reminders(db)["queued"] == 0
    assert followup_nudges(db)["queued"] == 0

    # The brief mentions all three and lands in the in-app + email outbox.
    assert daily_brief(db)["queued"] == 2
    db.commit()
    brief = db.scalar(select(Notification).where(Notification.kind == NotificationKind.DAILY_BRIEF, Notification.channel == NotificationChannel.IN_APP))
    assert brief is not None
    assert "Send Areeba the poster money" in brief.body
    assert "Assignment 3 — Raft" in brief.body
    assert "Sana Iqbal" in brief.body
    assert daily_brief(db)["queued"] == 0

    # Delivery: in-app rows are sent; email rows wait because SMTP is not configured.
    counts = deliver_due(db)
    db.commit()
    assert counts["sent"] == 4 and counts["waiting"] == 4 and counts["failed"] == 0
    email_rows = db.scalars(select(Notification).where(Notification.channel == NotificationChannel.EMAIL)).all()
    assert all(r.state == NotificationState.QUEUED and "SMTP" in r.error for r in email_rows)

    # The badge counts the two due-date reminders. The cold contact is not a reminder:
    # it shows under "Going cold" and on People, never twice.
    assert client.get("/api/notifications/badge").json() == {"unread": 2}
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["brief"] is not None and "Sana Iqbal" in dashboard["brief"]["body"]
    assert {r["kind"] for r in dashboard["reminders"]} == {"task_due", "academic_deadline"}
    assert any(p["name"] == "Sana Iqbal" for p in dashboard["going_cold"])

    # Reading one clears it from the badge; read-all clears the rest.
    first = dashboard["reminders"][0]["id"]
    assert client.post(f"/api/notifications/{first}/read").json()["read_at"] is not None
    assert client.get("/api/notifications/badge").json() == {"unread": 1}
    assert client.post("/api/notifications/read-all").json()["marked"] == 1
    assert client.get("/api/notifications/badge").json() == {"unread": 0}


def test_enqueue_is_idempotent_per_channel(db: Session) -> None:
    first = enqueue(db, kind=NotificationKind.TASK_DUE, title="t", body="b", dedupe_key="x:1", channels=(NotificationChannel.IN_APP,))
    second = enqueue(db, kind=NotificationKind.TASK_DUE, title="t", body="b", dedupe_key="x:1", channels=(NotificationChannel.IN_APP, NotificationChannel.EMAIL))
    assert len(first) == 1 and len(second) == 1 and second[0].channel == NotificationChannel.EMAIL


def test_future_notifications_wait(db: Session) -> None:
    enqueue(db, kind=NotificationKind.TASK_DUE, title="later", body="", dedupe_key="later:1", scheduled_for=NOW + timedelta(hours=2), channels=(NotificationChannel.IN_APP,))
    assert deliver_due(db)["sent"] == 0
    assert deliver_due(db, now=NOW + timedelta(hours=3))["sent"] == 1
