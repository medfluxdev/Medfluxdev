"""Typed documents per contract and framework linkage (H3).

Revision ID: g8b0c2d41004
Revises: f7a9b1c31004

Additive. Existing links keep their role; the 'main' link of each contract
becomes the main document with attachment type 'vertrag'. contract_relation
had no writer so far; a unique pair/type constraint prevents duplicates.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "g8b0c2d41004"
down_revision = "f7a9b1c31004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_document", sa.Column("attachment_type", sa.String(64), nullable=True))
    op.add_column("contract_document", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("contract_document", sa.Column("is_main", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("contract_document", sa.Column("is_valid", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("contract_document", sa.Column("added_by_name", sa.String(255), nullable=True))
    op.execute(
        """
        WITH ranked AS (
            SELECT id, row_number() OVER (PARTITION BY contract_id ORDER BY created_at, id) AS rn
            FROM contract_document
            WHERE role = 'main'
        )
        UPDATE contract_document cd
        SET is_main = true, attachment_type = 'vertrag'
        FROM ranked
        WHERE cd.id = ranked.id AND ranked.rn = 1
        """
    )
    op.create_index(
        "uq_contract_document_one_main", "contract_document", ["contract_id"],
        unique=True, postgresql_where=sa.text("is_main"),
    )
    op.create_unique_constraint(
        "uq_contract_relation_pair_type", "contract_relation",
        ["source_contract_id", "target_contract_id", "relation_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_contract_relation_pair_type", "contract_relation", type_="unique")
    op.drop_index("uq_contract_document_one_main", table_name="contract_document")
    for column in ("added_by_name", "is_valid", "is_main", "title", "attachment_type"):
        op.drop_column("contract_document", column)
