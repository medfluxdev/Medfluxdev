from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("account_membership", sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("account_membership", sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("account_membership", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_foreign_key("fk_membership_hospital", "account_membership", "hospital", ["hospital_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_membership_department", "account_membership", "department", ["department_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_account_membership_hospital_id", "account_membership", ["hospital_id"])
    op.create_index("ix_account_membership_department_id", "account_membership", ["department_id"])
    op.create_index("ix_account_membership_org_hospital", "account_membership", ["organization_id", "hospital_id"])
    op.create_index("ix_account_membership_org_department", "account_membership", ["organization_id", "department_id"])


def downgrade():
    op.drop_index("ix_account_membership_org_department", table_name="account_membership")
    op.drop_index("ix_account_membership_org_hospital", table_name="account_membership")
    op.drop_index("ix_account_membership_department_id", table_name="account_membership")
    op.drop_index("ix_account_membership_hospital_id", table_name="account_membership")
    op.drop_constraint("fk_membership_department", "account_membership", type_="foreignkey")
    op.drop_constraint("fk_membership_hospital", "account_membership", type_="foreignkey")
    op.drop_column("account_membership", "is_default")
    op.drop_column("account_membership", "department_id")
    op.drop_column("account_membership", "hospital_id")
