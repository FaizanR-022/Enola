from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from enola.core.models.learning import LearningGoal, LearningResource
from enola.core.repository import Repository
from enola.core.schemas.learning import LearningGoalCreate, LearningGoalRead
from enola.core.services.base import CrudService


class LearningGoalRepository(Repository[LearningGoal]):
    model = LearningGoal
    default_order = ("-progress_pct", "id")


class LearningGoalService(CrudService[LearningGoal, LearningGoalCreate, BaseModel]):
    repo_cls = LearningGoalRepository
    read_schema = LearningGoalRead

    def create(self, data: LearningGoalCreate) -> LearningGoal:
        goal = self.repo.create(**data.model_dump(exclude={"resources"}))
        goal.resources = [LearningResource(**r.model_dump()) for r in data.resources]
        self.db.flush()
        return goal

    def update(self, id_: int, data: BaseModel) -> LearningGoal:
        values = data.model_dump(exclude_unset=True)
        resources = values.pop("resources", None)
        goal = self.repo.update(id_, **values)
        if resources is not None:
            goal.resources = [LearningResource(**r) for r in resources]
            self.db.flush()
        return goal

    def to_read(self, row: LearningGoal) -> Any:
        return LearningGoalRead.model_validate(row)
