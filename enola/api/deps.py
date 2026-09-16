"""FastAPI dependencies. Routers import from here and nowhere else."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from enola.core.auth import SESSION_COOKIE, resolve_session
from enola.core.config import Settings, get_settings
from enola.core.db import get_sessionmaker
from enola.core.models.infra import UserSession


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_session(
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UserSession:
    return resolve_session(db, token)


CurrentSession = Annotated[UserSession, Depends(current_session)]
