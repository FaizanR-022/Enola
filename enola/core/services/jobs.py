from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from enola.core.enums import ActorSource, ApplicationEventKind, ApplicationStage, PostingStatus
from enola.core.errors import ConflictError, InvalidInputError
from enola.core.models.jobs import Application, ApplicationEvent, Company, JobPosting
from enola.core.models.people import Person
from enola.core.repository import Repository
from enola.core.schemas.jobs import (
    ApplicationCreate,
    ApplicationEventCreate,
    ApplicationEventRead,
    ApplicationRead,
    CompanyCreate,
    CompanyRead,
    JobPostingCreate,
    JobPostingRead,
)
from enola.core.services.base import CrudService


class CompanyRepository(Repository[Company]):
    model = Company
    default_order = ("name",)


class CompanyService(CrudService[Company, CompanyCreate, BaseModel]):
    repo_cls = CompanyRepository
    read_schema = CompanyRead

    def get_or_create(self, name: str) -> Company:
        existing = self.db.scalar(select(Company).where(Company.name.ilike(name.strip())))
        return existing or self.repo.create(name=name.strip())


class ApplicationRepository(Repository[Application]):
    model = Application
    default_order = ("-last_activity_at", "-id")


class ApplicationService(CrudService[Application, ApplicationCreate, BaseModel]):
    repo_cls = ApplicationRepository
    read_schema = ApplicationRead

    def create(self, data: ApplicationCreate) -> Application:
        values = data.model_dump()
        now = datetime.now(UTC)
        values["last_activity_at"] = values.get("applied_at") or now
        app = self.repo.create(**values)
        if app.applied_at is not None:
            self.add_event(app, ApplicationEventKind.APPLIED, f"Applied for {app.role_title}", app.applied_at)
        return app

    def update(self, id_: int, data: BaseModel) -> Application:
        values = data.model_dump(exclude_unset=True)
        app = self.repo.get(id_)
        old_stage = app.stage
        app = self.repo.update(id_, **values)
        if "stage" in values and values["stage"] != old_stage:
            self.add_event(
                app,
                ApplicationEventKind.STAGE_CHANGE,
                f"Moved from {old_stage.value} to {app.stage.value}",
                datetime.now(UTC),
            )
        return app

    def add_event(
        self,
        app: Application,
        kind: ApplicationEventKind,
        summary: str,
        occurred_at: datetime,
        source: ActorSource = ActorSource.YOU,
    ) -> ApplicationEvent:
        event = ApplicationEvent(application_id=app.id, kind=kind, summary=summary, occurred_at=occurred_at, source=source)
        self.db.add(event)
        if app.last_activity_at is None or occurred_at > app.last_activity_at:
            app.last_activity_at = occurred_at
        self.db.flush()
        return event

    def quiet_since(self, days: int) -> list[Application]:
        """Live applications with no activity for `days`: the follow-up nudge input."""
        cutoff = datetime.now(UTC).timestamp() - days * 86400
        live = (ApplicationStage.APPLIED, ApplicationStage.SCREENING, ApplicationStage.INTERVIEW)
        rows = self.db.scalars(select(Application).where(Application.stage.in_(live))).all()
        return [a for a in rows if a.last_activity_at is not None and a.last_activity_at.timestamp() < cutoff]

    def to_read(self, row: Application) -> ApplicationRead:
        referral = self.db.get(Person, row.referral_person_id) if row.referral_person_id else None
        quiet = (datetime.now(UTC) - row.last_activity_at).days if row.last_activity_at else None
        base = ApplicationCreate.model_validate(row).model_dump()
        return ApplicationRead(
            **base,
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            company_name=row.company.name,
            referral_person_name=referral.name if referral else None,
            last_activity_at=row.last_activity_at,
            days_quiet=quiet,
        )


class ApplicationEventRepository(Repository[ApplicationEvent]):
    model = ApplicationEvent
    default_order = ("-occurred_at",)


class ApplicationEventService(CrudService[ApplicationEvent, ApplicationEventCreate, BaseModel]):
    repo_cls = ApplicationEventRepository
    read_schema = ApplicationEventRead

    def create(self, data: ApplicationEventCreate) -> ApplicationEvent:
        app = ApplicationRepository(self.db).get(data.application_id)
        return ApplicationService(self.db).add_event(app, data.kind, data.summary, data.occurred_at, data.source)


def dedupe_key(company_name: str, role_title: str) -> str:
    """Company and role, lower-cased, punctuation stripped, whitespace collapsed."""

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()

    return f"{norm(company_name)}|{norm(role_title)}"


class JobPostingRepository(Repository[JobPosting]):
    model = JobPosting
    default_order = ("-match_score", "-discovered_at")


class JobPostingService(CrudService[JobPosting, JobPostingCreate, BaseModel]):
    repo_cls = JobPostingRepository
    read_schema = JobPostingRead

    def create(self, data: JobPostingCreate) -> JobPosting:
        row, created = self.upsert(data)
        if not created:
            raise ConflictError("That posting is already in discovery.", details={"posting_id": row.id})
        return row

    def upsert(self, data: JobPostingCreate) -> tuple[JobPosting, bool]:
        """Insert, or return the existing row for the same company+role. Discovery jobs
        call this so a posting seen twice never surfaces twice."""
        key = dedupe_key(data.company_name, data.role_title)
        existing = self.db.scalar(select(JobPosting).where(JobPosting.dedupe_key == key))
        if existing is not None:
            return existing, False
        row = self.repo.create(**data.model_dump(), dedupe_key=key, discovered_at=datetime.now(UTC))
        return row, True

    def pull_into_pipeline(self, posting_id: int) -> Application:
        """Turn a discovered posting into a Saved application. Local write only."""
        posting = self.repo.get(posting_id)
        if posting.application_id is not None:
            raise InvalidInputError("That posting is already in the pipeline.")
        company = CompanyService(self.db).get_or_create(posting.company_name)
        app = ApplicationService(self.db).create(
            ApplicationCreate(
                company_id=company.id,
                role_title=posting.role_title,
                stage=ApplicationStage.SAVED,
                location_kind=posting.location_kind,
                location_label=posting.location_label,
                pay_label=posting.pay_label,
                posting_url=posting.url,
                posting_summary=posting.summary,
                tags=list(posting.tags),
                next_action="Decide whether to apply",
            )
        )
        posting.application_id = app.id
        posting.status = PostingStatus.SAVED
        self.db.flush()
        return app

    def to_read(self, row: JobPosting) -> Any:
        return JobPostingRead.model_validate(row)
