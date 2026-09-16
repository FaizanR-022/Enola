from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from enola.core.db import database_reachable

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    reachable = database_reachable()
    return HealthResponse(
        status="ok" if reachable else "degraded",
        database="reachable" if reachable else "unreachable",
        version="0.1.0",
    )
