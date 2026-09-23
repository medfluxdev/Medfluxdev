"""add demo_workspace + demo_workspace_entry (Customer-Demo-Readiness)

Revision ID: fb2e6c8d1a54
Revises: f3c9d1a5b0e7
Create Date: 2026-09-05

Demo-/UAT-Arbeitsbereich: isolierte Sicht für die Kunden-Demo. Aktiv werden
nur Verträge sichtbar, die während der Demo hochgeladen wurden; Bestand-
Verträge bleiben unverändert in der DB. Deaktivieren stellt das normale
Portfolio wieder her. Reine Dev-/UAT-Ebene – keine Produktions-Geschäftslogik.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fb2e6c8d1a54"
down_revision = "f3c9d1a5b0e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_workspace",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "id = '01100000-0000-0000-0000-000000000001'::uuid", name="single_row"
        ),
    )
    op.create_table(
        "demo_workspace_entry",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_version_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["demo_workspace.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_version.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", name="uq_demo_workspace_entry_contract"),
    )
    op.create_index(
        "ix_demo_workspace_entry_workspace",
        "demo_workspace_entry",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_demo_workspace_entry_workspace", table_name="demo_workspace_entry")
    op.drop_table("demo_workspace_entry")
    op.drop_table("demo_workspace")