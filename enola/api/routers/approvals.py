from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from enola.agent.service import AgentService
from enola.api.deps import CurrentSession, DbSession
from enola.api.routers.chat import RunRead, run_read
from enola.core.schemas.base import Page
from enola.core.schemas.infra import ApprovalDecision, ApprovalListParams, ApprovalRead
from enola.core.services.approvals import ApprovalService

router = APIRouter(prefix="/approvals", tags=["approvals"])


class HeldCount(BaseModel):
    held: int


@router.get("", response_model=Page[ApprovalRead], operation_id="approvals_list")
def list_approvals(params: Annotated[ApprovalListParams, Query()], db: DbSession, _: CurrentSession) -> Page[ApprovalRead]:
    service = ApprovalService(db)
    rows, total = service.list(params)
    return Page[ApprovalRead](items=[ApprovalRead.model_validate(r) for r in rows], total=total)


@router.get("/count", response_model=HeldCount, operation_id="approvals_held_count")
def held_count(db: DbSession, _: CurrentSession) -> HeldCount:
    return HeldCount(held=ApprovalService(db).held_count())


@router.get("/{approval_id}", response_model=ApprovalRead, operation_id="approvals_get")
def get_approval(approval_id: int, db: DbSession, _: CurrentSession) -> ApprovalRead:
    return ApprovalRead.model_validate(ApprovalService(db).get(approval_id))


@router.post("/{approval_id}/approve", response_model=RunRead, operation_id="approvals_approve")
def approve(approval_id: int, body: ApprovalDecision, db: DbSession, _: CurrentSession) -> RunRead:
    result = AgentService(db).decide(approval_id, approve=True, args=body.args, note=body.note)
    return run_read(result)


@router.post("/{approval_id}/reject", response_model=RunRead, operation_id="approvals_reject")
def reject(approval_id: int, body: ApprovalDecision, db: DbSession, _: CurrentSession) -> RunRead:
    result = AgentService(db).decide(approval_id, approve=False, note=body.note)
    return run_read(result)
