"""Prove prompt caching is hitting: send two turns on a fresh thread and print the
cache numbers the model reported for each call, straight from activity_log.

    python -m enola.scripts.cache_check

Expect cache_creation > 0 on the first call and cache_read > 0 on every later one.
A second-turn cache_read of 0 means something in the prefix is changing per request.
Anthropic-only (exits cleanly on Google). Needs ANTHROPIC_API_KEY with credit; the calls are real and cost a few thousand tokens.
"""

from __future__ import annotations

import sys
import uuid

from sqlalchemy import select

from enola.agent.service import AgentService
from enola.core.config import get_settings
from enola.core.db import session_scope
from enola.core.enums import ActivityKind
from enola.core.models import ActivityLog


def main() -> None:
    if get_settings().model_provider != "anthropic":
        print("cache_check is Anthropic-only: Gemini caches implicitly and reports no cache fields. Set ENOLA_MODEL_PROVIDER=anthropic to run it.")
        return
    thread = f"cache-check-{uuid.uuid4().hex[:6]}"
    with session_scope() as db:
        service = AgentService(db)
        service.run(text="In one sentence: what can you help me with?", thread_id=thread)
        service.run(text="And in one sentence: what will you never do without asking?", thread_id=thread)
        rows = db.scalars(
            select(ActivityLog).where(ActivityLog.thread_id == thread, ActivityLog.kind == ActivityKind.MODEL_CALL).order_by(ActivityLog.id)
        ).all()
    print(f"{'call':>4}  {'model':<22} {'input':>7} {'cache_creation':>15} {'cache_read':>11} {'output':>7}")
    for i, row in enumerate(rows, 1):
        d = row.detail
        print(f"{i:>4}  {d['model']:<22} {d['input_tokens']:>7} {d['cache_creation']:>15} {d['cache_read']:>11} {d['output_tokens']:>7}")
    if len(rows) >= 2 and rows[-1].detail["cache_read"] > 0:
        print("\nCACHE HIT: the stable prefix is being read from cache.")
    else:
        print("\nNO CACHE READ on the later call. The prefix is changing per request, or it is under the model's minimum.")
        sys.exit(1)


if __name__ == "__main__":
    main()
