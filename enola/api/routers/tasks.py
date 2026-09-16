from __future__ import annotations

from fastapi import APIRouter

from enola.api.crud import crud_router
from enola.api.deps import CurrentSession, DbSession
from enola.core.enums import TaskState
from enola.core.schemas.tasks import TaskCreate, TaskListParams, TaskRead, TaskUpdate
from enola.core.services.tasks import TaskService

router = APIRouter()
router.include_router(
    crud_router(
        prefix="/tasks",
        tag="tasks",
        service_cls=TaskService,
        read_schema=TaskRead,
        create_schema=TaskCreate,
        update_schema=TaskUpdate,
        list_params=TaskListParams,
    )
)


@router.post("/tasks/{task_id}/state/{state}", response_model=TaskRead, tags=["tasks"], operation_id="tasks_set_state")
def set_state(task_id: int, state: TaskState, db: DbSession, _: CurrentSession) -> TaskRead:
    service = TaskService(db)
    return TaskRead.model_validate(service.set_state(task_id, state))
