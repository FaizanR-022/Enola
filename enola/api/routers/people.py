from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.people import (
    InteractionCreate,
    InteractionListParams,
    InteractionRead,
    InteractionUpdate,
    PersonCreate,
    PersonListParams,
    PersonRead,
    PersonUpdate,
    SharedMoneyRow,
)
from enola.core.services.people import InteractionService, PersonService, shared_money_for

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/people",
        tag="people",
        service_cls=PersonService,
        read_schema=PersonRead,
        create_schema=PersonCreate,
        update_schema=PersonUpdate,
        list_params=PersonListParams,
    )
)
router.include_router(
    crud_router(
        prefix="/interactions",
        tag="interactions",
        service_cls=InteractionService,
        read_schema=InteractionRead,
        create_schema=InteractionCreate,
        update_schema=InteractionUpdate,
        list_params=InteractionListParams,
    )
)


@router.get("/people/{person_id}/money", response_model=list[SharedMoneyRow], tags=["people"], operation_id="people_money")
def shared_money(person_id: int, db: DbSession, _: CurrentSession) -> list[SharedMoneyRow]:
    PersonService(db).get(person_id)
    return shared_money_for(db, person_id)
