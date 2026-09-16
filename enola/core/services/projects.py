from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import func, select

from enola.core.enums import EntityType
from enola.core.models.projects import Project
from enola.core.models.tasks import TaskLink
from enola.core.repository import Repository
from enola.core.schemas.projects import ProjectCreate, ProjectRead
from enola.core.services.base import CrudService


class ProjectRepository(Repository[Project]):
    model = Project
    default_order = ("-last_touched_at", "name")


class ProjectService(CrudService[Project, ProjectCreate, BaseModel]):
    repo_cls = ProjectRepository
    read_schema = ProjectRead

    def to_read(self, row: Project) -> ProjectRead:
        linked = (
            self.db.scalar(
                select(func.count()).select_from(TaskLink).where(TaskLink.entity_type == EntityType.PROJECT, TaskLink.entity_id == row.id)
            )
            or 0
        )
        base = ProjectCreate.model_validate(row).model_dump()
        return ProjectRead(**base, id=row.id, created_at=row.created_at, updated_at=row.updated_at, linked_task_count=int(linked))
