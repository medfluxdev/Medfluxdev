"""Contract rules ("Playbooks") per organisation, checked deterministically in code.

Revision ID: n5c7d9e01006
Revises: m4b6c8d01004

Additive only: one new table, no change to existing data.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "n5c7d9e01006"
down_revision = "m4b6c8d01004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_contract_rule_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("rule_kind", sa.String(32), nullable=False),
        sa.Column("threshold", sa.Numeric(14, 2), nullable=True),
        sa.Column("field_key", sa.String(64), nullable=True),
        sa.Column("contract_type_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_rule"),
    )
    op.create_index("ix_contract_rule_org_active", "contract_rule", ["organization_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_contract_rule_org_active", table_name="contract_rule")
    op.drop_table("contract_rule")
