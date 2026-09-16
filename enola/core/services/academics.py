from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select

from enola.core.enums import EntityType, TaskSource
from enola.core.models.academics import Assessment, Course, FypMilestone
from enola.core.models.documents import Document, scope_key
from enola.core.models.tasks import Task, TaskLink
from enola.core.repository import Repository
from enola.core.schemas.academics import (
    AssessmentCreate,
    AssessmentRead,
    CourseCreate,
    CourseRead,
    FypMilestoneCreate,
    FypMilestoneRead,
)
from enola.core.services.base import CrudService


class CourseRepository(Repository[Course]):
    model = Course
    default_order = ("code",)


class CourseService(CrudService[Course, CourseCreate, BaseModel]):
    repo_cls = CourseRepository
    read_schema = CourseRead

    def to_read(self, row: Course) -> CourseRead:
        now = datetime.now(UTC)
        docs = self.db.scalar(select(func.count()).select_from(Document).where(Document.scope == scope_key(EntityType.COURSE, row.id))) or 0
        upcoming = [a for a in row.assessments if a.due_at >= now]
        next_due = upcoming[0] if upcoming else None
        label = f"{next_due.kind.value} {next_due.due_at.astimezone().strftime('%a %d %b')}" if next_due else "—"
        base = CourseCreate.model_validate(row).model_dump()
        return CourseRead(
            **base,
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            document_count=int(docs),
            assessment_count=len(row.assessments),
            next_due_at=next_due.due_at if next_due else None,
            next_due_label=label,
        )


class AssessmentRepository(Repository[Assessment]):
    model = Assessment
    default_order = ("due_at",)


def _task_title(course: Course, assessment: Assessment) -> str:
    return f"{assessment.kind.value.capitalize()}: {assessment.title}"


class AssessmentService(CrudService[Assessment, AssessmentCreate, BaseModel]):
    """Every assessment writes into `task` so one reminder pipeline covers everything.
    The task is created, kept in step and removed here, not in the router."""

    repo_cls = AssessmentRepository
    read_schema = AssessmentRead

    def create(self, data: AssessmentCreate) -> Assessment:
        assessment = self.repo.create(**data.model_dump())
        self._sync_task(assessment)
        return assessment

    def update(self, id_: int, data: BaseModel) -> Assessment:
        assessment = self.repo.update(id_, **data.model_dump(exclude_unset=True))
        self._sync_task(assessment)
        return assessment

    def delete(self, id_: int) -> None:
        assessment = self.repo.get(id_)
        task = self.db.get(Task, assessment.task_id) if assessment.task_id else None
        self.repo.delete(id_)
        if task is not None:
            self.db.delete(task)
            self.db.flush()

    def _sync_task(self, assessment: Assessment) -> None:
        course = self.db.get(Course, assessment.course_id)
        assert course is not None
        task = self.db.get(Task, assessment.task_id) if assessment.task_id else None
        if task is None:
            task = Task(source=TaskSource.ASSESSMENT, title=_task_title(course, assessment), due_at=assessment.due_at)
            self.db.add(task)
            self.db.flush()
            assessment.task_id = task.id
        task.title = _task_title(course, assessment)
        task.due_at = assessment.due_at
        wanted = {(EntityType.COURSE, course.id), (EntityType.ASSESSMENT, assessment.id)}
        have = {(link.entity_type, link.entity_id) for link in task.links}
        for entity_type, entity_id in wanted - have:
            label = course.code if entity_type == EntityType.COURSE else assessment.kind.value
            task.links.append(TaskLink(entity_type=entity_type, entity_id=entity_id, label=label))
        self.db.flush()

    def to_read(self, row: Assessment) -> Any:
        base = AssessmentCreate.model_validate(row).model_dump()
        return AssessmentRead(**base, id=row.id, created_at=row.created_at, updated_at=row.updated_at, task_id=row.task_id, course_code=row.course.code)


class FypMilestoneRepository(Repository[FypMilestone]):
    model = FypMilestone
    default_order = ("sort_order", "id")


class FypMilestoneService(CrudService[FypMilestone, FypMilestoneCreate, BaseModel]):
    repo_cls = FypMilestoneRepository
    read_schema = FypMilestoneRead
