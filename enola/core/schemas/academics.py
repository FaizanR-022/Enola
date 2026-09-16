from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from enola.core.enums import AssessmentKind, MilestoneState
from enola.core.schemas.base import ReadSchema, Schema, partial


class CourseBase(Schema):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=160)
    instructor: str = ""
    schedule: str = ""
    room: str = ""
    term: str = ""
    is_fyp: bool = False
    fyp_title: str = ""
    fyp_note: str = ""


class CourseCreate(CourseBase):
    pass


CourseUpdate = partial(CourseBase, "CourseUpdate")


class CourseRead(CourseBase, ReadSchema):
    document_count: int
    assessment_count: int
    next_due_at: datetime | None
    next_due_label: str


class CourseListParams(Schema):
    term: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AssessmentBase(Schema):
    course_id: int
    kind: AssessmentKind
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime
    weight_pct: Decimal | None = None
    source_note: str = ""


class AssessmentCreate(AssessmentBase):
    pass


AssessmentUpdate = partial(AssessmentBase, "AssessmentUpdate")


class AssessmentRead(AssessmentBase, ReadSchema):
    task_id: int | None
    course_code: str


class AssessmentListParams(Schema):
    course_id: int | None = None
    due_after: datetime | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class FypMilestoneBase(Schema):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    note: str = ""
    due_at: datetime | None = None
    state: MilestoneState = MilestoneState.UPCOMING
    sort_order: int = 0


class FypMilestoneCreate(FypMilestoneBase):
    pass


FypMilestoneUpdate = partial(FypMilestoneBase, "FypMilestoneUpdate")


class FypMilestoneRead(FypMilestoneBase, ReadSchema):
    pass


class FypMilestoneListParams(Schema):
    course_id: int | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
