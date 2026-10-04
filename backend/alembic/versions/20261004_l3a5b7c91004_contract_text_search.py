"""Page-level text of contract documents with a German full-text index (§4A search).

Revision ID: l3a5b7c91004
Revises: k2f4a6b81004

Additive only. The index is filled lazily (search, daily job) from the stored
canonical document artifacts; no document leaves the machine.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "l3a5b7c91004"
down_revision = "k2f4a6b81004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_text_page",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_contract_text_page_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contract_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_text_page_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_version.id", name="fk_contract_text_page_document_version_id_document_version", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "search_vector", postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('german', regexp_replace(text, '[/–-]+', ' ', 'g'))", persisted=True), nullable=False,
        ),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
        sa.Column("embedding_model", sa.String(120), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_text_page"),
        sa.UniqueConstraint("contract_id", "document_version_id", "page_number", name="uq_contract_text_page"),
    )
    op.create_index("ix_contract_text_page_search", "contract_text_page", ["search_vector"], postgresql_using="gin")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_contract_text_page_trgm", "contract_text_page", ["text"],
        postgresql_using="gin", postgresql_ops={"text": "gin_trgm_ops"},
    )
    op.create_index("ix_contract_text_page_org", "contract_text_page", ["organization_id"])
    op.create_index("ix_contract_text_page_document", "contract_text_page", ["document_version_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_text_page_document", table_name="contract_text_page")
    op.drop_index("ix_contract_text_page_org", table_name="contract_text_page")
    op.drop_index("ix_contract_text_page_trgm", table_name="contract_text_page")
    op.drop_index("ix_contract_text_page_search", table_name="contract_text_page")
    op.drop_table("contract_text_page")
