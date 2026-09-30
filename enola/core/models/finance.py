from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import AccountKind, SettlementDirection, TransactionKind
from enola.core.models.base import Base, IdMixin, TimestampMixin, enum_column

# Manual entry only. There are no bank connections and there never will be.


class Account(Base, IdMixin, TimestampMixin):
    __tablename__ = "account"

    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    kind: Mapped[AccountKind] = enum_column(AccountKind, nullable=False, default=AccountKind.BANK)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))


class Category(Base, IdMixin, TimestampMixin):
    __tablename__ = "category"

    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    # A token name (cy, gr, oc, tx3, line2) so the UI never stores a hex colour.
    color_token: Mapped[str] = mapped_column(String(20), nullable=False, default="tx3")


class Transaction(Base, IdMixin, TimestampMixin):
    __tablename__ = "transaction"

    account_id: Mapped[int] = mapped_column(ForeignKey("account.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Transfers only: the account the money moved into.
    to_account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id", ondelete="RESTRICT"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    kind: Mapped[TransactionKind] = enum_column(TransactionKind, nullable=False, default=TransactionKind.EXPENSE)
    # Always positive; `kind` gives the direction.
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # True when you paid and others owe you their share; False when someone else paid.
    paid_by_me: Mapped[bool] = mapped_column(nullable=False, default=True)

    splits: Mapped[list[TransactionSplit]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class TransactionSplit(Base, IdMixin, TimestampMixin):
    """One person's share of a shared expense. Whether it is settled is derived from
    settlement allocations; nothing here is ever "marked paid"."""

    __tablename__ = "transaction_split"

    transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True)
    share_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="splits")
    allocations: Mapped[list[SettlementAllocation]] = relationship(back_populates="split", cascade="all, delete-orphan")


class Settlement(Base, IdMixin, TimestampMixin):
    """A payment between the owner and a person, full or partial, tied to specific
    splits only when an allocation says so. Balances are derived from splits minus
    settlements and never stored. Recording one moves no money."""

    __tablename__ = "settlement"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    direction: Mapped[SettlementDirection] = enum_column(SettlementDirection, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id", ondelete="SET NULL"))

    allocations: Mapped[list[SettlementAllocation]] = relationship(back_populates="settlement", cascade="all, delete-orphan")


class SettlementAllocation(Base, IdMixin):
    __tablename__ = "settlement_allocation"

    settlement_id: Mapped[int] = mapped_column(ForeignKey("settlement.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_split_id: Mapped[int] = mapped_column(ForeignKey("transaction_split.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    settlement: Mapped[Settlement] = relationship(back_populates="allocations")
    split: Mapped[TransactionSplit] = relationship(back_populates="allocations")
