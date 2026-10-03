"""data ownership for contracts and equipment

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_center",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospital.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_cost_center_org_code"),
    )
    op.create_index("ix_cost_center_organization_id", "cost_center", ["organization_id"])
    op.create_index("ix_cost_center_hospital_id", "cost_center", ["hospital_id"])
    op.create_index("ix_cost_center_department_id", "cost_center", ["department_id"])
    op.create_index("ix_cost_center_hospital_active", "cost_center", ["hospital_id", "is_active"])
    op.create_index("ix_cost_center_department_active", "cost_center", ["department_id", "is_active"])

    op.add_column("contract", sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contract", sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contract", sa.Column("scope_type", sa.String(length=24), server_default="organization", nullable=False))
    op.create_foreign_key("fk_contract_hospital_id", "contract", "hospital", ["hospital_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_contract_cost_center_id", "contract", "cost_center", ["cost_center_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint("scope_type", "contract", "scope_type IN ('organization','hospital','department')")
    op.create_index("ix_contract_org_hospital", "contract", ["organization_id", "hospital_id"])
    op.create_index("ix_contract_org_cost_center", "contract", ["organization_id", "cost_center_id"])

    op.add_column("equipment", sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("equipment", sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("equipment", sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_equipment_hospital_id", "equipment", "hospital", ["hospital_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_equipment_department_id", "equipment", "department", ["department_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_equipment_cost_center_id", "equipment", "cost_center", ["cost_center_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_equipment_org_hospital", "equipment", ["organization_id", "hospital_id"])
    op.create_index("ix_equipment_org_department", "equipment", ["organization_id", "department_id"])
    op.create_index("ix_equipment_org_cost_center", "equipment", ["organization_id", "cost_center_id"])


def downgrade() -> None:
    op.drop_index("ix_equipment_org_cost_center", table_name="equipment")
    op.drop_index("ix_equipment_org_department", table_name="equipment")
    op.drop_index("ix_equipment_org_hospital", table_name="equipment")
    op.drop_constraint("fk_equipment_cost_center_id", "equipment", type_="foreignkey")
    op.drop_constraint("fk_equipment_department_id", "equipment", type_="foreignkey")
    op.drop_constraint("fk_equipment_hospital_id", "equipment", type_="foreignkey")
    op.drop_column("equipment", "cost_center_id")
    op.drop_column("equipment", "department_id")
    op.drop_column("equipment", "hospital_id")

    op.drop_index("ix_contract_org_cost_center", table_name="contract")
    op.drop_index("ix_contract_org_hospital", table_name="contract")
    op.drop_constraint("scope_type", "contract", type_="check")
    op.drop_constraint("fk_contract_cost_center_id", "contract", type_="foreignkey")
    op.drop_constraint("fk_contract_hospital_id", "contract", type_="foreignkey")
    op.drop_column("contract", "scope_type")
    op.drop_column("contract", "cost_center_id")
    op.drop_column("contract", "hospital_id")

    op.drop_table("cost_center")
