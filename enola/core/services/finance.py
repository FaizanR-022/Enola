"""Money. Manual entry, PKR, and the owner's own records.

Balances are derived, never stored: a person's net is the signed sum of their split
shares minus the signed sum of settlements with them. Positive means they owe the
owner. Allocations tie a payment to particular splits for display; they never change
the net.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from enola.core.enums import SettlementDirection, TransactionKind
from enola.core.errors import InvalidInputError, NotFoundError
from enola.core.models.finance import (
    Account,
    Category,
    Settlement,
    SettlementAllocation,
    Transaction,
    TransactionSplit,
)
from enola.core.models.people import Person
from enola.core.repository import Repository
from enola.core.schemas.finance import (
    AccountCreate,
    AccountRead,
    CategoryCreate,
    CategoryRead,
    FinanceSummary,
    OwedRow,
    SettlementCreate,
    SettlementListParams,
    SettlementRead,
    SpendRow,
    SplitRead,
    TransactionBase,
    TransactionCreate,
    TransactionListParams,
    TransactionRead,
)
from enola.core.services.base import CrudService

OUTFLOW = (TransactionKind.EXPENSE, TransactionKind.TRANSFER)
ZERO = Decimal("0")


def month_bounds(month: str | None) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    year, mon = (int(x) for x in month.split("-")) if month else (now.year, now.month)
    start = datetime(year, mon, 1, tzinfo=UTC)
    end = datetime(year + (mon == 12), 1 if mon == 12 else mon + 1, 1, tzinfo=UTC)
    return start, end


# --- balances ------------------------------------------------------------------------


def _signed_share() -> Any:
    """+share when the owner paid (they owe), −share when someone else paid (owner owes)."""
    return case((Transaction.paid_by_me.is_(True), TransactionSplit.share_amount), else_=-TransactionSplit.share_amount)


def _signed_settlement() -> Any:
    """they_paid_me lowers what they owe (−); i_paid_them lowers what the owner owes (+)."""
    return case((Settlement.direction == SettlementDirection.THEY_PAID_ME, -Settlement.amount), else_=Settlement.amount)


def balances_for(db: Session, person_ids: Sequence[int] | None = None) -> dict[int, Decimal]:
    """Net PKR per person: positive means they owe the owner. Zero-net people are omitted."""
    shares_stmt = (
        select(TransactionSplit.person_id, func.coalesce(func.sum(_signed_share()), 0))
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .group_by(TransactionSplit.person_id)
    )
    settle_stmt = select(Settlement.person_id, func.coalesce(func.sum(_signed_settlement()), 0)).group_by(Settlement.person_id)
    if person_ids is not None:
        if not person_ids:
            return {}
        shares_stmt = shares_stmt.where(TransactionSplit.person_id.in_(list(person_ids)))
        settle_stmt = settle_stmt.where(Settlement.person_id.in_(list(person_ids)))
    totals: dict[int, Decimal] = {}
    for pid, total in db.execute(shares_stmt).all():
        totals[int(pid)] = totals.get(int(pid), ZERO) + Decimal(total)
    for pid, total in db.execute(settle_stmt).all():
        totals[int(pid)] = totals.get(int(pid), ZERO) + Decimal(total)
    return {pid: amount for pid, amount in totals.items() if amount != 0}


def person_balance(db: Session, person_id: int) -> Decimal:
    return balances_for(db, [person_id]).get(person_id, ZERO)


def allocated_for(db: Session, split_ids: Sequence[int]) -> dict[int, Decimal]:
    if not split_ids:
        return {}
    stmt = (
        select(SettlementAllocation.transaction_split_id, func.coalesce(func.sum(SettlementAllocation.amount), 0))
        .where(SettlementAllocation.transaction_split_id.in_(list(split_ids)))
        .group_by(SettlementAllocation.transaction_split_id)
    )
    return {int(sid): Decimal(total) for sid, total in db.execute(stmt).all()}


# --- accounts / categories ----------------------------------------------------------


class AccountRepository(Repository[Account]):
    model = Account
    default_order = ("id",)


def _account_flow(db: Session, account_id: int, start: datetime | None = None, end: datetime | None = None) -> Decimal:
    """Net movement on one account: income in, expenses and transfers out, transfers
    in, settlements in or out when they name the account."""
    signed_tx = case(
        (Transaction.kind == TransactionKind.INCOME, Transaction.amount),
        (Transaction.kind.in_(OUTFLOW), -Transaction.amount),
        else_=ZERO,
    )
    out_stmt = select(func.coalesce(func.sum(signed_tx), 0)).where(Transaction.account_id == account_id)
    in_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.to_account_id == account_id, Transaction.kind == TransactionKind.TRANSFER)
    signed_settle = case((Settlement.direction == SettlementDirection.THEY_PAID_ME, Settlement.amount), else_=-Settlement.amount)
    settle_stmt = select(func.coalesce(func.sum(signed_settle), 0)).where(Settlement.account_id == account_id)
    if start is not None and end is not None:
        out_stmt = out_stmt.where(Transaction.occurred_at >= start, Transaction.occurred_at < end)
        in_stmt = in_stmt.where(Transaction.occurred_at >= start, Transaction.occurred_at < end)
        settle_stmt = settle_stmt.where(Settlement.occurred_at >= start, Settlement.occurred_at < end)
    return Decimal(db.scalar(out_stmt) or 0) + Decimal(db.scalar(in_stmt) or 0) + Decimal(db.scalar(settle_stmt) or 0)


class AccountService(CrudService[Account, AccountCreate, BaseModel]):
    repo_cls = AccountRepository
    read_schema = AccountRead

    def to_read(self, row: Account) -> AccountRead:
        start, end = month_bounds(None)
        base = AccountCreate.model_validate(row).model_dump()
        return AccountRead(
            **base,
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            balance=row.opening_balance + _account_flow(self.db, row.id),
            month_delta=_account_flow(self.db, row.id, start, end),
        )


class CategoryRepository(Repository[Category]):
    model = Category
    default_order = ("name",)


class CategoryService(CrudService[Category, CategoryCreate, BaseModel]):
    repo_cls = CategoryRepository
    read_schema = CategoryRead

    def get_or_create(self, name: str) -> Category:
        existing = self.db.scalar(select(Category).where(Category.name.ilike(name.strip())))
        return existing or self.repo.create(name=name.strip().lower(), color_token="tx3")


# --- transactions -----------------------------------------------------------------------


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
            stmt = stmt.where((Transaction.account_id == params.account_id) | (Transaction.to_account_id == params.account_id))
        if params.category_id is not None:
            stmt = stmt.where(Transaction.category_id == params.category_id)
        if params.kind is not None:
            stmt = stmt.where(Transaction.kind == params.kind)
        if params.month:
            start, end = month_bounds(params.month)
            stmt = stmt.where(Transaction.occurred_at >= start, Transaction.occurred_at < end)
        rows = list(self.db.scalars(stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def create(self, data: TransactionCreate) -> Transaction:
        if data.kind == TransactionKind.TRANSFER:
            if data.to_account_id is None or data.to_account_id == data.account_id:
                raise InvalidInputError("A transfer needs a different destination account.")
            if self.db.get(Account, data.to_account_id) is None:
                raise NotFoundError("Destination account not found.")
        elif data.to_account_id is not None:
            raise InvalidInputError("Only transfers have a destination account.")
        if data.kind == TransactionKind.SETTLEMENT:
            raise InvalidInputError("Record repayments as settlements, not transactions.")
        if self.db.get(Account, data.account_id) is None:
            raise NotFoundError("Account not found.")
        values = data.model_dump(exclude={"splits"})
        tx = self.repo.create(**values)
        if data.splits:
            if data.kind != TransactionKind.EXPENSE:
                raise InvalidInputError("Only expenses can be split.")
            if any(self.db.get(Person, s.person_id) is None for s in data.splits):
                raise NotFoundError("One of the split people does not exist.")
            # Even split across everyone listed plus the owner, unless shares are given.
            even = (data.amount / (len(data.splits) + 1)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            for split in data.splits:
                share = split.share_amount if split.share_amount is not None else even
                if share <= 0 or share > data.amount:
                    raise InvalidInputError("A split share must be positive and no more than the amount.")
                tx.splits.append(TransactionSplit(person_id=split.person_id, share_amount=share))
            self.db.flush()
        return tx

    def to_read(self, row: Transaction) -> TransactionRead:
        base = TransactionBase.model_validate(row).model_dump()
        allocated = allocated_for(self.db, [s.id for s in row.splits])
        splits = []
        for s in row.splits:
            person = self.db.get(Person, s.person_id)
            covered = allocated.get(s.id, ZERO)
            splits.append(SplitRead(id=s.id, person_id=s.person_id, person_name=person.name if person else "?", share_amount=s.share_amount, allocated=covered, settled=covered >= s.share_amount))
        category = self.db.get(Category, row.category_id) if row.category_id else None
        account = self.db.get(Account, row.account_id)
        to_account = self.db.get(Account, row.to_account_id) if row.to_account_id else None
        return TransactionRead(
            **base,
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            category_name=category.name if category else None,
            account_name=account.name if account else "?",
            to_account_name=to_account.name if to_account else None,
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
        total = sum((Decimal(r[2]) for r in rows), ZERO)
        income = Decimal(
            self.db.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.kind == TransactionKind.INCOME, Transaction.occurred_at >= start, Transaction.occurred_at < end)
            )
            or 0
        )
        spend = sorted(
            (SpendRow(category_name=r[0] or "Uncategorised", color_token=r[1] or "tx3", amount=Decimal(r[2]), pct=int(round(100 * Decimal(r[2]) / total)) if total else 0) for r in rows),
            key=lambda s: -s.amount,
        )
        owed = owed_rows(self.db)
        return FinanceSummary(month=start.strftime("%Y-%m"), total_spend=total, total_income=income, spend=spend, owed=owed, net_owed=sum((o.amount for o in owed), ZERO))


def owed_rows(db: Session) -> list[OwedRow]:
    balances = balances_for(db)
    if not balances:
        return []
    people = {p.id: p for p in db.scalars(select(Person).where(Person.id.in_(list(balances)))).all()}
    latest: dict[int, tuple[str, datetime]] = {}
    for split, tx in db.execute(
        select(TransactionSplit, Transaction).join(Transaction, Transaction.id == TransactionSplit.transaction_id).where(TransactionSplit.person_id.in_(list(balances))).order_by(Transaction.occurred_at.desc())
    ).all():
        latest.setdefault(split.person_id, (tx.title, tx.occurred_at))
    rows = []
    for pid, amount in balances.items():
        person = people.get(pid)
        if person is None:
            continue
        title, when = latest.get(pid, ("", None))
        detail = f"{title} · {when.astimezone().strftime('%d %b')}" if when else "repayment on record"
        rows.append(OwedRow(person_id=pid, person_name=person.name, amount=amount, detail=detail))
    rows.sort(key=lambda o: -abs(o.amount))
    return rows


# --- settlements ------------------------------------------------------------------------


class SettlementRepository(Repository[Settlement]):
    model = Settlement
    default_order = ("-occurred_at", "-id")


class SettlementService(CrudService[Settlement, SettlementCreate, BaseModel]):
    repo_cls = SettlementRepository
    read_schema = SettlementRead

    def list(self, params: BaseModel) -> tuple[Sequence[Settlement], int]:
        assert isinstance(params, SettlementListParams)
        stmt = select(Settlement)
        if params.person_id is not None:
            stmt = stmt.where(Settlement.person_id == params.person_id)
        rows = list(self.db.scalars(stmt.order_by(Settlement.occurred_at.desc(), Settlement.id.desc())).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def create(self, data: SettlementCreate) -> Settlement:
        person = self.db.get(Person, data.person_id)
        if person is None:
            raise NotFoundError("Person not found.")
        if data.account_id is not None and self.db.get(Account, data.account_id) is None:
            raise NotFoundError("Account not found.")
        row = self.repo.create(**data.model_dump(exclude={"allocations", "occurred_at"}), occurred_at=data.occurred_at or datetime.now(UTC))
        if data.allocations is None:
            self._allocate_oldest_first(row)
        else:
            self._allocate_explicit(row, data)
        self.db.flush()
        return row

    def _open_splits(self, person_id: int, direction: SettlementDirection) -> Sequence[tuple[TransactionSplit, Decimal]]:
        """Splits this payment can cover, oldest first, with what is still owed on each."""
        paid_by_me = direction == SettlementDirection.THEY_PAID_ME
        stmt = (
            select(TransactionSplit)
            .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
            .where(TransactionSplit.person_id == person_id, Transaction.paid_by_me.is_(paid_by_me))
            .order_by(Transaction.occurred_at.asc(), TransactionSplit.id.asc())
        )
        splits = list(self.db.scalars(stmt).all())
        covered = allocated_for(self.db, [s.id for s in splits])
        return [(s, s.share_amount - covered.get(s.id, ZERO)) for s in splits if s.share_amount - covered.get(s.id, ZERO) > 0]

    def _allocate_oldest_first(self, row: Settlement) -> None:
        remaining = row.amount
        for split, open_amount in self._open_splits(row.person_id, row.direction):
            if remaining <= 0:
                break
            take = min(open_amount, remaining)
            row.allocations.append(SettlementAllocation(transaction_split_id=split.id, amount=take))
            remaining -= take
        # Anything left is an unallocated repayment: it still counts against the balance.

    def _allocate_explicit(self, row: Settlement, data: SettlementCreate) -> None:
        total = ZERO
        for alloc in data.allocations or []:
            split = self.db.get(TransactionSplit, alloc.transaction_split_id)
            if split is None or split.person_id != row.person_id:
                raise InvalidInputError("Allocation names a split that is not this person's.")
            open_amount = split.share_amount - allocated_for(self.db, [split.id]).get(split.id, ZERO)
            if alloc.amount > open_amount:
                raise InvalidInputError(f"Split #{split.id} has only {open_amount} outstanding.")
            row.allocations.append(SettlementAllocation(transaction_split_id=split.id, amount=alloc.amount))
            total += alloc.amount
        if total > row.amount:
            raise InvalidInputError("Allocations exceed the settlement amount.")

    def to_read(self, row: Settlement) -> SettlementRead:
        person = self.db.get(Person, row.person_id)
        base = SettlementCreate.model_validate({**{c: getattr(row, c) for c in ("person_id", "amount", "direction", "occurred_at", "note", "account_id")}, "allocations": None}).model_dump(exclude={"allocations"})
        return SettlementRead(**base, id=row.id, created_at=row.created_at, updated_at=row.updated_at, person_name=person.name if person else "?", allocated=sum((a.amount for a in row.allocations), ZERO))
