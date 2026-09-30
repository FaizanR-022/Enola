from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.base import Page
from enola.core.schemas.finance import (
    AccountCreate,
    AccountListParams,
    AccountRead,
    AccountUpdate,
    CategoryCreate,
    CategoryListParams,
    CategoryRead,
    CategoryUpdate,
    FinanceSummary,
    OwedRow,
    SettlementCreate,
    SettlementListParams,
    SettlementRead,
    TransactionCreate,
    TransactionListParams,
    TransactionRead,
    TransactionUpdate,
)
from enola.core.services.finance import (
    AccountService,
    CategoryService,
    SettlementService,
    TransactionService,
    owed_rows,
)

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/accounts",
        tag="accounts",
        service_cls=AccountService,
        read_schema=AccountRead,
        create_schema=AccountCreate,
        update_schema=AccountUpdate,
        list_params=AccountListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/categories",
        tag="categories",
        service_cls=CategoryService,
        read_schema=CategoryRead,
        create_schema=CategoryCreate,
        update_schema=CategoryUpdate,
        list_params=CategoryListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/transactions",
        tag="transactions",
        service_cls=TransactionService,
        read_schema=TransactionRead,
        create_schema=TransactionCreate,
        update_schema=TransactionUpdate,
        list_params=TransactionListParams,
    )
)


@router.get("/finance/summary", response_model=FinanceSummary, tags=["finance"], operation_id="finance_summary")
def summary(db: DbSession, _: CurrentSession, month: str | None = None) -> FinanceSummary:
    return TransactionService(db).summary(month)


@router.get("/finance/balances", response_model=list[OwedRow], tags=["finance"], operation_id="finance_balances")
def balances(db: DbSession, _: CurrentSession) -> list[OwedRow]:
    return owed_rows(db)


@router.get("/settlements", response_model=Page[SettlementRead], tags=["settlements"], operation_id="settlements_list")
def list_settlements(params: Annotated[SettlementListParams, Query()], db: DbSession, _: CurrentSession) -> Page[SettlementRead]:
    service = SettlementService(db)
    rows, total = service.list(params)
    return Page[SettlementRead](items=[service.to_read(r) for r in rows], total=total)


@router.post("/settlements", response_model=SettlementRead, status_code=201, tags=["settlements"], operation_id="settlements_create")
def create_settlement(body: SettlementCreate, db: DbSession, _: CurrentSession) -> SettlementRead:
    service = SettlementService(db)
    return service.to_read(service.create(body))
