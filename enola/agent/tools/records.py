"""Tools over the owner's own records. Reads are SAFE; local writes are WRITE_LOCAL and
land in activity_log; anything that deletes is DESTRUCTIVE and therefore Held."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from enola.agent.context import current_context
from enola.agent.registry import tool
from enola.core.enums import (
    ActorSource,
    EntityType,
    InteractionKind,
    MemorySource,
    Risk,
    TaskPriority,
    TaskState,
)
from enola.core.mailer import send_mail
from enola.core.models import Application, MemoryFact, Person
from enola.core.schemas.people import InteractionCreate
from enola.core.schemas.tasks import TaskCreate, TaskLinkIn
from enola.core.services.people import InteractionService, PersonService
from enola.core.services.tasks import TaskService


@tool(risk=Risk.SAFE, kind_label="people · read")
def search_people(query: str, limit: int = 8) -> str:
    """Search the People catalogue by name, role, notes or how you met. Returns one line per person."""
    ctx = current_context()
    needle = f"%{query.strip()}%"
    stmt = (
        select(Person)
        .where(or_(Person.name.ilike(needle), Person.role.ilike(needle), Person.notes.ilike(needle), Person.how_we_met.ilike(needle)))
        .order_by(Person.name)
        .limit(limit)
    )
    rows = ctx.db.scalars(stmt).all()
    if not rows:
        return "No one matches."
    lines = []
    for p in rows:
        last = p.last_contacted_at.strftime("%d %b") if p.last_contacted_at else "never"
        tags = ", ".join(t.tag for t in p.tags)
        lines.append(f"#{p.id} {p.name} — {p.role} · tags: {tags} · last contact {last}")
    return "\n".join(lines)


@tool(risk=Risk.SAFE, kind_label="tasks · read")
def list_open_tasks(days_ahead: int = 7) -> str:
    """List open tasks due within the next N days (default 7), soonest first."""
    ctx = current_context()
    until = datetime.now(UTC) + timedelta(days=days_ahead)
    rows = TaskService(ctx.db).due_by(until, limit=30)
    if not rows:
        return "Nothing due in that window."
    return "\n".join(f"#{t.id} {t.title} · due {t.due_at.strftime('%a %d %b') if t.due_at else '—'} · {t.priority.value}" for t in rows)


@tool(risk=Risk.SAFE, kind_label="jobs · read")
def list_applications(stage: str = "") -> str:
    """List job applications, optionally filtered by stage (saved, applied, screening, interview, offer, closed)."""
    ctx = current_context()
    stmt = select(Application).order_by(Application.last_activity_at.desc().nulls_last())
    if stage:
        stmt = stmt.where(Application.stage == stage)
    rows = ctx.db.scalars(stmt).all()
    if not rows:
        return "No applications."
    out = []
    for a in rows:
        quiet = (datetime.now(UTC) - a.last_activity_at).days if a.last_activity_at else None
        out.append(f"#{a.id} {a.role_title} at {a.company.name} · {a.stage.value} · quiet {quiet}d · next: {a.next_action or '—'}")
    return "\n".join(out)


@tool(risk=Risk.WRITE_LOCAL, kind_label="tasks · create")
def create_task(title: str, due_in_days: int | None = None, priority: str = "normal", application_id: int | None = None, person_id: int | None = None) -> str:
    """Create a task for the owner. Optionally link it to an application or a person."""
    ctx = current_context()
    links: list[TaskLinkIn] = []
    if application_id is not None:
        app = ctx.db.get(Application, application_id)
        if app is not None:
            links.append(TaskLinkIn(entity_type=EntityType.APPLICATION, entity_id=app.id, label=app.company.name.split()[0].lower()))
    if person_id is not None:
        person = ctx.db.get(Person, person_id)
        if person is not None:
            links.append(TaskLinkIn(entity_type=EntityType.PERSON, entity_id=person.id, label="people"))
    due = datetime.now(UTC).replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=due_in_days) if due_in_days is not None else None
    task = TaskService(ctx.db).create(TaskCreate(title=title, due_at=due, priority=TaskPriority(priority), links=links, state=TaskState.OPEN))
    return f"Created task #{task.id}: {task.title}"


@tool(risk=Risk.WRITE_LOCAL, kind_label="people · note")
def log_interaction(person_id: int, summary: str, kind: str = "note") -> str:
    """Record a touchpoint with a person (call, email, message, meeting or note). Updates their last-contacted date."""
    ctx = current_context()
    row = InteractionService(ctx.db).create(
        InteractionCreate(person_id=person_id, kind=InteractionKind(kind), summary=summary, occurred_at=datetime.now(UTC), source=ActorSource.ENOLA)
    )
    return f"Logged interaction #{row.id}"


@tool(risk=Risk.WRITE_LOCAL, kind_label="memory · write")
def remember(statement: str, group: str = "About you", confidence: int = 80, told_by_owner: bool = False) -> str:
    """Store a durable fact about the owner in Memory. Use told_by_owner=true when they said it outright."""
    ctx = current_context()
    fact = MemoryFact(
        group=group,
        statement=statement,
        source=MemorySource.TOLD if told_by_owner else MemorySource.INFERRED,
        evidence=("you told me" if told_by_owner else "inferred from conversation") + f" · {datetime.now(UTC).strftime('%d %b')}",
        confidence=100 if told_by_owner else max(0, min(100, confidence)),
        thread_id=ctx.thread_id,
    )
    ctx.db.add(fact)
    ctx.db.flush()
    return f"Remembered as fact #{fact.id}"


@tool(risk=Risk.DESTRUCTIVE, kind_label="people · destructive")
def delete_person(person_id: int, reason: str) -> str:
    """Delete a person from the catalogue (for duplicates). DESTRUCTIVE: always Held first."""
    ctx = current_context()
    person = PersonService(ctx.db).get(person_id)
    name = person.name
    PersonService(ctx.db).delete(person_id)
    return f"Deleted {name} (#{person_id}): {reason}"


@tool(risk=Risk.EXTERNAL, kind_label="email · outbound")
def send_email(to: str, subject: str, body: str, reply_to_message_id: str = "") -> str:
    """Send an email on the owner's behalf. EXTERNAL: always Held first, and the send is
    real — once approved the message leaves. Pass `reply_to_message_id` (from
    read_email_thread) when answering a thread, so it continues the conversation instead
    of starting a new one."""
    ctx = current_context()
    # Send first: an interaction logged for a message that never left would be a lie,
    # and the owner would believe they had replied.
    message_id = send_mail(to=to.strip(), subject=subject, body=body, in_reply_to=reply_to_message_id.strip())
    person = ctx.db.scalar(select(Person).where(Person.email.ilike(to.strip())))
    if person is not None:
        InteractionService(ctx.db).create(
            InteractionCreate(person_id=person.id, kind=InteractionKind.EMAIL, summary=f"Sent: {subject}", occurred_at=datetime.now(UTC), source=ActorSource.ENOLA)
        )
    threaded = " (as a reply in the existing thread)" if reply_to_message_id.strip() else ""
    return f"Sent to {to}: “{subject}”{threaded}. Message-ID {message_id}."
