"""Put a real Held item in the queue without an API key.

    python -m enola.scripts.demo_held

Runs the actual agent graph on the main thread with a scripted model that drafts a
recruiter follow-up and calls `send_email`. The gate does what it always does: writes
an approval_request with state Held and pauses at a Postgres checkpoint. Approving it
from the UI resumes that checkpoint for real.
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from sqlalchemy import select

from enola.agent.service import MAIN_THREAD, AgentService
from enola.core.db import session_scope
from enola.core.models import Application, Person

DRAFT = """Hi Ayesha,

Thanks again for the quick call last week; the notes on how Kestrel splits platform and product work were genuinely useful.

I wanted to follow up on the Backend Engineer (Python) role. I finished the take-home on Sunday and pushed a short write-up of the caching decisions alongside it. Happy to walk through the trade-offs whenever suits you.

One more thing: you mentioned the team was still deciding on the new-grad band. If that is settled, I would be glad to know where it landed before the next round.

Best,
Faizan"""


class DraftingModel(BaseChatModel):
    """Behaves like the model on a good day: reads the thread, drafts, asks to send."""

    to: str
    turns: int = 0

    @property
    def _llm_type(self) -> str:
        return "demo-drafting"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.turns += 1
        if self.turns == 1:
            message = AIMessage(
                content="You applied 5 days ago and submitted the take-home 3 days ago. Your rule: nudge a recruiter if there is no reply in 48h and an application is past take-home stage. I drafted from your last two exchanges and your own phrasing.",
                tool_calls=[{"name": "send_email", "args": {"to": self.to, "subject": "Backend Engineer (Python) — take-home follow-up", "body": DRAFT}, "id": f"demo-send-{uuid.uuid4().hex[:8]}", "type": "tool_call"}],
            )
        else:
            message = AIMessage(content="Sent, and logged to Ayesha's interaction history. I will flag it if there is no reply by Thursday.")
        return ChatResult(generations=[ChatGeneration(message=message)])


def main() -> None:
    with session_scope() as db:
        ayesha = db.scalar(select(Person).where(Person.name == "Ayesha Tariq"))
        to = ayesha.email if ayesha and ayesha.email else "ayesha.tariq@kestrellabs.io"
        kestrel = db.scalar(select(Application).where(Application.role_title.ilike("%Backend Engineer (Python)%")))
        service = AgentService(db, model=DraftingModel(to=to))
        result = service.run(text="Follow up with Ayesha about the Kestrel take-home.", thread_id=MAIN_THREAD)
        print(f"run {result.run_id} on thread {result.thread_id}: held approval #{result.held_approval_id}")
        if kestrel is not None:
            print(f"(application #{kestrel.id} is the one it relates to)")


if __name__ == "__main__":
    main()
