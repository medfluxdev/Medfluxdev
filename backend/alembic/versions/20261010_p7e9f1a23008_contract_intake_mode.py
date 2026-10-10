"""Contract intake mode chosen in the import wizard.

Revision ID: p7e9f1a23008
Revises: o6d8e0f12007

Additive only: one nullable column. NULL = imported before the wizard (follows the
organisation review mode as before).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "p7e9f1a23008"
down_revision = "o6d8e0f12007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract", sa.Column("intake_mode", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_contract_intake_mode",
        "contract",
        "intake_mode IS NULL OR intake_mode IN ('ai_human_review', 'ai_direct', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contract_intake_mode", "contract", type_="check")
    op.drop_column("contract", "intake_mode")
