"""Additional reminders before the notice date / contract end.

Revision ID: x6a8b0c12016
Revises: w5f7a9b01015

Additive only: `contract.reminder_extra_leads` (list of value + unit) and
`contract_deadline.extra_remind_on` (ISO dates, each reminder sent once).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "x6a8b0c12016"
down_revision = "w5f7a9b01015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract", sa.Column("reminder_extra_leads", postgresql.JSONB(), nullable=True))
    op.add_column("contract_deadline", sa.Column("extra_remind_on", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("contract_deadline", "extra_remind_on")
    op.drop_column("contract", "reminder_extra_leads")
