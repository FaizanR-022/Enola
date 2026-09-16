from __future__ import annotations

from datetime import datetime

from enola.core.schemas.base import Schema
from enola.core.schemas.infra import ActivityRead, NotificationRead
from enola.core.schemas.people import PersonRead
from enola.core.schemas.tasks import TaskRead


class HeldSummary(Schema):
    count: int
    summary: str
    oldest_created_at: datetime | None


class TodayItem(Schema):
    when: datetime
    time_label: str
    title: str
    sub: str
    path: str


class DashboardRead(Schema):
    date_label: str
    needs_you: int
    headline: str
    held: HeldSummary
    today: list[TodayItem]
    due: list[TaskRead]
    going_cold: list[PersonRead]
    activity: list[ActivityRead]
    brief: NotificationRead | None
    reminders: list[NotificationRead]


class SearchHit(Schema):
    group: str
    label: str
    meta: str
    path: str
    dot: str
