"""add contract_override (append-only audit/override ledger)

Revision ID: e3a4b5c6d7e8
Revises: d2b3a5c0f4e1
Create Date: 2026-09-04

UAT Defect Batch A: neue Tabellenklasse `contract_override` fuer dauerhafte
manuelle Bestaetigungs-/Override-Entscheidungen (Netto/Brutto-Steuerbasis,
Steuersatz, ereignisbasiertes Startdatum) inkl. append-only Audit-Historie.
Akteur (`actor_id`/`actor_type`) ist NULLABLE und RBAC-bereit, da STEP 16
(Authentication) noch nicht implementiert ist; `is_development` kennzeichnet
die Provenienz in Dev ehrlich.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e3a4b5c6d7e8"
down_revision = "d2b3a5c0f4e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_override",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fact_ref", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=True),
        sa.Column("is_development", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contract.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "action IN ('confirm', 'set', 'void')", name="action"
        ),
    )
    op.create_index(
        "ix_contract_override_contract_key",
        "contract_override",
        ["contract_id", "key"],
    )
    op.create_index(
        "ix_contract_override_contract_created",
        "contract_override",
        ["contract_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_contract_override_contract_created", table_name="contract_override")
    op.drop_index("ix_contract_override_contract_key", table_name="contract_override")
    op.drop_table("contract_override")
