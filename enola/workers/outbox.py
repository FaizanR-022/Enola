"""The notification outbox.

Jobs never deliver anything themselves: they `enqueue()` rows, one per channel, keyed
so the same reminder is never queued twice for the same day. `deliver_due()` hands
queued rows to the channel that owns them. Adding web push later is a new Channel
class and one line in CHANNELS; nothing else changes.
"""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.enums import EntityType, NotificationChannel, NotificationKind, NotificationState
from enola.core.logging import get_logger
from enola.core.models.infra import Notification

log = get_logger(__name__)


class Channel(Protocol):
    name: NotificationChannel

    def deliver(self, notification: Notification) -> None:
        """Deliver or raise. The outbox records the outcome; the channel does not."""


class InAppChannel:
    """The row itself is the delivery: the badge and the dashboard read it."""

    name = NotificationChannel.IN_APP

    def deliver(self, notification: Notification) -> None:
        return None


class EmailToSelfChannel:
    name = NotificationChannel.EMAIL

    def deliver(self, notification: Notification) -> None:
        settings = get_settings()
        if not settings.smtp_enabled:
            raise ChannelNotConfigured("SMTP is not configured (ENOLA_SMTP_HOST / ENOLA_SMTP_FROM).")
        message = EmailMessage()
        message["Subject"] = f"[enola] {notification.title}"
        message["From"] = settings.smtp_from
        message["To"] = settings.owner_email
        message.set_content(notification.body or notification.title)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)


class ChannelNotConfigured(Exception):
    """The channel exists but cannot deliver yet; the row stays queued, not failed."""


CHANNELS: dict[NotificationChannel, Channel] = {
    NotificationChannel.IN_APP: InAppChannel(),
    NotificationChannel.EMAIL: EmailToSelfChannel(),
}

DEFAULT_CHANNELS: tuple[NotificationChannel, ...] = (NotificationChannel.IN_APP, NotificationChannel.EMAIL)


def enqueue(
    db: Session,
    *,
    kind: NotificationKind,
    title: str,
    body: str,
    dedupe_key: str,
    scheduled_for: datetime | None = None,
    entity_type: EntityType | None = None,
    entity_id: int | None = None,
    channels: tuple[NotificationChannel, ...] = DEFAULT_CHANNELS,
) -> list[Notification]:
    """Queue one row per channel. Rows whose (dedupe_key, channel) already exist are skipped."""
    when = scheduled_for or datetime.now(UTC)
    created: list[Notification] = []
    for channel in channels:
        key = f"{dedupe_key}|{channel.value}"
        if db.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None:
            continue
        row = Notification(
            kind=kind,
            channel=channel,
            state=NotificationState.QUEUED,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=key,
            scheduled_for=when,
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def deliver_due(db: Session, *, now: datetime | None = None, limit: int = 200) -> dict[str, int]:
    """Deliver every queued row whose time has come. Returns counts per outcome."""
    now = now or datetime.now(UTC)
    rows = db.scalars(
        select(Notification)
        .where(Notification.state == NotificationState.QUEUED, Notification.scheduled_for <= now)
        .order_by(Notification.scheduled_for)
        .limit(limit)
    ).all()
    counts = {"sent": 0, "failed": 0, "waiting": 0}
    for row in rows:
        channel = CHANNELS.get(row.channel)
        if channel is None:
            row.state = NotificationState.FAILED
            row.error = f"No channel registered for {row.channel.value}"
            counts["failed"] += 1
            continue
        try:
            channel.deliver(row)
        except ChannelNotConfigured as exc:
            row.error = str(exc)
            counts["waiting"] += 1
            continue
        except Exception as exc:
            row.state = NotificationState.FAILED
            row.error = str(exc)[:500]
            counts["failed"] += 1
            log.warning("notification_failed", id=row.id, channel=row.channel.value, error=str(exc))
            continue
        row.state = NotificationState.SENT
        row.sent_at = now
        row.error = ""
        counts["sent"] += 1
    db.flush()
    return counts
