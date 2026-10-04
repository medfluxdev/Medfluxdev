"""fix contract_override.id server default uuidv7

Revision ID: f1a2b3c4d5e6
Revises: e3a4b5c6d7e8
Create Date: 2026-09-04

Die erste Contract_Override-Migration hat das `server_default` (uuidv7()) fuer
die `id`-Spalte vergessen. Der ORM (uuid_pk()) erzeugt die ID rein server-seitig,
daher muss die Spalte das Default nachtraeglich bekommen, sonst schlagen Inserts
mit NULL-id fehl. Wir fuegen es hier nach, damit die Spalte dem gemeinsamen
`uuid_pk()`-Muster der uebrigen Tabellen entspricht.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "e3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "contract_override",
        "id",
        server_default=sa.text("uuidv7()"),
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "contract_override",
        "id",
        server_default=None,
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
    )
