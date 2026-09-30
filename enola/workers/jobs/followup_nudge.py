"""Follow-up nudges: recruiter threads that have gone quiet, and contacts whose
cadence has lapsed. Nudges only ever notify; drafting a follow-up is the agent's job
and sending it is Held."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.enums import EntityType, NotificationKind
from enola.core.services.jobs import ApplicationService
from enola.core.services.people import PersonService
from enola.workers.outbox import enqueue

QUIET_DAYS = 3


def followup_nudges(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    day = now.astimezone(ZoneInfo(get_settings().timezone)).strftime("%Y-%m-%d")
    queued = 0

    quiet = ApplicationService(db).quiet_since(QUIET_DAYS)
    for app in quiet:
        assert app.last_activity_at is not None
        days = (now - app.last_activity_at).days
        created = enqueue(
            db,
            kind=NotificationKind.THREAD_QUIET,
            title=f"Quiet for {days} days: {app.role_title} at {app.company.name}",
            body=f"No activity since {app.last_activity_at.astimezone(ZoneInfo(get_settings().timezone)).strftime('%d %b')}. Stage: {app.stage.value}. Ask Enola to draft a follow-up; it will wait for your approval before anything goes out.",
            dedupe_key=f"nudge:application:{app.id}:{day}",
            entity_type=EntityType.APPLICATION,
            entity_id=app.id,
        )
        queued += len(created)

    cold = PersonService(db).going_cold(limit=20)
    for person in cold:
        since = f"{(now - person.last_contacted_at).days} days" if person.last_contacted_at else "never"
        created = enqueue(
            db,
            kind=NotificationKind.CONTACT_COLD,
            title=f"Going cold: {person.name}",
            body=f"Last contact: {since}. Cadence is every {person.cadence_days} days.",
            dedupe_key=f"nudge:person:{person.id}:{day}",
            entity_type=EntityType.PERSON,
            entity_id=person.id,
        )
        queued += len(created)

    return {"quiet_applications": len(quiet), "cold_people": len(cold), "queued": queued}
