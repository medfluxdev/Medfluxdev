"""Notizen bearbeitbar mit Verlauf.

Revision ID: zd4e6f8a0022
Revises: zc3d5e7f9021

`contract_remark` gets who edited it last and when (NULL = never edited).
`contract_remark_revision` keeps every earlier text of a note with its author and
the time it was written; nothing is deleted. Existing notes stay as they are.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zd4e6f8a0022"
down_revision = "zc3d5e7f9021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_remark", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contract_remark", sa.Column("edited_by_account_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contract_remark", sa.Column("edited_by_name", sa.String(255), nullable=True))
    op.create_foreign_key(
        "fk_contract_remark_edited_by_account_id_account", "contract_remark", "account",
        ["edited_by_account_id"], ["id"], ondelete="SET NULL",
    )
    op.create_table(
        "contract_remark_revision",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_contract_remark_revision_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("remark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contract_remark.id", name="fk_contract_remark_revision_remark_id_contract_remark", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("account.id", name="fk_contract_remark_revision_account_id_account", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_remark_revision"),
    )
    op.create_index("ix_contract_remark_revision_remark_written", "contract_remark_revision", ["remark_id", "written_at"])


def downgrade() -> None:
    op.drop_index("ix_contract_remark_revision_remark_written", table_name="contract_remark_revision")
    op.drop_table("contract_remark_revision")
    op.drop_constraint("fk_contract_remark_edited_by_account_id_account", "contract_remark", type_="foreignkey")
    op.drop_column("contract_remark", "edited_by_name")
    op.drop_column("contract_remark", "edited_by_account_id")
    op.drop_column("contract_remark", "edited_at")
