"""Device types (Gerätearten): catalog per organisation and assignment to contracts.

Revision ID: w5f7a9b01015
Revises: v4e6f8a90014

Additive only: two new tables. The default list is seeded lazily per organisation
(app/register/device_types.ensure_device_types), not by this migration.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "w5f7a9b01015"
down_revision = "v4e6f8a90014"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "catalog_device_type",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        *_timestamps(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_catalog_device_type_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("area", sa.String(32), nullable=False, server_default="sonstiges"),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("department.id", name="fk_catalog_device_type_department", ondelete="SET NULL"), nullable=True),
        sa.Column("keywords", sa.String(500), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_device_type"),
        sa.UniqueConstraint("organization_id", "code", name="uq_catalog_device_type_org_code"),
    )
    op.create_table(
        "contract_device_type",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        *_timestamps(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_contract_device_type_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contract.id", name="fk_contract_device_type_contract_id_contract", ondelete="CASCADE"), nullable=False),
        sa.Column("device_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("catalog_device_type.id", name="fk_contract_device_type_device_type", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_device_type"),
        sa.UniqueConstraint("contract_id", "device_type_id", name="uq_contract_device_type_pair"),
    )
    op.create_index("ix_contract_device_type_contract_id", "contract_device_type", ["contract_id"])
    op.create_index("ix_contract_device_type_device_type_id", "contract_device_type", ["device_type_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_device_type_device_type_id", table_name="contract_device_type")
    op.drop_index("ix_contract_device_type_contract_id", table_name="contract_device_type")
    op.drop_table("contract_device_type")
    op.drop_table("catalog_device_type")
