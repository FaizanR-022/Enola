from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import or_, select

from enola.core.enums import ActivityKind, TaskState
from enola.core.models.infra import ActivityLog
from enola.core.models.journal import LogEntry
from enola.core.models.tasks import Task
from enola.core.repository import Repository
from enola.core.schemas.journal import LogCandidate, LogEntryCreate, LogEntryListParams, LogEntryRead
from enola.core.services.base import CrudService


class LogEntryRepository(Repository[LogEntry]):
    model = LogEntry
    default_order = ("-occurred_at", "-id")


class LogEntryService(CrudService[LogEntry, LogEntryCreate, BaseModel]):
    repo_cls = LogEntryRepository
    read_schema = LogEntryRead

    def list(self, params: BaseModel) -> tuple[Sequence[LogEntry], int]:
        assert isinstance(params, LogEntryListParams)
        stmt = select(LogEntry)
        if params.tag:
            stmt = stmt.where(LogEntry.tags.contains([params.tag]))
        if params.q:
            needle = f"%{params.q.strip().lstrip('#')}%"
            stmt = stmt.where(or_(LogEntry.title.ilike(needle), LogEntry.body.ilike(needle)))
        if params.day:
            start = params.day.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = stmt.where(LogEntry.occurred_at >= start, LogEntry.occurred_at < start + timedelta(days=1))
        rows = list(self.db.scalars(stmt.order_by(LogEntry.occurred_at.desc(), LogEntry.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def candidates(self, since_hours: int = 24) -> Sequence[LogCandidate]:
        """Drawn from finished tasks and approved actions. Suggestions only: the log is
        the owner's to write, and Enola never writes here on its own."""
        since = datetime.now(UTC) - timedelta(hours=since_hours)
        out: list[LogCandidate] = []
        done = self.db.scalars(
            select(Task).where(Task.state == TaskState.DONE, Task.completed_at.is_not(None), Task.completed_at >= since)
        ).all()
        for task in done:
            assert task.completed_at is not None
            tags = [f"#{link.label.lower()}" for link in task.links if link.label][:1] or ["#done"]
            out.append(LogCandidate(key=f"task:{task.id}", text=f"Finished “{task.title}”", source_label="tasks · completed", occurred_at=task.completed_at, tags=tags))
        approved = self.db.scalars(
            select(ActivityLog).where(ActivityLog.kind == ActivityKind.APPROVED, ActivityLog.created_at >= since)
        ).all()
        for row in approved:
            out.append(LogCandidate(key=f"activity:{row.id}", text=row.summary, source_label="approvals", occurred_at=row.created_at, tags=["#enola"]))
        existing_keys = {e.source_label for e in self.db.scalars(select(LogEntry).where(LogEntry.occurred_at >= since)).all()}
        out = [c for c in out if c.key not in existing_keys]
        out.sort(key=lambda c: c.occurred_at, reverse=True)
        return out
