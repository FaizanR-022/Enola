from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, case, func, or_, select

from enola.core.models.finance import Transaction, TransactionSplit
from enola.core.models.people import Interaction, Person, PersonTag
from enola.core.repository import Repository
from enola.core.schemas.people import (
    InteractionCreate,
    InteractionRead,
    PersonCreate,
    PersonListParams,
    PersonRead,
    SharedMoneyRow,
)
from enola.core.services.base import CrudService


class PersonRepository(Repository[Person]):
    model = Person
    default_order = ("name",)

    def search(self, params: PersonListParams) -> Select[tuple[Person]]:
        stmt = select(Person)
        if params.tag:
            stmt = stmt.where(Person.id.in_(select(PersonTag.person_id).where(PersonTag.tag == params.tag)))
        if params.can_refer is not None:
            stmt = stmt.where(Person.can_refer == params.can_refer)
        if params.q:
            needle = f"%{params.q.strip()}%"
            tagged = select(PersonTag.person_id).where(PersonTag.tag.ilike(needle))
            stmt = stmt.where(
                or_(
                    Person.name.ilike(needle),
                    Person.role.ilike(needle),
                    Person.notes.ilike(needle),
                    Person.how_we_met.ilike(needle),
                    Person.id.in_(tagged),
                )
            )
        return stmt


def _going_cold(person: Person, now: datetime) -> tuple[int | None, bool]:
    if person.last_contacted_at is None:
        return None, person.cadence_days is not None
    days = (now - person.last_contacted_at).days
    return days, person.cadence_days is not None and days > person.cadence_days


def balances_for(db: Any, person_ids: Sequence[int]) -> dict[int, Decimal]:
    """Net unsettled PKR per person: positive means they owe you."""
    if not person_ids:
        return {}
    signed = case((Transaction.paid_by_me.is_(True), TransactionSplit.share_amount), else_=-TransactionSplit.share_amount)
    stmt = (
        select(TransactionSplit.person_id, func.coalesce(func.sum(signed), 0))
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .where(TransactionSplit.person_id.in_(list(person_ids)), TransactionSplit.settled_at.is_(None))
        .group_by(TransactionSplit.person_id)
    )
    return {int(pid): Decimal(total) for pid, total in db.execute(stmt).all()}


class PersonService(CrudService[Person, PersonCreate, BaseModel]):
    repo_cls = PersonRepository
    read_schema = PersonRead

    def __init__(self, db: Any) -> None:
        super().__init__(db)
        self._balances: dict[int, Decimal] = {}

    def list(self, params: BaseModel) -> tuple[Sequence[Person], int]:
        assert isinstance(params, PersonListParams)
        repo = self.repo
        assert isinstance(repo, PersonRepository)
        stmt = repo.search(params)
        rows = list(self.db.scalars(stmt.order_by(Person.name)).all())
        now = datetime.now(UTC)
        if params.going_cold is not None:
            rows = [p for p in rows if _going_cold(p, now)[1] == params.going_cold]
        total = len(rows)
        page = rows[params.offset : params.offset + params.limit]
        self._balances = balances_for(self.db, [p.id for p in page])
        return page, total

    def create(self, data: PersonCreate) -> Person:
        values = data.model_dump(exclude={"tags"})
        person = self.repo.create(**values)
        self._set_tags(person, data.tags)
        return person

    def update(self, id_: int, data: BaseModel) -> Person:
        values = data.model_dump(exclude_unset=True)
        tags = values.pop("tags", None)
        person = self.repo.update(id_, **values)
        if tags is not None:
            self._set_tags(person, tags)
        return person

    def _set_tags(self, person: Person, tags: Sequence[str]) -> None:
        """Reconcile in place: replacing the whole list would insert the new rows before
        the old ones are deleted and trip the (person_id, tag) unique constraint."""
        wanted = [t.strip() for t in dict.fromkeys(tags) if t.strip()]
        for existing in list(person.tags):
            if existing.tag not in wanted:
                person.tags.remove(existing)
        have = {t.tag for t in person.tags}
        for tag in wanted:
            if tag not in have:
                person.tags.append(PersonTag(tag=tag))
        self.db.flush()

    def to_read(self, row: Person) -> PersonRead:
        now = datetime.now(UTC)
        days, cold = _going_cold(row, now)
        balance = self._balances.get(row.id)
        if balance is None:
            balance = balances_for(self.db, [row.id]).get(row.id, Decimal("0"))
        return PersonRead(
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            name=row.name,
            role=row.role,
            company_id=row.company_id,
            email=row.email,
            phone=row.phone,
            how_we_met=row.how_we_met,
            notes=row.notes,
            can_refer=row.can_refer,
            cadence_days=row.cadence_days,
            tags=[t.tag for t in row.tags],
            last_contacted_at=row.last_contacted_at,
            days_since_contact=days,
            going_cold=cold,
            balance=float(balance),
        )

    def going_cold(self, limit: int = 5) -> Sequence[Person]:
        now = datetime.now(UTC)
        rows = self.db.scalars(select(Person).where(Person.cadence_days.is_not(None))).all()
        cold = [(p, _going_cold(p, now)[0] or 10**6) for p in rows if _going_cold(p, now)[1]]
        cold.sort(key=lambda pair: -pair[1])
        return [p for p, _ in cold[:limit]]


class InteractionRepository(Repository[Interaction]):
    model = Interaction
    default_order = ("-occurred_at",)


class InteractionService(CrudService[Interaction, InteractionCreate, BaseModel]):
    repo_cls = InteractionRepository
    read_schema = InteractionRead

    def create(self, data: InteractionCreate) -> Interaction:
        row = self.repo.create(**data.model_dump())
        touch_person(self.db, data.person_id, data.occurred_at)
        return row


def touch_person(db: Any, person_id: int, when: datetime) -> None:
    """Interactions are the source of truth for `last_contacted_at`; keep it monotonic."""
    person = db.get(Person, person_id)
    if person is None:
        return
    if person.last_contacted_at is None or when > person.last_contacted_at:
        person.last_contacted_at = when
        db.flush()


def shared_money_for(db: Any, person_id: int) -> list[SharedMoneyRow]:
    stmt = (
        select(TransactionSplit, Transaction)
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .where(TransactionSplit.person_id == person_id)
        .order_by(Transaction.occurred_at.desc())
        .limit(30)
    )
    rows = []
    for split, tx in db.execute(stmt).all():
        signed = split.share_amount if tx.paid_by_me else -split.share_amount
        rows.append(SharedMoneyRow(split_id=split.id, transaction_id=tx.id, title=tx.title, occurred_at=tx.occurred_at, amount=float(signed), settled_at=split.settled_at))
    return rows
