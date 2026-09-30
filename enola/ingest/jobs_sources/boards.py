"""The keyless remote boards. No API key, no signup, no cost — these work the moment
the worker runs. Each one is small enough to read, because each will eventually break
when its board changes shape.
"""

from __future__ import annotations

from typing import Any

from enola.core.enums import LocationKind
from enola.ingest.jobs_sources.base import RawPosting, clean, get_json, location_from

# Boards return everything; we only want engineering roles near the owner's level.
WANTED = ("software", "engineer", "developer", "backend", "frontend", "full stack", "fullstack", "python", "javascript", "typescript", "react", "node")
LIMIT = 60


def _relevant(title: str) -> bool:
    lowered = title.lower()
    return any(word in lowered for word in WANTED)


class Remotive:
    name = "remotive"

    def unavailable(self) -> str | None:
        return None

    def fetch(self) -> list[RawPosting]:
        payload = get_json("https://remotive.com/api/remote-jobs", params={"category": "software-dev", "limit": LIMIT})
        jobs: list[dict[str, Any]] = (payload or {}).get("jobs", []) if isinstance(payload, dict) else []
        out: list[RawPosting] = []
        for job in jobs:
            title = str(job.get("title") or "")
            if not _relevant(title):
                continue
            out.append(
                RawPosting(
                    company_name=str(job.get("company_name") or "Unknown"),
                    role_title=title,
                    url=str(job.get("url") or ""),
                    location_kind=LocationKind.REMOTE,
                    location_label=str(job.get("candidate_required_location") or "Remote"),
                    pay_label=str(job.get("salary") or ""),
                    summary=clean(str(job.get("description") or "")),
                    tags=[str(t) for t in (job.get("tags") or [])][:8],
                    source=self.name,
                )
            )
        return out


class RemoteOK:
    name = "remoteok"

    def unavailable(self) -> str | None:
        return None

    def fetch(self) -> list[RawPosting]:
        payload = get_json("https://remoteok.com/api")
        # The first element is a legal notice, not a job.
        rows: list[dict[str, Any]] = [r for r in payload if isinstance(r, dict) and r.get("position")] if isinstance(payload, list) else []
        out: list[RawPosting] = []
        for job in rows[:LIMIT]:
            title = str(job.get("position") or "")
            if not _relevant(title):
                continue
            salary_min, salary_max = job.get("salary_min"), job.get("salary_max")
            pay = f"${int(salary_min):,}–${int(salary_max):,}" if salary_min and salary_max else ""
            out.append(
                RawPosting(
                    company_name=str(job.get("company") or "Unknown"),
                    role_title=title,
                    url=str(job.get("url") or ""),
                    location_kind=LocationKind.REMOTE,
                    location_label=str(job.get("location") or "Remote"),
                    pay_label=pay,
                    summary=clean(str(job.get("description") or "")),
                    tags=[str(t) for t in (job.get("tags") or [])][:8],
                    source=self.name,
                )
            )
        return out


class Arbeitnow:
    name = "arbeitnow"

    def unavailable(self) -> str | None:
        return None

    def fetch(self) -> list[RawPosting]:
        payload = get_json("https://www.arbeitnow.com/api/job-board-api")
        rows: list[dict[str, Any]] = (payload or {}).get("data", []) if isinstance(payload, dict) else []
        out: list[RawPosting] = []
        for job in rows[:LIMIT]:
            title = str(job.get("title") or "")
            if not _relevant(title):
                continue
            label = str(job.get("location") or "")
            out.append(
                RawPosting(
                    company_name=str(job.get("company_name") or "Unknown"),
                    role_title=title,
                    url=str(job.get("url") or ""),
                    location_kind=LocationKind.REMOTE if job.get("remote") else location_from(label),
                    location_label=label or "Remote",
                    pay_label="",
                    summary=clean(str(job.get("description") or "")),
                    tags=[str(t) for t in (job.get("tags") or [])][:8],
                    source=self.name,
                )
            )
        return out
