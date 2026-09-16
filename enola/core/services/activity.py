from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.enums import ActivityKind, Risk
from enola.core.models.infra import ActivityLog
from enola.core.repository import Repository
from enola.core.schemas.infra import ActivityListParams, ActivityRead
from enola.core.services.base import CrudService


class ActivityRepository(Repository[ActivityLog]):
    model = ActivityLog
    default_order = ("-created_at", "-id")


def record_activity(
    db: Session,
    *,
    kind: ActivityKind,
    summary: str,
    run_id: str | None = None,
    thread_id: str | None = None,
    tool_name: str = "",
    risk: Risk | None = None,
    detail: dict[str, Any] | None = None,
) -> ActivityLog:
    """The one way anything gets into activity_log."""
    row = ActivityLog(
        kind=kind,
        summary=summary,
        run_id=run_id,
        thread_id=thread_id,
        tool_name=tool_name,
        risk=risk,
        detail=detail or {},
    )
    db.add(row)
    db.flush()
    return row


class ActivityService(CrudService[ActivityLog, BaseModel, BaseModel]):
    repo_cls = ActivityRepository
    read_schema = ActivityRead

    def list(self, params: BaseModel) -> tuple[Sequence[ActivityLog], int]:
        assert isinstance(params, ActivityListParams)
        stmt = select(ActivityLog)
        if params.kind is not None:
            stmt = stmt.where(ActivityLog.kind == params.kind)
        if params.run_id is not None:
            stmt = stmt.where(ActivityLog.run_id == params.run_id)
        if params.since is not None:
            stmt = stmt.where(ActivityLog.created_at >= params.since)
        rows = list(self.db.scalars(stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)
