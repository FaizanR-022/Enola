from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from enola.core.enums import (
    ActivityKind,
    ApprovalState,
    EntityType,
    MemorySource,
    MemoryState,
    NotificationChannel,
    NotificationKind,
    NotificationState,
    Risk,
)
from enola.core.models.base import JSONB, Base, IdMixin, TimestampMixin, enum_column


class UserSession(Base, IdMixin):
    """A browser session. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "user_session"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class MemoryFact(Base, IdMixin, TimestampMixin):
    """A durable statement about the owner, with where it came from and how sure Enola is."""

    __tablename__ = "memory_fact"

    group: Mapped[str] = mapped_column(String(80), nullable=False, default="About you", index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[MemorySource] = enum_column(MemorySource, nullable=False, default=MemorySource.TOLD)
    evidence: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    state: Mapped[MemoryState] = enum_column(MemoryState, nullable=False, default=MemoryState.ACTIVE, index=True)
    # Locked facts are standing rules ("never send anything outbound without approval").
    locked: Mapped[bool] = mapped_column(nullable=False, default=False)
    thread_id: Mapped[str | None] = mapped_column(String(80))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalRequest(Base, IdMixin):
    """A gated tool call paused mid-run. The word for this state is Held, everywhere."""

    __tablename__ = "approval_request"
    __table_args__ = (UniqueConstraint("thread_id", "tool_call_id"),)

    thread_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(80))
    run_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tool_call_id: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk: Mapped[Risk] = enum_column(Risk, nullable=False)
    state: Mapped[ApprovalState] = enum_column(ApprovalState, nullable=False, default=ApprovalState.HELD, index=True)
    payload_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # What the larger job is and where it stopped, so the UI can show "step 3 of 4".
    job_label: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    step_labels: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base, IdMixin):
    """The outbox. Jobs write rows; delivery channels read them."""

    __tablename__ = "notification"

    kind: Mapped[NotificationKind] = enum_column(NotificationKind, nullable=False, index=True)
    channel: Mapped[NotificationChannel] = enum_column(NotificationChannel, nullable=False)
    state: Mapped[NotificationState] = enum_column(NotificationState, nullable=False, default=NotificationState.QUEUED, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    entity_type: Mapped[EntityType | None] = enum_column(EntityType)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    # One reminder per (kind, entity, day, channel); the job computes this key.
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActivityLog(Base, IdMixin):
    """What Enola did. Never notifies; collects here for the dashboard and the Log."""

    __tablename__ = "activity_log"

    run_id: Mapped[str | None] = mapped_column(String(40), index=True)
    thread_id: Mapped[str | None] = mapped_column(String(80))
    kind: Mapped[ActivityKind] = enum_column(ActivityKind, nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    risk: Mapped[Risk | None] = enum_column(Risk)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
