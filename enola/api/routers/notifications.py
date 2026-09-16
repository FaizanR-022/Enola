from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.base import Page
from enola.core.schemas.infra import NotificationListParams, NotificationRead
from enola.core.services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


class BadgeCount(BaseModel):
    unread: int


class MarkedRead(BaseModel):
    marked: int


@router.get("", response_model=Page[NotificationRead], operation_id="notifications_list")
def list_notifications(params: Annotated[NotificationListParams, Query()], db: DbSession, _: CurrentSession) -> Page[NotificationRead]:
    rows, total = NotificationService(db).list(params)
    return Page[NotificationRead](items=[NotificationRead.model_validate(r) for r in rows], total=total)


@router.get("/badge", response_model=BadgeCount, operation_id="notifications_badge")
def badge(db: DbSession, _: CurrentSession) -> BadgeCount:
    return BadgeCount(unread=NotificationService(db).badge_count())


@router.post("/{notification_id}/read", response_model=NotificationRead, operation_id="notifications_read")
def mark_read(notification_id: int, db: DbSession, _: CurrentSession) -> NotificationRead:
    return NotificationRead.model_validate(NotificationService(db).mark_read(notification_id))


@router.post("/read-all", response_model=MarkedRead, operation_id="notifications_read_all")
def mark_all_read(db: DbSession, _: CurrentSession) -> MarkedRead:
    return MarkedRead(marked=NotificationService(db).mark_all_read())
