from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response
from pydantic import BaseModel, Field

from enola.api.deps import AppSettings, CurrentSession, DbSession
from enola.core import auth as auth_service
from enola.core.auth import SESSION_COOKIE

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class Owner(BaseModel):
    name: str
    email: str
    timezone: str


@router.post("/login", response_model=Owner)
def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Owner:
    token = auth_service.login(db, body.password, request.headers.get("user-agent", ""))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return Owner(name=settings.owner_name, email=settings.owner_email, timezone=settings.timezone)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    auth_service.logout(db, token)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=Owner)
def me(_: CurrentSession, settings: AppSettings) -> Owner:
    return Owner(name=settings.owner_name, email=settings.owner_email, timezone=settings.timezone)
