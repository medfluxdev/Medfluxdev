"""activity scope snapshots

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_log", sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("activity_log", sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_activity_log_hospital_id", "activity_log", "hospital", ["hospital_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_activity_log_department_id", "activity_log", "department", ["department_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_activity_log_hospital_id", "activity_log", ["hospital_id"])
    op.create_index("ix_activity_log_department_id", "activity_log", ["department_id"])
    op.create_index("ix_activity_log_scope_created", "activity_log", ["organization_id", "hospital_id", "department_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_log_scope_created", table_name="activity_log")
    op.drop_index("ix_activity_log_department_id", table_name="activity_log")
    op.drop_index("ix_activity_log_hospital_id", table_name="activity_log")
    op.drop_constraint("fk_activity_log_department_id", "activity_log", type_="foreignkey")
    op.drop_constraint("fk_activity_log_hospital_id", "activity_log", type_="foreignkey")
    op.drop_column("activity_log", "department_id")
    op.drop_column("activity_log", "hospital_id")
