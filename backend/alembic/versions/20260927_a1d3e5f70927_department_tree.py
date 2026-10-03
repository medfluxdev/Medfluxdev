"""Add optional department parent for same-hospital organization trees.

Revision ID: a1d3e5f70927
Revises: k0f1a2b3c4d5
"""
from alembic import op
import sqlalchemy as sa

revision = "a1d3e5f70927"
down_revision = "k0f1a2b3c4d5"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("department", sa.Column("parent_id", sa.UUID(), nullable=True))
    op.create_index("ix_department_parent_id", "department", ["parent_id"])
    # Parent must belong to the SAME hospital and organization, even for direct SQL writes.
    op.create_unique_constraint(
        "uq_department_id_org_hospital", "department",
        ["id", "organization_id", "hospital_id"],
    )
    op.create_foreign_key(
        "fk_department_parent_same_scope", "department", "department",
        ["parent_id", "organization_id", "hospital_id"],
        ["id", "organization_id", "hospital_id"],
        ondelete="NO ACTION",
    )
    op.create_check_constraint(
        "ck_department_not_self_parent", "department",
        "parent_id IS NULL OR parent_id <> id",
    )

def downgrade() -> None:
    # Downgrade removes only the new hierarchy, never departments/contracts.
    op.drop_constraint("ck_department_not_self_parent", "department", type_="check")
    op.drop_constraint("fk_department_parent_same_scope", "department", type_="foreignkey")
    op.drop_constraint("uq_department_id_org_hospital", "department", type_="unique")
    op.drop_index("ix_department_parent_id", table_name="department")
    op.drop_column("department", "parent_id")
