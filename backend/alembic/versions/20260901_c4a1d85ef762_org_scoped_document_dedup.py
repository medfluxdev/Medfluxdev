"""Scope document deduplication to an organization.

Revision ID: c4a1d85ef762
Revises: b7e2a8f34c91
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4a1d85ef762"
down_revision: Union[str, None] = "b7e2a8f34c91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_document_file_sha256", "document_file", type_="unique")
    op.drop_constraint("uq_document_version_sha256", "document_version", type_="unique")
    op.create_unique_constraint(
        "uq_document_file_org_sha256",
        "document_file",
        ["organization_id", "sha256"],
    )
    op.create_unique_constraint(
        "uq_document_version_org_sha256",
        "document_version",
        ["organization_id", "sha256"],
    )


def downgrade() -> None:
    # Refuse to collapse isolated per-organization documents into a global
    # identity when the same bytes legitimately exist in multiple tenants.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT sha256 FROM document_file
                GROUP BY sha256 HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade while duplicate hashes exist across organizations';
            END IF;
        END $$;
        """
    )
    op.drop_constraint(
        "uq_document_version_org_sha256", "document_version", type_="unique"
    )
    op.drop_constraint(
        "uq_document_file_org_sha256", "document_file", type_="unique"
    )
    op.create_unique_constraint(
        "uq_document_version_sha256", "document_version", ["sha256"]
    )
    op.create_unique_constraint(
        "uq_document_file_sha256", "document_file", ["sha256"]
    )
