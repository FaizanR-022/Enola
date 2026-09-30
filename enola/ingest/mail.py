"""Reading Gmail over IMAP with an app password.

Read-only by design: this module opens mailboxes with `readonly=True` and has no code
path that appends, flags, moves or deletes anything. Drafting and sending live
elsewhere and go through the approval gate.

Credentials come from the environment and are never logged.
"""

from __future__ import annotations

import email
import imaplib
import re
import ssl
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from typing import Iterator

from enola.core.config import Settings, get_settings
from enola.core.errors import AgentUnavailableError
from enola.core.logging import get_logger

log = get_logger(__name__)

INBOX = "INBOX"
BODY_LIMIT = 4000
DISABLED = "Email is not configured. Set ENOLA_IMAP_PASSWORD (or the SMTP one) to a Google app password."


@dataclass(frozen=True)
class MailAddress:
    name: str
    address: str

    @property
    def label(self) -> str:
        return self.name or self.address


@dataclass(frozen=True)
class MailMessage:
    uid: str
    message_id: str
    thread_key: str
    subject: str
    sender: MailAddress
    recipients: list[MailAddress]
    date: datetime
    body: str
    unread: bool
    from_me: bool
    # Bulk, automated or no-reply mail. Newsletters and job alerts are the bulk of an
    # inbox and must never sit in "needs you", or the bucket means nothing.
    automated: bool = False


NOREPLY = ("noreply", "no-reply", "donotreply", "do-not-reply", "notifications", "mailer", "bounce", "automated", "alerts", "newsletter")


def _is_automated(message: Message, sender: MailAddress) -> bool:
    if message.get("List-Unsubscribe") or message.get("List-Id"):
        return True
    if (message.get("Precedence") or "").lower() in {"bulk", "list", "junk"}:
        return True
    if (message.get("Auto-Submitted") or "").lower() not in {"", "no"}:
        return True
    local = sender.address.split("@")[0]
    return any(marker in local for marker in NOREPLY)


@dataclass
class MailThread:
    """Messages sharing a normalised subject, newest first."""

    key: str
    subject: str
    messages: list[MailMessage] = field(default_factory=list)

    @property
    def latest(self) -> MailMessage:
        return self.messages[0]

    @property
    def unread(self) -> bool:
        return any(m.unread for m in self.messages)

    @property
    def participants(self) -> list[str]:
        seen: list[str] = []
        for m in self.messages:
            label = "You" if m.from_me else m.sender.label
            if label not in seen:
                seen.append(label)
        return seen

    @property
    def automated(self) -> bool:
        return all(m.automated for m in self.messages)

    @property
    def awaiting_you(self) -> bool:
        """The newest message is from a person, and it is not yours: the ball is in
        your court. Automated mail is never awaiting anything."""
        return not self.latest.from_me and not self.latest.automated


def _decode(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw.strip()


def _addresses(message: Message, header: str) -> list[MailAddress]:
    values = message.get_all(header, [])
    return [MailAddress(name=_decode(name), address=addr.lower()) for name, addr in getaddresses(values) if addr]


def _body_of(message: Message) -> str:
    """Prefer text/plain; fall back to stripped HTML. Attachments are ignored."""
    parts: list[str] = []
    html: list[str] = []
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            continue
        if not isinstance(payload, bytes):
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
        (parts if part.get_content_subtype() == "plain" else html).append(text)
    text = "\n".join(parts) or re.sub(r"<[^>]+>", " ", "\n".join(html))
    # Quoted replies and signatures triple the length and add nothing.
    text = re.split(r"\nOn .{0,80}wrote:\n|\n-{2,}\s*\n|\n_{5,}\n", text)[0]
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()[:BODY_LIMIT]


def thread_key_of(subject: str) -> str:
    """Gmail threads by subject closely enough for triage. Strip the Re:/Fwd: chain."""
    base = re.sub(r"^\s*((re|fwd|fw|aw|sv)\s*(\[\d+\])?\s*:\s*)+", "", subject or "", flags=re.I)
    return re.sub(r"\s+", " ", base).strip().lower() or "(no subject)"


@contextmanager
def connection(settings: Settings | None = None) -> Iterator[imaplib.IMAP4_SSL]:
    settings = settings or get_settings()
    if not settings.imap_enabled:
        raise AgentUnavailableError(DISABLED)
    client = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, ssl_context=ssl.create_default_context())
    try:
        client.login(settings.mail_user, settings.mail_password)
        yield client
    except imaplib.IMAP4.error as exc:
        # Never let the password reach a log line or an error body.
        log.warning("imap_error", host=settings.imap_host, user=settings.mail_user)
        raise AgentUnavailableError(f"Gmail refused the IMAP login for {settings.mail_user}. Check the app password.") from exc
    finally:
        try:
            client.logout()
        except Exception:
            pass


def fetch_recent(limit: int = 60, *, mailbox: str = INBOX, settings: Settings | None = None) -> list[MailMessage]:
    settings = settings or get_settings()
    me = settings.mail_user.lower()
    out: list[MailMessage] = []
    with connection(settings) as client:
        client.select(mailbox, readonly=True)
        typ, data = client.uid("SEARCH", "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        uids = data[0].split()[-limit:]
        if not uids:
            return []
        typ, fetched = client.uid("FETCH", b",".join(uids).decode(), "(FLAGS RFC822)")
        if typ != "OK":
            return []
        for item in fetched:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            header_blob = item[0].decode(errors="replace") if isinstance(item[0], bytes) else str(item[0])
            uid_match = re.search(r"UID (\d+)", header_blob)
            raw = item[1]
            if not uid_match or not isinstance(raw, bytes):
                continue
            message = email.message_from_bytes(raw)
            sender = (_addresses(message, "From") or [MailAddress("", "")])[0]
            try:
                when = parsedate_to_datetime(message.get("Date", ""))
            except Exception:
                when = datetime.now(timezone.utc)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            subject = _decode(message.get("Subject"))
            out.append(
                MailMessage(
                    uid=uid_match.group(1),
                    message_id=_decode(message.get("Message-ID")),
                    thread_key=thread_key_of(subject),
                    subject=subject or "(no subject)",
                    sender=sender,
                    recipients=_addresses(message, "To") + _addresses(message, "Cc"),
                    date=when,
                    body=_body_of(message),
                    unread="\\Seen" not in header_blob,
                    from_me=sender.address == me,
                    automated=_is_automated(message, sender),
                )
            )
    out.sort(key=lambda m: m.date, reverse=True)
    return out


def group_threads(messages: list[MailMessage]) -> list[MailThread]:
    threads: dict[str, MailThread] = {}
    for message in messages:
        thread = threads.setdefault(message.thread_key, MailThread(key=message.thread_key, subject=message.subject))
        thread.messages.append(message)
    for thread in threads.values():
        thread.messages.sort(key=lambda m: m.date, reverse=True)
    return sorted(threads.values(), key=lambda t: t.latest.date, reverse=True)
