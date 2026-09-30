"""ENOLA_AUTOLOGIN mints a session for private-range clients only, and never weakens
the auth system otherwise."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from enola.api import deps
from enola.api.main import create_app
from enola.core.config import get_settings
from enola.core.db import get_sessionmaker
from tests.conftest import TEST_URL


def _client(monkeypatch: pytest.MonkeyPatch, *, autologin: bool, address: str) -> TestClient:
    settings = get_settings()
    monkeypatch.setattr(settings, "autologin", autologin)
    app = create_app()

    def test_db():  # type: ignore[no-untyped-def]
        session = get_sessionmaker(TEST_URL)()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = test_db
    return TestClient(app, client=(address, 50000))


def test_autologin_from_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, autologin=True, address="127.0.0.1") as client:
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["name"]
        assert "enola_session" in response.cookies
        # The minted session is a real one: it keeps working on the next request.
        assert client.get("/api/auth/me").status_code == 200


def test_autologin_from_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, autologin=True, address="192.168.0.42") as client:
        assert client.get("/api/auth/me").status_code == 200


def test_autologin_refused_for_public_address(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, autologin=True, address="93.184.216.34") as client:
        response = client.get("/api/auth/me")
        assert response.status_code == 401 and response.json()["error"]["code"] == "unauthorized"


def test_forwarded_public_address_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, autologin=True, address="127.0.0.1") as client:
        assert client.get("/api/auth/me", headers={"x-forwarded-for": "93.184.216.34"}).status_code == 401


def test_autologin_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, autologin=False, address="127.0.0.1") as client:
        assert client.get("/api/auth/me").status_code == 401


def test_private_address_classifier() -> None:
    assert deps.is_private_address("127.0.0.1")
    assert deps.is_private_address("10.1.2.3")
    assert deps.is_private_address("192.168.0.103")
    assert deps.is_private_address("::1")
    assert not deps.is_private_address("8.8.8.8")
    assert not deps.is_private_address("93.184.216.34")
    assert not deps.is_private_address("203.0.113.9")  # a documentation range is not a LAN
    assert not deps.is_private_address("")
