"""Maintained annual cost cache on contract, indexes for the register and
server-side saved views for the classic contract list (H7 gaps).

Revision ID: k2f4a6b81004
Revises: j1e3f5a71004

Additive only. The cache columns are filled by the daily job (and on every
finance or master-data change); until then the list falls back to the AI
calculation, exactly as before.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "k2f4a6b81004"
down_revision = "j1e3f5a71004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract", sa.Column("maintained_annual_cost", sa.Numeric(14, 2), nullable=True))
    op.add_column("contract", sa.Column("maintained_annual_currency", sa.String(3), nullable=True))
    op.add_column("contract", sa.Column("maintained_cost_as_of", sa.Date(), nullable=True))
    op.create_index("ix_contract_org_maintained_cost", "contract", ["organization_id", "maintained_annual_cost"])
    op.create_index("ix_notification_contract_id", "notification", ["contract_id"])
    op.drop_constraint("ck_saved_view_view_kind", "saved_view", type_="check")
    op.create_check_constraint("ck_saved_view_view_kind", "saved_view", "view_kind IN ('register', 'contracts')")


def downgrade() -> None:
    op.execute("DELETE FROM saved_view WHERE view_kind = 'contracts'")
    op.drop_constraint("ck_saved_view_view_kind", "saved_view", type_="check")
    op.create_check_constraint("ck_saved_view_view_kind", "saved_view", "view_kind IN ('register')")
    op.drop_index("ix_notification_contract_id", table_name="notification")
    op.drop_index("ix_contract_org_maintained_cost", table_name="contract")
    op.drop_column("contract", "maintained_cost_as_of")
    op.drop_column("contract", "maintained_annual_currency")
    op.drop_column("contract", "maintained_annual_cost")
