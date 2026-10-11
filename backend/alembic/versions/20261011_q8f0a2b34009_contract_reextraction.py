"""Re-extraction runs from the contract document (candidate, compare, apply).

Revision ID: q8f0a2b34009
Revises: p7e9f1a23008

Additive: one new table and one more notification kind ("reextraction"). A run
stores a candidate extraction; the accepted contract state changes only when a
person applies selected facts.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q8f0a2b34009"
down_revision = "p7e9f1a23008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_reextraction",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_contract_reextraction_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contract_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_reextraction_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_version.id", name="fk_contract_reextraction_document_version_id_document_version", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("fields", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("page_hint", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("reread_document", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("provider_id", sa.String(60), nullable=True),
        sa.Column("model_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "base_extraction_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract_extraction.id", name="fk_contract_reextraction_base_extraction", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "candidate_extraction_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract_extraction.id", name="fk_contract_reextraction_candidate_extraction", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("applied_keys", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("requested_by_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_name", sa.String(200), nullable=True),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_reextraction"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed', 'applied', 'discarded', 'cancelled')",
            name="ck_contract_reextraction_status_allowed",
        ),
        sa.CheckConstraint("mode IN ('full', 'missing_fields')", name="ck_contract_reextraction_mode_allowed"),
    )
    op.create_index(
        "ix_contract_reextraction_contract", "contract_reextraction", ["organization_id", "contract_id", "created_at"]
    )
    op.create_index("ix_contract_reextraction_status", "contract_reextraction", ["status"])
    op.create_index(
        "uq_contract_reextraction_active", "contract_reextraction", ["contract_id"], unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_constraint("ck_notification_kind", "notification", type_="check")
    op.create_check_constraint(
        "ck_notification_kind", "notification",
        "kind IN ('deadline_reminder', 'deadline_overdue', 'deadline_escalation', 'deadline_assigned', 'reextraction')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE kind = 'reextraction'")
    op.drop_constraint("ck_notification_kind", "notification", type_="check")
    op.create_check_constraint(
        "ck_notification_kind", "notification",
        "kind IN ('deadline_reminder', 'deadline_overdue', 'deadline_escalation', 'deadline_assigned')",
    )
    op.drop_index("uq_contract_reextraction_active", table_name="contract_reextraction")
    op.drop_index("ix_contract_reextraction_status", table_name="contract_reextraction")
    op.drop_index("ix_contract_reextraction_contract", table_name="contract_reextraction")
    op.drop_table("contract_reextraction")
