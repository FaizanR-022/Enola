"""One round-trip per router: create, read, list, update, delete, plus the domain rules
that the generic pattern specialises (assessment → task, splits, posting dedupe)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

NOW = datetime.now(UTC)


def iso(days: float) -> str:
    return (NOW + timedelta(days=days)).isoformat()


def test_requires_session() -> None:
    from enola.api.main import create_app

    with TestClient(create_app()) as anonymous:
        assert anonymous.get("/api/people").status_code == 401
        body = anonymous.get("/api/people").json()
        assert body["error"]["code"] == "unauthorized"


def test_people_round_trip(client: TestClient) -> None:
    created = client.post("/api/people", json={"name": "Ayesha Tariq", "role": "Recruiter", "tags": ["recruiter", "kestrel"], "cadence_days": 14})
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert sorted(created.json()["tags"]) == ["kestrel", "recruiter"]
    assert created.json()["going_cold"] is True  # cadence but never contacted

    touched = client.post("/api/interactions", json={"person_id": pid, "kind": "call", "summary": "Intro call", "occurred_at": iso(-1)})
    assert touched.status_code == 201
    person = client.get(f"/api/people/{pid}").json()
    assert person["days_since_contact"] in (0, 1)
    assert person["going_cold"] is False

    listed = client.get("/api/people", params={"tag": "kestrel"}).json()
    assert listed["total"] == 1
    assert client.get("/api/people", params={"q": "nobody"}).json()["total"] == 0

    updated = client.patch(f"/api/people/{pid}", json={"tags": ["recruiter"], "notes": "Short emails."})
    assert updated.json()["tags"] == ["recruiter"]
    assert client.delete(f"/api/people/{pid}").status_code == 204
    assert client.get(f"/api/people/{pid}").status_code == 404


def test_tasks_state_and_links(client: TestClient) -> None:
    created = client.post("/api/tasks", json={"title": "Tailor resume", "due_at": iso(0), "links": [{"entity_type": "application", "entity_id": 1, "label": "kestrel"}]}).json()
    assert created["links"][0]["label"] == "kestrel"
    done = client.post(f"/api/tasks/{created['id']}/state/done").json()
    assert done["state"] == "done" and done["completed_at"] is not None
    reopened = client.patch(f"/api/tasks/{created['id']}", json={"state": "open"}).json()
    assert reopened["completed_at"] is None
    assert client.get("/api/tasks", params={"state": "open"}).json()["total"] == 1


def test_assessment_writes_task(client: TestClient) -> None:
    course = client.post("/api/courses", json={"code": "CS3006", "name": "Parallel and Distributed Computing"}).json()
    assessment = client.post("/api/assessments", json={"course_id": course["id"], "kind": "assignment", "title": "Assignment 3", "due_at": iso(2)}).json()
    assert assessment["task_id"] is not None
    task = client.get(f"/api/tasks/{assessment['task_id']}").json()
    assert task["source"] == "assessment" and "Assignment 3" in task["title"]
    assert {link["entity_type"] for link in task["links"]} == {"course", "assessment"}

    moved = client.patch(f"/api/assessments/{assessment['id']}", json={"due_at": iso(5)}).json()
    assert client.get(f"/api/tasks/{moved['task_id']}").json()["due_at"][:10] == iso(5)[:10]
    assert client.get("/api/courses").json()["items"][0]["assessment_count"] == 1

    assert client.delete(f"/api/assessments/{assessment['id']}").status_code == 204
    assert client.get(f"/api/tasks/{assessment['task_id']}").status_code == 404


def test_jobs_pipeline_and_dedupe(client: TestClient) -> None:
    company = client.post("/api/companies", json={"name": "Kestrel Labs"}).json()
    app = client.post("/api/applications", json={"company_id": company["id"], "role_title": "Backend Engineer", "stage": "applied", "applied_at": iso(-3)}).json()
    assert app["company_name"] == "Kestrel Labs" and app["days_quiet"] == 3
    events = client.get("/api/application-events", params={"application_id": app["id"]}).json()
    assert [e["kind"] for e in events["items"]] == ["applied"]

    moved = client.patch(f"/api/applications/{app['id']}", json={"stage": "screening"}).json()
    assert moved["stage"] == "screening"
    kinds = [e["kind"] for e in client.get("/api/application-events", params={"application_id": app["id"]}).json()["items"]]
    assert "stage_change" in kinds

    posting = {"company_name": "Palegate", "role_title": "Junior Backend Engineer (FastAPI)", "match_score": 87}
    first = client.post("/api/postings", json=posting)
    assert first.status_code == 201
    dup = client.post("/api/postings", json={**posting, "role_title": "junior backend engineer (fastapi)"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "conflict"

    pulled = client.post(f"/api/postings/{first.json()['id']}/pull").json()
    assert pulled["stage"] == "saved" and pulled["company_name"] == "Palegate"
    assert client.get(f"/api/postings/{first.json()['id']}").json()["status"] == "saved"
    assert client.post(f"/api/postings/{first.json()['id']}/pull").status_code == 422


def test_finance_splits_and_summary(client: TestClient) -> None:
    usman = client.post("/api/people", json={"name": "Usman Raza"}).json()["id"]
    hamza = client.post("/api/people", json={"name": "Hamza Sheikh"}).json()["id"]
    account = client.post("/api/accounts", json={"name": "Cash", "kind": "cash", "opening_balance": "5000"}).json()
    carpool = client.post("/api/categories", json={"name": "carpool", "color_token": "oc"}).json()
    tx = client.post("/api/transactions", json={"account_id": account["id"], "category_id": carpool["id"], "amount": "2400", "title": "Carpool fuel", "occurred_at": iso(0), "splits": [{"person_id": usman}, {"person_id": hamza}]}).json()
    assert [float(s["share_amount"]) for s in tx["splits"]] == [800.0, 800.0]
    assert float(client.get(f"/api/accounts/{account['id']}").json()["balance"]) == 2600.0

    summary = client.get("/api/finance/summary").json()
    assert float(summary["net_owed"]) == 1600.0
    assert {o["person_name"]: float(o["amount"]) for o in summary["owed"]} == {"Usman Raza": 800.0, "Hamza Sheikh": 800.0}
    assert summary["spend"][0]["category_name"] == "carpool" and summary["spend"][0]["pct"] == 100

    settled = client.post(f"/api/splits/{tx['splits'][0]['id']}/settle").json()
    assert settled["settled_at"] is not None
    assert float(client.get("/api/finance/summary").json()["net_owed"]) == 800.0
    assert client.get(f"/api/people/{hamza}").json()["balance"] == 800.0


def test_projects_learning_log_memory(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "faizan/enola", "stack": ["python"], "status": "active"}).json()
    assert project["linked_task_count"] == 0
    client.post("/api/tasks", json={"title": "Write README", "links": [{"entity_type": "project", "entity_id": project["id"], "label": "enola"}]})
    assert client.get(f"/api/projects/{project['id']}").json()["linked_task_count"] == 1

    goal = client.post("/api/learning-goals", json={"title": "Go", "resources": [{"label": "tour of go"}]}).json()
    assert goal["resources"][0]["label"] == "tour of go"
    assert client.patch(f"/api/learning-goals/{goal['id']}", json={"progress_pct": 40}).json()["progress_pct"] == 40

    entry = client.post("/api/log", json={"title": "Raft stable", "tags": ["#code"], "occurred_at": iso(0)}).json()
    assert client.get("/api/log", params={"tag": "#code"}).json()["total"] == 1
    assert client.get("/api/log", params={"q": "raft"}).json()["items"][0]["id"] == entry["id"]
    assert client.get("/api/log-candidates").json() == []

    fact = client.post("/api/memory", json={"statement": "Lives in Lahore", "source": "inferred", "confidence": 41}).json()
    corrected = client.patch(f"/api/memory/{fact['id']}", json={"statement": "Lives in Karachi"}).json()
    assert corrected["corrected_at"] is not None and corrected["confidence"] == 100
    forgotten = client.post(f"/api/memory/{fact['id']}/forget").json()
    assert forgotten["state"] == "forgotten"
    rule = client.post("/api/memory", json={"statement": "Never send without approval", "source": "rule", "locked": True}).json()
    assert client.post(f"/api/memory/{rule['id']}/forget").status_code == 422
    assert client.get("/api/activity").json() == []
