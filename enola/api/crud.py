"""The one router pattern.

`crud_router()` builds list / create / get / patch / delete for an entity from its
service and schemas. Routers stay thin: parse, call the service, shape the response.
Entities that genuinely differ add extra routes next to the generated ones.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.base import Page
from enola.core.services.base import CrudService


def crud_router(
    *,
    prefix: str,
    tag: str,
    service_cls: type[CrudService[Any, Any, Any]],
    read_schema: type[BaseModel],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    list_params: type[BaseModel],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    page_schema = Page[read_schema]  # type: ignore[valid-type]

    # The schema classes are values here, but FastAPI reads them as annotations, so
    # the handlers below annotate with variables. mypy's `valid-type` complaint is the
    # cost of having one router instead of ten.

    @router.get("", response_model=page_schema, operation_id=f"{tag}_list")
    def list_items(
        params: Annotated[list_params, Query()],  # type: ignore[valid-type]
        db: DbSession,
        _: CurrentSession,
    ) -> Any:
        service = service_cls(db)
        items, total = service.list(params)
        return page_schema(items=[service.to_read(item) for item in items], total=total)

    @router.post("", response_model=read_schema, status_code=201, operation_id=f"{tag}_create")
    def create_item(body: create_schema, db: DbSession, _: CurrentSession) -> Any:  # type: ignore[valid-type]
        service = service_cls(db)
        return service.to_read(service.create(body))

    @router.get("/{item_id}", response_model=read_schema, operation_id=f"{tag}_get")
    def get_item(item_id: int, db: DbSession, _: CurrentSession) -> Any:
        service = service_cls(db)
        return service.to_read(service.get(item_id))

    @router.patch("/{item_id}", response_model=read_schema, operation_id=f"{tag}_update")
    def update_item(item_id: int, body: update_schema, db: DbSession, _: CurrentSession) -> Any:  # type: ignore[valid-type]
        service = service_cls(db)
        return service.to_read(service.update(item_id, body))

    @router.delete("/{item_id}", status_code=204, operation_id=f"{tag}_delete")
    def delete_item(item_id: int, db: DbSession, _: CurrentSession) -> Response:
        service_cls(db).delete(item_id)
        return Response(status_code=204)

    return router
