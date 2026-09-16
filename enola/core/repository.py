"""The one CRUD pattern.

`Repository[Model]` covers get / list / create / update / delete for every entity.
Services specialise by subclassing or by adding functions next to it, never by
copying this file. Filters are equality on column names; anything cleverer is a
method on a subclass.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from enola.core.errors import NotFoundError
from enola.core.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    model: type[ModelT]
    default_order: tuple[str, ...] = ("-id",)

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- reads -------------------------------------------------------------------

    def get(self, id_: int) -> ModelT:
        row = self.db.get(self.model, id_)
        if row is None:
            raise NotFoundError(f"{self.model.__name__} {id_} not found")
        return row

    def find(self, id_: int) -> ModelT | None:
        return self.db.get(self.model, id_)

    def query(self, **filters: Any) -> Select[tuple[ModelT]]:
        stmt = select(self.model)
        for name, value in filters.items():
            if value is None:
                continue
            column = getattr(self.model, name)
            stmt = stmt.where(column.in_(value) if isinstance(value, (list, tuple, set)) else column == value)
        return stmt

    def list(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        order: Iterable[str] | None = None,
        **filters: Any,
    ) -> Sequence[ModelT]:
        stmt = self.query(**filters)
        for key in order or self.default_order:
            column = getattr(self.model, key.lstrip("-"))
            stmt = stmt.order_by(column.desc() if key.startswith("-") else column.asc())
        return self.db.scalars(stmt.limit(limit).offset(offset)).all()

    def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.query(**filters).subquery())
        return int(self.db.scalar(stmt) or 0)

    # --- writes ------------------------------------------------------------------

    def create(self, **values: Any) -> ModelT:
        row = self.model(**values)
        self.db.add(row)
        self.db.flush()
        return row

    def update(self, id_: int, **values: Any) -> ModelT:
        row = self.get(id_)
        for name, value in values.items():
            setattr(row, name, value)
        self.db.flush()
        return row

    def delete(self, id_: int) -> None:
        row = self.get(id_)
        self.db.delete(row)
        self.db.flush()
