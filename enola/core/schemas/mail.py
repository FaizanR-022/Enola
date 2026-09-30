from __future__ import annotations

from datetime import datetime

from enola.core.enums import MailBucket
from enola.core.schemas.base import Schema


class MailMessageRead(Schema):
    uid: str
    who: str
    from_me: bool
    when: datetime
    body: str


class MailThreadRead(Schema):
    id: str
    subject: str
    from_name: str
    when: datetime
    message_count: int
    unread: bool
    bucket: MailBucket
    reason: str


class MailGroupRead(Schema):
    bucket: MailBucket
    label: str
    threads: list[MailThreadRead]


class MailInboxRead(Schema):
    enabled: bool
    # Why mail is unavailable, when it is. The screen says this rather than showing nothing.
    disabled_reason: str = ""
    account: str = ""
    fetched_at: datetime | None = None
    total_threads: int = 0
    groups: list[MailGroupRead] = []


class MailThreadDetail(Schema):
    id: str
    subject: str
    parties: str
    bucket: MailBucket
    reason: str
    message_count: int
    # Written by the utility model when one is available; empty otherwise, and the
    # screen falls back to the triage reason rather than showing an empty card.
    summary: str = ""
    messages: list[MailMessageRead]
