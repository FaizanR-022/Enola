"""Money tools. Reads are SAFE; every write is local (WRITE_LOCAL) and logged, and
every write echoes exactly what was recorded so a misparse is visible at once.
Nothing here moves money; there is nothing to gate."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select

from enola.agent.context import current_context
from enola.agent.registry import tool
from enola.core.config import get_settings
from enola.core.enums import Risk, SettlementDirection, TransactionKind
from enola.core.errors import InvalidInputError
from enola.core.models.finance import Account, Category
from enola.core.models.people import Person
from enola.core.schemas.finance import SettlementCreate, SplitIn, TransactionCreate
from enola.core.services.finance import (
    CategoryService,
    SettlementService,
    TransactionService,
    balances_for,
    owed_rows,
    person_balance,
)


def _pkr(amount: Decimal | float | int | str) -> str:
    return f"PKR {Decimal(str(amount)):,.0f}"


def _amount(value: float | int | str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise InvalidInputError(f"Not an amount: {value}") from exc
    if amount <= 0:
        raise InvalidInputError("Amount must be positive.")
    return amount


def _today_label() -> str:
    return datetime.now(ZoneInfo(get_settings().timezone)).strftime("%a %d %b")


def _account(db: object, name: str | None) -> Account:
    ctx = current_context()
    stmt = select(Account).order_by(Account.id)
    accounts = list(ctx.db.scalars(stmt).all())
    if not accounts:
        raise InvalidInputError("There are no accounts yet. Add one on Finance first.")
    if not name:
        return accounts[0]  # the first account is the default (Cash, in the seed)
    for account in accounts:
        if account.name.lower().startswith(name.strip().lower()):
            return account
    raise InvalidInputError(f"No account named '{name}'. Accounts: " + ", ".join(a.name for a in accounts))


def _category(name: str | None) -> Category | None:
    ctx = current_context()
    if not name:
        return None
    existing = ctx.db.scalar(select(Category).where(Category.name.ilike(name.strip())))
    if existing is not None:
        return existing
    # Prefix match ("subs" → "subscriptions") before creating anything new.
    for category in ctx.db.scalars(select(Category)).all():
        if category.name.lower().startswith(name.strip().lower()):
            return category
    return CategoryService(ctx.db).get_or_create(name)


def _person(person_id: int) -> Person:
    ctx = current_context()
    person = ctx.db.get(Person, person_id)
    if person is None:
        raise InvalidInputError(f"No person with id {person_id}. Use search_people first.")
    return person


@tool(risk=Risk.SAFE, kind_label="finance · read")
def list_accounts() -> str:
    """The owner's accounts with their ids and current balances. The first one is the default."""
    ctx = current_context()
    from enola.core.services.finance import AccountService

    service = AccountService(ctx.db)
    rows = [service.to_read(a) for a in ctx.db.scalars(select(Account).order_by(Account.id)).all()]
    return "\n".join(f"#{a.id} {a.name} · {a.kind.value} · balance {_pkr(a.balance)}" for a in rows) or "No accounts yet."


@tool(risk=Risk.SAFE, kind_label="finance · read")
def list_categories() -> str:
    """The owner's spending categories, with ids."""
    ctx = current_context()
    rows = ctx.db.scalars(select(Category).order_by(Category.name)).all()
    return ", ".join(f"{c.name} (#{c.id})" for c in rows) or "No categories yet."


@tool(risk=Risk.SAFE, kind_label="finance · read")
def finance_summary(month: str = "") -> str:
    """This month's spend by category, income, and the net of who owes whom. Pass month as YYYY-MM for another month."""
    ctx = current_context()
    s = TransactionService(ctx.db).summary(month or None)
    lines = [f"{s.month}: spent {_pkr(s.total_spend)}, income {_pkr(s.total_income)}."]
    for row in s.spend:
        lines.append(f"  {row.category_name}: {_pkr(row.amount)} ({row.pct}%)")
    if s.owed:
        lines.append("Balances: " + "; ".join(f"{o.person_name} {'owes you' if o.amount > 0 else 'is owed'} {_pkr(abs(o.amount))}" for o in s.owed))
    else:
        lines.append("Nobody owes anybody.")
    return "\n".join(lines)


@tool(risk=Risk.SAFE, kind_label="finance · read")
def who_owes_me() -> str:
    """Per-person balances from splits and repayments. Positive means they owe the owner."""
    ctx = current_context()
    rows = owed_rows(ctx.db)
    if not rows:
        return "Nobody owes anybody right now."
    return "\n".join(f"#{o.person_id} {o.person_name}: {'owes you' if o.amount > 0 else 'you owe'} {_pkr(abs(o.amount))} · last: {o.detail}" for o in rows)


@tool(risk=Risk.WRITE_LOCAL, kind_label="finance · expense")
def log_expense(amount: float, category: str = "", account: str = "", title: str = "", note: str = "") -> str:
    """Record an expense in PKR. Category and account match the owner's existing ones by prefix
    ("fuel", "Cash"); the first account is the default. Echoes what was recorded."""
    ctx = current_context()
    acct = _account(ctx.db, account)
    cat = _category(category)
    tx = TransactionService(ctx.db).create(
        TransactionCreate(account_id=acct.id, category_id=cat.id if cat else None, kind=TransactionKind.EXPENSE, amount=_amount(amount), title=title or (cat.name if cat else "expense"), notes=note, occurred_at=datetime.now(UTC))
    )
    return f"Logged: {_pkr(tx.amount)} · {cat.name if cat else 'uncategorised'} · {acct.name} · {_today_label()} (#{tx.id})"


@tool(risk=Risk.WRITE_LOCAL, kind_label="finance · income")
def log_income(amount: float, title: str, account: str = "", note: str = "") -> str:
    """Record money the owner received (freelance, stipend, refund) into an account. Echoes what was recorded."""
    ctx = current_context()
    acct = _account(ctx.db, account)
    tx = TransactionService(ctx.db).create(TransactionCreate(account_id=acct.id, kind=TransactionKind.INCOME, amount=_amount(amount), title=title, notes=note, occurred_at=datetime.now(UTC)))
    return f"Logged income: {_pkr(tx.amount)} · {title} · {acct.name} · {_today_label()} (#{tx.id})"


@tool(risk=Risk.WRITE_LOCAL, kind_label="finance · transfer")
def log_transfer(amount: float, from_account: str, to_account: str, note: str = "") -> str:
    """Move money between two of the owner's own accounts. Total balance is unchanged. Echoes what was recorded."""
    ctx = current_context()
    src = _account(ctx.db, from_account)
    dst = _account(ctx.db, to_account)
    tx = TransactionService(ctx.db).create(
        TransactionCreate(account_id=src.id, to_account_id=dst.id, kind=TransactionKind.TRANSFER, amount=_amount(amount), title=f"Transfer {src.name} → {dst.name}", notes=note, occurred_at=datetime.now(UTC))
    )
    return f"Transferred {_pkr(tx.amount)} from {src.name} to {dst.name} · {_today_label()} (#{tx.id})"


@tool(risk=Risk.WRITE_LOCAL, kind_label="finance · split")
def split_expense(amount: float, person_ids: list[int], category: str = "", account: str = "", title: str = "", shares: list[float] | None = None) -> str:
    """Record an expense the owner paid and split it with people (ids from search_people). Even
    shares across everyone including the owner unless `shares` gives one amount per person."""
    ctx = current_context()
    if not person_ids:
        raise InvalidInputError("Name at least one person to split with.")
    if shares is not None and len(shares) != len(person_ids):
        raise InvalidInputError("Give one share per person, or none.")
    people = [_person(pid) for pid in person_ids]
    acct = _account(ctx.db, account)
    cat = _category(category)
    splits = [SplitIn(person_id=p.id, share_amount=_amount(shares[i]) if shares else None) for i, p in enumerate(people)]
    tx = TransactionService(ctx.db).create(
        TransactionCreate(account_id=acct.id, category_id=cat.id if cat else None, kind=TransactionKind.EXPENSE, amount=_amount(amount), title=title or (cat.name if cat else "shared expense"), occurred_at=datetime.now(UTC), paid_by_me=True, splits=splits)
    )
    read = TransactionService(ctx.db).to_read(tx)
    owed = ", ".join(f"{s.person_name.split()[0]} owes {_pkr(s.share_amount)}" for s in read.splits)
    return f"Logged {_pkr(tx.amount)} · {cat.name if cat else 'uncategorised'} · {acct.name} · {_today_label()}, split {len(splits) + 1} ways: {owed} (#{tx.id})"


@tool(risk=Risk.WRITE_LOCAL, kind_label="finance · settlement")
def record_settlement(person_id: int, amount: float, direction: str, note: str = "", account: str = "") -> str:
    """Record a repayment with a person: direction "they_paid_me" or "i_paid_them". Partial amounts
    are fine; the balance is derived. Echoes the new balance."""
    ctx = current_context()
    person = _person(person_id)
    try:
        where = SettlementDirection(direction)
    except ValueError as exc:
        raise InvalidInputError('direction must be "they_paid_me" or "i_paid_them"') from exc
    acct = _account(ctx.db, account) if account else None
    row = SettlementService(ctx.db).create(SettlementCreate(person_id=person.id, amount=_amount(amount), direction=where, note=note, account_id=acct.id if acct else None))
    balance = person_balance(ctx.db, person.id)
    first = person.name.split()[0]
    who = f"{first} paid you" if where == SettlementDirection.THEY_PAID_ME else f"You paid {first}"
    state = f"{first} now owes you {_pkr(balance)}." if balance > 0 else f"You now owe {first} {_pkr(-balance)}." if balance < 0 else f"You and {first} are square."
    return f"Recorded: {who} {_pkr(row.amount)}. {state} (#{row.id})"


__all__ = ["balances_for"]
