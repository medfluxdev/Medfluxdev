"""add fact_review + contract_review (Customer-Demo-Readiness: Fakt-Prüfung)

Revision ID: f3c9d1a5b0e7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-05

Neue Tabellen für die verpflichtende Faktgenaue menschliche Verifikation:
- `fact_review` (append-only): BESTÄTIGT/KORRIGIERT/VERWORFEN/WIEDER GEÖFFNET
  je materialem Fakt mit Original-/alter-/neuer-Wert, Reviewer-Anzeigename
  (manual_unverified), Note, optionalem Evidence-Ref und Zeitstempel.
- `contract_review` (ein Eintrag je Vertrag): Nicht geprüft / In Prüfung /
  Geprüft / Änderung nach Prüfung. `changed_after_review` wird automatisch
  gesetzt, wenn nach Abschluss ein materialer Fakt korrigiert/verworfen wird.

STEP 16 (Authentifizierung) ist NICHT implementiert: `authenticated_actor_id`
bleibt NULL, `reviewer_identity_type='manual_unverified'` kennzeichnet die
selbst angegebene (nicht authentifizierte) Prüfer-Identität ehrlich.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f3c9d1a5b0e7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fact_review",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fact_key", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("original_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "previous_effective_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "new_effective_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("reviewer_display_name", sa.String(length=255), nullable=True),
        sa.Column("reviewer_identity_type", sa.String(length=32), nullable=False),
        sa.Column("authenticated_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "action IN ('confirmed', 'corrected', 'reopened', 'voided')", name="action"
        ),
    )
    op.create_index(
        "ix_fact_review_contract_key_created",
        "fact_review",
        ["contract_id", "fact_key", "created_at"],
    )
    op.create_index(
        "ix_fact_review_contract_created",
        "fact_review",
        ["contract_id", "created_at"],
    )

    op.create_table(
        "contract_review",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_display_name", sa.String(length=255), nullable=True),
        sa.Column("reviewer_identity_type", sa.String(length=32), nullable=False),
        sa.Column("authenticated_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_noted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", name="uq_contract_review_contract"),
        sa.CheckConstraint(
            "status IN ('changed_after_review', 'in_review', 'manual_review_required', "
            "'reviewed', 'unreviewed')",
            name="status",
        ),
    )


def downgrade() -> None:
    op.drop_table("contract_review")
    op.drop_index("ix_fact_review_contract_created", table_name="fact_review")
    op.drop_index("ix_fact_review_contract_key_created", table_name="fact_review")
    op.drop_table("fact_review")