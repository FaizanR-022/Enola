from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import func, select

from enola.core.enums import ApprovalState
from enola.core.models.infra import ApprovalRequest
from enola.core.repository import Repository
from enola.core.schemas.infra import ApprovalListParams, ApprovalRead
from enola.core.services.base import CrudService


class ApprovalRepository(Repository[ApprovalRequest]):
    model = ApprovalRequest
    default_order = ("-created_at",)


class ApprovalService(CrudService[ApprovalRequest, BaseModel, BaseModel]):
    """Reads only. Deciding lives in AgentService because it resumes the run."""

    repo_cls = ApprovalRepository
    read_schema = ApprovalRead

    def list(self, params: BaseModel) -> tuple[Sequence[ApprovalRequest], int]:
        assert isinstance(params, ApprovalListParams)
        stmt = select(ApprovalRequest)
        if params.state is not None:
            stmt = stmt.where(ApprovalRequest.state == params.state)
        # Held first, then newest.
        stmt = stmt.order_by((ApprovalRequest.state == ApprovalState.HELD).desc(), ApprovalRequest.created_at.desc())
        rows = list(self.db.scalars(stmt).all())
        return rows[params.offset : params.offset + params.limit], len(rows)

    def held_count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.state == ApprovalState.HELD)) or 0)
