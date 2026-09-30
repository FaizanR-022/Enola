"""Test fixtures. Every test runs against the real Postgres test database
(ENOLA_TEST_DATABASE_URL) because the approval gate depends on the Postgres
checkpointer and pgvector; there is no SQLite substitute for what is being tested.

The schema is created by running the Alembic migrations once per session, and
every table is truncated between tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from enola.core.config import get_settings
from enola.core.db import Base, get_engine, get_sessionmaker

TEST_URL = get_settings().test_database_url
if not TEST_URL:
    raise RuntimeError("ENOLA_TEST_DATABASE_URL must be set to run the tests")


def alembic_config() -> Config:
    cfg = Config("alembic.ini")
    os.environ["ENOLA_ALEMBIC_URL"] = TEST_URL or ""
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> Iterator[None]:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def no_outbound_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test suite must never send real email.

    The email-to-self channel connects to a live SMTP server. Once the owner configures
    ENOLA_SMTP_*, an unguarded run would deliver every queued notification to their real
    inbox — and it did, once. Blanking the host here makes delivery fail as
    "not configured" regardless of what .env says, which is also what the scheduling
    tests assert.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "")


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    engine = get_engine(TEST_URL)
    tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
        # LangGraph's checkpoint tables are created lazily by the saver; clear them too.
        for name in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            conn.execute(text(f"DELETE FROM {name}")) if _table_exists(conn, name) else None
    yield


def _table_exists(conn: object, name: str) -> bool:
    from sqlalchemy import inspect

    return name in inspect(conn).get_table_names()  # type: ignore[arg-type]


@pytest.fixture
def db() -> Iterator[Session]:
    session = get_sessionmaker(TEST_URL)()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """An API client bound to the test database and signed in as the owner."""
    from enola.api import deps
    from enola.api.main import create_app
    from enola.core import auth

    def test_db() -> Iterator[Session]:
        session = get_sessionmaker(TEST_URL)()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[deps.get_db] = test_db
    settings = get_settings()
    monkeypatch.setattr(settings, "owner_password_hash", auth.hash_password("test-password"))
    with TestClient(app) as tc:
        response = tc.post("/api/auth/login", json={"password": "test-password"})
        assert response.status_code == 200, response.text
        yield tc
