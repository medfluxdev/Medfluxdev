"""Notizen löschbar (weich): wer wann gelöscht hat.

Revision ID: zf6a8b0c1024
Revises: ze5f7a9b0023

`contract_remark` gets `deleted_at`, `deleted_by_account_id` and `deleted_by_name`. A deleted note
disappears from the list but stays in the table together with its earlier versions; nothing is
removed. Existing notes are unaffected (all NULL). The FK is added NOT VALID because the table is
populated (precedent: step16 `app_user` provenance).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zf6a8b0c1024"
down_revision = "ze5f7a9b0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_remark", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contract_remark", sa.Column("deleted_by_account_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contract_remark", sa.Column("deleted_by_name", sa.String(255), nullable=True))
    op.create_foreign_key(
        "fk_contract_remark_deleted_by_account_id_account", "contract_remark", "account",
        ["deleted_by_account_id"], ["id"], ondelete="SET NULL", postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_contract_remark_deleted_by_account_id_account", "contract_remark", type_="foreignkey")
    op.drop_column("contract_remark", "deleted_by_name")
    op.drop_column("contract_remark", "deleted_by_account_id")
    op.drop_column("contract_remark", "deleted_at")
