from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.jobs import (
    ApplicationCreate,
    ApplicationEventCreate,
    ApplicationEventListParams,
    ApplicationEventRead,
    ApplicationEventUpdate,
    ApplicationListParams,
    ApplicationRead,
    ApplicationUpdate,
    CompanyCreate,
    CompanyListParams,
    CompanyRead,
    CompanyUpdate,
    JobPostingCreate,
    JobPostingListParams,
    JobPostingRead,
    JobPostingUpdate,
)
from enola.core.services.jobs import (
    ApplicationEventService,
    ApplicationService,
    CompanyService,
    JobPostingService,
)

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/companies",
        tag="companies",
        service_cls=CompanyService,
        read_schema=CompanyRead,
        create_schema=CompanyCreate,
        update_schema=CompanyUpdate,
        list_params=CompanyListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/applications",
        tag="applications",
        service_cls=ApplicationService,
        read_schema=ApplicationRead,
        create_schema=ApplicationCreate,
        update_schema=ApplicationUpdate,
        list_params=ApplicationListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/application-events",
        tag="application_events",
        service_cls=ApplicationEventService,
        read_schema=ApplicationEventRead,
        create_schema=ApplicationEventCreate,
        update_schema=ApplicationEventUpdate,
        list_params=ApplicationEventListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/postings",
        tag="postings",
        service_cls=JobPostingService,
        read_schema=JobPostingRead,
        create_schema=JobPostingCreate,
        update_schema=JobPostingUpdate,
        list_params=JobPostingListParams,
    )
)


@router.post("/postings/{posting_id}/pull", response_model=ApplicationRead, tags=["postings"], operation_id="postings_pull")
def pull_into_pipeline(posting_id: int, db: DbSession, _: CurrentSession) -> ApplicationRead:
    app = JobPostingService(db).pull_into_pipeline(posting_id)
    return ApplicationService(db).to_read(app)
