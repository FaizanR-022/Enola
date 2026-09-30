from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select

from enola.core.enums import NotificationChannel, NotificationKind, NotificationState
from enola.core.models.infra import Notification
from enola.core.repository import Repository
from enola.core.schemas.infra import NotificationListParams, NotificationRead
from enola.core.services.base import CrudService

# What the dashboard and the badge count as a reminder. Cold contacts are deliberately
# absent: the dashboard already shows them under "Going cold", and People owns them.
REMINDER_KINDS = (NotificationKind.TASK_DUE, NotificationKind.ACADEMIC_DEADLINE, NotificationKind.THREAD_QUIET, NotificationKind.HELD)


class NotificationRepository(Repository[Notification]):
    model = Notification
    default_order = ("-scheduled_for",)


class NotificationService(CrudService[Notification, BaseModel, BaseModel]):
    repo_cls = NotificationRepository
    read_schema = NotificationRead

    def list(self, params: BaseModel) -> tuple[Sequence[Notification], int]:
        assert isinstance(params, NotificationListParams)
        stmt = select(Notification)
        if params.state is not None:
            stmt = stmt.where(Notification.state == params.state)
        if params.kind is not None:
            stmt = stmt.where(Notification.kind == params.kind)
        if params.channel is not None:
            stmt = stmt.where(Notification.channel == params.channel)
        rows = list(self.db.scalars(stmt.order_by(Notification.scheduled_for.desc(), Notification.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def unread_in_app(self, *, limit: int = 20) -> Sequence[Notification]:
        return (
            self.db.scalars(
                select(Notification)
                .where(
                    Notification.channel == NotificationChannel.IN_APP,
                    Notification.kind.in_(REMINDER_KINDS),
                    Notification.read_at.is_(None),
                    Notification.state != NotificationState.FAILED,
                )
                .order_by(Notification.scheduled_for.desc())
                .limit(limit)
            ).all()
        )

    def badge_count(self) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.channel == NotificationChannel.IN_APP,
                    Notification.kind.in_(REMINDER_KINDS),
                    Notification.read_at.is_(None),
                    Notification.state != NotificationState.FAILED,
                )
            )
            or 0
        )

    def mark_read(self, id_: int) -> Notification:
        row = self.repo.get(id_)
        if row.read_at is None:
            row.read_at = datetime.now(UTC)
            if row.state == NotificationState.SENT:
                row.state = NotificationState.READ
            self.db.flush()
        return row

    def mark_all_read(self) -> int:
        rows = self.unread_in_app(limit=500)
        now = datetime.now(UTC)
        for row in rows:
            row.read_at = now
            if row.state == NotificationState.SENT:
                row.state = NotificationState.READ
        self.db.flush()
        return len(rows)
