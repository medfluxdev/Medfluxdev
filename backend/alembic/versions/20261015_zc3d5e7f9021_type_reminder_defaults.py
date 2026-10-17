"""Reminder defaults per contract type.

Revision ID: zc3d5e7f9021
Revises: zb2c4d6e8020

Additive only: `catalog_contract_type.reminder_leads` (JSONB) and
`catalog_contract_type.escalation_days_before`. Both start NULL, so every
contract keeps the organisation default (4 months, escalate when overdue)
until an admin sets a default for its type. No reminder moves on upgrade.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zc3d5e7f9021"
down_revision = "zb2c4d6e8020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_contract_type", sa.Column("reminder_leads", postgresql.JSONB(), nullable=True))
    op.add_column("catalog_contract_type", sa.Column("escalation_days_before", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_contract_type", "escalation_days_before")
    op.drop_column("catalog_contract_type", "reminder_leads")
