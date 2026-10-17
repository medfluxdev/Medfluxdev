"""Leistungen & SLA: manually maintained service scope, availability and penalties.

Revision ID: z8c0d2e34018
Revises: y7b9c1d23017

Additive only: three nullable columns on `contract`. Existing AI values for
Leistungsumfang/SLA stay in the extraction and the fact review; nothing is moved.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "z8c0d2e34018"
down_revision = "y7b9c1d23017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract", sa.Column("service_scope_text", sa.Text(), nullable=True))
    op.add_column("contract", sa.Column("sla_availability_percent", sa.Numeric(6, 3), nullable=True))
    op.add_column("contract", sa.Column("penalty_terms", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("contract", "penalty_terms")
    op.drop_column("contract", "sla_availability_percent")
    op.drop_column("contract", "service_scope_text")
