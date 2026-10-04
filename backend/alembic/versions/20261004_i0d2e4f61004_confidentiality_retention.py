"""Confidential contracts with access grants, data-protection flag and
default retention per contract type (H8.2, H9).

Revision ID: i0d2e4f61004
Revises: h9c1d3e51004

Additive only. No contract becomes confidential by this migration; contract
types already flagged confidential take effect through the scope query.
Default retention: 10 years for all existing types (commercial records,
§ 257 HGB / § 147 AO); editable per type.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "i0d2e4f61004"
down_revision = "h9c1d3e51004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract", sa.Column("is_confidential", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("contract", sa.Column("data_protection_relevant", sa.Boolean(), nullable=True))
    op.add_column("catalog_contract_type", sa.Column("retention_years", sa.Integer(), nullable=True))
    op.execute("UPDATE catalog_contract_type SET retention_years = 10")
    op.create_table(
        "contract_access_grant",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_contract_access_grant_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contract_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_access_grant_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", name="fk_contract_access_grant_account_id_account", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("granted_by_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_access_grant"),
        sa.UniqueConstraint("contract_id", "account_id", name="uq_contract_access_grant_pair"),
    )
    op.create_index("ix_contract_access_grant_account", "contract_access_grant", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_access_grant_account", table_name="contract_access_grant")
    op.drop_table("contract_access_grant")
    op.drop_column("catalog_contract_type", "retention_years")
    op.drop_column("contract", "data_protection_relevant")
    op.drop_column("contract", "is_confidential")
