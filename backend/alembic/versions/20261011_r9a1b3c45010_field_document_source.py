"""Document source (page + verbatim quote) for register values captured from a marked passage.

Revision ID: r9a1b3c45010
Revises: q8f0a2b34009

Additive only: three nullable columns on contract_field_provenance. The foreign key
onto the populated table is added NOT VALID (no full-table check at deploy time).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r9a1b3c45010"
down_revision = "q8f0a2b34009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_field_provenance", sa.Column("source_document_version_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contract_field_provenance", sa.Column("source_page", sa.Integer(), nullable=True))
    op.add_column("contract_field_provenance", sa.Column("source_quote", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_contract_field_provenance_source_document",
        "contract_field_provenance", "document_version",
        ["source_document_version_id"], ["id"], ondelete="SET NULL", postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_contract_field_provenance_source_document", "contract_field_provenance", type_="foreignkey")
    op.drop_column("contract_field_provenance", "source_quote")
    op.drop_column("contract_field_provenance", "source_page")
    op.drop_column("contract_field_provenance", "source_document_version_id")
