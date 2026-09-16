from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import ActorSource, ApplicationEventKind, ApplicationStage, LocationKind, PostingStatus
from enola.core.models.base import JSONB, Base, IdMixin, TimestampMixin, enum_column


class Company(Base, IdMixin, TimestampMixin):
    __tablename__ = "company"

    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    website: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    applications: Mapped[list[Application]] = relationship(back_populates="company")


class Application(Base, IdMixin, TimestampMixin):
    __tablename__ = "application"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[ApplicationStage] = enum_column(ApplicationStage, nullable=False, default=ApplicationStage.SAVED, index=True)
    location_kind: Mapped[LocationKind] = enum_column(LocationKind, nullable=False, default=LocationKind.REMOTE)
    location_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    pay_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    posting_url: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    posting_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    referral_person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id", ondelete="SET NULL"))
    resume_version: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    resume_note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    next_action: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped by every event; the follow-up nudge job reads this to find quiet threads.
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    closed_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    company: Mapped[Company] = relationship(back_populates="applications")
    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.occurred_at.desc()"
    )


class ApplicationEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "application_event"

    application_id: Mapped[int] = mapped_column(ForeignKey("application.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[ApplicationEventKind] = enum_column(ApplicationEventKind, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[ActorSource] = enum_column(ActorSource, nullable=False, default=ActorSource.YOU)

    application: Mapped[Application] = relationship(back_populates="events")


class JobPosting(Base, IdMixin, TimestampMixin):
    """A posting Enola found or the owner pasted, before it becomes an application."""

    __tablename__ = "job_posting"

    company_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    # Normalised company+role, used to stop the same posting surfacing twice.
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    location_kind: Mapped[LocationKind] = enum_column(LocationKind, nullable=False, default=LocationKind.REMOTE)
    location_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    pay_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    match_score: Mapped[int | None] = mapped_column(Integer)
    match_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[PostingStatus] = enum_column(PostingStatus, nullable=False, default=PostingStatus.DISCOVERED, index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("application.id", ondelete="SET NULL"))
