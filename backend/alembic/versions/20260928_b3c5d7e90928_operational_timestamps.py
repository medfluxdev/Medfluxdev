"""Restore three operational timestamp columns absent from historical migrations.

Revision ID: b3c5d7e90928
Revises: a2b4c6d80928

Existing records receive their migration-time timestamp; no existing values
or rows are rewritten, and no historical migration is modified.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b3c5d7e90928"
down_revision = "a2b4c6d80928"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "equipment_lifecycle",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "work_item_collaboration",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "work_item_comment",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("work_item_comment", "updated_at")
    op.drop_column("work_item_collaboration", "created_at")
    op.drop_column("equipment_lifecycle", "created_at")
