"""Phase 3 gate: a fact stated in one session is recalled in a fresh session and is
traceable to a memory_fact row; a scoped retrieval query returns only in-scope chunks."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

import enola.agent.tools  # noqa: F401
from enola.agent.memory.retrieval import retrieve
from enola.agent.registry import ToolRegistry, registry as app_registry
from enola.agent.service import AgentService
from enola.core.enums import DocumentStatus, EntityType, MemorySource
from enola.core.models import Course, MemoryFact
from enola.core.services.documents import DocumentService
from enola.core.storage import LocalDiskStorage
from enola.ingest.documents import chunk_text
from enola.ingest.embeddings import HashEmbedder
from tests.agent_helpers import ScriptedModel, ai_tool_call
from tests.conftest import TEST_URL


def _records_registry() -> ToolRegistry:
    reg = ToolRegistry()
    spec = app_registry.get("remember")
    reg.register(spec)
    return reg


def test_fact_recalled_in_fresh_session(db: Session) -> None:
    registry = _records_registry()
    first = ScriptedModel(script=[
        ai_tool_call("remember", {"statement": "Prefers async-first teams with small overlap windows", "group": "About the job hunt", "told_by_owner": True}, "call_1"),
        AIMessage(content="Noted."),
    ])
    svc = AgentService(db, model=first, registry=registry, database_url=TEST_URL)
    result = svc.run(text="Just so you know: I prefer async-first teams with small overlap windows.", thread_id="session-a")
    assert result.held_approval_id is None
    db.expire_all()

    fact = db.scalar(select(MemoryFact).where(MemoryFact.statement.ilike("%async-first%")))
    assert fact is not None, "the remember tool must write a memory_fact row"
    assert fact.source == MemorySource.TOLD and fact.confidence == 100
    assert fact.thread_id == "session-a", "the fact is traceable to the session that stated it"

    second = ScriptedModel(script=[AIMessage(content="Async-first, small overlap: got it.")])
    AgentService(db, model=second, registry=registry, database_url=TEST_URL).run(text="What kind of team do I like?", thread_id="session-b")
    assert second.received, "the model must have been called in the fresh session"
    system_prompt = str(second.received[0][0].content)
    assert "Prefers async-first teams with small overlap windows" in system_prompt
    assert "(told)" in system_prompt


def test_chunking_keeps_order_and_overlap() -> None:
    text = "\n\n".join(f"Paragraph {i}. " + ("lorem ipsum " * 40) for i in range(6))
    chunks = chunk_text(text, size=600, overlap=100)
    assert len(chunks) > 3
    assert "Paragraph 0" in chunks[0]
    assert all(len(c) <= 700 for c in chunks)


def test_scoped_retrieval_returns_only_in_scope_chunks(db: Session, tmp_path: Path) -> None:
    course = Course(code="CS3006", name="Parallel and Distributed Computing")
    db.add(course)
    db.flush()
    storage = LocalDiskStorage(tmp_path)
    embedder = HashEmbedder()
    docs = DocumentService(db)
    notes = docs.upload(
        storage=storage, embedder=embedder, filename="lecture-07-consensus.md",
        data=b"# Raft leader election\n\nRandomised election timeouts between 150 and 300 milliseconds avoid split votes. A candidate wins when it collects a majority of votes for the term.\n\nLog compaction is not covered by assignment 3.",
        mime_type="text/markdown", title="Lecture 7 — consensus", entity_type=EntityType.COURSE, entity_id=course.id,
    )
    finance = docs.upload(
        storage=storage, embedder=embedder, filename="carpool-rules.txt",
        data=b"Carpool fuel is split three ways at the end of each week. Usman drives Wednesday to Friday. Settling only records the balance; nobody moves money.",
        mime_type="text/plain", title="Carpool rules", entity_type=None, entity_id=None,
    )
    assert notes.status == DocumentStatus.INGESTED and notes.chunk_count >= 1 and notes.scope == f"course:{course.id}"
    assert finance.status == DocumentStatus.INGESTED and finance.scope == "general"
    assert storage.exists(notes.storage_key)

    # Unscoped: both documents are searchable, and the semantically closer one ranks first.
    everything = retrieve(db, embedder, "how does leader election avoid split votes", scope=None, limit=5)
    assert {h.document_id for h in everything} == {notes.id, finance.id}
    assert everything[0].document_id == notes.id

    # Scoped to the course: the finance chunk never appears, even for a finance query.
    scoped = retrieve(db, embedder, "who drives the carpool and how is fuel split", scope=f"course:{course.id}", limit=5)
    assert scoped, "in-scope chunks are returned"
    assert {h.scope for h in scoped} == {f"course:{course.id}"}
    assert all(h.document_id == notes.id for h in scoped)

    # Re-attaching moves the chunks' scope with the document.
    docs.attach(finance.id, EntityType.COURSE, course.id)
    moved = retrieve(db, embedder, "carpool fuel split", scope=f"course:{course.id}", limit=5)
    assert finance.id in {h.document_id for h in moved}

    docs.delete_with_file(notes.id, storage)
    assert not storage.exists(notes.storage_key)
