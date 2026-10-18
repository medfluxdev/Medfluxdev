"""Protokoll der Feldprüfung (Zurückstellen, Hauptnachweis, ausgeschlossene Nachweise, Weitere Informationen).

Revision ID: zl2g4b6c7030
Revises: zk1f3a5b6029

Rein additiv: neue Tabelle `contract_review_event`. Bestehende Prüfungen (`fact_review`,
`contract_evidence_review`) bleiben unverändert und werden weiter gelesen.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zl2g4b6c7030"
down_revision = "zk1f3a5b6029"
branch_labels = None
depends_on = None

_KINDS = (
    "decision", "deferred", "not_in_document", "primary_selected", "evidence_excluded", "evidence_restored",
    "finding_linked", "finding_note", "finding_dismissed", "finding_restored",
)


def upgrade() -> None:
    op.create_table(
        "contract_review_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("fact_key", sa.String(120), nullable=True),
        sa.Column("evidence_id", sa.String(255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("actor_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_review_event"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], name="fk_contract_review_event_organization_id_organization", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], name="fk_contract_review_event_contract_id_contract", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_account_id"], ["account.id"], name="fk_contract_review_event_actor_account_id_account", ondelete="SET NULL"),
        sa.CheckConstraint("kind IN (" + ", ".join(repr(k) for k in _KINDS) + ")", name="ck_contract_review_event_kind"),
    )
    op.create_index("ix_contract_review_event_contract_fact", "contract_review_event", ["contract_id", "fact_key", "created_at"])
    op.create_index("ix_contract_review_event_contract_evidence", "contract_review_event", ["contract_id", "evidence_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_contract_review_event_contract_evidence", table_name="contract_review_event")
    op.drop_index("ix_contract_review_event_contract_fact", table_name="contract_review_event")
    op.drop_table("contract_review_event")
