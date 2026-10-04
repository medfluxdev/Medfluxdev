"""Contract register core (H1/H2/H6): editable master fields, field provenance,
number ranges, remarks, partners, catalogues, multi-hospital link.

Revision ID: e6f8a0b21004
Revises: d5e7f9a01003

Additive only. Existing rows keep their data; they get a register number
(per organisation, ordered by creation) and business_status 'in_arbeit'
('geloescht' for already deleted contracts). AI values are filled into the
register lazily by the application (provenance 'ai'), not by this migration.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e6f8a0b21004"
down_revision = "d5e7f9a01003"
branch_labels = None
depends_on = None

BUSINESS_STATUS = ("in_arbeit", "gueltig", "gekuendigt", "beendet", "geloescht")
TERM_MODEL = ("fixed_term", "terminable", "terminable_min_term", "auto_renewal", "perpetual")
NOTICE_TO = ("contract_end", "month_end", "quarter_end", "half_year_end", "year_end", "anytime")
ORIGIN = ("ai", "manual", "ai_confirmed", "ai_corrected", "imported_legacy", "system")
ALLOCATION_STATE = ("used", "reserved", "free")

OLD_SEARCH = (
    "(setweight(to_tsvector('simple', coalesce(contract_number, '')), 'A') || ' ' || "
    "setweight(to_tsvector('german', coalesce(supplier, '')), 'B') || ' ' || "
    "setweight(to_tsvector('simple', coalesce(status, '')), 'C'))"
)
NEW_SEARCH = (
    "(setweight(to_tsvector('simple', coalesce(contract_number, '')), 'A') || ' ' || "
    "setweight(to_tsvector('simple', coalesce(register_number, '')), 'A') || ' ' || "
    "setweight(to_tsvector('german', coalesce(supplier, '')), 'B') || ' ' || "
    "setweight(to_tsvector('german', coalesce(short_description, '')), 'B') || ' ' || "
    "setweight(to_tsvector('simple', coalesce(status, '')), 'C'))"
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join("'%s'" % value for value in values)


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()"))


def _org_fk(table: str) -> sa.Column:
    return sa.Column(
        "organization_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organization.id", name=f"fk_{table}_organization_id_organization", ondelete="RESTRICT"),
        nullable=False,
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "contract_partner",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("contract_partner"),
        sa.Column("short_name", sa.String(120), nullable=False),
        sa.Column("name1", sa.String(255), nullable=False),
        sa.Column("name2", sa.String(255), nullable=True),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("postal_code", sa.String(16), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("country", sa.String(80), nullable=True),
        sa.Column("po_box", sa.String(40), nullable=True),
        sa.Column("po_box_postal_code", sa.String(16), nullable=True),
        sa.Column("phone", sa.String(80), nullable=True),
        sa.Column("fax", sa.String(80), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("vat_id", sa.String(40), nullable=True),
        sa.Column("industry_code", sa.String(64), nullable=True),
        sa.Column("partner_type", sa.String(64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_partner"),
    )
    op.create_index(
        "uq_contract_partner_org_short_name",
        "contract_partner",
        ["organization_id", sa.text("lower(short_name)")],
        unique=True,
    )
    op.create_index("ix_contract_partner_org_active", "contract_partner", ["organization_id", "is_active"])

    op.create_table(
        "catalog_contract_type",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("catalog_contract_type"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_confidential", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_contract_type"),
        sa.UniqueConstraint("organization_id", "code", name="uq_catalog_contract_type_org_code"),
    )
    op.create_table(
        "catalog_contract_category",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("catalog_contract_category"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_contract_category"),
        sa.UniqueConstraint("organization_id", "code", name="uq_catalog_contract_category_org_code"),
    )
    op.create_table(
        "catalog_contract_type_category",
        _uuid_pk(),
        sa.Column(
            "contract_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "catalog_contract_type.id",
                name="fk_cctc_contract_type_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "contract_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "catalog_contract_category.id",
                name="fk_cctc_contract_category_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_contract_type_category"),
        sa.UniqueConstraint(
            "contract_type_id", "contract_category_id", name="uq_catalog_contract_type_category_pair"
        ),
    )
    op.create_table(
        "lookup_value",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("lookup_value"),
        sa.Column("field_key", sa.String(48), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_lookup_value"),
        sa.UniqueConstraint("organization_id", "field_key", "code", name="uq_lookup_value_org_field_code"),
    )
    op.create_index("ix_lookup_value_org_field", "lookup_value", ["organization_id", "field_key"])

    # --- contract: register columns -------------------------------------
    columns = [
        sa.Column("register_number", sa.String(32), nullable=True),
        sa.Column("internal_number", sa.String(120), nullable=True),
        sa.Column("short_description", sa.String(500), nullable=True),
        sa.Column("subject_text", sa.Text(), nullable=True),
        sa.Column("is_framework", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("manual_billing", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("account_number", sa.String(64), nullable=True),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contract_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contract_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_location_code", sa.String(64), nullable=True),
        sa.Column("business_status", sa.String(24), server_default="in_arbeit", nullable=False),
        sa.Column("term_model", sa.String(32), nullable=True),
        sa.Column("term_start_date", sa.Date(), nullable=True),
        sa.Column("term_fixed_end_date", sa.Date(), nullable=True),
        sa.Column("initial_term_value", sa.Integer(), nullable=True),
        sa.Column("initial_term_unit", sa.String(8), nullable=True),
        sa.Column("minimum_term_value", sa.Integer(), nullable=True),
        sa.Column("minimum_term_unit", sa.String(8), nullable=True),
        sa.Column("notice_period_value", sa.Integer(), nullable=True),
        sa.Column("notice_period_unit", sa.String(8), nullable=True),
        sa.Column("notice_to", sa.String(16), nullable=True),
        sa.Column("renewal_period_value", sa.Integer(), nullable=True),
        sa.Column("renewal_period_unit", sa.String(8), nullable=True),
        sa.Column("reminder_lead_months", sa.Integer(), nullable=True),
        sa.Column("reminder_recipient_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("escalation_recipient_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reminder_todo", sa.String(500), nullable=True),
        sa.Column("terminated_on", sa.Date(), nullable=True),
        sa.Column("terminated_effective", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("retention_years_after_end", sa.Integer(), nullable=True),
    ]
    for column in columns:
        op.add_column("contract", column)
    op.create_foreign_key(
        "fk_contract_partner_id_contract_partner", "contract", "contract_partner",
        ["partner_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_contract_contract_type_id_catalog_contract_type", "contract", "catalog_contract_type",
        ["contract_type_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_contract_contract_category_id_catalog_contract_category", "contract", "catalog_contract_category",
        ["contract_category_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_contract_reminder_recipient_account_id_account", "contract", "account",
        ["reminder_recipient_account_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_contract_escalation_recipient_account_id_account", "contract", "account",
        ["escalation_recipient_account_id"], ["id"], ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_contract_business_status", "contract", f"business_status IN ({_in(BUSINESS_STATUS)})"
    )
    op.create_check_constraint(
        "ck_contract_term_model", "contract", f"term_model IS NULL OR term_model IN ({_in(TERM_MODEL)})"
    )
    op.create_check_constraint(
        "ck_contract_notice_to", "contract", f"notice_to IS NULL OR notice_to IN ({_in(NOTICE_TO)})"
    )
    op.create_index(
        "uq_contract_org_register_number",
        "contract",
        ["organization_id", "register_number"],
        unique=True,
        postgresql_where=sa.text("register_number IS NOT NULL"),
    )
    op.create_index("ix_contract_org_business_status", "contract", ["organization_id", "business_status"])
    op.create_index("ix_contract_partner_id", "contract", ["partner_id"])
    op.execute(f"ALTER TABLE contract ALTER COLUMN search_vector SET EXPRESSION AS {NEW_SEARCH}")

    # --- dependent tables -------------------------------------------------
    op.create_table(
        "contract_field_provenance",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("contract_field_provenance"),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_field_provenance_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_key", sa.String(64), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column(
            "extraction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "contract_extraction.id",
                name="fk_contract_field_provenance_extraction_id_contract_extraction",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("source_field", sa.String(120), nullable=True),
        sa.Column("ai_proposed_value", postgresql.JSONB(), nullable=True),
        sa.Column(
            "confirmed_by_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "account.id", name="fk_contract_field_provenance_confirmed_by_account_id_account", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column("confirmed_by_name", sa.String(255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_by_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "account.id", name="fk_contract_field_provenance_updated_by_account_id_account", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column("updated_by_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_field_provenance"),
        sa.UniqueConstraint("contract_id", "field_key", name="uq_contract_field_provenance_contract_field"),
        sa.CheckConstraint(f"origin IN ({_in(ORIGIN)})", name="ck_contract_field_provenance_origin"),
    )
    op.create_index("ix_contract_field_provenance_contract_id", "contract_field_provenance", ["contract_id"])

    op.create_table(
        "number_range",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("number_range"),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("prefix", sa.String(16), server_default="", nullable=False),
        sa.Column("padding", sa.Integer(), server_default="6", nullable=False),
        sa.Column("next_value", sa.BigInteger(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_number_range"),
        sa.UniqueConstraint("organization_id", "purpose", name="uq_number_range_org_purpose"),
        sa.CheckConstraint("next_value >= 1", name="ck_number_range_next_value_positive"),
        sa.CheckConstraint("padding BETWEEN 1 AND 12", name="ck_number_range_padding_range"),
    )
    op.create_table(
        "number_allocation",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("number_allocation"),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("formatted", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_number_allocation_contract_id_contract", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", name="fk_number_allocation_account_id_account", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_number_allocation"),
        sa.UniqueConstraint("organization_id", "purpose", "value", name="uq_number_allocation_org_purpose_value"),
        sa.CheckConstraint(f"state IN ({_in(ALLOCATION_STATE)})", name="ck_number_allocation_state"),
    )
    op.create_table(
        "contract_remark",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("contract_remark"),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_remark_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", name="fk_contract_remark_account_id_account", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_remark"),
        sa.CheckConstraint("length(btrim(body)) > 0", name="ck_contract_remark_body_not_blank"),
    )
    op.create_index("ix_contract_remark_contract_created", "contract_remark", ["contract_id", "created_at"])
    op.create_table(
        "contract_hospital",
        _uuid_pk(),
        *_timestamps(),
        _org_fk("contract_hospital"),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_hospital_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospital.id", name="fk_contract_hospital_hospital_id_hospital", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contract_hospital"),
        sa.UniqueConstraint("contract_id", "hospital_id", name="uq_contract_hospital_pair"),
    )
    op.create_index("ix_contract_hospital_hospital_id", "contract_hospital", ["hospital_id"])

    # --- data: existing contracts ----------------------------------------
    op.execute("UPDATE contract SET business_status = 'geloescht' WHERE lifecycle_state = 'deleted'")
    op.execute(
        """
        WITH numbered AS (
            SELECT id, organization_id,
                   row_number() OVER (PARTITION BY organization_id ORDER BY created_at, id) AS rn
            FROM contract
        )
        UPDATE contract c
        SET register_number = lpad(numbered.rn::text, 6, '0')
        FROM numbered
        WHERE c.id = numbered.id
        """
    )
    op.execute(
        """
        INSERT INTO number_allocation (organization_id, purpose, value, formatted, state, contract_id)
        SELECT organization_id, 'contract', register_number::bigint, register_number, 'used', id
        FROM contract
        WHERE register_number IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO number_range (organization_id, purpose, prefix, padding, next_value)
        SELECT organization_id, 'contract', '', 6, max(register_number::bigint) + 1
        FROM contract
        WHERE register_number IS NOT NULL
        GROUP BY organization_id
        """
    )
    # Existing department-scoped hospital assignment becomes the primary link.
    op.execute(
        """
        INSERT INTO contract_hospital (organization_id, contract_id, hospital_id, is_primary)
        SELECT organization_id, id, hospital_id, true
        FROM contract
        WHERE hospital_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_contract_hospital_hospital_id", table_name="contract_hospital")
    op.drop_table("contract_hospital")
    op.drop_index("ix_contract_remark_contract_created", table_name="contract_remark")
    op.drop_table("contract_remark")
    op.drop_table("number_allocation")
    op.drop_table("number_range")
    op.drop_index("ix_contract_field_provenance_contract_id", table_name="contract_field_provenance")
    op.drop_table("contract_field_provenance")

    op.execute(f"ALTER TABLE contract ALTER COLUMN search_vector SET EXPRESSION AS {OLD_SEARCH}")
    op.drop_index("ix_contract_partner_id", table_name="contract")
    op.drop_index("ix_contract_org_business_status", table_name="contract")
    op.drop_index("uq_contract_org_register_number", table_name="contract")
    op.drop_constraint("ck_contract_notice_to", "contract", type_="check")
    op.drop_constraint("ck_contract_term_model", "contract", type_="check")
    op.drop_constraint("ck_contract_business_status", "contract", type_="check")
    for name in (
        "fk_contract_escalation_recipient_account_id_account",
        "fk_contract_reminder_recipient_account_id_account",
        "fk_contract_contract_category_id_catalog_contract_category",
        "fk_contract_contract_type_id_catalog_contract_type",
        "fk_contract_partner_id_contract_partner",
    ):
        op.drop_constraint(name, "contract", type_="foreignkey")
    for column in (
        "retention_years_after_end", "ended_on", "terminated_effective", "terminated_on", "reminder_todo",
        "escalation_recipient_account_id", "reminder_recipient_account_id", "reminder_lead_months",
        "renewal_period_unit", "renewal_period_value", "notice_to", "notice_period_unit", "notice_period_value",
        "minimum_term_unit", "minimum_term_value", "initial_term_unit", "initial_term_value",
        "term_fixed_end_date", "term_start_date", "term_model", "business_status", "storage_location_code",
        "contract_category_id", "contract_type_id", "partner_id", "account_number", "manual_billing",
        "is_framework", "subject_text", "short_description", "internal_number", "register_number",
    ):
        op.drop_column("contract", column)

    op.drop_index("ix_lookup_value_org_field", table_name="lookup_value")
    op.drop_table("lookup_value")
    op.drop_table("catalog_contract_type_category")
    op.drop_table("catalog_contract_category")
    op.drop_table("catalog_contract_type")
    op.drop_index("ix_contract_partner_org_active", table_name="contract_partner")
    op.drop_index("uq_contract_partner_org_short_name", table_name="contract_partner")
    op.drop_table("contract_partner")
