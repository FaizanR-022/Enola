"""settlements: partial repayment, derived split state, transfer target

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17

Migrations are never edited after being applied. Add a new one instead.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "settlement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("direction", sa.Enum("they_paid_me", "i_paid_them", name="settlementdirection", native_enum=False, length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], name=op.f("fk_settlement_account_id_account"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], name=op.f("fk_settlement_person_id_person"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settlement")),
    )
    op.create_index(op.f("ix_settlement_occurred_at"), "settlement", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_settlement_person_id"), "settlement", ["person_id"], unique=False)
    op.create_table(
        "settlement_allocation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("transaction_split_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["settlement_id"], ["settlement.id"], name=op.f("fk_settlement_allocation_settlement_id_settlement"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_split_id"], ["transaction_split.id"], name=op.f("fk_settlement_allocation_transaction_split_id_transaction_split"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settlement_allocation")),
    )
    op.create_index(op.f("ix_settlement_allocation_settlement_id"), "settlement_allocation", ["settlement_id"], unique=False)
    op.create_index(op.f("ix_settlement_allocation_transaction_split_id"), "settlement_allocation", ["transaction_split_id"], unique=False)
    op.add_column("transaction", sa.Column("to_account_id", sa.Integer(), nullable=True))
    op.create_foreign_key(op.f("fk_transaction_to_account_id_account"), "transaction", "account", ["to_account_id"], ["id"], ondelete="RESTRICT")

    # Backfill: every split that was marked settled becomes a full settlement with an
    # allocation, so nothing the owner recorded is lost.
    op.execute(
        sa.text(
            """
            INSERT INTO settlement (person_id, amount, direction, occurred_at, note, account_id)
            SELECT s.person_id, s.share_amount,
                   CASE WHEN t.paid_by_me THEN 'they_paid_me' ELSE 'i_paid_them' END,
                   s.settled_at, 'backfilled from settled split', NULL
            FROM transaction_split s JOIN transaction t ON t.id = s.transaction_id
            WHERE s.settled_at IS NOT NULL
            ORDER BY s.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO settlement_allocation (settlement_id, transaction_split_id, amount)
            SELECT st.id, s.id, s.share_amount
            FROM transaction_split s
            JOIN transaction t ON t.id = s.transaction_id
            JOIN settlement st ON st.person_id = s.person_id AND st.amount = s.share_amount
                 AND st.occurred_at = s.settled_at AND st.note = 'backfilled from settled split'
            WHERE s.settled_at IS NOT NULL
            """
        )
    )
    op.drop_column("transaction_split", "settled_at")


def downgrade() -> None:
    op.add_column("transaction_split", sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True))
    # A split counts as settled again when allocations cover its share.
    op.execute(
        sa.text(
            """
            UPDATE transaction_split s SET settled_at = sub.latest
            FROM (
                SELECT a.transaction_split_id AS split_id, SUM(a.amount) AS covered, MAX(st.occurred_at) AS latest
                FROM settlement_allocation a JOIN settlement st ON st.id = a.settlement_id
                GROUP BY a.transaction_split_id
            ) sub
            WHERE sub.split_id = s.id AND sub.covered >= s.share_amount
            """
        )
    )
    op.drop_constraint(op.f("fk_transaction_to_account_id_account"), "transaction", type_="foreignkey")
    op.drop_column("transaction", "to_account_id")
    op.drop_index(op.f("ix_settlement_allocation_transaction_split_id"), table_name="settlement_allocation")
    op.drop_index(op.f("ix_settlement_allocation_settlement_id"), table_name="settlement_allocation")
    op.drop_table("settlement_allocation")
    op.drop_index(op.f("ix_settlement_person_id"), table_name="settlement")
    op.drop_index(op.f("ix_settlement_occurred_at"), table_name="settlement")
    op.drop_table("settlement")
