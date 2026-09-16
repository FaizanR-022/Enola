from __future__ import annotations

from datetime import datetime

from pydantic import Field

from enola.core.enums import ActorSource
from enola.core.schemas.base import ReadSchema, Schema, partial


class LogEntryBase(Schema):
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    occurred_at: datetime
    source: ActorSource = ActorSource.YOU
    source_label: str = "you"


class LogEntryCreate(LogEntryBase):
    pass


LogEntryUpdate = partial(LogEntryBase, "LogEntryUpdate")


class LogEntryRead(LogEntryBase, ReadSchema):
    pass


class LogEntryListParams(Schema):
    tag: str | None = None
    q: str | None = None
    day: datetime | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class LogCandidate(Schema):
    """Something Enola noticed that could become an entry. Suggestion only."""

    key: str
    text: str
    source_label: str
    occurred_at: datetime
    tags: list[str]
