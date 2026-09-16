"""Session auth for a single owner.

The password is checked against a scrypt hash from config. A successful login
creates a `user_session` row and sets an HttpOnly cookie holding a random token;
the row stores only the token's SHA-256. There is no password reset, no user
table, and no "TODO: add auth" — this is the real thing, sized for one person.

    python -m enola.core.auth hash "your password"   # prints a hash for .env
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.errors import UnauthorizedError
from enola.core.models.infra import UserSession

SESSION_COOKIE = "enola_session"
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    parts = [
        "scrypt",
        str(_SCRYPT_N),
        str(_SCRYPT_R),
        str(_SCRYPT_P),
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    ]
    return "$".join(parts)


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login(db: Session, password: str, user_agent: str) -> str:
    """Return a fresh session token, or raise UnauthorizedError."""
    settings = get_settings()
    if not settings.owner_password_hash:
        raise UnauthorizedError(
            "No owner password is configured. Set ENOLA_OWNER_PASSWORD_HASH in .env."
        )
    if not verify_password(password, settings.owner_password_hash):
        raise UnauthorizedError("Wrong password.")
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        UserSession(
            token_hash=_token_hash(token),
            created_at=now,
            expires_at=now + timedelta(hours=settings.session_ttl_hours),
            last_seen_at=now,
            user_agent=user_agent[:300],
        )
    )
    db.flush()
    return token


def resolve_session(db: Session, token: str | None) -> UserSession:
    """Look up a cookie token; raise UnauthorizedError if missing, unknown or expired."""
    if not token:
        raise UnauthorizedError("Not signed in.")
    row = db.scalar(select(UserSession).where(UserSession.token_hash == _token_hash(token)))
    now = datetime.now(UTC)
    if row is None or row.expires_at < now:
        raise UnauthorizedError("Session expired. Sign in again.")
    # Touch at most once a minute to avoid a write on every request.
    if now - row.last_seen_at > timedelta(minutes=1):
        row.last_seen_at = now
        db.flush()
    return row


def logout(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))


def purge_expired(db: Session) -> int:
    result = db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
    return int(getattr(result, "rowcount", 0) or 0)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "hash":
        print(hash_password(sys.argv[2]))
    else:
        print("usage: python -m enola.core.auth hash <password>", file=sys.stderr)
        sys.exit(2)
