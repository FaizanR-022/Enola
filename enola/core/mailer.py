"""Outbound SMTP, in one place.

Two callers, and they must not drift apart: the notification outbox mailing the owner,
and the `send_email` tool mailing other people after an approval. One transport means
one place where credentials are read, one place where a send is logged, and one place
to change when the account moves.

This module sends. It does not decide whether sending is allowed — the approval gate
does that, before anything here is called.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from enola.core.config import Settings, get_settings
from enola.core.errors import EnolaError, InvalidInputError
from enola.core.logging import get_logger

log = get_logger(__name__)

NOT_CONFIGURED = "Email sending is not configured. Set ENOLA_SMTP_HOST and ENOLA_SMTP_FROM."


class MailNotConfigured(EnolaError):
    """There is no transport yet. The caller decides whether that is fatal or a wait."""

    code = "mail_not_configured"
    status = 503


def valid_address(value: str) -> bool:
    name, addr = parseaddr(value or "")
    return bool(addr) and "@" in addr and "." in addr.split("@")[-1] and " " not in addr


def send_mail(
    *,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    settings: Settings | None = None,
) -> str:
    """Send one message and return its Message-ID.

    `in_reply_to` is the Message-ID being answered. Without it Gmail starts a new
    conversation rather than continuing the thread, which looks broken to the recipient.
    """
    settings = settings or get_settings()
    if not settings.smtp_enabled:
        raise MailNotConfigured(NOT_CONFIGURED)
    if not valid_address(to):
        raise InvalidInputError(f"{to!r} is not a usable email address.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.owner_name, settings.smtp_from))
    message["To"] = to
    message_id = make_msgid()
    message["Message-ID"] = message_id
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)

    # Recipient and subject only: the body is the owner's correspondence, not log material.
    log.info("mail_sent", to=to, subject=subject[:120], threaded=bool(in_reply_to))
    return message_id
