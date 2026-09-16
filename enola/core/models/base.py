from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from enola.core.db import Base

__all__ = ["Base", "IdMixin", "TimestampMixin", "enum_column", "JSONB", "utcnow_column"]


class IdMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def enum_column(enum_type: type[StrEnum], **kwargs: Any) -> Any:
    """Store enums as short strings, not native Postgres enums.

    Native enums make every added value a migration with ALTER TYPE; a plain
    varchar validated by SQLAlchemy and Pydantic keeps the schema boring.
    """
    return mapped_column(
        Enum(enum_type, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        **kwargs,
    )


def utcnow_column(**kwargs: Any) -> Any:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), **kwargs)
