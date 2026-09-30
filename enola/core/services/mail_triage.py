"""Sorting an inbox into three buckets.

Two passes, in this order for a reason. Headers are free and remove the ~90% of an
inbox that is bulk mail, so the model only ever sees the handful of threads that
survive — a few a day, not a few hundred. If no model is available the heuristic
answer stands, and the screen still works.

Nothing here writes to the mailbox.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from enola.agent.models import ModelRole, model_available
from enola.agent.utility import utility_complete
from enola.core.enums import MailBucket
from enola.core.logging import get_logger
from enola.ingest.mail import MailThread

log = get_logger(__name__)

# Transactional mail that reaches the "needs you" pass because it carries no
# List-Unsubscribe: receipts, confirmations, verifications. It is worth knowing, not doing.
TRANSACTIONAL = (
    "thank you for applying", "application received", "registration successful", "verification successful",
    "your receipt", "order confirm", "password", "verify your", "confirm your", "welcome to", "invoice",
    "otp", "one-time", "sign-in", "security alert",
)

CLASSIFY = """You sort one person's inbox. For each thread you are given, decide one bucket:

needs_you    — a person is waiting on a reply, a decision, or an action from the owner.
ongoing      — a real conversation that is alive but not currently blocked on the owner.
worth_knowing — no reply needed: notifications, confirmations, receipts, newsletters, alerts.

A "thank you for applying" auto-reply is worth_knowing, not needs_you. A recruiter asking
to schedule is needs_you. Answer with JSON only: {"<id>": "<bucket>", ...}. No prose."""


@dataclass
class TriagedThread:
    thread: MailThread
    bucket: MailBucket
    reason: str


def _looks_transactional(subject: str, body: str) -> bool:
    text = f"{subject} {body[:400]}".lower()
    return any(phrase in text for phrase in TRANSACTIONAL)


def _heuristic(thread: MailThread) -> TriagedThread:
    if thread.automated:
        return TriagedThread(thread, MailBucket.WORTH_KNOWING, "bulk or no-reply sender")
    if _looks_transactional(thread.subject, thread.latest.body):
        return TriagedThread(thread, MailBucket.WORTH_KNOWING, "transactional notification")
    if not thread.awaiting_you:
        return TriagedThread(thread, MailBucket.ONGOING, "you replied last")
    if len(thread.messages) > 1:
        return TriagedThread(thread, MailBucket.NEEDS_YOU, "a live thread waiting on you")
    return TriagedThread(thread, MailBucket.NEEDS_YOU, "from a person, unanswered")


def _refine(db: Session, candidates: list[TriagedThread]) -> None:
    """Ask the model about the survivors only. Failure is not fatal: the heuristic
    answer is already on each thread."""
    if not candidates or not model_available():
        return
    lines = []
    for index, item in enumerate(candidates):
        latest = item.thread.latest
        lines.append(f"[{index}] from: {latest.sender.label} | subject: {item.thread.subject} | {latest.body[:400]}")
    try:
        raw = utility_complete(db, instructions=CLASSIFY, text="\n\n".join(lines), purpose="mail_triage")
        # Models wrap JSON in prose or code fences often enough to be worth tolerating.
        found = re.search(r"\{.*\}", raw, re.S)
        payload = json.loads(found.group(0)) if found else {}
    except Exception as exc:
        log.warning("mail_triage_model_failed", error=str(exc)[:200])
        return
    for key, value in payload.items():
        try:
            item = candidates[int(key)]
        except (ValueError, IndexError):
            continue
        try:
            bucket = MailBucket(str(value).strip().lower())
        except ValueError:
            continue
        if bucket is not item.bucket:
            item.bucket = bucket
            item.reason = "sorted by Enola"


def triage(db: Session, threads: list[MailThread], *, use_model: bool = True) -> list[TriagedThread]:
    triaged = [_heuristic(t) for t in threads]
    if use_model:
        # Only what the cheap pass could not dismiss.
        _refine(db, [t for t in triaged if t.bucket is MailBucket.NEEDS_YOU])
    return triaged
