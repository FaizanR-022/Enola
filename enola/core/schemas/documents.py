from __future__ import annotations

from pydantic import Field

from enola.core.enums import DocumentStatus, EntityType
from enola.core.schemas.base import ReadSchema, Schema


class DocumentRead(ReadSchema):
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    entity_type: EntityType | None
    entity_id: int | None
    scope: str
    status: DocumentStatus
    chunk_count: int
    error: str


class DocumentListParams(Schema):
    entity_type: EntityType | None = None
    entity_id: int | None = None
    scope: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class RetrievalHit(Schema):
    document_id: int
    document_title: str
    chunk_id: int
    ordinal: int
    text: str
    score: float
    scope: str


class RetrievalQuery(Schema):
    query: str = Field(min_length=1)
    scope: str | None = None
    limit: int = Field(default=6, ge=1, le=50)
