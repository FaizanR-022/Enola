from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from enola.core.enums import ActorSource, InteractionKind
from enola.core.schemas.base import ReadSchema, Schema, partial


class PersonBase(Schema):
    name: str = Field(min_length=1, max_length=120)
    role: str = ""
    company_id: int | None = None
    email: str = ""
    phone: str = ""
    how_we_met: str = ""
    notes: str = ""
    can_refer: bool = False
    cadence_days: int | None = Field(default=None, ge=1, le=365)


class PersonCreate(PersonBase):
    tags: list[str] = Field(default_factory=list)


PersonUpdate = partial(PersonCreate, "PersonUpdate")


class PersonRead(PersonBase, ReadSchema):
    tags: list[str]
    last_contacted_at: datetime | None
    # Derived: days since last contact, and whether that is past the cadence.
    days_since_contact: int | None
    going_cold: bool
    # Net PKR the person owes you (positive) or you owe them (negative), unsettled splits only.
    balance: float


class PersonListParams(Schema):
    tag: str | None = None
    going_cold: bool | None = None
    can_refer: bool | None = None
    q: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class InteractionBase(Schema):
    person_id: int
    kind: InteractionKind = InteractionKind.NOTE
    summary: str = Field(min_length=1)
    occurred_at: datetime
    source: ActorSource = ActorSource.YOU


class InteractionCreate(InteractionBase):
    pass


InteractionUpdate = partial(InteractionBase, "InteractionUpdate")


class InteractionRead(InteractionBase, ReadSchema):
    pass


class InteractionListParams(Schema):
    person_id: int | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class SharedMoneyRow(Schema):
    split_id: int
    transaction_id: int
    title: str
    occurred_at: datetime
    # Positive: they owe you. Negative: you owe them.
    amount: float
    allocated: Decimal
    settled: bool
