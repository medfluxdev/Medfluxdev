"""Add organization soft delete flag.

Revision ID: h7c8d9e0f1a2
Revises: g6b7c8d9e0f1
"""

from alembic import op
import sqlalchemy as sa

revision = "h7c8d9e0f1a2"
down_revision = "g6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_organization_is_active", "organization", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_organization_is_active", table_name="organization")
    op.drop_column("organization", "is_active")
