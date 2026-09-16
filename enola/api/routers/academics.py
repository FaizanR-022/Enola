from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.core.schemas.academics import (
    AssessmentCreate,
    AssessmentListParams,
    AssessmentRead,
    AssessmentUpdate,
    CourseCreate,
    CourseListParams,
    CourseRead,
    CourseUpdate,
    FypMilestoneCreate,
    FypMilestoneListParams,
    FypMilestoneRead,
    FypMilestoneUpdate,
)
from enola.core.services.academics import AssessmentService, CourseService, FypMilestoneService

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/courses",
        tag="courses",
        service_cls=CourseService,
        read_schema=CourseRead,
        create_schema=CourseCreate,
        update_schema=CourseUpdate,
        list_params=CourseListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/assessments",
        tag="assessments",
        service_cls=AssessmentService,
        read_schema=AssessmentRead,
        create_schema=AssessmentCreate,
        update_schema=AssessmentUpdate,
        list_params=AssessmentListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/fyp-milestones",
        tag="fyp_milestones",
        service_cls=FypMilestoneService,
        read_schema=FypMilestoneRead,
        create_schema=FypMilestoneCreate,
        update_schema=FypMilestoneUpdate,
        list_params=FypMilestoneListParams,
    )
)
