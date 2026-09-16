from __future__ import annotations

from fastapi import APIRouter, Query

from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.dashboard import DashboardRead, SearchHit
from enola.core.services.dashboard import build_dashboard, search

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardRead, operation_id="dashboard")
def dashboard(db: DbSession, _: CurrentSession) -> DashboardRead:
    return build_dashboard(db)


@router.get("/search", response_model=list[SearchHit], operation_id="search")
def global_search(db: DbSession, _: CurrentSession, q: str = Query(min_length=1, max_length=200)) -> list[SearchHit]:
    return search(db, q)
