"""Retrieval as a tool. The scope comes from the conversation, never from the model:
a course chat cannot ask for finance documents by naming a different scope."""

from __future__ import annotations

from enola.agent.context import current_context
from enola.agent.memory.retrieval import retrieve
from enola.agent.registry import tool
from enola.core.enums import Risk
from enola.ingest.embeddings import get_embedder

EVERYTHING = "everything"


@tool(risk=Risk.SAFE, kind_label="documents · read")
def search_documents(query: str, limit: int = 5) -> str:
    """Search the owner's uploaded documents (course notes, postings, resumes) for passages
    relevant to the query. Only documents inside this conversation's scope are visible."""
    ctx = current_context()
    scope = None if ctx.scope in (EVERYTHING, "", "today") else ctx.scope
    hits = retrieve(ctx.db, get_embedder(), query, scope=scope, limit=limit)
    if not hits:
        return "No matching passages" + (f" in scope {scope}." if scope else ".")
    return "\n\n".join(f"[{h.document_title} · chunk {h.ordinal} · score {h.score}]\n{h.text}" for h in hits)
