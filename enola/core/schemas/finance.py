from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from enola.core.enums import AccountKind, TransactionKind
from enola.core.schemas.base import ReadSchema, Schema, partial


class AccountBase(Schema):
    name: str = Field(min_length=1, max_length=80)
    kind: AccountKind = AccountKind.BANK
    currency: str = "PKR"
    opening_balance: Decimal = Decimal("0")


class AccountCreate(AccountBase):
    pass


AccountUpdate = partial(AccountBase, "AccountUpdate")


class AccountRead(AccountBase, ReadSchema):
    balance: Decimal
    month_delta: Decimal


class AccountListParams(Schema):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class CategoryBase(Schema):
    name: str = Field(min_length=1, max_length=60)
    color_token: str = "tx3"


class CategoryCreate(CategoryBase):
    pass


CategoryUpdate = partial(CategoryBase, "CategoryUpdate")


class CategoryRead(CategoryBase, ReadSchema):
    pass


class CategoryListParams(Schema):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class SplitIn(Schema):
    person_id: int
    share_amount: Decimal | None = None  # None = split evenly with everyone listed plus you


class SplitRead(Schema):
    id: int
    person_id: int
    person_name: str
    share_amount: Decimal
    settled_at: datetime | None


class TransactionBase(Schema):
    account_id: int
    category_id: int | None = None
    kind: TransactionKind = TransactionKind.EXPENSE
    amount: Decimal = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    notes: str = ""
    occurred_at: datetime
    paid_by_me: bool = True


class TransactionCreate(TransactionBase):
    splits: list[SplitIn] = Field(default_factory=list)


TransactionUpdate = partial(TransactionBase, "TransactionUpdate")


class TransactionRead(TransactionBase, ReadSchema):
    category_name: str | None
    account_name: str
    splits: list[SplitRead]


class TransactionListParams(Schema):
    account_id: int | None = None
    category_id: int | None = None
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class OwedRow(Schema):
    person_id: int
    person_name: str
    # Positive: they owe you. Negative: you owe them.
    amount: Decimal
    detail: str


class SpendRow(Schema):
    category_name: str
    color_token: str
    amount: Decimal
    pct: int


class FinanceSummary(Schema):
    month: str
    total_spend: Decimal
    spend: list[SpendRow]
    owed: list[OwedRow]
    net_owed: Decimal
