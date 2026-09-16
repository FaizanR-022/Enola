"""Layer three of memory: semantic retrieval over document chunks, always scoped.

A scope is the document's attachment ("course:3", "application:7") or "general".
Passing scope=None searches everything; the Academics chat passes its course and
sees nothing from finance, because the filter is on the chunk row itself.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from enola.core.models.documents import Document, DocumentChunk
from enola.core.schemas.documents import RetrievalHit
from enola.ingest.embeddings import Embedder


def retrieve(db: Session, embedder: Embedder, query: str, *, scope: str | None, limit: int = 6) -> list[RetrievalHit]:
    vector = embedder.embed([query])[0]
    distance = DocumentChunk.embedding.cosine_distance(vector)
    stmt = (
        select(DocumentChunk, Document.title, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .order_by(distance)
        .limit(limit)
    )
    if scope is not None:
        stmt = stmt.where(DocumentChunk.scope == scope)
    hits = []
    for chunk, title, dist in db.execute(stmt).all():
        hits.append(
            RetrievalHit(
                document_id=chunk.document_id,
                document_title=title,
                chunk_id=chunk.id,
                ordinal=chunk.ordinal,
                text=chunk.text,
                score=round(1.0 - float(dist), 4),
                scope=chunk.scope,
            )
        )
    return hits
