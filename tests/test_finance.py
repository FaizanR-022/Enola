"""Iteration 1, Phase 4: derived balances with partial settlement, the five entry paths
through the API, the migration backfill, and "I spent 450 on fuel" through the agent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from enola.agent.registry import ToolRegistry
from enola.agent.registry import registry as app_registry
from enola.agent.service import AgentService
from enola.core.enums import SettlementDirection, TransactionKind
from enola.core.models import Account, Category, Person
from enola.core.schemas.finance import SettlementCreate, SplitIn, TransactionCreate
from enola.core.services.finance import (
    SettlementService,
    TransactionService,
    balances_for,
    person_balance,
)
from tests.agent_helpers import ScriptedModel, ai_tool_call
from tests.conftest import TEST_URL, alembic_config

NOW = datetime.now(UTC)


def _fixtures(db: Session) -> tuple[Account, Category, Person]:
    account = Account(name="Cash", opening_balance=Decimal("5000"))
    fuel = Category(name="fuel", color_token="oc")
    hamza = Person(name="Hamza Sheikh")
    db.add_all([account, fuel, hamza])
    db.flush()
    return account, fuel, hamza


def test_balance_math_with_partial_settlements(db: Session) -> None:
    account, fuel, hamza = _fixtures(db)
    txs = TransactionService(db)
    # Hamza paid 1000 for something; the owner's share is 500 → owner owes 500.
    txs.create(TransactionCreate(account_id=account.id, category_id=fuel.id, kind=TransactionKind.EXPENSE, amount=Decimal("1000"), title="Dinner, Hamza paid", occurred_at=NOW, paid_by_me=False, splits=[SplitIn(person_id=hamza.id, share_amount=Decimal("500"))]))
    assert person_balance(db, hamza.id) == Decimal("-500")

    settlements = SettlementService(db)
    settlements.create(SettlementCreate(person_id=hamza.id, amount=Decimal("300"), direction=SettlementDirection.I_PAID_THEM))
    assert person_balance(db, hamza.id) == Decimal("-200")
    settlements.create(SettlementCreate(person_id=hamza.id, amount=Decimal("200"), direction=SettlementDirection.I_PAID_THEM))
    assert person_balance(db, hamza.id) == Decimal("0")
    assert balances_for(db) == {}  # zero-net people drop out

    # Now the owner pays 2400 and Hamza owes 800; a repayment tied to nothing still reduces it.
    tx = txs.create(TransactionCreate(account_id=account.id, category_id=fuel.id, kind=TransactionKind.EXPENSE, amount=Decimal("2400"), title="Carpool fuel", occurred_at=NOW, paid_by_me=True, splits=[SplitIn(person_id=hamza.id, share_amount=Decimal("800"))]))
    assert person_balance(db, hamza.id) == Decimal("800")
    unallocated = settlements.create(SettlementCreate(person_id=hamza.id, amount=Decimal("300"), direction=SettlementDirection.THEY_PAID_ME, allocations=[]))
    assert unallocated.allocations == []
    assert person_balance(db, hamza.id) == Decimal("500")
    # A further repayment allocates oldest-first and the split shows partial coverage.
    settlements.create(SettlementCreate(person_id=hamza.id, amount=Decimal("300"), direction=SettlementDirection.THEY_PAID_ME))
    read = txs.to_read(tx)
    assert read.splits[0].allocated == Decimal("300") and read.splits[0].settled is False
    assert person_balance(db, hamza.id) == Decimal("200")


def test_migration_backfills_settled_splits(db: Session) -> None:
    """Downgrade to the settled_at era, mark a split settled the old way, upgrade, and
    the split reads as settled through a real settlement row."""
    account, fuel, hamza = _fixtures(db)
    tx = TransactionService(db).create(TransactionCreate(account_id=account.id, category_id=fuel.id, kind=TransactionKind.EXPENSE, amount=Decimal("2400"), title="Carpool fuel", occurred_at=NOW - timedelta(days=3), paid_by_me=True, splits=[SplitIn(person_id=hamza.id, share_amount=Decimal("800"))]))
    split_id = tx.splits[0].id
    db.commit()
    db.close()
    cfg = alembic_config()
    command.downgrade(cfg, "a1b2c3d4e5f6")
    from enola.core.db import get_engine

    with get_engine(TEST_URL).begin() as conn:
        conn.execute(text("UPDATE transaction_split SET settled_at = now() WHERE id = :id"), {"id": split_id})
    command.upgrade(cfg, "head")
    with get_engine(TEST_URL).connect() as conn:
        settlement = conn.execute(text("SELECT person_id, amount, direction FROM settlement")).all()
        allocation = conn.execute(text("SELECT transaction_split_id, amount FROM settlement_allocation")).all()
    assert settlement == [(hamza.id, Decimal("800.00"), "they_paid_me")]
    assert allocation == [(split_id, Decimal("800.00"))]


def test_five_entry_paths_over_http(client: TestClient) -> None:
    cash = client.post("/api/accounts", json={"name": "Cash", "kind": "cash", "opening_balance": "5000"}).json()
    bank = client.post("/api/accounts", json={"name": "Meezan", "kind": "bank", "opening_balance": "20000"}).json()
    fuel = client.post("/api/categories", json={"name": "fuel"}).json()
    usman = client.post("/api/people", json={"name": "Usman Raza"}).json()["id"]

    expense = client.post("/api/transactions", json={"account_id": cash["id"], "category_id": fuel["id"], "kind": "expense", "amount": "450", "title": "Fuel", "occurred_at": NOW.isoformat()})
    assert expense.status_code == 201 and expense.json()["category_name"] == "fuel"
    income = client.post("/api/transactions", json={"account_id": bank["id"], "kind": "income", "amount": "25000", "title": "Freelance", "occurred_at": NOW.isoformat()})
    assert income.status_code == 201
    transfer = client.post("/api/transactions", json={"account_id": bank["id"], "to_account_id": cash["id"], "kind": "transfer", "amount": "3000", "title": "Top up cash", "occurred_at": NOW.isoformat()})
    assert transfer.status_code == 201 and transfer.json()["to_account_name"] == "Cash"
    bad_transfer = client.post("/api/transactions", json={"account_id": bank["id"], "kind": "transfer", "amount": "10", "title": "x", "occurred_at": NOW.isoformat()})
    assert bad_transfer.status_code == 422
    split = client.post("/api/transactions", json={"account_id": cash["id"], "category_id": fuel["id"], "kind": "expense", "amount": "2400", "title": "Carpool", "occurred_at": NOW.isoformat(), "splits": [{"person_id": usman}]})
    assert split.status_code == 201 and float(split.json()["splits"][0]["share_amount"]) == 1200.0
    settle = client.post("/api/settlements", json={"person_id": usman, "amount": "700", "direction": "they_paid_me", "account_id": cash["id"]})
    assert settle.status_code == 201 and float(settle.json()["allocated"]) == 700.0

    ledger = client.get("/api/transactions").json()
    assert {t["kind"] for t in ledger["items"]} == {"expense", "income", "transfer"}
    assert float(client.get(f"/api/accounts/{cash['id']}").json()["balance"]) == 5000 - 450 + 3000 - 2400 + 700
    assert float(client.get(f"/api/accounts/{bank['id']}").json()["balance"]) == 20000 + 25000 - 3000
    balances = client.get("/api/finance/balances").json()
    assert [(b["person_name"], float(b["amount"])) for b in balances] == [("Usman Raza", 500.0)]
    summary = client.get("/api/finance/summary").json()
    assert float(summary["total_spend"]) == 2850.0 and float(summary["total_income"]) == 25000.0
    assert float(client.get(f"/api/people/{usman}").json()["balance"]) == 500.0
    money = client.get(f"/api/people/{usman}/money").json()
    assert money[0]["allocated"] == "700.00" and money[0]["settled"] is False
    assert client.get("/api/settlements", params={"person_id": usman}).json()["total"] == 1


def test_spent_450_on_fuel_through_the_agent(db: Session) -> None:
    account, fuel, _ = _fixtures(db)
    db.commit()
    reg = ToolRegistry()
    for name in ("list_categories", "list_accounts", "log_expense"):
        reg.register(app_registry.get(name))
    model = ScriptedModel(script=[
        ai_tool_call("log_expense", {"amount": 450, "category": "fuel"}, "c1"),
        AIMessage(content="Logged: PKR 450 · fuel · Cash · today."),
    ])
    result = AgentService(db, model=model, registry=reg, database_url=TEST_URL).run(text="I spent 450 on fuel", thread_id="t-fuel")
    tool_echo = next(m.text for m in result.messages if m.role == "tool")
    assert tool_echo.startswith("Logged: PKR 450 · fuel · Cash ·")
    db.expire_all()
    rows = TransactionService(db).list(__import__("enola.core.schemas.finance", fromlist=["TransactionListParams"]).TransactionListParams())[0]
    assert len(rows) == 1 and rows[0].amount == Decimal("450") and rows[0].category_id == fuel.id and rows[0].account_id == account.id
    assert result.held_approval_id is None
