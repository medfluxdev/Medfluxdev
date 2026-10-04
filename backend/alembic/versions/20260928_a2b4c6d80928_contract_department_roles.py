"""A2: additive explicit contract-department role; historic links stay unclassified.

Revision ID: a2b4c6d80928
Revises: a1d3e5f70927
"""
from alembic import op
import sqlalchemy as sa

revision = "a2b4c6d80928"
down_revision = "a1d3e5f70927"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("contract_department", sa.Column("relation_role", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_contract_department_relation_role", "contract_department",
        "relation_role IS NULL OR relation_role IN ('responsible', 'beneficiary')",
    )
    op.create_index(
        "uq_contract_department_one_responsible", "contract_department",
        ["contract_id"], unique=True,
        postgresql_where=sa.text("relation_role = 'responsible'"),
    )

def downgrade():
    op.drop_index("uq_contract_department_one_responsible", table_name="contract_department")
    op.drop_constraint("ck_contract_department_relation_role", "contract_department", type_="check")
    op.drop_column("contract_department", "relation_role")
