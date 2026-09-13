"""accounts and organization memberships

Revision ID: c6d0e1f2a3b4
Revises: b5c9d0e3f1a4
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c6d0e1f2a3b4"
down_revision = "b5c9d0e3f1a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("login_name", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("credential_digest", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("login_name", name=op.f("uq_account_login_name")),
    )
    op.create_index(op.f("ix_account_login_name"), "account", ["login_name"], unique=True)
    op.create_table(
        "account_membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_membership")),
        sa.UniqueConstraint("organization_id", "account_id", name="uq_account_membership_org_account"),
        sa.CheckConstraint("role IN ('admin','contract_manager','reviewer','viewer')", name="ck_account_membership_role"),
    )
    op.create_index(op.f("ix_account_membership_organization_id"), "account_membership", ["organization_id"], unique=False)
    op.create_index(op.f("ix_account_membership_account_id"), "account_membership", ["account_id"], unique=False)
    op.create_index("ix_account_membership_account_active", "account_membership", ["account_id", "is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_account_membership_account_active", table_name="account_membership")
    op.drop_index(op.f("ix_account_membership_account_id"), table_name="account_membership")
    op.drop_index(op.f("ix_account_membership_organization_id"), table_name="account_membership")
    op.drop_table("account_membership")
    op.drop_index(op.f("ix_account_login_name"), table_name="account")
    op.drop_table("account")
