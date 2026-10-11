"""Further responsible persons per contract (besides contract.responsible_account_id).

Revision ID: s0b2c4d56011
Revises: r9a1b3c45010

Additive only: one new table. They receive the same as the main responsible person
(bell reminders, "Ich verantwortlich", access to confidential contracts).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "s0b2c4d56011"
down_revision = "r9a1b3c45010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_responsible",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_contract_responsible_organization_id_organization", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contract_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_responsible_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", name="fk_contract_responsible_account_id_account", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_responsible"),
        sa.UniqueConstraint("contract_id", "account_id", name="uq_contract_responsible_pair"),
    )
    op.create_index("ix_contract_responsible_contract_id", "contract_responsible", ["contract_id"])
    op.create_index("ix_contract_responsible_account_id", "contract_responsible", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_responsible_account_id", table_name="contract_responsible")
    op.drop_index("ix_contract_responsible_contract_id", table_name="contract_responsible")
    op.drop_table("contract_responsible")
