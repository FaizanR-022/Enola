"""JSearch on RapidAPI — the only free route to onsite Karachi listings, because it
reads Google for Jobs rather than one board.

Dormant until JSEARCH_API_KEY is set. The free tier is ~200 requests a month, so this
runs a small fixed set of queries once a day and no more: two remote, one local.
"""

from __future__ import annotations

from typing import Any

from enola.core.config import get_settings
from enola.core.enums import LocationKind
from enola.core.logging import get_logger
from enola.ingest.jobs_sources.base import RawPosting, clean, get_json

log = get_logger(__name__)

HOST = "jsearch.p.rapidapi.com"
URL = f"https://{HOST}/search"

# Three queries a day is ~90 a month, inside the free tier with room to spare.
QUERIES: tuple[tuple[str, str], ...] = (
    ("junior software engineer remote", "remote"),
    ("react node developer remote", "remote"),
    ("software engineer in Karachi, Pakistan", "onsite"),
)


def _kind(job: dict[str, Any], intent: str) -> LocationKind:
    if job.get("job_is_remote"):
        return LocationKind.REMOTE
    return LocationKind.ONSITE if intent == "onsite" else LocationKind.REMOTE


def _label(job: dict[str, Any]) -> str:
    parts = [job.get("job_city"), job.get("job_state"), job.get("job_country")]
    label = ", ".join(str(p) for p in parts if p)
    return label or ("Remote" if job.get("job_is_remote") else "")


def _pay(job: dict[str, Any]) -> str:
    low, high, period = job.get("job_min_salary"), job.get("job_max_salary"), job.get("job_salary_period")
    if not low or not high:
        return ""
    return f"{int(low):,}–{int(high):,} {str(period or '').lower()}".strip()


class JSearch:
    name = "jsearch"

    def unavailable(self) -> str | None:
        if not get_settings().jsearch_api_key:
            return "JSEARCH_API_KEY is not set, so onsite Karachi listings are not being fetched."
        return None

    def fetch(self) -> list[RawPosting]:
        key = get_settings().jsearch_api_key
        headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}
        out: list[RawPosting] = []
        for query, intent in QUERIES:
            try:
                payload = get_json(URL, params={"query": query, "page": 1, "num_pages": 1}, headers=headers)
            except Exception as exc:  # one bad query must not lose the other two
                log.warning("jsearch_query_failed", query=query, error=str(exc)[:200])
                continue
            rows: list[dict[str, Any]] = (payload or {}).get("data", []) if isinstance(payload, dict) else []
            for job in rows:
                title = str(job.get("job_title") or "")
                if not title:
                    continue
                out.append(
                    RawPosting(
                        company_name=str(job.get("employer_name") or "Unknown"),
                        role_title=title,
                        url=str(job.get("job_apply_link") or ""),
                        location_kind=_kind(job, intent),
                        location_label=_label(job),
                        pay_label=_pay(job),
                        summary=clean(str(job.get("job_description") or "")),
                        tags=[],
                        source=self.name,
                    )
                )
        return out
