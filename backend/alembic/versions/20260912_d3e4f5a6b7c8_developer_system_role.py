"""developer system role

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column("is_developer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_account_is_developer", "account", ["is_developer"])


def downgrade() -> None:
    op.drop_index("ix_account_is_developer", table_name="account")
    op.drop_column("account", "is_developer")
