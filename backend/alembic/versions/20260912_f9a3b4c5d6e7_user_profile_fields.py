"""user profile fields

Revision ID: f9a3b4c5d6e7
Revises: e8f2a3b4c5d6
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

revision = "f9a3b4c5d6e7"
down_revision = "e8f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("account", sa.Column("profile_photo_data_url", sa.Text(), nullable=True))
    op.add_column("account", sa.Column("phone", sa.String(length=80), nullable=True))
    op.add_column("account", sa.Column("job_title", sa.String(length=160), nullable=True))
    op.add_column("account", sa.Column("department", sa.String(length=160), nullable=True))
    op.add_column("account", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("account", "bio")
    op.drop_column("account", "department")
    op.drop_column("account", "job_title")
    op.drop_column("account", "phone")
    op.drop_column("account", "profile_photo_data_url")
