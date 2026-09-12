"""add contract archive columns (is_archived, archived_at)

Revision ID: a4b7c9d2e0f1
Revises: fb2e6c8d1a54
Create Date: 2026-09-07

Archiv-Ebene (PR-5): nicht-destruktives Verschieben von Verträgen ins Archiv.
`is_archived` blendet Verträge aus dem aktiven Portfolio aus (Liste,
Dashboard, Arbeitsliste, Gerätebestand); `archived_at` dokumentiert den
Zeitpunkt. Archivieren ist reversibel (Unarchive) und löscht nichts.
"""

from alembic import op
import sqlalchemy as sa

revision = "a4b7c9d2e0f1"
down_revision = "fb2e6c8d1a54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contract",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "contract",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_contract_org_is_archived",
        "contract",
        ["organization_id", "is_archived"],
    )


def downgrade() -> None:
    op.drop_index("ix_contract_org_is_archived", table_name="contract")
    op.drop_column("contract", "archived_at")
    op.drop_column("contract", "is_archived")