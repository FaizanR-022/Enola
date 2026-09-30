from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.infra import ActivityListParams, ActivityRead
from enola.core.schemas.journal import (
    LogCandidate,
    LogEntryCreate,
    LogEntryListParams,
    LogEntryRead,
    LogEntryUpdate,
)
from enola.core.services.activity import ActivityService
from enola.core.services.journal import LogEntryService

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/log",
        tag="log",
        service_cls=LogEntryService,
        read_schema=LogEntryRead,
        create_schema=LogEntryCreate,
        update_schema=LogEntryUpdate,
        list_params=LogEntryListParams,
    )
)


@router.get("/log-candidates", response_model=list[LogCandidate], tags=["log"], operation_id="log_candidates")
def candidates(db: DbSession, _: CurrentSession) -> list[LogCandidate]:
    return list(LogEntryService(db).candidates())


@router.get("/activity", response_model=list[ActivityRead], tags=["activity"], operation_id="activity_list")
def activity(db: DbSession, _: CurrentSession, limit: int = 50, since_hours: int | None = None) -> list[ActivityRead]:
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(hours=since_hours) if since_hours else None
    service = ActivityService(db)
    rows, _total = service.list(ActivityListParams(limit=limit, since=since))
    return [ActivityRead.model_validate(r) for r in rows]
