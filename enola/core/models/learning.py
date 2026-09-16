from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import LearningGoalState
from enola.core.models.base import Base, IdMixin, TimestampMixin, enum_column


class LearningGoal(Base, IdMixin, TimestampMixin):
    __tablename__ = "learning_goal"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Where the gap came from: "Surfaced from 4 saved postings, including Marrow."
    gap_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[LearningGoalState] = enum_column(LearningGoalState, nullable=False, default=LearningGoalState.ACTIVE)
    seeded_from_postings: Mapped[bool] = mapped_column(nullable=False, default=False)

    resources: Mapped[list[LearningResource]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="LearningResource.id"
    )


class LearningResource(Base, IdMixin, TimestampMixin):
    __tablename__ = "learning_resource"

    goal_id: Mapped[int] = mapped_column(ForeignKey("learning_goal.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    done: Mapped[bool] = mapped_column(nullable=False, default=False)

    goal: Mapped[LearningGoal] = relationship(back_populates="resources")
