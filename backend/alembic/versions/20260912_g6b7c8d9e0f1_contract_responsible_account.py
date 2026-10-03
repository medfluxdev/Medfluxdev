"""add responsible account to contracts

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contract",
        sa.Column("responsible_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_contract_responsible_account",
        "contract",
        "account",
        ["responsible_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_contract_org_responsible_account",
        "contract",
        ["organization_id", "responsible_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contract_org_responsible_account", table_name="contract")
    op.drop_constraint("fk_contract_responsible_account", "contract", type_="foreignkey")
    op.drop_column("contract", "responsible_account_id")
