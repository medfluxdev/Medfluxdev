"""Nachweisprüfung: Ergebnis je Nachweis.

Revision ID: zg7b9c1d2025
Revises: zf6a8b0c1024

`contract_evidence_review` keeps the current result of the guided evidence check per contract and
evidence: confirmed, document (deviation, document value taken), medflux (deviation, resolved:
MedFlux applies), manual (both wrong, value entered by hand) or skipped. The value itself stays in the
fact review; this table only records how each evidence was settled, by whom and when. New table,
nothing existing changes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zg7b9c1d2025"
down_revision = "zf6a8b0c1024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_evidence_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_contract_evidence_review_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contract.id", name="fk_contract_evidence_review_contract_id_contract", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.String(255), nullable=False),
        sa.Column("fact_key", sa.String(120), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("account.id", name="fk_contract_evidence_review_reviewed_by_account_id_account", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by_name", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_evidence_review"),
        sa.UniqueConstraint("contract_id", "evidence_id", name="uq_contract_evidence_review_contract_evidence"),
        sa.CheckConstraint(
            "status IN ('confirmed', 'document', 'medflux', 'manual', 'skipped')",
            name="ck_contract_evidence_review_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("contract_evidence_review")
