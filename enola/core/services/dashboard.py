"""What needs you today, in one query bundle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.enums import (
    ActivityKind,
    ApplicationStage,
    ApprovalState,
    NotificationChannel,
    NotificationKind,
    TaskState,
)
from enola.core.models import (
    Application,
    ApprovalRequest,
    Assessment,
    Company,
    Course,
    Document,
    JobPosting,
    LogEntry,
    MemoryFact,
    Notification,
    Person,
    Task,
)
from enola.core.schemas.dashboard import DashboardRead, HeldSummary, SearchHit, TodayItem
from enola.core.schemas.infra import ActivityListParams, ActivityRead, NotificationRead
from enola.core.schemas.tasks import TaskRead
from enola.core.services.activity import ActivityService
from enola.core.services.notifications import NotificationService
from enola.core.services.people import PersonService


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def _held_summary(db: Session) -> HeldSummary:
    rows = db.scalars(select(ApprovalRequest).where(ApprovalRequest.state == ApprovalState.HELD).order_by(ApprovalRequest.created_at)).all()
    if not rows:
        return HeldSummary(count=0, summary="Nothing is waiting on you.", oldest_created_at=None)
    oldest = rows[0]
    minutes = int((datetime.now(UTC) - oldest.created_at).total_seconds() // 60)
    age = f"{minutes} minutes" if minutes < 90 else f"{minutes // 60} hours" if minutes < 48 * 60 else f"{minutes // 1440} days"
    noun = "action is" if len(rows) == 1 else "actions are"
    label = oldest.job_label.split("·", 1)[-1].strip() if "·" in oldest.job_label else oldest.tool_name
    return HeldSummary(
        count=len(rows),
        summary=f"{len(rows)} {noun} drafted and paused. The oldest ({label}) has been waiting {age}.",
        oldest_created_at=oldest.created_at,
    )


def build_dashboard(db: Session) -> DashboardRead:
    now_local = _local_now()
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    week_end = day_start + timedelta(days=7)

    held = _held_summary(db)

    today: list[TodayItem] = []
    for a in db.scalars(select(Assessment).where(Assessment.due_at >= day_start, Assessment.due_at < day_end)).all():
        course = db.get(Course, a.course_id)
        code = course.code if course else ""
        when = a.due_at.astimezone(now_local.tzinfo)
        today.append(TodayItem(when=a.due_at, time_label=when.strftime("%H:%M"), title=f"{a.kind.value.capitalize()} — {a.title}", sub=f"{code} · {a.course.name if course else ''}", path="/academics"))
    live = (ApplicationStage.APPLIED, ApplicationStage.SCREENING, ApplicationStage.INTERVIEW, ApplicationStage.SAVED)
    for app in db.scalars(select(Application).where(Application.stage.in_(live), Application.next_action_at.is_not(None), Application.next_action_at >= day_start, Application.next_action_at < day_end + timedelta(days=1))).all():
        assert app.next_action_at is not None
        when = app.next_action_at.astimezone(now_local.tzinfo)
        prefix = "" if when < day_end else "tomorrow · "
        today.append(TodayItem(when=app.next_action_at, time_label=when.strftime("%H:%M"), title=app.next_action or app.role_title, sub=f"{prefix}{app.company.name} · {app.role_title}", path=f"/jobs/{app.id}"))
    today.sort(key=lambda t: t.when)

    due_rows = db.scalars(
        select(Task).where(Task.state == TaskState.OPEN, Task.due_at.is_not(None), Task.due_at < week_end).order_by(Task.due_at.asc()).limit(7)
    ).all()
    due = [TaskRead.model_validate(t) for t in due_rows]

    people = PersonService(db)
    cold = [people.to_read(p) for p in people.going_cold(limit=4)]

    activity_rows, _ = ActivityService(db).list(ActivityListParams(limit=12, since=datetime.now(UTC) - timedelta(hours=12)))
    activity = [ActivityRead.model_validate(a) for a in activity_rows if a.kind != ActivityKind.MODEL_CALL][:6]

    brief_row = db.scalar(
        select(Notification)
        .where(Notification.kind == NotificationKind.DAILY_BRIEF, Notification.channel == NotificationChannel.IN_APP, Notification.scheduled_for >= day_start - timedelta(hours=12))
        .order_by(Notification.scheduled_for.desc())
    )
    brief = NotificationRead.model_validate(brief_row) if brief_row else None
    reminders = [NotificationRead.model_validate(n) for n in NotificationService(db).unread_in_app(limit=8)]

    overdue = sum(1 for t in due_rows if t.due_at is not None and t.due_at < datetime.now(UTC))
    due_today = sum(1 for t in due_rows if t.due_at is not None and day_start <= t.due_at.astimezone(now_local.tzinfo) < day_end)
    needs_you = held.count + due_today + overdue + len(today) + len(reminders)
    if needs_you == 0:
        headline = "Nothing needs you right now."
    elif needs_you == 1:
        headline = "One thing needs you today."
    else:
        headline = f"{['Two', 'Three', 'Four', 'Five', 'Six'][needs_you - 2] if needs_you <= 6 else needs_you} things need you today."

    return DashboardRead(
        date_label=now_local.strftime("%A, %d %B").replace(" 0", " "),
        needs_you=needs_you,
        headline=headline,
        held=held,
        today=today,
        due=due,
        going_cold=cold,
        activity=activity,
        brief=brief,
        reminders=reminders,
    )


def search(db: Session, q: str, limit: int = 20) -> list[SearchHit]:
    needle = f"%{q.strip()}%"
    hits: list[SearchHit] = []
    for p in db.scalars(select(Person).where(or_(Person.name.ilike(needle), Person.role.ilike(needle))).limit(5)).all():
        hits.append(SearchHit(group="People", label=f"{p.name} — {p.role}" if p.role else p.name, meta="person", path=f"/people/{p.id}", dot="accent"))
    for a in db.scalars(select(Application).join(Company, Company.id == Application.company_id).where(or_(Application.role_title.ilike(needle), Company.name.ilike(needle))).limit(5)).all():
        hits.append(SearchHit(group="Jobs", label=f"{a.role_title} — {a.company.name}", meta=a.stage.value, path=f"/jobs/{a.id}", dot="held" if a.stage == ApplicationStage.SCREENING else "ok" if a.stage == ApplicationStage.INTERVIEW else "muted"))
    for t in db.scalars(select(Task).where(Task.title.ilike(needle)).order_by(Task.state, Task.due_at).limit(5)).all():
        due = t.due_at.astimezone(_local_now().tzinfo).strftime("due %a %d %b") if t.due_at else "no date"
        hits.append(SearchHit(group="Tasks", label=t.title, meta=due if t.state == TaskState.OPEN else "done", path="/tasks", dot="danger" if t.due_at and t.due_at < datetime.now(UTC) and t.state == TaskState.OPEN else "muted"))
    for c in db.scalars(select(Course).where(or_(Course.code.ilike(needle), Course.name.ilike(needle))).limit(3)).all():
        hits.append(SearchHit(group="Academics", label=f"{c.code} {c.name}", meta="course", path="/academics", dot="paper"))
    for d in db.scalars(select(Document).where(or_(Document.title.ilike(needle), Document.filename.ilike(needle))).limit(3)).all():
        hits.append(SearchHit(group="Academics" if d.scope.startswith("course:") else "Documents", label=d.filename, meta="document", path="/academics" if d.scope.startswith("course:") else "/memory", dot="paper"))
    for e in db.scalars(select(LogEntry).where(or_(LogEntry.title.ilike(needle), LogEntry.body.ilike(needle))).order_by(LogEntry.occurred_at.desc()).limit(3)).all():
        hits.append(SearchHit(group="Log", label=e.title, meta=e.occurred_at.astimezone(_local_now().tzinfo).strftime("%d %b %H:%M"), path="/log", dot="accent"))
    for m in db.scalars(select(MemoryFact).where(MemoryFact.statement.ilike(needle)).limit(3)).all():
        hits.append(SearchHit(group="Memory", label=f"“{m.statement}”", meta=f"belief · {m.confidence}%", path="/memory", dot="soft"))
    for j in db.scalars(select(JobPosting).where(or_(JobPosting.role_title.ilike(needle), JobPosting.company_name.ilike(needle))).limit(3)).all():
        hits.append(SearchHit(group="Discovery", label=f"{j.role_title} — {j.company_name}", meta=f"match {j.match_score or '—'}", path="/jobs", dot="muted"))
    return hits[:limit]
