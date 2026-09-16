from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
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
    SplitRead,
    TransactionCreate,
    TransactionListParams,
    TransactionRead,
    TransactionUpdate,
)
from enola.core.services.finance import AccountService, CategoryService, TransactionService

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


@router.post("/splits/{split_id}/settle", response_model=SplitRead, tags=["finance"], operation_id="splits_settle")
def settle(split_id: int, db: DbSession, _: CurrentSession) -> SplitRead:
    split = TransactionService(db).settle_split(split_id)
    tx = TransactionService(db).to_read(split.transaction)
    return next(s for s in tx.splits if s.id == split.id)
