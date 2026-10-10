"""Payment and maintenance reminders, organisation review mode.

Revision ID: o6d8e0f12007
Revises: n5c7d9e01006

Additive only: new nullable/defaulted columns, no change to existing data.
- contract_finance_entry.payment_timing (in_advance | in_arrears | NULL = nicht gepflegt)
- contract_finance_entry.payment_reminder (Zahlungserinnerung, Standard aus)
- contract.maintenance_interval_months / maintenance_next_date (Wartungstermine)
- organization.review_mode (manual | auto_noncritical, Standard manual)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "o6d8e0f12007"
down_revision = "n5c7d9e01006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_finance_entry", sa.Column("payment_timing", sa.String(12), nullable=True))
    op.add_column(
        "contract_finance_entry",
        sa.Column("payment_reminder", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_check_constraint(
        "ck_contract_finance_entry_payment_timing",
        "contract_finance_entry",
        "payment_timing IS NULL OR payment_timing IN ('in_advance', 'in_arrears')",
    )

    op.add_column("contract", sa.Column("maintenance_interval_months", sa.Integer(), nullable=True))
    op.add_column("contract", sa.Column("maintenance_next_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_contract_maintenance_interval_months",
        "contract",
        "maintenance_interval_months IS NULL OR (maintenance_interval_months >= 1 AND maintenance_interval_months <= 120)",
    )

    op.add_column(
        "organization",
        sa.Column("review_mode", sa.String(16), server_default="manual", nullable=False),
    )
    op.create_check_constraint(
        "ck_organization_review_mode",
        "organization",
        "review_mode IN ('manual', 'auto_noncritical')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_organization_review_mode", "organization", type_="check")
    op.drop_column("organization", "review_mode")
    op.drop_constraint("ck_contract_maintenance_interval_months", "contract", type_="check")
    op.drop_column("contract", "maintenance_next_date")
    op.drop_column("contract", "maintenance_interval_months")
    op.drop_constraint("ck_contract_finance_entry_payment_timing", "contract_finance_entry", type_="check")
    op.drop_column("contract_finance_entry", "payment_reminder")
    op.drop_column("contract_finance_entry", "payment_timing")
