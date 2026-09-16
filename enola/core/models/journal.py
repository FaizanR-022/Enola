from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from enola.core.enums import ActorSource
from enola.core.models.base import JSONB, Base, IdMixin, TimestampMixin, enum_column


class LogEntry(Base, IdMixin, TimestampMixin):
    """The owner's journal: what actually happened, in their words. Enola only suggests
    entries (drawn from activity_log and finished tasks); it never writes here itself."""

    __tablename__ = "log_entry"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # "you" for hand-written, otherwise the accepted suggestion's origin (tasks, approvals…).
    source: Mapped[ActorSource] = enum_column(ActorSource, nullable=False, default=ActorSource.YOU)
    source_label: Mapped[str] = mapped_column(String(80), nullable=False, default="you")
