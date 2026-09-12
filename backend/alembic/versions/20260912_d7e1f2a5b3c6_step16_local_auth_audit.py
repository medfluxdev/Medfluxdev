"""step16 local users and append-only audit

Revision ID: d7e1f2a5b3c6
Revises: c6d0e1f4a2b5
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7e1f2a5b3c6"
down_revision = "c6d0e1f4a2b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=24), server_default="viewer", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin','reviewer','viewer')",
            name="ck_app_user_app_user_role",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "username", name="uq_app_user_org_username"
        ),
    )
    op.create_index(
        "ix_app_user_org_active", "app_user", ["organization_id", "active"]
    )

    op.create_table(
        "audit_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_event_org_created",
        "audit_event",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_audit_event_entity", "audit_event", ["entity_type", "entity_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_event_entity", table_name="audit_event")
    op.drop_index("ix_audit_event_org_created", table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index("ix_app_user_org_active", table_name="app_user")
    op.drop_table("app_user")
