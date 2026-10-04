"""Contract finance (H4): finance entries, service catalogue, cost-centre
allocation, dismissed AI suggestions, structured price adjustment.

Revision ID: h9c1d3e51004
Revises: g8b0c2d41004

Additive only. Existing contracts keep their single cost centre
(`contract.cost_center_id`); allocations are optional.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h9c1d3e51004"
down_revision = "g8b0c2d41004"
branch_labels = None
depends_on = None


def _pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()"))


def _org(table: str) -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name=f"fk_{table}_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
    ]


def _contract_fk(table: str) -> sa.Column:
    return sa.Column(
        "contract_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("contract.id", name=f"fk_{table}_contract_id_contract", ondelete="CASCADE"),
        nullable=False,
    )


def _extraction_fk(table: str) -> sa.Column:
    return sa.Column(
        "extraction_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("contract_extraction.id", name=f"fk_{table}_extraction_id_contract_extraction", ondelete="SET NULL"),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        "contract_finance_entry",
        _pk(),
        *_org("contract_finance_entry"),
        _contract_fk("contract_finance_entry"),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("cost_type_code", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_basis", sa.String(8), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("interval", sa.String(16), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("apply_price_adjustment", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("source_key", sa.String(120), nullable=True),
        _extraction_fk("contract_finance_entry"),
        sa.Column("created_by_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_finance_entry"),
        sa.CheckConstraint("direction IN ('expense', 'income')", name="ck_contract_finance_entry_direction"),
        sa.CheckConstraint("amount_basis IN ('net', 'gross')", name="ck_contract_finance_entry_amount_basis"),
        sa.CheckConstraint(
            "interval IN ('monthly', 'quarterly', 'semi_annual', 'annual', 'once')",
            name="ck_contract_finance_entry_interval",
        ),
        sa.CheckConstraint("origin IN ('manual', 'ai_confirmed', 'imported_legacy')", name="ck_contract_finance_entry_origin"),
        sa.CheckConstraint("amount >= 0", name="ck_contract_finance_entry_amount_non_negative"),
        sa.CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="ck_contract_finance_entry_vat_rate_range"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_contract_finance_entry_validity"),
    )
    op.create_index("ix_contract_finance_entry_contract", "contract_finance_entry", ["contract_id"])

    op.create_table(
        "contract_service_item",
        _pk(),
        *_org("contract_service_item"),
        _contract_fk("contract_service_item"),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("service_kind", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("plus_vat", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("source_key", sa.String(120), nullable=True),
        _extraction_fk("contract_service_item"),
        sa.PrimaryKeyConstraint("id", name="pk_contract_service_item"),
        sa.CheckConstraint("origin IN ('manual', 'ai_confirmed', 'imported_legacy')", name="ck_contract_service_item_origin"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_contract_service_item_amount_non_negative"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_contract_service_item_validity"
        ),
    )
    op.create_index("ix_contract_service_item_contract", "contract_service_item", ["contract_id"])

    op.create_table(
        "contract_cost_allocation",
        _pk(),
        *_org("contract_cost_allocation"),
        _contract_fk("contract_cost_allocation"),
        sa.Column(
            "cost_center_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_center.id", name="fk_contract_cost_allocation_cost_center_id_cost_center", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("recharge_mode", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_cost_allocation"),
        sa.UniqueConstraint("contract_id", "cost_center_id", name="uq_contract_cost_allocation_pair"),
        sa.CheckConstraint("share_percent > 0 AND share_percent <= 100", name="ck_contract_cost_allocation_share_range"),
    )

    op.create_table(
        "contract_suggestion_dismissal",
        _pk(),
        *_org("contract_suggestion_dismissal"),
        _contract_fk("contract_suggestion_dismissal"),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("suggestion_key", sa.String(120), nullable=False),
        sa.Column("dismissed_by_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_suggestion_dismissal"),
        sa.UniqueConstraint("contract_id", "scope", "suggestion_key", name="uq_contract_suggestion_dismissal_key"),
    )

    op.add_column("contract", sa.Column("price_adjustment_kind", sa.String(16), nullable=True))
    op.add_column("contract", sa.Column("price_adjustment_percent", sa.Numeric(6, 3), nullable=True))
    op.add_column("contract", sa.Column("price_adjustment_index_name", sa.String(120), nullable=True))
    op.add_column("contract", sa.Column("price_adjustment_next_date", sa.Date(), nullable=True))
    op.add_column("contract", sa.Column("price_adjustment_interval_months", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_contract_price_adjustment_kind",
        "contract",
        "price_adjustment_kind IS NULL OR price_adjustment_kind IN ('fixed', 'percent', 'index', 'negotiation')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contract_price_adjustment_kind", "contract", type_="check")
    for column in (
        "price_adjustment_interval_months", "price_adjustment_next_date", "price_adjustment_index_name",
        "price_adjustment_percent", "price_adjustment_kind",
    ):
        op.drop_column("contract", column)
    op.drop_table("contract_suggestion_dismissal")
    op.drop_table("contract_cost_allocation")
    op.drop_index("ix_contract_service_item_contract", table_name="contract_service_item")
    op.drop_table("contract_service_item")
    op.drop_index("ix_contract_finance_entry_contract", table_name="contract_finance_entry")
    op.drop_table("contract_finance_entry")
