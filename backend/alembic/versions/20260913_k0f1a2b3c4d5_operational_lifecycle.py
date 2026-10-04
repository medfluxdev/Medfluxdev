"""operational lifecycle

Revision ID: k0f1a2b3c4d5
Revises: j9e0f1a2b3c4
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa

revision = "k0f1a2b3c4d5"
down_revision = "j9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_lifecycle_decision",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="planned", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_account_id", sa.UUID(), nullable=True),
        sa.Column("actor_display_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("decision IN ('monitor','renegotiate','renew','terminate')", name="ck_contract_lifecycle_decision_decision"),
        sa.CheckConstraint("status IN ('cancelled','completed','in_progress','planned')", name="ck_contract_lifecycle_decision_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_account_id"], ["account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_lifecycle_contract", "contract_lifecycle_decision", ["contract_id", "created_at"])

    op.create_table(
        "equipment_lifecycle",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("equipment_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by_account_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_display_name", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','maintenance_due','out_of_service','retired')", name="ck_equipment_lifecycle_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_account_id"], ["account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id", name="uq_equipment_lifecycle_equipment"),
    )
    op.create_index("ix_equipment_lifecycle_status", "equipment_lifecycle", ["organization_id", "status"])
    op.create_index("ix_equipment_lifecycle_service", "equipment_lifecycle", ["next_service_date"])


def downgrade() -> None:
    op.drop_index("ix_equipment_lifecycle_service", table_name="equipment_lifecycle")
    op.drop_index("ix_equipment_lifecycle_status", table_name="equipment_lifecycle")
    op.drop_table("equipment_lifecycle")
    op.drop_index("ix_contract_lifecycle_contract", table_name="contract_lifecycle_decision")
    op.drop_table("contract_lifecycle_decision")
