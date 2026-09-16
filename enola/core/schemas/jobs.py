from __future__ import annotations

from datetime import datetime

from pydantic import Field

from enola.core.enums import ActorSource, ApplicationEventKind, ApplicationStage, LocationKind, PostingStatus
from enola.core.schemas.base import ReadSchema, Schema, partial


class CompanyBase(Schema):
    name: str = Field(min_length=1, max_length=160)
    website: str = ""
    location: str = ""
    notes: str = ""


class CompanyCreate(CompanyBase):
    pass


CompanyUpdate = partial(CompanyBase, "CompanyUpdate")


class CompanyRead(CompanyBase, ReadSchema):
    pass


class CompanyListParams(Schema):
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ApplicationBase(Schema):
    company_id: int
    role_title: str = Field(min_length=1, max_length=200)
    stage: ApplicationStage = ApplicationStage.SAVED
    location_kind: LocationKind = LocationKind.REMOTE
    location_label: str = ""
    pay_label: str = ""
    posting_url: str = ""
    posting_summary: str = ""
    tags: list[str] = Field(default_factory=list)
    referral_person_id: int | None = None
    resume_version: str = ""
    resume_note: str = ""
    next_action: str = ""
    next_action_at: datetime | None = None
    applied_at: datetime | None = None
    closed_reason: str = ""


class ApplicationCreate(ApplicationBase):
    pass


ApplicationUpdate = partial(ApplicationBase, "ApplicationUpdate")


class ApplicationRead(ApplicationBase, ReadSchema):
    company_name: str
    referral_person_name: str | None
    last_activity_at: datetime | None
    days_quiet: int | None


class ApplicationListParams(Schema):
    stage: ApplicationStage | None = None
    company_id: int | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ApplicationEventBase(Schema):
    application_id: int
    kind: ApplicationEventKind
    summary: str = Field(min_length=1)
    occurred_at: datetime
    source: ActorSource = ActorSource.YOU


class ApplicationEventCreate(ApplicationEventBase):
    pass


ApplicationEventUpdate = partial(ApplicationEventBase, "ApplicationEventUpdate")


class ApplicationEventRead(ApplicationEventBase, ReadSchema):
    pass


class ApplicationEventListParams(Schema):
    application_id: int | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class JobPostingBase(Schema):
    company_name: str = Field(min_length=1, max_length=160)
    role_title: str = Field(min_length=1, max_length=200)
    url: str = ""
    location_kind: LocationKind = LocationKind.REMOTE
    location_label: str = ""
    pay_label: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    match_score: int | None = Field(default=None, ge=0, le=100)
    match_reason: str = ""
    status: PostingStatus = PostingStatus.DISCOVERED
    closes_at: datetime | None = None


class JobPostingCreate(JobPostingBase):
    pass


JobPostingUpdate = partial(JobPostingBase, "JobPostingUpdate")


class JobPostingRead(JobPostingBase, ReadSchema):
    dedupe_key: str
    discovered_at: datetime
    application_id: int | None


class JobPostingListParams(Schema):
    status: PostingStatus | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
