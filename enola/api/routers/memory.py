from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
from enola.core.schemas.infra import (
    MemoryFactCreate,
    MemoryFactListParams,
    MemoryFactRead,
    MemoryFactUpdate,
)
from enola.core.services.memory import MemoryFactService

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/memory",
        tag="memory",
        service_cls=MemoryFactService,
        read_schema=MemoryFactRead,
        create_schema=MemoryFactCreate,
        update_schema=MemoryFactUpdate,
        list_params=MemoryFactListParams,
    )
)


@router.post("/memory/{fact_id}/forget", response_model=MemoryFactRead, tags=["memory"], operation_id="memory_forget")
def forget(fact_id: int, db: DbSession, _: CurrentSession) -> MemoryFactRead:
    service = MemoryFactService(db)
    return MemoryFactRead.model_validate(service.forget(fact_id))


@router.post("/memory/{fact_id}/restore", response_model=MemoryFactRead, tags=["memory"], operation_id="memory_restore")
def restore(fact_id: int, db: DbSession, _: CurrentSession) -> MemoryFactRead:
    service = MemoryFactService(db)
    return MemoryFactRead.model_validate(service.restore(fact_id))
