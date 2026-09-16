"""What a tool can see while it runs: a database session and the run's correlation ids.

Tools take only their user-facing arguments (that is what the model sees), so the
rest arrives through a context variable set by the graph before each call.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ToolContext:
    db: Session
    run_id: str
    thread_id: str
    scope: str


_current: ContextVar[ToolContext | None] = ContextVar("enola_tool_context", default=None)


def current_context() -> ToolContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError("No tool context: tools may only be called by the agent graph.")
    return ctx


@contextmanager
def tool_context(ctx: ToolContext) -> Iterator[None]:
    token = _current.set(ctx)
    try:
        yield
    finally:
        _current.reset(token)
