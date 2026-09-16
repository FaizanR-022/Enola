from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import case, func, select

from enola.core.enums import TransactionKind
from enola.core.errors import InvalidInputError, NotFoundError
from enola.core.models.finance import Account, Category, Transaction, TransactionSplit
from enola.core.models.people import Person
from enola.core.repository import Repository
from enola.core.schemas.finance import (
    AccountCreate,
    AccountRead,
    CategoryCreate,
    CategoryRead,
    FinanceSummary,
    OwedRow,
    SpendRow,
    SplitRead,
    TransactionBase,
    TransactionCreate,
    TransactionListParams,
    TransactionRead,
)
from enola.core.services.base import CrudService

OUTFLOW = (TransactionKind.EXPENSE, TransactionKind.TRANSFER)


def _signed_amount() -> Any:
    """Inflow positive, outflow negative. Settlements follow `paid_by_me`."""
    return case(
        (Transaction.kind == TransactionKind.INCOME, Transaction.amount),
        (Transaction.kind.in_(OUTFLOW), -Transaction.amount),
        (Transaction.paid_by_me.is_(True), -Transaction.amount),
        else_=Transaction.amount,
    )


def month_bounds(month: str | None) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    year, mon = (int(x) for x in month.split("-")) if month else (now.year, now.month)
    start = datetime(year, mon, 1, tzinfo=UTC)
    end = datetime(year + (mon == 12), 1 if mon == 12 else mon + 1, 1, tzinfo=UTC)
    return start, end


class AccountRepository(Repository[Account]):
    model = Account
    default_order = ("id",)


class AccountService(CrudService[Account, AccountCreate, BaseModel]):
    repo_cls = AccountRepository
    read_schema = AccountRead

    def to_read(self, row: Account) -> AccountRead:
        signed = _signed_amount()
        total = self.db.scalar(select(func.coalesce(func.sum(signed), 0)).where(Transaction.account_id == row.id)) or 0
        start, end = month_bounds(None)
        delta = (
            self.db.scalar(
                select(func.coalesce(func.sum(signed), 0)).where(
                    Transaction.account_id == row.id, Transaction.occurred_at >= start, Transaction.occurred_at < end
                )
            )
            or 0
        )
        base = AccountCreate.model_validate(row).model_dump()
        return AccountRead(
            **base,
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            balance=row.opening_balance + Decimal(total),
            month_delta=Decimal(delta),
        )


class CategoryRepository(Repository[Category]):
    model = Category
    default_order = ("name",)


class CategoryService(CrudService[Category, CategoryCreate, BaseModel]):
    repo_cls = CategoryRepository
    read_schema = CategoryRead


class TransactionRepository(Repository[Transaction]):
    model = Transaction
    default_order = ("-occurred_at", "-id")


class TransactionService(CrudService[Transaction, TransactionCreate, BaseModel]):
    repo_cls = TransactionRepository
    read_schema = TransactionRead

    def list(self, params: BaseModel) -> tuple[Sequence[Transaction], int]:
        assert isinstance(params, TransactionListParams)
        stmt = select(Transaction)
        if params.account_id is not None:
            stmt = stmt.where(Transaction.account_id == params.account_id)
        if params.category_id is not None:
            stmt = stmt.where(Transaction.category_id == params.category_id)
        if params.month:
            start, end = month_bounds(params.month)
            stmt = stmt.where(Transaction.occurred_at >= start, Transaction.occurred_at < end)
        rows = list(self.db.scalars(stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def create(self, data: TransactionCreate) -> Transaction:
        values = data.model_dump(exclude={"splits"})
        tx = self.repo.create(**values)
        if data.splits:
            if any(self.db.get(Person, s.person_id) is None for s in data.splits):
                raise NotFoundError("One of the split people does not exist.")
            # Even split across everyone listed plus you, unless shares are given.
            even = (data.amount / (len(data.splits) + 1)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            for split in data.splits:
                share = split.share_amount if split.share_amount is not None else even
                if share <= 0 or share > data.amount:
                    raise InvalidInputError("A split share must be positive and no more than the amount.")
                tx.splits.append(TransactionSplit(person_id=split.person_id, share_amount=share))
            self.db.flush()
        return tx

    def settle_split(self, split_id: int) -> TransactionSplit:
        split = self.db.get(TransactionSplit, split_id)
        if split is None:
            raise NotFoundError(f"Split {split_id} not found")
        split.settled_at = datetime.now(UTC)
        self.db.flush()
        return split

    def to_read(self, row: Transaction) -> TransactionRead:
        base = TransactionBase.model_validate(row).model_dump()
        splits = []
        for s in row.splits:
            person = self.db.get(Person, s.person_id)
            splits.append(SplitRead(id=s.id, person_id=s.person_id, person_name=person.name if person else "?", share_amount=s.share_amount, settled_at=s.settled_at))
        category = self.db.get(Category, row.category_id) if row.category_id else None
        account = self.db.get(Account, row.account_id)
        return TransactionRead(
            **base,
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            category_name=category.name if category else None,
            account_name=account.name if account else "?",
            splits=splits,
        )

    def summary(self, month: str | None) -> FinanceSummary:
        start, end = month_bounds(month)
        spend_stmt = (
            select(Category.name, Category.color_token, func.sum(Transaction.amount))
            .join(Category, Category.id == Transaction.category_id, isouter=True)
            .where(Transaction.kind == TransactionKind.EXPENSE, Transaction.occurred_at >= start, Transaction.occurred_at < end)
            .group_by(Category.name, Category.color_token)
        )
        rows = self.db.execute(spend_stmt).all()
        total = sum((Decimal(r[2]) for r in rows), Decimal("0"))
        spend = sorted(
            (
                SpendRow(category_name=r[0] or "Uncategorised", color_token=r[1] or "tx3", amount=Decimal(r[2]), pct=int(round(100 * Decimal(r[2]) / total)) if total else 0)
                for r in rows
            ),
            key=lambda s: -s.amount,
        )
        signed = case((Transaction.paid_by_me.is_(True), TransactionSplit.share_amount), else_=-TransactionSplit.share_amount)
        owed_stmt = (
            select(Person.id, Person.name, func.sum(signed), func.max(Transaction.title), func.max(Transaction.occurred_at))
            .join(TransactionSplit, TransactionSplit.person_id == Person.id)
            .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
            .where(TransactionSplit.settled_at.is_(None))
            .group_by(Person.id, Person.name)
        )
        owed = [
            OwedRow(person_id=pid, person_name=name, amount=Decimal(amount), detail=f"{title} · {when.astimezone().strftime('%d %b')}")
            for pid, name, amount, title, when in self.db.execute(owed_stmt).all()
            if Decimal(amount) != 0
        ]
        owed.sort(key=lambda o: -abs(o.amount))
        return FinanceSummary(
            month=start.strftime("%Y-%m"),
            total_spend=total,
            spend=spend,
            owed=owed,
            net_owed=sum((o.amount for o in owed), Decimal("0")),
        )
