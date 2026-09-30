"""Job discovery. The three rules the job exists to enforce, plus the failure modes
that would otherwise be discovered in production: a board that is down, and a board
that is not configured."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.enums import ApplicationStage, LocationKind, PostingStatus
from enola.core.models.jobs import JobPosting
from enola.core.schemas.jobs import ApplicationCreate, CompanyCreate
from enola.core.services.job_match import score_posting
from enola.core.services.jobs import ApplicationService, CompanyService
from enola.ingest.jobs_sources.base import RawPosting
from enola.workers.jobs.discovery import MIN_SCORE, discover_jobs

REMOTE = RawPosting(
    company_name="Kestrel Labs",
    role_title="Junior Backend Engineer",
    url="https://example.test/1",
    location_kind=LocationKind.REMOTE,
    location_label="Europe / Anywhere",
    summary="Python, FastAPI and Postgres. Async-first team.",
    tags=["python", "postgres"],
    source="fake",
)
ONSITE = RawPosting(
    company_name="Systems Ltd",
    role_title="Associate Software Engineer",
    url="https://example.test/2",
    location_kind=LocationKind.ONSITE,
    location_label="Karachi, Sindh, Pakistan",
    summary="React and Node across our product teams.",
    tags=["react", "node"],
    source="fake",
)


class FakeSource:
    name = "fake"

    def __init__(self, postings: list[RawPosting], *, reason: str | None = None, boom: bool = False) -> None:
        self.postings = postings
        self.reason = reason
        self.boom = boom
        self.fetched = 0

    def unavailable(self) -> str | None:
        return self.reason

    def fetch(self) -> list[RawPosting]:
        self.fetched += 1
        if self.boom:
            raise RuntimeError("board is down")
        return self.postings


def posting_by_title(db: Session, title: str) -> JobPosting | None:
    return db.scalar(select(JobPosting).where(JobPosting.role_title == title))


def test_discovery_inserts_remote_and_onsite_with_readable_reasons(db: Session) -> None:
    result = discover_jobs(db, sources=[FakeSource([REMOTE, ONSITE])])
    assert result["fetched"] == 2 and result["added"] == 2

    remote = posting_by_title(db, REMOTE.role_title)
    onsite = posting_by_title(db, ONSITE.role_title)
    assert remote is not None and onsite is not None
    # Onsite is never filtered out: it is discovered, scored and visible.
    assert remote.status is PostingStatus.DISCOVERED and onsite.status is PostingStatus.DISCOVERED
    assert remote.match_score is not None and onsite.match_score is not None
    # Remote is preferred, so it outranks an otherwise comparable Karachi role.
    assert remote.match_score > onsite.match_score
    for row in (remote, onsite):
        assert row.match_reason and len(row.match_reason) > 10, "a score with no readable reason is not useful"
    assert "Karachi" in onsite.match_reason


def test_running_twice_adds_nothing(db: Session) -> None:
    source = FakeSource([REMOTE, ONSITE])
    first = discover_jobs(db, sources=[source])
    second = discover_jobs(db, sources=[source])
    assert first["added"] == 2
    assert second["added"] == 0 and second["duplicate"] == 2
    assert db.scalar(select(JobPosting.id).where(JobPosting.role_title == REMOTE.role_title)) is not None
    assert len(db.scalars(select(JobPosting)).all()) == 2


def test_a_role_already_applied_to_never_surfaces(db: Session) -> None:
    company = CompanyService(db).create(CompanyCreate(name="Kestrel Labs"))
    ApplicationService(db).create(ApplicationCreate(company_id=company.id, role_title="Junior Backend Engineer", stage=ApplicationStage.APPLIED))
    db.commit()

    result = discover_jobs(db, sources=[FakeSource([REMOTE, ONSITE])])

    assert result["already_applied"] == 1
    assert posting_by_title(db, REMOTE.role_title) is None, "a role already applied to reappeared in discovery"
    assert posting_by_title(db, ONSITE.role_title) is not None


def test_one_source_failing_does_not_lose_the_others(db: Session) -> None:
    broken = FakeSource([], boom=True)
    working = FakeSource([ONSITE])
    result = discover_jobs(db, sources=[broken, working])
    assert result["added"] == 1
    assert posting_by_title(db, ONSITE.role_title) is not None


def test_unconfigured_source_is_skipped_not_called(db: Session) -> None:
    dormant = FakeSource([REMOTE], reason="NO_KEY is not set")
    result = discover_jobs(db, sources=[dormant])
    assert dormant.fetched == 0, "a dormant source must not be called at all"
    assert result["fetched"] == 0 and result["added"] == 0


def test_noise_is_filed_below_threshold_rather_than_shown(db: Session) -> None:
    noise = RawPosting(
        company_name="Faraway Inc",
        role_title="Senior Staff Rust Architect",
        location_kind=LocationKind.ONSITE,
        location_label="Zurich, Switzerland",
        summary="Fifteen years of systems experience required.",
        source="fake",
    )
    discover_jobs(db, sources=[FakeSource([noise])])
    row = posting_by_title(db, noise.role_title)
    assert row is not None and row.status is PostingStatus.DISMISSED


def test_scoring_prefers_workable_timezones(db: Session) -> None:
    friendly = score_posting(role_title="Backend Engineer", summary="python", tags=[], location_kind=LocationKind.REMOTE, location_label="Europe")
    hard = score_posting(role_title="Backend Engineer", summary="python", tags=[], location_kind=LocationKind.REMOTE, location_label="US only, PST overlap required")
    assert friendly.score > hard.score
    assert "overlap" in friendly.reason or "workable" in friendly.reason
    assert "UTC+5" in hard.reason


def test_seniority_matches_whole_words_only() -> None:
    """Regression: "i" and "1" mark an entry-level title ("Engineer I"), but matched as
    substrings they fire inside "Tier III" and "AI agent" and inflate the score."""
    kw = {"summary": "python react", "tags": [], "location_kind": LocationKind.REMOTE, "location_label": "Europe"}
    assert "junior" not in score_posting(role_title="Tier III Service Desk Engineer", **kw).reason
    assert "junior" not in score_posting(role_title="AI agent engineer", **kw).reason
    assert "junior-friendly" in score_posting(role_title="Software Engineer I", **kw).reason
    assert "junior-friendly" in score_posting(role_title="Junior Backend Engineer", **kw).reason
    # "lead" must not fire inside "leadership", nor "head" inside "headless".
    assert "senior" not in score_posting(role_title="Backend Engineer, Headless CMS", **kw).reason


def test_non_engineering_titles_sink_below_threshold() -> None:
    kw = {"summary": "python javascript", "tags": [], "location_kind": LocationKind.REMOTE, "location_label": "Europe"}
    desk = score_posting(role_title="Tier III Service Desk Engineer", **kw)
    real = score_posting(role_title="Backend Engineer", **kw)
    assert desk.score < MIN_SCORE < real.score
    assert "not a software engineering role" in desk.reason
