from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import ProjectStatus
from enola.core.models.base import JSONB, Base, IdMixin, TimestampMixin, enum_column

# "Remind me what this repo was." Deliberately shallow; this is not a code browser.


class Project(Base, IdMixin, TimestampMixin):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    repo_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    local_path: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    status: Mapped[ProjectStatus] = enum_column(ProjectStatus, nullable=False, default=ProjectStatus.ACTIVE, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stack: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    structure_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_touched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    snapshots: Mapped[list[ProjectSnapshot]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectSnapshot.taken_at.desc()"
    )


class ProjectSnapshot(Base, IdMixin):
    __tablename__ = "project_snapshot"

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[Project] = relationship(back_populates="snapshots")
