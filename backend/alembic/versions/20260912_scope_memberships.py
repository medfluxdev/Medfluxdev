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


def downgrade():
    op.drop_column("account_membership", "is_default")
    op.drop_column("account_membership", "department_id")
    op.drop_column("account_membership", "hospital_id")
