"""The daily brief: one message that answers "what needs me today". Composed from the
same aggregate the dashboard uses, so the two never disagree."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.enums import NotificationChannel, NotificationKind, NotificationState
from enola.core.models.infra import Notification
from enola.core.services.dashboard import build_dashboard
from enola.workers.outbox import enqueue


def compose_brief(db: Session, *, now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now(UTC)
    tz = ZoneInfo(get_settings().timezone)
    dashboard = build_dashboard(db)
    lines: list[str] = [dashboard.headline, ""]
    if dashboard.held.count:
        lines += [f"Held · {dashboard.held.count}", f"  {dashboard.held.summary}", ""]
    if dashboard.today:
        lines.append("Today")
        for item in dashboard.today:
            lines.append(f"  {item.time_label}  {item.title} · {item.sub}")
        lines.append("")
    if dashboard.due:
        lines.append("Due")
        for task in dashboard.due:
            when = task.due_at.astimezone(tz).strftime("%a %d %b") if task.due_at else "—"
            overdue = task.due_at is not None and task.due_at < now
            lines.append(f"  {'!' if overdue else '·'} {task.title} · {when}")
        lines.append("")
    reminders = db.scalars(
        select(Notification)
        .where(
            Notification.channel == NotificationChannel.IN_APP,
            Notification.kind.in_((NotificationKind.THREAD_QUIET, NotificationKind.TASK_DUE, NotificationKind.ACADEMIC_DEADLINE)),
            Notification.read_at.is_(None),
            Notification.state != NotificationState.FAILED,
        )
        .order_by(Notification.scheduled_for.desc())
        .limit(12)
    ).all()
    if reminders:
        lines.append("Reminders")
        for r in reminders:
            lines.append(f"  · {r.title}")
        lines.append("")
    if dashboard.going_cold:
        lines.append("Going cold")
        for person in dashboard.going_cold:
            lines.append(f"  · {person.name} · {person.days_since_contact}d" if person.days_since_contact is not None else f"  · {person.name} · never contacted")
        lines.append("")
    if dashboard.activity:
        lines.append("Enola did (last 12h)")
        for row in dashboard.activity:
            lines.append(f"  · {row.summary}")
    title = f"Daily brief · {now.astimezone(tz).strftime('%A %d %B')}"
    return title, "\n".join(lines).strip()


def daily_brief(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    title, body = compose_brief(db, now=now)
    day = now.astimezone(ZoneInfo(get_settings().timezone)).strftime("%Y-%m-%d")
    created = enqueue(db, kind=NotificationKind.DAILY_BRIEF, title=title, body=body, dedupe_key=f"brief:{day}", scheduled_for=now)
    return {"queued": len(created)}
