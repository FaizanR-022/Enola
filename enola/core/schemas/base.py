"""Pydantic conventions shared by every entity.

For each entity there is a `<Name>Base` (the editable fields), `<Name>Create`
(usually just the base) and `<Name>Read` (base + id + timestamps). The update shape
is derived with `partial()` rather than written out a third time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, create_model


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class ReadSchema(Schema):
    id: int
    created_at: datetime
    updated_at: datetime


def partial(base: type[BaseModel], name: str) -> type[BaseModel]:
    """An all-optional copy of `base` for PATCH bodies. Unset fields are left alone."""
    fields: dict[str, Any] = {}
    for field_name, info in base.model_fields.items():
        annotation: Any = info.annotation if info.annotation is not None else Any
        fields[field_name] = (annotation | None, None)
    return create_model(name, __base__=Schema, **fields)


ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
