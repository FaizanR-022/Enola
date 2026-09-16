from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import EntityType, TaskPriority, TaskSource, TaskState
from enola.core.models.base import Base, IdMixin, TimestampMixin, enum_column


class Task(Base, IdMixin, TimestampMixin):
    __tablename__ = "task"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[TaskState] = enum_column(TaskState, nullable=False, default=TaskState.OPEN, index=True)
    priority: Mapped[TaskPriority] = enum_column(TaskPriority, nullable=False, default=TaskPriority.NORMAL)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[TaskSource] = enum_column(TaskSource, nullable=False, default=TaskSource.YOU)

    links: Mapped[list[TaskLink]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskLink(Base, IdMixin):
    """Polymorphic link from a task to the thing it is about (project, course, application…)."""

    __tablename__ = "task_link"

    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[EntityType] = enum_column(EntityType, nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    # Short display label ("kestrel", "CS-421") so lists do not need a join per row.
    label: Mapped[str] = mapped_column(String(60), nullable=False, default="")

    task: Mapped[Task] = relationship(back_populates="links")
