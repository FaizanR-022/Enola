"""Phase 1 gate: migrations run up and down cleanly, the seed loads, /health sees the DB."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from alembic import command
from enola.core.db import get_engine
from enola.core.enums import EntityType, TaskSource
from enola.core.models import Assessment, Person, Task, TaskLink
from enola.scripts.seed import seed
from tests.conftest import TEST_URL, alembic_config

# LangGraph's checkpointer owns these; they are created by its setup(), not by Alembic.
LANGGRAPH_TABLES = {"checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoint_migrations"}


def test_migrations_round_trip() -> None:
    cfg = alembic_config()
    try:
        command.downgrade(cfg, "base")
        remaining = set(inspect(get_engine(TEST_URL)).get_table_names()) - {"alembic_version"} - LANGGRAPH_TABLES
        assert remaining == set(), f"downgrade left tables behind: {remaining}"
    finally:
        command.upgrade(cfg, "head")
    names = set(inspect(get_engine(TEST_URL)).get_table_names())
    for expected in ("person", "task", "application", "assessment", "document_chunk", "approval_request", "notification", "activity_log"):
        assert expected in names


def test_seed_loads(db: Session) -> None:
    counts = seed(db)
    db.commit()
    assert counts["person"] >= 10
    assert db.query(Person).count() == counts["person"]
    # Every assessment wrote a task row, linked to its course, via the service.
    for assessment in db.query(Assessment).all():
        assert assessment.task_id is not None
        task = db.get(Task, assessment.task_id)
        assert task is not None and task.source == TaskSource.ASSESSMENT
        assert any(link.entity_type == EntityType.COURSE for link in task.links)
    assert db.query(TaskLink).count() > 0
    # Interactions set last_contacted_at on the person.
    ayesha = db.query(Person).filter(Person.name == "Ayesha Tariq").one()
    assert ayesha.last_contacted_at is not None
    # pgvector is installed in the schema.
    assert db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar() == "vector"


def test_health_reports_database(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "reachable"
