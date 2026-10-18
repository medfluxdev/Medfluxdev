"""Analyse modes: numbered runs, supplement/sections/full, hint, protection, reset, progress.

Revision ID: zh8c0d2e3026
Revises: zg7b9c1d2025

`contract_reextraction` gets a run number per contract (#1 is the analysis at import, which has no
row; existing runs are numbered from #2, or from #1 when the first run started without a prior
analysis), the selected sections, a free-text hint for the local model, the manual-value protection
and reset flags and the progress of a running analysis. The mode `missing_fields` becomes
`supplement`; `sections` and `rollback` are new. Additive; existing rows keep their meaning.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zh8c0d2e3026"
down_revision = "zg7b9c1d2025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_reextraction", sa.Column("number", sa.Integer(), nullable=True))
    op.add_column("contract_reextraction", sa.Column("sections", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("contract_reextraction", sa.Column("hint", sa.String(500), nullable=True))
    op.add_column("contract_reextraction", sa.Column("protect_manual", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("contract_reextraction", sa.Column("reset_confirmations", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("contract_reextraction", sa.Column("progress", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.execute(
        """
        WITH ordered AS (
            SELECT id, contract_id, base_extraction_id,
                   row_number() OVER (PARTITION BY contract_id ORDER BY created_at, id) AS n
            FROM contract_reextraction
        ), offsets AS (
            SELECT contract_id, CASE WHEN base_extraction_id IS NULL THEN 0 ELSE 1 END AS o
            FROM ordered WHERE n = 1
        )
        UPDATE contract_reextraction AS r
        SET number = ordered.n + offsets.o
        FROM ordered JOIN offsets USING (contract_id)
        WHERE r.id = ordered.id
        """
    )
    op.alter_column("contract_reextraction", "number", nullable=False)
    op.create_unique_constraint("uq_contract_reextraction_number", "contract_reextraction", ["contract_id", "number"])
    op.drop_constraint("ck_contract_reextraction_mode_allowed", "contract_reextraction", type_="check")
    op.execute("UPDATE contract_reextraction SET mode = 'supplement' WHERE mode = 'missing_fields'")
    op.create_check_constraint(
        "ck_contract_reextraction_mode_allowed", "contract_reextraction",
        "mode IN ('supplement', 'sections', 'full', 'rollback')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contract_reextraction_mode_allowed", "contract_reextraction", type_="check")
    op.execute("DELETE FROM contract_reextraction WHERE mode = 'rollback'")
    op.execute("UPDATE contract_reextraction SET mode = 'missing_fields' WHERE mode = 'supplement'")
    op.execute("UPDATE contract_reextraction SET mode = 'full' WHERE mode = 'sections'")
    op.create_check_constraint(
        "ck_contract_reextraction_mode_allowed", "contract_reextraction", "mode IN ('full', 'missing_fields')",
    )
    op.drop_constraint("uq_contract_reextraction_number", "contract_reextraction", type_="unique")
    for column in ("progress", "reset_confirmations", "protect_manual", "hint", "sections", "number"):
        op.drop_column("contract_reextraction", column)
