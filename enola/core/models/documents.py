from __future__ import annotations

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import DocumentStatus, EntityType
from enola.core.models.base import Base, IdMixin, TimestampMixin, enum_column

# The embedding width is fixed at the schema level. Changing the embedder to one with
# a different width is a migration, on purpose.
EMBEDDING_DIM = 1024


def scope_key(entity_type: EntityType | None, entity_id: int | None) -> str:
    """Retrieval scope, e.g. "course:3". Documents attached to nothing are "general"."""
    if entity_type is None or entity_id is None:
        return "general"
    return f"{entity_type.value}:{entity_id}"


class Document(Base, IdMixin, TimestampMixin):
    __tablename__ = "document"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entity_type: Mapped[EntityType | None] = enum_column(EntityType)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(80), nullable=False, default="general", index=True)
    status: Mapped[DocumentStatus] = enum_column(DocumentStatus, nullable=False, default=DocumentStatus.UPLOADED)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.ordinal"
    )


class DocumentChunk(Base, IdMixin):
    __tablename__ = "document_chunk"

    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Denormalised from the document so scoped search is a single indexed filter.
    scope: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")
