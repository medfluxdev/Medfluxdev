"""bind contract_equipment rows to extraction snapshots

Revision ID: b5c9d0e3f1a4
Revises: a4b8c9d2e0f2
Create Date: 2026-09-09

Reanalysis keeps historical equipment relationships immutable by binding every
contract_equipment row to the ContractExtraction that produced it. Current rows
are selected through contract.accepted_extraction_id.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5c9d0e3f1a4"
down_revision = "a4b8c9d2e0f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contract_equipment",
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Existing rows predate extraction-scoped equipment snapshots. Their only
    # trustworthy provenance is the contract's currently accepted extraction.
    op.execute(
        sa.text(
            """
            UPDATE contract_equipment AS ce
            SET extraction_id = c.accepted_extraction_id
            FROM contract AS c
            WHERE ce.contract_id = c.id
              AND ce.extraction_id IS NULL
              AND c.accepted_extraction_id IS NOT NULL
            """
        )
    )

    # Do not silently manufacture provenance for inconsistent legacy rows. Abort
    # safely instead; Alembic/PostgreSQL will roll the migration transaction back.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM contract_equipment
                    WHERE extraction_id IS NULL
                ) THEN
                    RAISE EXCEPTION
                        'contract_equipment contains rows without an accepted extraction; migration aborted';
                END IF;
            END
            $$;
            """
        )
    )

    op.alter_column(
        "contract_equipment",
        "extraction_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_contract_equipment_extraction_id_contract_extraction",
        "contract_equipment",
        "contract_extraction",
        ["extraction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_contract_equipment_extraction_id",
        "contract_equipment",
        ["extraction_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_contract_equipment_contract_extraction_fingerprint",
        "contract_equipment",
        ["contract_id", "extraction_id", "logical_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_contract_equipment_contract_extraction_fingerprint",
        "contract_equipment",
        type_="unique",
    )
    op.drop_index(
        "ix_contract_equipment_extraction_id",
        table_name="contract_equipment",
    )
    op.drop_constraint(
        "fk_contract_equipment_extraction_id_contract_extraction",
        "contract_equipment",
        type_="foreignkey",
    )
    op.drop_column("contract_equipment", "extraction_id")
