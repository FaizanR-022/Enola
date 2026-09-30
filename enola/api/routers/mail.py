"""Email: read and triage only.

There is no send or draft endpoint here on purpose. Sending is a registered tool with
risk EXTERNAL, so it goes through the agent and lands in Approvals as Held. Adding a
direct route here would be a way around the gate.

An IMAP round trip over sixty messages takes seconds, so results are cached briefly in
process. The cache is per worker and dies with it; nothing about mail is persisted.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from typing_extensions import Annotated

from enola.agent.models import model_available
from enola.agent.utility import utility_complete
from enola.api.deps import CurrentSession, DbSession
from enola.core.config import get_settings
from enola.core.enums import MailBucket
from enola.core.errors import AgentUnavailableError
from enola.core.schemas.mail import MailGroupRead, MailInboxRead, MailMessageRead, MailThreadDetail, MailThreadRead
from enola.core.services.mail_triage import TriagedThread, triage
from enola.ingest.mail import DISABLED, fetch_recent, group_threads

router = APIRouter(prefix="/email", tags=["email"])

CACHE_TTL_SECONDS = 180
LABELS = {MailBucket.NEEDS_YOU: "Needs you", MailBucket.ONGOING: "Ongoing threads", MailBucket.WORTH_KNOWING: "Worth knowing"}


def thread_id(key: str) -> str:
    """A stable, URL-safe id for a thread. The key is a subject line, which is not."""
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


SUMMARISE = """Summarise this email thread for its owner in two or three sentences.
Say where it stands and what, if anything, is waiting on them. Plain prose, no preamble,
no bullet points. If nothing is waiting on them, say so."""


@dataclass
class _Cached:
    at: float
    fetched_at: datetime
    items: list[TriagedThread]
    # Summaries cost a model call, so they are written once per fetch window.
    summaries: dict[str, str] = field(default_factory=dict)


_cache: _Cached | None = None


def _load(db: DbSession, *, refresh: bool) -> _Cached:
    global _cache
    if _cache and not refresh and (time.monotonic() - _cache.at) < CACHE_TTL_SECONDS:
        return _cache
    threads = group_threads(fetch_recent(limit=60))
    _cache = _Cached(at=time.monotonic(), fetched_at=datetime.now(UTC), items=triage(db, threads))
    return _cache


def _to_read(item: TriagedThread) -> MailThreadRead:
    latest = item.thread.latest
    return MailThreadRead(
        id=thread_id(item.thread.key),
        subject=item.thread.subject,
        from_name="You" if latest.from_me else latest.sender.label,
        when=latest.date,
        message_count=len(item.thread.messages),
        unread=item.thread.unread,
        bucket=item.bucket,
        reason=item.reason,
    )


@router.get("/threads", response_model=MailInboxRead, operation_id="email_threads")
def list_threads(db: DbSession, _: CurrentSession, refresh: Annotated[bool, Query()] = False) -> MailInboxRead:
    settings = get_settings()
    if not settings.imap_enabled:
        return MailInboxRead(enabled=False, disabled_reason=DISABLED)
    try:
        cached = _load(db, refresh=refresh)
    except AgentUnavailableError as exc:
        return MailInboxRead(enabled=False, disabled_reason=str(exc))
    groups = [
        MailGroupRead(bucket=bucket, label=LABELS[bucket], threads=[_to_read(i) for i in cached.items if i.bucket is bucket])
        for bucket in (MailBucket.NEEDS_YOU, MailBucket.ONGOING, MailBucket.WORTH_KNOWING)
    ]
    return MailInboxRead(
        enabled=True,
        account=settings.mail_user,
        fetched_at=cached.fetched_at,
        total_threads=len(cached.items),
        groups=groups,
    )


def _summarise(db: DbSession, cached: _Cached, item: TriagedThread, item_id: str) -> str:
    """One call per thread per fetch window. Failure is silent: the screen falls back
    to the triage reason, which is always present."""
    if item_id in cached.summaries:
        return cached.summaries[item_id]
    if not model_available():
        return ""
    parts = [
        f"{'You' if m.from_me else m.sender.label} ({m.date:%d %b %H:%M}):\n{m.body[:1200]}"
        for m in item.thread.messages[:6]
    ]
    transcript = "\n\n".join(parts)
    try:
        text = utility_complete(
            db,
            instructions=SUMMARISE,
            text=f"Subject: {item.thread.subject}\n\n{transcript}",
            purpose="mail_summary",
        )
    except Exception:
        return ""
    cached.summaries[item_id] = text
    return text


@router.get("/threads/{item_id}", response_model=MailThreadDetail, operation_id="email_thread")
def get_thread(item_id: str, db: DbSession, _: CurrentSession) -> MailThreadDetail:
    cached = _load(db, refresh=False)
    for item in cached.items:
        if thread_id(item.thread.key) != item_id:
            continue
        return MailThreadDetail(
            id=item_id,
            subject=item.thread.subject,
            parties=" · ".join(item.thread.participants),
            bucket=item.bucket,
            reason=item.reason,
            message_count=len(item.thread.messages),
            summary=_summarise(db, cached, item, item_id),
            messages=[
                MailMessageRead(uid=m.uid, who="You" if m.from_me else m.sender.label, from_me=m.from_me, when=m.date, body=m.body)
                for m in item.thread.messages
            ],
        )
    raise HTTPException(status_code=404, detail="Thread not found in the current inbox window.")
