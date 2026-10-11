"""Contract type: which type-specific sections the contract page shows.

Revision ID: v4e6f8a90014
Revises: u3d5e7f89013

Additive only: nullable JSONB column; NULL keeps the default profile by type code
(app/register/sections.py).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v4e6f8a90014"
down_revision = "u3d5e7f89013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_contract_type", sa.Column("sections", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_contract_type", "sections")
