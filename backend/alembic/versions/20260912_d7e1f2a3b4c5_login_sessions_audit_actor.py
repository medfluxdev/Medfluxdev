"""login sessions and authenticated audit actor snapshots

Revision ID: d7e1f2a3b4c5
Revises: c6d0e1f2a3b4
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7e1f2a3b4c5"
down_revision = "c6d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selector_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_session")),
        sa.UniqueConstraint("selector_digest", name=op.f("uq_login_session_selector_digest")),
    )
    op.create_index(op.f("ix_login_session_account_id"), "login_session", ["account_id"], unique=False)
    op.create_index(op.f("ix_login_session_selector_digest"), "login_session", ["selector_digest"], unique=True)
    op.create_index(op.f("ix_login_session_expires_at"), "login_session", ["expires_at"], unique=False)
    op.create_index("ix_login_session_account_expires", "login_session", ["account_id", "expires_at"], unique=False)

    op.add_column("fact_review", sa.Column("actor_role_snapshot", sa.String(length=32), nullable=True))
    op.add_column("contract_review", sa.Column("actor_role_snapshot", sa.String(length=32), nullable=True))
    op.add_column("contract_override", sa.Column("actor_display_name_snapshot", sa.String(length=255), nullable=True))
    op.add_column("contract_override", sa.Column("actor_role_snapshot", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("contract_override", "actor_role_snapshot")
    op.drop_column("contract_override", "actor_display_name_snapshot")
    op.drop_column("contract_review", "actor_role_snapshot")
    op.drop_column("fact_review", "actor_role_snapshot")
    op.drop_index("ix_login_session_account_expires", table_name="login_session")
    op.drop_index(op.f("ix_login_session_expires_at"), table_name="login_session")
    op.drop_index(op.f("ix_login_session_selector_digest"), table_name="login_session")
    op.drop_index(op.f("ix_login_session_account_id"), table_name="login_session")
    op.drop_table("login_session")
