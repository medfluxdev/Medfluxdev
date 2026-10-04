"""Add optional German unit_type label to department (WP1.1).

Revision ID: d5e7f9a01003
Revises: c4d6e8f00930

Additive only: nullable column + check constraint. No row is modified.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d5e7f9a01003"
down_revision = "c4d6e8f00930"
branch_labels = None
depends_on = None

UNIT_TYPES = ("klinik", "abteilung", "bereich", "einheit", "station", "funktionsbereich")


def upgrade() -> None:
    op.add_column("department", sa.Column("unit_type", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        "ck_department_unit_type",
        "department",
        "unit_type IS NULL OR unit_type IN (%s)" % ", ".join("'%s'" % value for value in UNIT_TYPES),
    )


def downgrade() -> None:
    op.drop_constraint("ck_department_unit_type", "department", type_="check")
    op.drop_column("department", "unit_type")
