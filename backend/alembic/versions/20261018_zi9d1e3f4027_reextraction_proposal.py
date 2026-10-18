"""Analyse proposals: one row per field and analysis, with old/new snapshot and decision.

Revision ID: zi9d1e3f4027
Revises: zh8c0d2e3026

`contract_reextraction_proposal` holds what an analysis proposes for each field (new, deviating,
missing, unchanged), the old and new value with their evidence (so an accepted proposal can be
rolled back) and the person's decision. New table; proposals of runs that finished before this
migration are created lazily from their candidate when they are first read.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zi9d1e3f4027"
down_revision = "zh8c0d2e3026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_reextraction_proposal",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_contract_reextraction_proposal_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contract_reextraction.id", name="fk_contract_reextraction_proposal_run_id_contract_reextraction", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("section", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("protected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("old_display", sa.Text(), nullable=True),
        sa.Column("new_display", sa.Text(), nullable=True),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("old_evidence", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("new_evidence", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(12), server_default="pending", nullable=False),
        sa.Column("decided_by_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_name", sa.String(200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_reextraction_proposal"),
        sa.UniqueConstraint("run_id", "field_key", name="uq_contract_reextraction_proposal_run_field"),
        sa.CheckConstraint("kind IN ('new', 'deviating', 'missing', 'unchanged')", name="ck_contract_reextraction_proposal_kind_allowed"),
        sa.CheckConstraint(
            "decision IN ('pending', 'accepted', 'kept_old', 'manual', 'rejected', 'rolled_back')",
            name="ck_contract_reextraction_proposal_decision_allowed",
        ),
    )
    op.create_index("ix_contract_reextraction_proposal_run", "contract_reextraction_proposal", ["organization_id", "run_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_reextraction_proposal_run", table_name="contract_reextraction_proposal")
    op.drop_table("contract_reextraction_proposal")
