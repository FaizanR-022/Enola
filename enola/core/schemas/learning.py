from __future__ import annotations

from pydantic import Field

from enola.core.enums import LearningGoalState
from enola.core.schemas.base import ReadSchema, Schema, partial


class LearningResourceIn(Schema):
    label: str = Field(min_length=1, max_length=200)
    url: str = ""
    done: bool = False


class LearningResourceRead(LearningResourceIn):
    id: int


class LearningGoalBase(Schema):
    title: str = Field(min_length=1, max_length=200)
    gap_note: str = ""
    progress_pct: int = Field(default=0, ge=0, le=100)
    state: LearningGoalState = LearningGoalState.ACTIVE
    seeded_from_postings: bool = False


class LearningGoalCreate(LearningGoalBase):
    resources: list[LearningResourceIn] = Field(default_factory=list)


LearningGoalUpdate = partial(LearningGoalCreate, "LearningGoalUpdate")


class LearningGoalRead(LearningGoalBase, ReadSchema):
    resources: list[LearningResourceRead]


class LearningGoalListParams(Schema):
    state: LearningGoalState | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
