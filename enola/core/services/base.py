"""Services own business rules. Routers call services; services call repositories.

`CrudService` is the default behaviour for an entity with nothing special about it.
Override `create` / `update` / `delete` / `list` / `to_read` where the domain says so.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from enola.core.models.base import Base
from enola.core.repository import Repository

ModelT = TypeVar("ModelT", bound=Base)
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)

PAGINATION_KEYS = frozenset({"limit", "offset"})


class CrudService(Generic[ModelT, CreateT, UpdateT]):
    repo_cls: type[Repository[ModelT]]
    read_schema: type[BaseModel]

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = self.repo_cls(db)

    def filters(self, params: BaseModel) -> dict[str, Any]:
        """Equality filters from list params. Override to translate richer params."""
        return {k: v for k, v in params.model_dump(exclude_none=True).items() if k not in PAGINATION_KEYS}

    def list(self, params: BaseModel) -> tuple[Sequence[ModelT], int]:
        limit = int(getattr(params, "limit", 200))
        offset = int(getattr(params, "offset", 0))
        filters = self.filters(params)
        return self.repo.list(limit=limit, offset=offset, **filters), self.repo.count(**filters)

    def get(self, id_: int) -> ModelT:
        return self.repo.get(id_)

    def create(self, data: CreateT) -> ModelT:
        return self.repo.create(**data.model_dump())

    def update(self, id_: int, data: UpdateT) -> ModelT:
        return self.repo.update(id_, **data.model_dump(exclude_unset=True))

    def delete(self, id_: int) -> None:
        self.repo.delete(id_)

    def to_read(self, row: ModelT) -> BaseModel:
        return self.read_schema.model_validate(row)
