"""work queue collaboration

Revision ID: j9e0f1a2b3c4
Revises: i8d9e0f1a2b3
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa

revision = "j9e0f1a2b3c4"
down_revision = "i8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_item_collaboration",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("work_item_id", sa.UUID(), nullable=False),
        sa.Column("assignee_account_id", sa.UUID(), nullable=True),
        sa.Column("owner_note", sa.Text(), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_level", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_account_id"], ["account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_item_id", name="uq_work_item_collaboration_item"),
    )
    op.create_index("ix_work_item_collaboration_assignee", "work_item_collaboration", ["assignee_account_id"])
    op.create_index("ix_work_item_collaboration_remind_at", "work_item_collaboration", ["remind_at"])

    op.create_table(
        "work_item_comment",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("work_item_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_item_comment_item_created", "work_item_comment", ["work_item_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_work_item_comment_item_created", table_name="work_item_comment")
    op.drop_table("work_item_comment")
    op.drop_index("ix_work_item_collaboration_remind_at", table_name="work_item_collaboration")
    op.drop_index("ix_work_item_collaboration_assignee", table_name="work_item_collaboration")
    op.drop_table("work_item_collaboration")
