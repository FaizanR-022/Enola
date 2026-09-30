"""split followup_nudge into thread_quiet and contact_cold

Revision ID: a1b2c3d4e5f6
Revises: eef4b8d6ea63
Create Date: 2026-09-17

Migrations are never edited after being applied. Add a new one instead.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "eef4b8d6ea63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Kinds are plain strings (no native enum), so this is a data migration only.
    op.execute(
        sa.text(
            "UPDATE notification SET kind = CASE WHEN entity_type = 'person' THEN 'contact_cold' ELSE 'thread_quiet' END "
            "WHERE kind = 'followup_nudge'"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE notification SET kind = 'followup_nudge' WHERE kind IN ('thread_quiet', 'contact_cold')"))
