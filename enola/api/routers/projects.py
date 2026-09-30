from __future__ import annotations

from enola.api.crud import crud_router
from enola.core.schemas.projects import ProjectCreate, ProjectListParams, ProjectRead, ProjectUpdate
from enola.core.services.projects import ProjectService

router = crud_router(
    prefix="/projects",
    tag="projects",
    service_cls=ProjectService,
    read_schema=ProjectRead,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    list_params=ProjectListParams,
)
