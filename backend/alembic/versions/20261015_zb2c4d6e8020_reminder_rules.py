"""Termine & Aufgaben: escalation rule and per-Termin reminders.

Revision ID: zb2c4d6e8020
Revises: za1b3c5d7019

Additive only:
- `contract.escalation_days_before` (NULL = type default, otherwise escalate only when overdue),
- `contract_deadline.escalate_on` (computed by the deadline sync; NULL = escalate when overdue).
Per-Termin reminder overrides live in `contract_deadline.overrides.reminder_leads`.
Existing contracts keep their behaviour: both columns start NULL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "zb2c4d6e8020"
down_revision = "za1b3c5d7019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract", sa.Column("escalation_days_before", sa.Integer(), nullable=True))
    op.add_column("contract_deadline", sa.Column("escalate_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("contract_deadline", "escalate_on")
    op.drop_column("contract", "escalation_days_before")
