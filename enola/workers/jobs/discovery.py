"""Job discovery: poll the boards, score what comes back, and file anything new as a
discovered posting.

Three rules this job exists to enforce:
  - a posting already in discovery never surfaces twice (JobPostingService.upsert),
  - a posting for a role already applied to never surfaces at all,
  - a source that is down or unconfigured costs us the others' results, never all of them.

Nothing here contacts a model, so running it is free.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.enums import PostingStatus
from enola.core.logging import get_logger
from enola.core.models.jobs import Application, Company
from enola.core.schemas.jobs import JobPostingCreate
from enola.core.services.job_match import score_posting
from enola.core.services.jobs import JobPostingService, dedupe_key
from enola.ingest.jobs_sources.base import JobSource, RawPosting
from enola.ingest.jobs_sources.boards import Arbeitnow, RemoteOK, Remotive
from enola.ingest.jobs_sources.jsearch import JSearch

log = get_logger(__name__)

# Below this a posting is noise: senior roles abroad, nothing from the owner's stack.
# It is filed as dismissed rather than dropped, so the threshold can be reviewed later.
MIN_SCORE = 30


def default_sources() -> list[JobSource]:
    return [Remotive(), RemoteOK(), Arbeitnow(), JSearch()]


def _applied_keys(db: Session) -> set[str]:
    """Company+role of everything already in the pipeline, in the posting's key format."""
    rows = db.execute(select(Company.name, Application.role_title).join(Application, Application.company_id == Company.id)).all()
    return {dedupe_key(company, role) for company, role in rows}


def _title_ok(title: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", title)) and len(title) <= 200


def discover_jobs(db: Session, *, sources: list[JobSource] | None = None, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    sources = sources if sources is not None else default_sources()
    postings = JobPostingService(db)
    applied = _applied_keys(db)

    raw: list[RawPosting] = []
    for source in sources:
        reason = source.unavailable()
        if reason:
            log.info("discovery_source_skipped", source=source.name, reason=reason)
            continue
        try:
            found = source.fetch()
        except Exception as exc:
            # One board being down must not cost us the others.
            log.warning("discovery_source_failed", source=source.name, error=str(exc)[:200])
            continue
        log.info("discovery_source_ok", source=source.name, found=len(found))
        raw.extend(found)

    added = skipped_applied = duplicate = low = 0
    for posting in raw:
        if not _title_ok(posting.role_title) or not posting.company_name:
            continue
        if dedupe_key(posting.company_name, posting.role_title) in applied:
            skipped_applied += 1
            continue
        match = score_posting(
            role_title=posting.role_title,
            summary=posting.summary,
            tags=posting.tags,
            location_kind=posting.location_kind,
            location_label=posting.location_label,
        )
        row, created = postings.upsert(
            JobPostingCreate(
                company_name=posting.company_name[:160],
                role_title=posting.role_title[:200],
                url=posting.url[:600],
                location_kind=posting.location_kind,
                location_label=posting.location_label[:120],
                pay_label=posting.pay_label[:80],
                summary=posting.summary,
                tags=posting.tags,
                match_score=match.score,
                match_reason=match.reason,
                status=PostingStatus.DISCOVERED if match.score >= MIN_SCORE else PostingStatus.DISMISSED,
            )
        )
        if not created:
            duplicate += 1
            continue
        if row.status is PostingStatus.DISMISSED:
            low += 1
        else:
            added += 1

    db.commit()
    result = {"fetched": len(raw), "added": added, "below_threshold": low, "already_applied": skipped_applied, "duplicate": duplicate}
    log.info("discovery_done", **result)
    return result
