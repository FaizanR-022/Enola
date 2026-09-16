from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import AssessmentKind, MilestoneState
from enola.core.models.base import Base, IdMixin, TimestampMixin, enum_column


class Course(Base, IdMixin, TimestampMixin):
    __tablename__ = "course"

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    instructor: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    schedule: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    room: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    term: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    is_fyp: Mapped[bool] = mapped_column(nullable=False, default=False)
    fyp_title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    fyp_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    assessments: Mapped[list[Assessment]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Assessment.due_at"
    )
    milestones: Mapped[list[FypMilestone]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="FypMilestone.sort_order"
    )


class Assessment(Base, IdMixin, TimestampMixin):
    """An assignment, quiz or exam. Every assessment also writes into `task` so one
    reminder pipeline covers everything; `task_id` is that row."""

    __tablename__ = "assessment"

    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[AssessmentKind] = enum_column(AssessmentKind, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    weight_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("task.id", ondelete="SET NULL"), unique=True)
    source_note: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    course: Mapped[Course] = relationship(back_populates="assessments")


class FypMilestone(Base, IdMixin, TimestampMixin):
    __tablename__ = "fyp_milestone"

    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[MilestoneState] = enum_column(MilestoneState, nullable=False, default=MilestoneState.UPCOMING)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    course: Mapped[Course] = relationship(back_populates="milestones")
