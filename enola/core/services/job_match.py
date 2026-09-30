"""Scoring a posting against the owner, as a heuristic rather than a model call.

Two reasons it is not a model call: it costs nothing to run over a hundred postings a
day, and every score comes with a reason the owner can read and disagree with. A
score nobody can interrogate is worse than no score.

Remote is preferred and weighted higher. Onsite is never filtered out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from enola.core.config import get_settings
from enola.core.enums import LocationKind

# Timezone overlap with UTC+5, for remote roles. Anything demanding a full US working
# day is a different proposition from EU or async-first, and should not rank alike.
FRIENDLY_REGIONS = ("europe", "emea", "uk", "united kingdom", "germany", "netherlands", "asia", "pakistan", "india", "gulf", "uae", "middle east", "worldwide", "anywhere", "global")
HARD_REGIONS = ("us only", "usa only", "united states only", "us-based", "pacific", "pst", "americas only", "canada only")

LOCAL_CITY = "karachi"
LOCAL_COUNTRY = "pakistan"

# Matched on word boundaries. Substring matching looked fine until "Tier III Service
# Desk Engineer" and "AI agent engineer" both read as junior because of a bare "i".
JUNIOR = ("junior", "jr", "graduate", "grad", "entry", "associate", "intern", "trainee", "fresher", "i", "1")
SENIOR = ("senior", "sr", "staff", "principal", "lead", "architect", "head", "manager", "director", "vp", "iii", "iv")

# Titles that carry an engineering word but are not the job. Cheaper and more honest
# than trying to whitelist every real title.
NOT_ENGINEERING = ("service desk", "help desk", "helpdesk", "sales", "recruiter", "recruiting", "account executive", "customer success", "marketing", "technician")


@dataclass(frozen=True)
class Match:
    score: int
    reason: str


def _skills(haystack: str, skills: list[str]) -> list[str]:
    return [s for s in skills if s and s.lower() in haystack]


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    """Word-boundary match. `in` is wrong here: a bare "i" appears inside half of all
    job titles, and a bare "lead" inside "leadership"."""
    tokens = set(re.findall(r"[a-z0-9+#]+", text.lower()))
    return any(word in tokens for word in words)


def score_posting(
    *,
    role_title: str,
    summary: str,
    tags: list[str],
    location_kind: LocationKind,
    location_label: str,
    skills: list[str] | None = None,
) -> Match:
    settings = get_settings()
    skills = skills if skills is not None else list(settings.job_skills)
    haystack = " ".join([role_title, summary, " ".join(tags)]).lower()
    label = (location_label or "").lower()
    title = role_title.lower()

    score = 40  # a plausible posting starts in the middle and argues its way up or down
    notes: list[str] = []

    hits = _skills(haystack, skills)
    if hits:
        score += min(30, 8 * len(hits))
        notes.append(f"matches {', '.join(hits[:4])}")
    else:
        score -= 10
        notes.append("none of your stack named")

    if any(phrase in title for phrase in NOT_ENGINEERING):
        score -= 30
        notes.append("not a software engineering role")

    # Seniority. Junior-friendly is the point; senior postings stay visible but sink.
    if _has_word(title, SENIOR):
        score -= 22
        notes.append("written for a senior")
    elif _has_word(title, JUNIOR):
        score += 14
        notes.append("junior-friendly title")

    # Location. Remote preferred; onsite Karachi is a real option, not a reject.
    if location_kind is LocationKind.REMOTE:
        score += 12
        if any(r in label for r in HARD_REGIONS):
            score -= 18
            notes.append("remote but wants US hours — hard from UTC+5")
        elif any(r in label for r in FRIENDLY_REGIONS):
            score += 8
            notes.append("remote with workable overlap")
        else:
            notes.append("remote")
    elif location_kind is LocationKind.HYBRID:
        if LOCAL_CITY in label:
            score += 8
            notes.append("hybrid in Karachi")
        else:
            score -= 14
            notes.append("hybrid, but not in Karachi")
    else:
        if LOCAL_CITY in label:
            score += 10
            notes.append("onsite in Karachi")
        elif LOCAL_COUNTRY in label:
            score -= 6
            notes.append("onsite elsewhere in Pakistan")
        else:
            score -= 25
            notes.append("onsite abroad — would need relocation")

    return Match(score=max(0, min(100, score)), reason="; ".join(notes))
