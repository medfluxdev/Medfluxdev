"""Link a lifecycle decision to the reminder created with it.

Revision ID: y7b9c1d23017
Revises: x6a8b0c12016

Additive only: `contract_lifecycle_decision.reminder_deadline_id` (nullable,
SET NULL when the deadline row goes away). The FK is added NOT VALID because the
table may already hold rows; all existing values are NULL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "y7b9c1d23017"
down_revision = "x6a8b0c12016"
branch_labels = None
depends_on = None

FK = "fk_contract_lifecycle_decision_reminder_deadline_id_con_5d4b"  # convention name, truncated like SQLAlchemy


def upgrade() -> None:
    op.add_column(
        "contract_lifecycle_decision",
        sa.Column("reminder_deadline_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f(FK), "contract_lifecycle_decision", "contract_deadline",
        ["reminder_deadline_id"], ["id"], ondelete="SET NULL", postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint(op.f(FK), "contract_lifecycle_decision", type_="foreignkey")
    op.drop_column("contract_lifecycle_decision", "reminder_deadline_id")
