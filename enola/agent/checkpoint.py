"""LangGraph's Postgres checkpointer. The interrupt → Held → resume flow depends on it;
an in-memory saver would lose every paused run on restart and must never be substituted."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from enola.core.config import get_settings

_setup_done: set[str] = set()


def psycopg_url(sqlalchemy_url: str) -> str:
    """SQLAlchemy spells the driver into the scheme; psycopg wants the plain one."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def open_checkpointer(url: str | None = None) -> Iterator[PostgresSaver]:
    dsn = psycopg_url(url or get_settings().database_url)
    conn: Connection[DictRow]
    with Connection.connect(dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row) as conn:
        saver = PostgresSaver(conn)
        if dsn not in _setup_done:
            saver.setup()
            _setup_done.add(dsn)
        yield saver
