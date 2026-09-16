"""Task due-date reminders and academic deadlines.

Assessments write into `task`, so one query covers both; the notification kind just
says which it was. One reminder per task per local day.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.enums import EntityType, NotificationKind, TaskSource, TaskState
from enola.core.models.tasks import Task
from enola.workers.outbox import enqueue

LOOKAHEAD = timedelta(hours=24)


def _day_key(now: datetime) -> str:
    return now.astimezone(ZoneInfo(get_settings().timezone)).strftime("%Y-%m-%d")


def due_reminders(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    horizon = now + LOOKAHEAD
    tasks = db.scalars(
        select(Task).where(Task.state == TaskState.OPEN, Task.due_at.is_not(None), Task.due_at <= horizon).order_by(Task.due_at)
    ).all()
    day = _day_key(now)
    queued = 0
    for task in tasks:
        assert task.due_at is not None
        overdue = task.due_at < now
        kind = NotificationKind.ACADEMIC_DEADLINE if task.source == TaskSource.ASSESSMENT else NotificationKind.TASK_DUE
        when = task.due_at.astimezone(ZoneInfo(get_settings().timezone)).strftime("%a %d %b %H:%M")
        title = f"{'Overdue' if overdue else 'Due soon'}: {task.title}"
        body = f"{'Was due' if overdue else 'Due'} {when}." + (" This came from a course deadline." if kind == NotificationKind.ACADEMIC_DEADLINE else "")
        created = enqueue(
            db,
            kind=kind,
            title=title,
            body=body,
            dedupe_key=f"{kind.value}:{task.id}:{day}",
            entity_type=EntityType.TASK,
            entity_id=task.id,
        )
        queued += len(created)
    return {"tasks_considered": len(tasks), "queued": queued}
