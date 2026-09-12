"""activity history for authenticated user actions

Revision ID: e8f2a3b4c5d6
Revises: d7e1f2a3b4c5
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e8f2a3b4c5d6"
down_revision = "d7e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("role_snapshot", sa.String(length=32), nullable=False),
        sa.Column("event_name", sa.String(length=80), nullable=False),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("context_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_log")),
    )
    op.create_index(op.f("ix_activity_log_organization_id"), "activity_log", ["organization_id"], unique=False)
    op.create_index(op.f("ix_activity_log_account_id"), "activity_log", ["account_id"], unique=False)
    op.create_index(op.f("ix_activity_log_event_name"), "activity_log", ["event_name"], unique=False)
    op.create_index(op.f("ix_activity_log_object_id"), "activity_log", ["object_id"], unique=False)
    op.create_index("ix_activity_log_org_created", "activity_log", ["organization_id", "created_at"], unique=False)
    op.create_index("ix_activity_log_object_created", "activity_log", ["object_type", "object_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_activity_log_object_created", table_name="activity_log")
    op.drop_index("ix_activity_log_org_created", table_name="activity_log")
    op.drop_index(op.f("ix_activity_log_object_id"), table_name="activity_log")
    op.drop_index(op.f("ix_activity_log_event_name"), table_name="activity_log")
    op.drop_index(op.f("ix_activity_log_account_id"), table_name="activity_log")
    op.drop_index(op.f("ix_activity_log_organization_id"), table_name="activity_log")
    op.drop_table("activity_log")
