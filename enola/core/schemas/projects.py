from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from enola.core.enums import ProjectStatus
from enola.core.schemas.base import ReadSchema, Schema, partial


class ProjectBase(Schema):
    name: str = Field(min_length=1, max_length=120)
    repo_url: str = ""
    local_path: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    summary: str = ""
    stack: list[str] = Field(default_factory=list)
    structure_summary: str = ""
    last_touched_at: datetime | None = None


class ProjectCreate(ProjectBase):
    pass


ProjectUpdate = partial(ProjectBase, "ProjectUpdate")


class ProjectRead(ProjectBase, ReadSchema):
    linked_task_count: int


class ProjectListParams(Schema):
    status: ProjectStatus | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ProjectSnapshotRead(Schema):
    id: int
    project_id: int
    taken_at: datetime
    summary: str
    stats: dict[str, Any]
