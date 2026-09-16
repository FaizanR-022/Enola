from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import select

from enola.core.enums import DocumentStatus, EntityType
from enola.core.models.documents import Document, scope_key
from enola.core.repository import Repository
from enola.core.schemas.documents import DocumentListParams, DocumentRead
from enola.core.services.base import CrudService
from enola.core.storage import Storage, make_key
from enola.ingest.documents import ingest_document, rescope_chunks
from enola.ingest.embeddings import Embedder


class DocumentRepository(Repository[Document]):
    model = Document
    default_order = ("-created_at",)


class DocumentService(CrudService[Document, BaseModel, BaseModel]):
    repo_cls = DocumentRepository
    read_schema = DocumentRead

    def list(self, params: BaseModel) -> tuple[Sequence[Document], int]:
        assert isinstance(params, DocumentListParams)
        stmt = select(Document)
        if params.scope:
            stmt = stmt.where(Document.scope == params.scope)
        elif params.entity_type is not None:
            stmt = stmt.where(Document.scope == scope_key(params.entity_type, params.entity_id))
        rows = list(self.db.scalars(stmt.order_by(Document.created_at.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def upload(
        self,
        *,
        storage: Storage,
        embedder: Embedder,
        filename: str,
        data: bytes,
        mime_type: str,
        title: str | None,
        entity_type: EntityType | None,
        entity_id: int | None,
    ) -> Document:
        key = make_key(filename)
        storage.put(key, data)
        document = self.repo.create(
            title=title or filename,
            filename=filename,
            storage_key=key,
            mime_type=mime_type or "application/octet-stream",
            size_bytes=len(data),
            entity_type=entity_type,
            entity_id=entity_id,
            scope=scope_key(entity_type, entity_id),
            status=DocumentStatus.UPLOADED,
        )
        try:
            ingest_document(self.db, document, data, embedder)
        except Exception:
            pass  # the row records the failure; the upload itself succeeded
        return document

    def attach(self, id_: int, entity_type: EntityType | None, entity_id: int | None) -> Document:
        document = self.repo.get(id_)
        document.entity_type = entity_type
        document.entity_id = entity_id
        rescope_chunks(self.db, document, scope_key(entity_type, entity_id))
        return document

    def delete_with_file(self, id_: int, storage: Storage) -> None:
        document = self.repo.get(id_)
        storage.delete(document.storage_key)
        self.repo.delete(id_)
