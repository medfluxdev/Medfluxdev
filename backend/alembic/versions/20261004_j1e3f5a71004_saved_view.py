"""Saved views of the contract register, personal or organisation-wide (H7.2).

Revision ID: j1e3f5a71004
Revises: i0d2e4f61004

Additive only. Default views are created lazily per organisation by the
application (system_key), not by this migration.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "j1e3f5a71004"
down_revision = "i0d2e4f61004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_view",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_saved_view_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "owner_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", name="fk_saved_view_owner_account_id_account", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("view_kind", sa.String(24), server_default="register", nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("system_key", sa.String(48), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_saved_view"),
        sa.CheckConstraint("view_kind IN ('register')", name="ck_saved_view_view_kind"),
    )
    op.create_index("ix_saved_view_org_owner", "saved_view", ["organization_id", "owner_account_id"])
    op.create_index(
        "uq_saved_view_org_system_key", "saved_view", ["organization_id", "system_key"],
        unique=True, postgresql_where=sa.text("system_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_saved_view_org_system_key", table_name="saved_view")
    op.drop_index("ix_saved_view_org_owner", table_name="saved_view")
    op.drop_table("saved_view")
