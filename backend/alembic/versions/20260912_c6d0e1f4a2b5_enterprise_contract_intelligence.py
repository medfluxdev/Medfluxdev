"""enterprise contract intelligence foundation

Revision ID: c6d0e1f4a2b5
Revises: b5c9d0e3f1a4
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c6d0e1f4a2b5"
down_revision = "b5c9d0e3f1a4"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade():
    op.create_table(
        "contract_relation",
        *_common(),
        sa.Column("source_contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("authority", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["source_contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_version_id"], ["document_version.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_document_version_id"], ["document_version.id"], ondelete="SET NULL"),
        sa.CheckConstraint("relation_type IN ('amends','supersedes','references','renews','governs','covers','ordered_by','corroborates','conflicts_with')", name="ck_contract_relation_relation_type"),
        sa.CheckConstraint("authority IN ('primary','secondary','unknown')", name="ck_contract_relation_authority"),
    )
    op.create_index("ix_contract_relation_source","contract_relation",["source_contract_id"])
    op.create_index("ix_contract_relation_target","contract_relation",["target_contract_id"])

    op.create_table(
        "contract_obligation",
        *_common(),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_key", sa.String(160), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_role", sa.String(120), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("recurrence", sa.String(120), nullable=True),
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
        sa.Column("source_field_refs", postgresql.JSONB(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('proposed','active','satisfied','breached','waived','unknown')", name="ck_contract_obligation_status"),
        sa.UniqueConstraint("organization_id","contract_id","obligation_key", name="uq_contract_obligation_key"),
    )
    op.create_index("ix_contract_obligation_contract_status","contract_obligation",["contract_id","status"])
    op.create_index("ix_contract_obligation_due","contract_obligation",["due_date"])

    op.create_table(
        "policy_decision",
        *_common(),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_key", sa.String(160), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.CheckConstraint("outcome IN ('pass','warn','fail','unknown')", name="ck_policy_decision_outcome"),
    )
    op.create_index("ix_policy_decision_contract","policy_decision",["contract_id"])
    op.create_index("ix_policy_decision_outcome","policy_decision",["outcome"])

    op.create_table(
        "intelligence_event",
        *_common(),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_intelligence_event_type","intelligence_event",["event_type"])
    op.create_index("ix_intelligence_event_unprocessed","intelligence_event",["processed_at"])

    op.create_table(
        "action_proposal",
        *_common(),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("assignee_role", sa.String(120), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('proposed','approved','rejected','executed','cancelled')", name="ck_action_proposal_status"),
    )
    op.create_index("ix_action_proposal_contract_status","action_proposal",["contract_id","status"])


def downgrade():
    op.drop_table("action_proposal")
    op.drop_table("intelligence_event")
    op.drop_table("policy_decision")
    op.drop_table("contract_obligation")
    op.drop_table("contract_relation")
