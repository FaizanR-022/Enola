"""One shape for every job board, so a source that rots can be switched off without
touching the rest.

A source that cannot run (no API key, say) reports why through `unavailable()` and is
skipped. It never raises for being unconfigured — only for genuinely failing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx

from enola.core.enums import LocationKind

TIMEOUT = httpx.Timeout(20.0)
USER_AGENT = "Enola/0.1 (personal job tracker; one user)"


@dataclass(frozen=True)
class RawPosting:
    """A posting as a board described it, before scoring or deduplication."""

    company_name: str
    role_title: str
    url: str = ""
    location_kind: LocationKind = LocationKind.REMOTE
    location_label: str = ""
    pay_label: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""


@runtime_checkable
class JobSource(Protocol):
    name: str

    def unavailable(self) -> str | None:
        """None when the source can run; otherwise a human-readable reason it is dormant."""
        ...

    def fetch(self) -> list[RawPosting]:
        ...


def get_json(url: str, *, params: dict[str, str | int] | None = None, headers: dict[str, str] | None = None) -> object:
    response = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT, **(headers or {})}, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def clean(text: str, limit: int = 600) -> str:
    """Boards ship HTML in summary fields. Strip tags crudely and cap the length —
    this text is a preview in a list, not a document."""
    import re

    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"&[a-z]+;", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:limit]


def location_from(label: str) -> LocationKind:
    """Read a board's free-text location. Defaults to remote: these are remote boards,
    and a wrong guess only affects ranking, never whether the posting is shown."""
    lowered = (label or "").lower()
    if "hybrid" in lowered:
        return LocationKind.HYBRID
    if "remote" in lowered or "anywhere" in lowered or not lowered:
        return LocationKind.REMOTE
    return LocationKind.ONSITE
