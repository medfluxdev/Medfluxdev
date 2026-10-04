"""multi hospital and department structure

Revision ID: a0b1c2d3e4f5
Revises: f9a3b4c5d6e7
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a0b1c2d3e4f5"
down_revision = "f9a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hospital",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_hospital_org_code"),
    )
    op.create_index("ix_hospital_organization_id", "hospital", ["organization_id"])
    op.create_index("ix_hospital_org_active", "hospital", ["organization_id", "is_active"])

    op.create_table(
        "department",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospital.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_department_hospital_code"),
    )
    op.create_index("ix_department_organization_id", "department", ["organization_id"])
    op.create_index("ix_department_hospital_id", "department", ["hospital_id"])
    op.create_index("ix_department_hospital_active", "department", ["hospital_id", "is_active"])

    op.create_table(
        "contract_department",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "department_id", name="uq_contract_department_pair"),
    )
    op.create_index("ix_contract_department_organization_id", "contract_department", ["organization_id"])
    op.create_index("ix_contract_department_contract_id", "contract_department", ["contract_id"])
    op.create_index("ix_contract_department_department_id", "contract_department", ["department_id"])


def downgrade() -> None:
    op.drop_table("contract_department")
    op.drop_table("department")
    op.drop_table("hospital")
