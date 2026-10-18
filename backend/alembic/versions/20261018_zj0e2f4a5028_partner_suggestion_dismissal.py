"""Partner master-data suggestions: remember ignored values.

Revision ID: zj0e2f4a5028
Revises: zi9d1e3f4027

Contract analyses find partner data (e-mail, phone, address) that MedFlux offers to add to the
linked Vertragspartner. `partner_suggestion_dismissal` remembers which value a person ignored for
which partner field, so the same value is not offered again. New table, nothing existing changes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zj0e2f4a5028"
down_revision = "zi9d1e3f4027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partner_suggestion_dismissal",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", name="fk_partner_suggestion_dismissal_organization_id_organization", ondelete="RESTRICT"), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contract_partner.id", name="fk_partner_suggestion_dismissal_partner_id_contract_partner", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(40), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("dismissed_by_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dismissed_by_name", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_partner_suggestion_dismissal"),
        sa.UniqueConstraint("partner_id", "field_key", "value", name="uq_partner_suggestion_dismissal_value"),
    )


def downgrade() -> None:
    op.drop_table("partner_suggestion_dismissal")
