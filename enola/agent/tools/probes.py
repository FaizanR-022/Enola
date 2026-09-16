"""Two probe tools that prove the gate: one runs freely, one must halt.

They stay registered in production on purpose. `send_probe` is the canary: if it ever
runs without a Held row, the gate is broken.
"""

from __future__ import annotations

from enola.agent.registry import tool
from enola.core.enums import Risk

# Everything `send_probe` has ever "sent". In-memory, so tests can assert on it.
SENT: list[dict[str, str]] = []


@tool(risk=Risk.SAFE, kind_label="probe · read")
def echo_probe(text: str) -> str:
    """Return the text unchanged. A SAFE probe used to check the agent loop works."""
    return f"echo: {text}"


@tool(risk=Risk.EXTERNAL, kind_label="probe · outbound")
def send_probe(to: str, message: str) -> str:
    """Pretend to send a message somewhere outside Enola. EXTERNAL: always Held first."""
    SENT.append({"to": to, "message": message})
    return f"sent to {to}"
