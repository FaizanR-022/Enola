"""Reading the inbox. Both tools are SAFE: they open IMAP read-only and return text.

There is no drafting or sending tool here. `send_email` lives in records.py and is
EXTERNAL, so every outbound message is Held. Keeping the read tools separate makes it
obvious at a glance that nothing in this module can change a mailbox.
"""

from __future__ import annotations

from enola.agent.context import current_context
from enola.agent.registry import tool
from enola.core.config import get_settings
from enola.core.enums import Risk
from enola.core.services.mail_triage import triage
from enola.ingest.mail import DISABLED, fetch_recent, group_threads

WINDOW = 60


@tool(risk=Risk.SAFE, kind_label="email · read")
def list_email_threads(bucket: str = "needs_you", limit: int = 10) -> str:
    """List recent email threads, most recent first. `bucket` is needs_you, ongoing,
    worth_knowing, or "all". Use this before drafting a reply, so the draft answers
    what was actually asked."""
    if not get_settings().imap_enabled:
        return DISABLED
    ctx = current_context()
    items = triage(ctx.db, group_threads(fetch_recent(limit=WINDOW)), use_model=False)
    wanted = bucket.strip().lower()
    if wanted != "all":
        items = [i for i in items if i.bucket.value == wanted]
    if not items:
        return f"No threads in {bucket}."
    lines = [f"{len(items)} thread(s) in {bucket}:"]
    for item in items[:limit]:
        latest = item.thread.latest
        who = "You" if latest.from_me else latest.sender.label
        lines.append(f"- [{item.thread.key}] {who} · {item.thread.subject} · {latest.date:%d %b %H:%M} · {len(item.thread.messages)} message(s)")
    return "\n".join(lines)


@tool(risk=Risk.SAFE, kind_label="email · read")
def read_email_thread(thread: str) -> str:
    """Read one email thread in full, newest message first. `thread` is the bracketed
    key from list_email_threads, or any distinctive part of the subject line."""
    if not get_settings().imap_enabled:
        return DISABLED
    ctx = current_context()
    threads = group_threads(fetch_recent(limit=WINDOW))
    needle = thread.strip().lower()
    match = next((t for t in threads if t.key == needle), None) or next((t for t in threads if needle in t.key), None)
    if match is None:
        return f"No thread matching {thread!r} in the last {WINDOW} messages."
    newest = match.messages[0]
    out = [
        f"Subject: {match.subject}",
        f"Participants: {' · '.join(match.participants)}",
        # send_email takes this as reply_to_message_id so the reply threads in Gmail
        # instead of starting a new conversation.
        f"Reply to message-id: {newest.message_id or '(unknown)'}",
        f"Reply to address: {newest.sender.address}" if not newest.from_me else "Newest message is yours.",
        "",
    ]
    for message in match.messages:
        who = "You" if message.from_me else f"{message.sender.label} <{message.sender.address}>"
        out.append(f"--- {who} · {message.date:%a %d %b %H:%M} ---")
        out.append(message.body[:1500] or "(no text body)")
        out.append("")
    return "\n".join(out)
