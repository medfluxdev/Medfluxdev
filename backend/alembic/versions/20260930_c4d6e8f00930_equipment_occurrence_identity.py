"""Separate persisted equipment occurrence from stable semantic relationship identity.

Revision ID: c4d6e8f00930
Revises: b3c5d7e90928

Historical rows retain their logical fingerprints and receive a stable,
unique occurrence backfill. No historical row is deleted or merged.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "c4d6e8f00930"
down_revision = "b3c5d7e90928"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contract_equipment",
        sa.Column("occurrence_fingerprint", sa.String(length=64), nullable=True),
    )
    # Historical rows were unique on logical_fingerprint. A row-id-based
    # backfill preserves each existing occurrence without claiming source
    # stability for legacy data with insufficient evidence.
    op.execute(
        """
        UPDATE contract_equipment
        SET occurrence_fingerprint =
            encode(digest(id::text, 'sha256'), 'hex')
        WHERE occurrence_fingerprint IS NULL
        """
    )
    op.drop_constraint(
        "uq_contract_equipment_contract_extraction_fingerprint",
        "contract_equipment",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_contract_equipment_contract_extraction_occurrence",
        "contract_equipment",
        ["contract_id", "extraction_id", "occurrence_fingerprint"],
    )


def downgrade() -> None:
    # Refuse a destructive downgrade if new independent occurrences share
    # the same legacy logical fingerprint.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM contract_equipment
            WHERE logical_fingerprint IS NOT NULL
            GROUP BY contract_id, extraction_id, logical_fingerprint
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION 'Cannot downgrade: independent equipment occurrences share legacy logical fingerprints';
          END IF;
        END $$;
        """
    )
    op.drop_constraint(
        "uq_contract_equipment_contract_extraction_occurrence",
        "contract_equipment",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_contract_equipment_contract_extraction_fingerprint",
        "contract_equipment",
        ["contract_id", "extraction_id", "logical_fingerprint"],
    )
    op.drop_column("contract_equipment", "occurrence_fingerprint")
