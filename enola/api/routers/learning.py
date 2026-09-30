from __future__ import annotations

from enola.api.crud import crud_router
from enola.core.schemas.learning import (
    LearningGoalCreate,
    LearningGoalListParams,
    LearningGoalRead,
    LearningGoalUpdate,
)
from enola.core.services.learning import LearningGoalService

router = crud_router(
    prefix="/learning-goals",
    tag="learning_goals",
    service_cls=LearningGoalService,
    read_schema=LearningGoalRead,
    create_schema=LearningGoalCreate,
    update_schema=LearningGoalUpdate,
    list_params=LearningGoalListParams,
)
