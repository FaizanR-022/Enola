from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

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
from enola.core.schemas.base import ReadSchema, Schema, partial


class MemoryFactBase(Schema):
    group: str = "About you"
    statement: str = Field(min_length=1)
    source: MemorySource = MemorySource.TOLD
    evidence: str = ""
    confidence: int = Field(default=100, ge=0, le=100)
    locked: bool = False


class MemoryFactCreate(MemoryFactBase):
    pass


MemoryFactUpdate = partial(MemoryFactBase, "MemoryFactUpdate")


class MemoryFactRead(MemoryFactBase, ReadSchema):
    state: MemoryState
    thread_id: str | None
    corrected_at: datetime | None


class MemoryFactListParams(Schema):
    state: MemoryState | None = None
    group: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ApprovalRead(Schema):
    id: int
    thread_id: str
    checkpoint_id: str | None
    run_id: str
    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    rationale: str
    risk: Risk
    state: ApprovalState
    payload_preview: str
    job_label: str
    step_labels: list[str]
    step_index: int
    resolution_note: str
    created_at: datetime
    resolved_at: datetime | None


class ApprovalListParams(Schema):
    state: ApprovalState | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ApprovalDecision(Schema):
    """Approve (optionally with edited args) or reject with a reason."""

    args: dict[str, Any] | None = None
    note: str = ""


class NotificationRead(Schema):
    id: int
    kind: NotificationKind
    channel: NotificationChannel
    state: NotificationState
    title: str
    body: str
    entity_type: EntityType | None
    entity_id: int | None
    scheduled_for: datetime
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class NotificationListParams(Schema):
    state: NotificationState | None = None
    kind: NotificationKind | None = None
    channel: NotificationChannel | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ActivityRead(Schema):
    id: int
    run_id: str | None
    thread_id: str | None
    kind: ActivityKind
    tool_name: str
    risk: Risk | None
    summary: str
    detail: dict[str, Any]
    created_at: datetime


class ActivityListParams(Schema):
    kind: ActivityKind | None = None
    run_id: str | None = None
    since: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
