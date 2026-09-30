"""FastAPI dependencies. Routers import from here and nowhere else."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterator
from typing import Annotated

from fastapi import Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from enola.core.auth import SESSION_COOKIE, mint_session, resolve_session
from enola.core.config import Settings, get_settings
from enola.core.db import get_sessionmaker
from enola.core.errors import UnauthorizedError
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


# The ranges a home or office LAN actually uses. Deliberately not `is_private`, which
# also covers documentation and other special-purpose blocks.
LAN_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


def is_private_address(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host == "localhost"
    return address.is_loopback or address.is_link_local or any(address in net for net in LAN_NETWORKS)


def caller_is_private(request: Request) -> bool:
    """True only when the socket peer is on a loopback or private range, and, if a proxy
    added X-Forwarded-For, the original client is too. A public caller can send any
    header it likes; it cannot fake its peer address, so the header alone never
    unlocks anything."""
    peer = request.client.host if request.client else ""
    if not is_private_address(peer):
        return False
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return is_private_address(forwarded.split(",")[0].strip())
    return True


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def current_session(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UserSession:
    try:
        return resolve_session(db, token)
    except UnauthorizedError:
        # Autologin is a LAN convenience, never a bypass: it applies only when the flag is
        # on AND the caller is on a loopback or private-range address. Everyone else logs in.
        if not (settings.autologin and caller_is_private(request)):
            raise
        fresh_token, row = mint_session(db, request.headers.get("user-agent", "") + " (autologin)")
        set_session_cookie(response, fresh_token, settings)
        return row


CurrentSession = Annotated[UserSession, Depends(current_session)]
