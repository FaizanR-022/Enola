"""HTTP-level agent flow: chat → Held → approve/reject through the API, plus the
dashboard and search aggregates that the wired screens depend on."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from enola.agent import service as agent_service
from enola.agent.tools import probes
from enola.scripts.seed import seed
from tests.agent_helpers import ScriptedModel, ai_tool_call


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> ScriptedModel:
    model = ScriptedModel(script=[
        ai_tool_call("send_probe", {"to": "ayesha@kestrellabs.io", "message": "Following up on the take-home."}, "call_1", text="Your 48h rule applies."),
        AIMessage(content="Sent and logged."),
    ])
    monkeypatch.setattr(agent_service, "make_model", lambda *a, **k: model)
    monkeypatch.setattr(agent_service, "model_available", lambda: True)
    probes.SENT.clear()
    return model


def test_chat_holds_and_approves_over_http(client: TestClient, scripted: ScriptedModel) -> None:
    sent = client.post("/api/chat", json={"text": "Follow up with Ayesha.", "thread_id": "http-1"})
    assert sent.status_code == 200, sent.text
    run = sent.json()
    assert run["held_approval_id"] is not None
    assert client.get("/api/approvals/count").json() == {"held": 1}
    held = client.get(f"/api/approvals/{run['held_approval_id']}").json()
    assert held["state"] == "held" and held["tool_name"] == "send_probe" and held["risk"] == "external"
    assert "48h" in held["rationale"]
    assert probes.SENT == []

    approved = client.post(f"/api/approvals/{run['held_approval_id']}/approve", json={"args": None, "note": "go"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["held_approval_id"] is None
    assert probes.SENT == [{"to": "ayesha@kestrellabs.io", "message": "Following up on the take-home."}]
    assert client.get("/api/approvals/count").json() == {"held": 0}
    history = client.get("/api/chat/http-1").json()
    assert [m["role"] for m in history] == ["you", "enola", "tool", "enola"]
    activity = client.get("/api/activity").json()
    assert [a["kind"] for a in activity] == ["approved", "held"]
    # Deciding again is refused with the one error shape.
    again = client.post(f"/api/approvals/{run['held_approval_id']}/approve", json={"args": None, "note": ""})
    assert again.status_code == 422 and again.json()["error"]["code"] == "invalid_input"


def test_chat_rejects_over_http(client: TestClient, scripted: ScriptedModel) -> None:
    run = client.post("/api/chat", json={"text": "Follow up.", "thread_id": "http-2"}).json()
    rejected = client.post(f"/api/approvals/{run['held_approval_id']}/reject", json={"args": None, "note": "Too soon."})
    assert rejected.status_code == 200 and rejected.json()["aborted"] is True
    assert probes.SENT == []
    assert client.get(f"/api/approvals/{run['held_approval_id']}").json()["resolution_note"] == "Too soon."


def test_chat_without_key_is_refused(client: TestClient) -> None:
    response = client.post("/api/chat", json={"text": "hi"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "agent_unavailable"


def test_dashboard_and_search_aggregate_real_rows(client: TestClient, db: Session) -> None:
    seed(db)
    db.commit()
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["needs_you"] > 0
    assert dashboard["held"]["count"] == 0
    assert len(dashboard["due"]) > 0 and len(dashboard["going_cold"]) > 0 and len(dashboard["activity"]) > 0
    assert any(item["title"].startswith("Quiz") for item in dashboard["today"])
    hits = client.get("/api/search", params={"q": "kestrel"}).json()
    groups = {h["group"] for h in hits}
    assert "Jobs" in groups
    assert any(h["path"].startswith("/jobs/") for h in hits)
    people = client.get("/api/search", params={"q": "ayesha"}).json()
    assert people and people[0]["group"] == "People" and people[0]["path"].startswith("/people/")
    assert client.get("/api/search", params={"q": ""}).status_code == 422
