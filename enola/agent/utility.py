"""One-shot completions on the UTILITY role: brief prose, classification, scoring,
summaries. Separate from the agent loop so the two can be priced independently."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from enola.agent.models import ModelRole, invoke_checked, make_chat_model, model_id_for, record_model_call, system_message
from enola.agent.prompts.system import CACHEABLE


def utility_complete(
    db: Session,
    *,
    instructions: str,
    text: str,
    purpose: str,
    model: BaseChatModel | None = None,
    run_id: str | None = None,
) -> str:
    """Run one prompt and return the text. `instructions` is the stable part and is
    marked cacheable; `text` is the volatile input."""
    chat = model or make_chat_model(ModelRole.UTILITY)
    system = system_message([{"type": "text", "text": instructions, CACHEABLE: True}])
    response = invoke_checked(chat, [system, HumanMessage(content=text)])
    record_model_call(db, role=ModelRole.UTILITY, model_id=model_id_for(ModelRole.UTILITY), message=response, run_id=run_id, thread_id=None, purpose=purpose)
    db.commit()
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict)).strip()
