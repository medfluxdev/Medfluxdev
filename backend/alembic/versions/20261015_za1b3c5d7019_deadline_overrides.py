"""Termine & Aufgaben: per-Termin values a person set (ToDo now; reminder override later).

Revision ID: za1b3c5d7019
Revises: z8c0d2e34018

Adds `contract_deadline.overrides` (JSONB, NULL = everything follows the contract).
The system-deadline sync never overwrites a key present there.

Data: the contract-level ToDo (`contract.reminder_todo`) moves to the open
Kündigungs-/Vertragsende-Termine it applied to; the column itself is kept
(no data is dropped). Open system Termine get their action titles right away
instead of waiting for the next sync.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "za1b3c5d7019"
down_revision = "z8c0d2e34018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_deadline", sa.Column("overrides", postgresql.JSONB(), nullable=True))
    op.execute(
        """
        UPDATE contract_deadline AS d
           SET todo_text = c.reminder_todo,
               overrides = jsonb_build_object('todo_text', c.reminder_todo)
          FROM contract AS c
         WHERE d.contract_id = c.id
           AND d.source = 'system'
           AND d.status = 'open'
           AND d.system_key IN ('cancel_by', 'contract_end')
           AND c.reminder_todo IS NOT NULL
           AND btrim(c.reminder_todo) <> ''
        """
    )
    op.execute(
        """
        UPDATE contract_deadline
           SET title = CASE system_key
                 WHEN 'cancel_by' THEN 'Kündigung prüfen'
                 WHEN 'contract_end' THEN 'Vertragsende'
                 WHEN 'retention_review' THEN 'Löschprüfung'
               END
         WHERE source = 'system'
           AND status = 'open'
           AND system_key IN ('cancel_by', 'contract_end', 'retention_review')
        """
    )


def downgrade() -> None:
    op.drop_column("contract_deadline", "overrides")
