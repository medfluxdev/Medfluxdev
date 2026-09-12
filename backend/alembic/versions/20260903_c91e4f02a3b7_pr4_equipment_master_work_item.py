"""pr4 equipment master + work item

Revision ID: c91e4f02a3b7
Revises: 7f2c9a1e4b80
Create Date: 2026-09-03

PR-4: kanonische `equipment`-Identität (org-gebunden), Ausbau von
`contract_equipment` zur n:m-Relation mit Provenienz/Qualität/Abdeckung,
und `work_item` für die materialisierte autoritative Arbeitsliste.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c91e4f02a3b7"
down_revision = "7f2c9a1e4b80"
branch_labels = None
depends_on = None

_FID = op.f


def _uuid():
    return sa.UUID()


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1) Kanonische Geräte-Identität
    # ------------------------------------------------------------------
    op.create_table(
        "equipment",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("inventory_number", sa.String(length=120), nullable=True),
        sa.Column("equipment_type", sa.String(length=64), nullable=True),
        sa.Column("equipment_category", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("identification_quality", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"],
            name=_FID("fk_equipment_organization_id_organization"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=_FID("pk_equipment")),
    )
    op.create_index("ix_equipment_org", "equipment", ["organization_id"], unique=False)
    op.create_index("ix_equipment_org_serial", "equipment", ["organization_id", "serial_number"], unique=False)
    op.create_index("ix_equipment_org_inventory", "equipment", ["organization_id", "inventory_number"], unique=False)
    op.create_index("ix_equipment_org_model", "equipment", ["organization_id", "model"], unique=False)

    # ------------------------------------------------------------------
    # 2) contract_equipment -> n:m-Relation mit Provenienz/Abdeckung
    # ------------------------------------------------------------------
    op.add_column(
        "contract_equipment",
        sa.Column("equipment_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        _FID("fk_contract_equipment_equipment_id_equipment"),
        "contract_equipment", "equipment",
        ["equipment_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_contract_equipment_equipment_id",
        "contract_equipment", ["equipment_id"], unique=False,
    )

    for name, ddl in {
        "inventory_number": sa.String(length=120),
        "equipment_type": sa.String(length=64),
        "location": sa.String(length=255),
        "department": sa.String(length=255),
        "service_scope": sa.String(),
        "coverage_start": sa.Date(),
        "coverage_end": sa.Date(),
        "included_services": postgresql.JSONB(astext_type=sa.Text()),
        "excluded_services": postgresql.JSONB(astext_type=sa.Text()),
        "sla_notes": sa.String(),
        "identification_quality": sa.String(length=16),
        "relationship_quality": sa.String(length=16),
        "requires_review": sa.Boolean(),
        "review_reasons": postgresql.JSONB(astext_type=sa.Text()),
        "field_ref": sa.String(length=120),
        "equipment_index": sa.Integer(),
        "logical_fingerprint": sa.String(length=64),
    }.items():
        op.add_column("contract_equipment", sa.Column(name, ddl, nullable=True))

    op.create_index(
        "ix_contract_equipment_org_requires_review",
        "contract_equipment", ["organization_id", "requires_review"], unique=False,
    )

    # ------------------------------------------------------------------
    # 3) Arbeitselemente (PR-4, materialisiert aus autoritativen Quellen)
    # ------------------------------------------------------------------
    op.create_table(
        "work_item",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("equipment_id", sa.UUID(), nullable=True),
        sa.Column("contract_equipment_id", sa.UUID(), nullable=True),
        sa.Column("source_warning_id", sa.UUID(), nullable=True),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("title_de", sa.String(length=255), nullable=False),
        sa.Column("why_de", sa.String(), nullable=True),
        sa.Column("action_hint_de", sa.String(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("days_remaining", sa.Integer(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("logical_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("calc_field_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_field_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('automatic_renewal', 'cancellation_deadline', 'contract_expired', 'contract_expiry', 'equipment_coverage_review', 'equipment_relationship_ambiguous', 'manual_review', 'missing_cost', 'sla_issue')",
            name=_FID("ck_work_item_item_type"),
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'info', 'low', 'medium')",
            name=_FID("ck_work_item_severity"),
        ),
        sa.CheckConstraint(
            "status IN ('acknowledged', 'open', 'resolved')",
            name=_FID("ck_work_item_status"),
        ),
        sa.ForeignKeyConstraint(
            ["contract_equipment_id"], ["contract_equipment.id"],
            name=_FID("fk_work_item_contract_equipment_contract_equipment"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contract.id"],
            name=_FID("fk_work_item_contract_id_contract"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["equipment.id"],
            name=_FID("fk_work_item_equipment_id_equipment"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"],
            name=_FID("fk_work_item_organization_id_organization"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_warning_id"], ["contract_warning.id"],
            name=_FID("fk_work_item_source_warning_id_contract_warning"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=_FID("pk_work_item")),
        sa.UniqueConstraint(
            "organization_id", "contract_id", "logical_fingerprint",
            name=_FID("uq_work_item_fingerprint"),
        ),
    )
    op.create_index("ix_work_item_org_status", "work_item", ["organization_id", "status"], unique=False)
    op.create_index("ix_work_item_org_active", "work_item", ["organization_id", "active"], unique=False)
    op.create_index("ix_work_item_contract", "work_item", ["contract_id"], unique=False)
    op.create_index("ix_work_item_equipment", "work_item", ["equipment_id"], unique=False)
    op.create_index("ix_work_item_target_date", "work_item", ["target_date"], unique=False)
    op.create_index("ix_work_item_severity", "work_item", ["severity"], unique=False)
    op.create_index("ix_work_item_source_warning", "work_item", ["source_warning_id"], unique=False)


def downgrade() -> None:
    op.drop_table("work_item")
    op.drop_index("ix_contract_equipment_org_requires_review", table_name="contract_equipment")
    for name in (
        "equipment_index", "field_ref", "logical_fingerprint", "review_reasons", "requires_review",
        "relationship_quality", "identification_quality", "sla_notes",
        "excluded_services", "included_services", "coverage_end", "coverage_start",
        "service_scope", "department", "location", "equipment_type", "inventory_number",
    ):
        op.drop_column("contract_equipment", name)
    op.drop_index("ix_contract_equipment_equipment_id", table_name="contract_equipment")
    op.drop_constraint(
        _FID("fk_contract_equipment_equipment_id_equipment"),
        "contract_equipment", type_="foreignkey",
    )
    op.drop_column("contract_equipment", "equipment_id")
    op.drop_index("ix_equipment_org_model", table_name="equipment")
    op.drop_index("ix_equipment_org_inventory", table_name="equipment")
    op.drop_index("ix_equipment_org_serial", table_name="equipment")
    op.drop_index("ix_equipment_org", table_name="equipment")
    op.drop_table("equipment")
