"""The worker process. Runs in its own process, talks to the API only through Postgres.

    python -m enola.workers.scheduler          # run forever
    python -m enola.workers.scheduler --once   # run every job once, deliver, exit

Every job opens its own session, commits, and writes a one-line summary to the log.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from enola.core import auth
from enola.core.config import get_settings
from enola.core.db import session_scope
from enola.core.enums import ActivityKind
from enola.core.logging import bind_context, configure_logging, get_logger
from enola.core.services.activity import record_activity
from enola.workers.jobs import daily_brief, discover_jobs, due_reminders, followup_nudges
from enola.workers.outbox import deliver_due

log = get_logger(__name__)

Job = Callable[[Session], dict[str, int]]


def run_job(name: str, job: Job, *, record: bool = False) -> dict[str, int]:
    run_id = f"job-{uuid.uuid4().hex[:8]}"
    with bind_context(run_id=run_id, job=name):
        try:
            with session_scope() as db:
                summary = job(db)
                if record and summary.get("queued"):
                    record_activity(db, kind=ActivityKind.JOB_RUN, summary=f"{name}: queued {summary['queued']}", run_id=run_id, detail=summary)
            log.info("job_done", **summary)
            return summary
        except Exception as exc:
            log.exception("job_failed", error=str(exc))
            return {"error": 1}


def _reminders(db: Session) -> dict[str, int]:
    return due_reminders(db)


def _nudges(db: Session) -> dict[str, int]:
    return followup_nudges(db)


def _brief(db: Session) -> dict[str, int]:
    return daily_brief(db)


def _discovery(db: Session) -> dict[str, int]:
    return discover_jobs(db)


def _deliver(db: Session) -> dict[str, int]:
    return deliver_due(db)


def _purge_sessions(db: Session) -> dict[str, int]:
    return {"purged": auth.purge_expired(db)}


def run_all_once() -> None:
    run_job("reminders", _reminders, record=True)
    run_job("followup_nudges", _nudges, record=True)
    run_job("daily_brief", _brief, record=True)
    run_job("discovery", _discovery, record=True)
    run_job("deliver", _deliver)
    run_job("purge_sessions", _purge_sessions)


def main() -> None:
    configure_logging()
    settings = get_settings()
    if "--once" in sys.argv:
        run_all_once()
        return
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(lambda: run_job("reminders", _reminders, record=True), IntervalTrigger(minutes=15), id="reminders")
    scheduler.add_job(lambda: run_job("followup_nudges", _nudges, record=True), IntervalTrigger(hours=1), id="nudges")
    scheduler.add_job(lambda: run_job("daily_brief", _brief, record=True), CronTrigger(hour=settings.daily_brief_hour, minute=0), id="brief")
    # Once a day, just after the brief: the free tiers are small and postings do not
    # move fast enough to be worth more.
    scheduler.add_job(lambda: run_job("discovery", _discovery, record=True), CronTrigger(hour=settings.daily_brief_hour, minute=20), id="discovery")
    scheduler.add_job(lambda: run_job("deliver", _deliver), IntervalTrigger(minutes=1), id="deliver")
    scheduler.add_job(lambda: run_job("purge_sessions", _purge_sessions), CronTrigger(hour=3, minute=30), id="purge")
    log.info("worker_start", brief_hour=settings.daily_brief_hour, timezone=settings.timezone, started=datetime.now(UTC).isoformat())
    scheduler.start()


if __name__ == "__main__":
    main()
