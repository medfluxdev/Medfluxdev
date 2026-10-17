"""Umsetzung von Vertragsentscheidungen: Ausgangs-Vertragsende und abgehakte Schritte.

Revision ID: ze5f7a9b0023
Revises: zd4e6f8a0022

`contract_lifecycle_decision.baseline_end` keeps the contract end at the time of the
decision (NULL for older decisions; the effective date is used instead).
`steps_done` stores the steps a person ticked off (key -> who/when). Existing rows get
an empty object; nothing else changes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ze5f7a9b0023"
down_revision = "zd4e6f8a0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_lifecycle_decision", sa.Column("baseline_end", sa.Date(), nullable=True))
    op.add_column(
        "contract_lifecycle_decision",
        sa.Column("steps_done", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("contract_lifecycle_decision", "steps_done")
    op.drop_column("contract_lifecycle_decision", "baseline_end")
