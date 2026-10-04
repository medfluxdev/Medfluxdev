"""Display preferences per account (theme, text size, density) – UX plan U8.

Revision ID: m4b6c8d01004
Revises: l3a5b7c91004

Additive, nullable column; no backfill. Browser storage stays the fast path,
the server copy lets preferences follow the user to another device.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m4b6c8d01004"
down_revision = "l3a5b7c91004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("account", sa.Column("ui_preferences", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("account", "ui_preferences")
