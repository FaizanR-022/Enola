from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from enola.core.enums import MemoryState
from enola.core.errors import InvalidInputError
from enola.core.models.infra import MemoryFact
from enola.core.repository import Repository
from enola.core.schemas.infra import MemoryFactCreate, MemoryFactRead
from enola.core.services.base import CrudService


class MemoryFactRepository(Repository[MemoryFact]):
    model = MemoryFact
    default_order = ("group", "-confidence", "id")


class MemoryFactService(CrudService[MemoryFact, MemoryFactCreate, BaseModel]):
    """What Enola believes about the owner. Corrections are immediate: the statement
    changes in place and the row records when it was corrected."""

    repo_cls = MemoryFactRepository
    read_schema = MemoryFactRead

    def update(self, id_: int, data: BaseModel) -> MemoryFact:
        values = data.model_dump(exclude_unset=True)
        fact = self.repo.get(id_)
        if fact.locked and ("statement" in values or "locked" in values):
            raise InvalidInputError("That is a standing rule. Unlocking it is not something Enola does.")
        if "statement" in values and values["statement"] != fact.statement:
            values["corrected_at"] = datetime.now(UTC)
            values.setdefault("confidence", 100)
        return self.repo.update(id_, **values)

    def forget(self, id_: int) -> MemoryFact:
        fact = self.repo.get(id_)
        if fact.locked:
            raise InvalidInputError("Standing rules cannot be forgotten.")
        fact.state = MemoryState.FORGOTTEN
        fact.corrected_at = datetime.now(UTC)
        self.db.flush()
        return fact

    def restore(self, id_: int) -> MemoryFact:
        fact = self.repo.get(id_)
        fact.state = MemoryState.ACTIVE
        self.db.flush()
        return fact

    def delete(self, id_: int) -> None:
        # Forgetting keeps the row (strike-through in the UI). Deleting is for mistakes.
        fact = self.repo.get(id_)
        if fact.locked:
            raise InvalidInputError("Standing rules cannot be deleted.")
        self.repo.delete(id_)
