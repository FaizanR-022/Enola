from __future__ import annotations

from datetime import datetime

from pydantic import Field

from enola.core.enums import EntityType, TaskPriority, TaskSource, TaskState
from enola.core.schemas.base import ReadSchema, Schema, partial


class TaskLinkIn(Schema):
    entity_type: EntityType
    entity_id: int
    label: str = ""


class TaskLinkRead(TaskLinkIn):
    id: int


class TaskBase(Schema):
    title: str = Field(min_length=1, max_length=300)
    notes: str = ""
    state: TaskState = TaskState.OPEN
    priority: TaskPriority = TaskPriority.NORMAL
    due_at: datetime | None = None
    source: TaskSource = TaskSource.YOU


class TaskCreate(TaskBase):
    links: list[TaskLinkIn] = Field(default_factory=list)


TaskUpdate = partial(TaskCreate, "TaskUpdate")


class TaskRead(TaskBase, ReadSchema):
    completed_at: datetime | None
    links: list[TaskLinkRead]


class TaskListParams(Schema):
    state: TaskState | None = None
    due_before: datetime | None = None
    due_after: datetime | None = None
    entity_type: EntityType | None = None
    entity_id: int | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
