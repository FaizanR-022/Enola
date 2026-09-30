"""What Enola says aloud for a run. Computed on the server so a Held outcome can never be
spoken as if it had happened: the approval notice comes first, then the reply."""

from __future__ import annotations

from collections.abc import Sequence

from enola.agent.service import ChatMessage

APPROVAL_NOTICE = "Drafted, not sent. It's waiting for your approval in Approvals."
ABORTED_NOTICE = "Stopped. Nothing else ran."


def spoken_text_for(messages: Sequence[ChatMessage], *, held: bool, aborted: bool) -> str:
    """The text a client should speak for this turn. Never empty for a held turn."""
    reply = ""
    for message in reversed(messages):
        if message.role == "enola" and message.text.strip():
            reply = message.text.strip()
            break
    parts: list[str] = []
    if held:
        parts.append(APPROVAL_NOTICE)
    elif aborted:
        parts.append(ABORTED_NOTICE)
    if reply:
        parts.append(reply)
    return " ".join(parts)
