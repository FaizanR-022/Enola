from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from pydantic import BaseModel

from enola.agent.memory.retrieval import retrieve
from enola.api.deps import CurrentSession, DbSession
from enola.core.enums import EntityType
from enola.core.schemas.base import Page
from enola.core.schemas.documents import DocumentListParams, DocumentRead, RetrievalHit, RetrievalQuery
from enola.core.services.documents import DocumentService
from enola.core.storage import get_storage
from enola.ingest.embeddings import get_embedder

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class AttachRequest(BaseModel):
    entity_type: EntityType | None = None
    entity_id: int | None = None


@router.get("", response_model=Page[DocumentRead], operation_id="documents_list")
def list_documents(params: Annotated[DocumentListParams, Query()], db: DbSession, _: CurrentSession) -> Page[DocumentRead]:
    rows, total = DocumentService(db).list(params)
    return Page[DocumentRead](items=[DocumentRead.model_validate(r) for r in rows], total=total)


@router.post("", response_model=DocumentRead, status_code=201, operation_id="documents_upload")
async def upload(
    db: DbSession,
    _: CurrentSession,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    entity_type: Annotated[EntityType | None, Form()] = None,
    entity_id: Annotated[int | None, Form()] = None,
) -> DocumentRead:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        from enola.core.errors import InvalidInputError

        raise InvalidInputError("File is larger than 25 MB.")
    document = DocumentService(db).upload(
        storage=get_storage(),
        embedder=get_embedder(),
        filename=file.filename or "upload",
        data=data,
        mime_type=file.content_type or "application/octet-stream",
        title=title,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return DocumentRead.model_validate(document)


@router.post("/search", response_model=list[RetrievalHit], operation_id="documents_search")
def search(body: RetrievalQuery, db: DbSession, _: CurrentSession) -> list[RetrievalHit]:
    return retrieve(db, get_embedder(), body.query, scope=body.scope, limit=body.limit)


@router.get("/{document_id}", response_model=DocumentRead, operation_id="documents_get")
def get_document(document_id: int, db: DbSession, _: CurrentSession) -> DocumentRead:
    return DocumentRead.model_validate(DocumentService(db).get(document_id))


@router.get("/{document_id}/file", operation_id="documents_file")
def get_file(document_id: int, db: DbSession, _: CurrentSession) -> Response:
    document = DocumentService(db).get(document_id)
    data = get_storage().get(document.storage_key)
    return Response(content=data, media_type=document.mime_type, headers={"content-disposition": f'inline; filename="{document.filename}"'})


@router.post("/{document_id}/attach", response_model=DocumentRead, operation_id="documents_attach")
def attach(document_id: int, body: AttachRequest, db: DbSession, _: CurrentSession) -> DocumentRead:
    return DocumentRead.model_validate(DocumentService(db).attach(document_id, body.entity_type, body.entity_id))


@router.delete("/{document_id}", status_code=204, operation_id="documents_delete")
def delete_document(document_id: int, db: DbSession, _: CurrentSession) -> Response:
    DocumentService(db).delete_with_file(document_id, get_storage())
    return Response(status_code=204)
