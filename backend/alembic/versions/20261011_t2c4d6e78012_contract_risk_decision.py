"""Risk: computed value, human confirmation and manual override with reason.

Revision ID: t2c4d6e78012
Revises: s0b2c4d56011

Additive only: nullable columns on contract. Existing rows keep risk_level; the
computed value is filled by the next warning evaluation.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "t2c4d6e78012"
down_revision = "s0b2c4d56011"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("risk_computed", sa.String(24)),
    ("risk_override", sa.String(24)),
    ("risk_override_reason", sa.String(500)),
    ("risk_override_by_name", sa.String(255)),
    ("risk_override_at", sa.DateTime(timezone=True)),
    ("risk_confirmed_level", sa.String(24)),
    ("risk_confirmed_by_name", sa.String(255)),
    ("risk_confirmed_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column("contract", sa.Column(name, type_, nullable=True))
    op.execute("UPDATE contract SET risk_computed = risk_level WHERE risk_computed IS NULL")


def downgrade() -> None:
    for name, _type in reversed(_COLUMNS):
        op.drop_column("contract", name)
