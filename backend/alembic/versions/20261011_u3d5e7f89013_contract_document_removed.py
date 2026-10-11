"""Documents removed from a contract (audit trail, restorable).

Revision ID: u3d5e7f89013
Revises: t2c4d6e78012

Additive only: one new table. Removing a document moves its contract link here;
the file and its versions are kept.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "u3d5e7f89013"
down_revision = "t2c4d6e78012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_document_removed",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_contract_document_removed_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contract.id", name="fk_contract_document_removed_contract_id_contract", ondelete="CASCADE"), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_version.id", name="fk_contract_document_removed_document_version", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(32), nullable=True),
        sa.Column("attachment_type", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("added_by_name", sa.String(255), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("removed_by_name", sa.String(255), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_document_removed"),
    )
    op.create_index("ix_contract_document_removed_contract_id", "contract_document_removed", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_document_removed_contract_id", table_name="contract_document_removed")
    op.drop_table("contract_document_removed")
