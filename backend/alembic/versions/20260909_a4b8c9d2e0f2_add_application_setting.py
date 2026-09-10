"""add application_setting (globale key/value Einstellungen)

Revision ID: a4b8c9d2e0f2
Revises: a4b7c9d2e0f1
Create Date: 2026-09-09

Schritt 6B: Deployment-weit wird die persistierte KI-Provider-/Modell-
Auswahl (Einstellungs-Oberfläche) gespeichert. Bewusst OHNE Organisations-
Scope – die aktive lokale KI ist pro Installation einmalig.
"""

from alembic import op
import sqlalchemy as sa

revision = "a4b8c9d2e0f2"
down_revision = "a4b7c9d2e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_setting",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_application_setting")),
    )


def downgrade() -> None:
    op.drop_table("application_setting")