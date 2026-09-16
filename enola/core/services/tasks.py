from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from enola.core.enums import TaskState
from enola.core.models.tasks import Task, TaskLink
from enola.core.repository import Repository
from enola.core.schemas.tasks import TaskCreate, TaskListParams, TaskRead
from enola.core.services.base import CrudService


class TaskRepository(Repository[Task]):
    model = Task
    default_order = ("due_at", "-id")


class TaskService(CrudService[Task, TaskCreate, BaseModel]):
    repo_cls = TaskRepository
    read_schema = TaskRead

    def list(self, params: BaseModel) -> tuple[Sequence[Task], int]:
        assert isinstance(params, TaskListParams)
        stmt = select(Task)
        if params.state is not None:
            stmt = stmt.where(Task.state == params.state)
        if params.due_before is not None:
            stmt = stmt.where(Task.due_at <= params.due_before)
        if params.due_after is not None:
            stmt = stmt.where(Task.due_at >= params.due_after)
        if params.entity_type is not None:
            link = select(TaskLink.task_id).where(TaskLink.entity_type == params.entity_type)
            if params.entity_id is not None:
                link = link.where(TaskLink.entity_id == params.entity_id)
            stmt = stmt.where(Task.id.in_(link))
        rows = list(self.db.scalars(stmt.order_by(Task.due_at.asc().nulls_last(), Task.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def create(self, data: TaskCreate) -> Task:
        values = data.model_dump(exclude={"links"})
        if values.get("state") == TaskState.DONE:
            values["completed_at"] = datetime.now(UTC)
        task = self.repo.create(**values)
        task.links = [TaskLink(**link.model_dump()) for link in data.links]
        self.db.flush()
        return task

    def update(self, id_: int, data: BaseModel) -> Task:
        values = data.model_dump(exclude_unset=True)
        links = values.pop("links", None)
        task = self.repo.get(id_)
        new_state = values.get("state")
        if new_state is not None and new_state != task.state:
            values["completed_at"] = datetime.now(UTC) if new_state == TaskState.DONE else None
        task = self.repo.update(id_, **values)
        if links is not None:
            task.links = [TaskLink(**link) for link in links]
            self.db.flush()
        return task

    def set_state(self, id_: int, state: TaskState) -> Task:
        task = self.repo.get(id_)
        task.state = state
        task.completed_at = datetime.now(UTC) if state == TaskState.DONE else None
        self.db.flush()
        return task

    def due_by(self, until: datetime, *, limit: int = 20) -> Sequence[Task]:
        stmt = (
            select(Task)
            .where(Task.state == TaskState.OPEN, Task.due_at.is_not(None), Task.due_at <= until)
            .order_by(Task.due_at.asc())
            .limit(limit)
        )
        return self.db.scalars(stmt).all()

    def to_read(self, row: Task) -> Any:
        return TaskRead.model_validate(row)
