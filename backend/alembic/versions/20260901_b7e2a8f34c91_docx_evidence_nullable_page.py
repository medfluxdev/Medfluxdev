"""DOCX evidence uses logical indexes and no invented page number.

Revision ID: b7e2a8f34c91
Revises: a3f9c1127305
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b7e2a8f34c91"
down_revision: Union[str, None] = "a3f9c1127305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "extraction_evidence",
        "page",
        existing_type=__import__("sqlalchemy").Integer(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_extraction_evidence_source_address_present",
        "extraction_evidence",
        "page IS NOT NULL OR paragraph_index IS NOT NULL OR table_index IS NOT NULL",
    )


def downgrade() -> None:
    # Never delete DOCX evidence or fabricate pages during downgrade.  Refuse an
    # unsafe downgrade until page-less evidence has been migrated explicitly.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM extraction_evidence WHERE page IS NULL) THEN
                RAISE EXCEPTION
                    'Cannot downgrade while page-less DOCX evidence exists';
            END IF;
        END $$;
        """
    )
    op.drop_constraint(
        "ck_extraction_evidence_source_address_present",
        "extraction_evidence",
        type_="check",
    )
    op.alter_column(
        "extraction_evidence",
        "page",
        existing_type=__import__("sqlalchemy").Integer(),
        nullable=False,
    )