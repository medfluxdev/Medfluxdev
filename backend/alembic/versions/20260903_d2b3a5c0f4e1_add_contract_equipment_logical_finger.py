"""add contract_equipment.logical_fingerprint

Revision ID: d2b3a5c0f4e1
Revises: c91e4f02a3b7
Create Date: 2026-09-03

Nachträglich ergänzte Idempotenz-Spalte `logical_fingerprint` auf
`contract_equipment` (PR-4). Kein Datenmaterial vorhanden vor diesem
Schritt (leere Tabelle), daher keine Backfill-Logik nötig.
"""

from alembic import op
import sqlalchemy as sa

revision = "d2b3a5c0f4e1"
down_revision = "c91e4f02a3b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: die additive PR-4-Migration (c91e4f02a3b7) erzeugt die Spalte
    # bereits. Auf historisch inkrementell migrierten DBs existiert sie ebenfalls.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contract_equipment")}
    if "logical_fingerprint" not in cols:
        op.add_column(
            "contract_equipment",
            sa.Column("logical_fingerprint", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contract_equipment")}
    if "logical_fingerprint" in cols:
        op.drop_column("contract_equipment", "logical_fingerprint")
