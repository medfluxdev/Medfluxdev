"""Vertragstitel als eigenes Feld des Vertragsregisters.

Revision ID: zk1f3a5b6029
Revises: zj0e2f4a5028

Der von der KI gelesene Vertragstitel (identity.contract_title, mit Nachweis) stand bisher in
`contract.short_description` („Kurzbeschreibung“). Neu: eigene Spalte `contract_title`. Vorhandene Titel mit
KI-Herkunft wandern samt Herkunftszeile dorthin; die Kurzbeschreibung bleibt fuer Eigenes frei. Von Hand
eingegebene Kurzbeschreibungen werden nicht angefasst.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "zk1f3a5b6029"
down_revision = "zj0e2f4a5028"
branch_labels = None
depends_on = None

_AI_ORIGINS = "('ai', 'ai_confirmed', 'ai_corrected')"


def upgrade() -> None:
    op.add_column("contract", sa.Column("contract_title", sa.String(500), nullable=True))
    # Zuerst die Herkunftszeilen markieren (ueber sie wird der Vertrag gefunden), dann Werte verschieben.
    op.execute(f"""
        UPDATE contract c SET contract_title = c.short_description, short_description = NULL
        FROM contract_field_provenance p
        WHERE p.contract_id = c.id AND p.field_key = 'short_description'
          AND p.source_field = 'identity.contract_title' AND p.origin IN {_AI_ORIGINS}
    """)
    op.execute(f"""
        UPDATE contract_field_provenance SET field_key = 'contract_title'
        WHERE field_key = 'short_description' AND source_field = 'identity.contract_title'
          AND origin IN {_AI_ORIGINS}
          AND NOT EXISTS (SELECT 1 FROM contract_field_provenance q
                          WHERE q.contract_id = contract_field_provenance.contract_id AND q.field_key = 'contract_title')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE contract_field_provenance SET field_key = 'short_description'
        WHERE field_key = 'contract_title'
          AND NOT EXISTS (SELECT 1 FROM contract_field_provenance q
                          WHERE q.contract_id = contract_field_provenance.contract_id AND q.field_key = 'short_description')
    """)
    op.execute("UPDATE contract SET short_description = contract_title WHERE short_description IS NULL AND contract_title IS NOT NULL")
    op.drop_column("contract", "contract_title")
