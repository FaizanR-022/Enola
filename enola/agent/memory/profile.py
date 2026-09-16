"""Layer two of memory: durable statements about the owner, loaded into every run's
system prompt. Layer one is the structured tables; layer three is retrieval."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.enums import MemoryState
from enola.core.models.infra import MemoryFact

MAX_FACTS = 60


def active_facts(db: Session) -> list[str]:
    rows = db.scalars(
        select(MemoryFact)
        .where(MemoryFact.state == MemoryState.ACTIVE)
        .order_by(MemoryFact.locked.desc(), MemoryFact.confidence.desc(), MemoryFact.id)
        .limit(MAX_FACTS)
    ).all()
    out = []
    for fact in rows:
        tag = "rule" if fact.locked else ("told" if fact.source.value == "told" else f"inferred, {fact.confidence}%")
        out.append(f"{fact.statement} ({tag})")
    return out
