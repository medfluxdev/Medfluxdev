"""Deadlines, notifications, e-mail outbox, deputies, job runs (H5).

Revision ID: f7a9b1c31004
Revises: e6f8a0b21004

Additive only. Existing accounts receive notifications and reminders by
default (same as before: nobody had opted out because nothing was sent).
System deadlines are created by the application, not by this migration.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f7a9b1c31004"
down_revision = "e6f8a0b21004"
branch_labels = None
depends_on = None


def _in(values: tuple[str, ...]) -> str:
    return ", ".join("'%s'" % value for value in values)


def _pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()"))


def _org(table: str) -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name=f"fk_{table}_organization_id_organization", ondelete="RESTRICT"),
            nullable=False,
        ),
    ]


def _account_fk(table: str, column: str, *, nullable: bool = True, ondelete: str = "SET NULL") -> sa.Column:
    return sa.Column(
        column,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("account.id", name=f"fk_{table}_{column}_account", ondelete=ondelete),
        nullable=nullable,
    )


def upgrade() -> None:
    op.add_column("account", sa.Column("receives_notifications", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("account", sa.Column("receives_reminders", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("account", sa.Column("default_deputy_account_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_account_default_deputy_account_id_account", "account", "account",
        ["default_deputy_account_id"], ["id"], ondelete="SET NULL",
    )

    op.create_table(
        "contract_deadline",
        _pk(),
        *_org("contract_deadline"),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_contract_deadline_contract_id_contract", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("system_key", sa.String(32), nullable=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("remind_on", sa.Date(), nullable=False),
        _account_fk("contract_deadline", "assignee_account_id"),
        _account_fk("contract_deadline", "escalation_account_id"),
        sa.Column("todo_text", sa.String(500), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("send_email", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("send_ics", sa.Boolean(), server_default="false", nullable=False),
        _account_fk("contract_deadline", "done_by_account_id"),
        sa.Column("done_by_name", sa.String(255), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_deadline"),
        sa.CheckConstraint("status IN ('open', 'done', 'cancelled')", name="ck_contract_deadline_status"),
        sa.CheckConstraint("source IN ('manual', 'system')", name="ck_contract_deadline_source"),
        sa.CheckConstraint("source = 'manual' OR system_key IS NOT NULL", name="ck_contract_deadline_system_key_required"),
    )
    op.create_index(
        "uq_contract_deadline_open_system_key", "contract_deadline", ["contract_id", "system_key"],
        unique=True, postgresql_where=sa.text("source = 'system' AND status = 'open'"),
    )
    op.create_index("ix_contract_deadline_contract_status", "contract_deadline", ["contract_id", "status"])
    op.create_index("ix_contract_deadline_org_status_remind", "contract_deadline", ["organization_id", "status", "remind_on"])
    op.create_index("ix_contract_deadline_assignee", "contract_deadline", ["assignee_account_id"])

    op.create_table(
        "notification",
        _pk(),
        *_org("notification"),
        _account_fk("notification", "account_id", nullable=False, ondelete="CASCADE"),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract.id", name="fk_notification_contract_id_contract", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "deadline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract_deadline.id", name="fk_notification_deadline_id_contract_deadline", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("on_behalf_of_name", sa.String(255), nullable=True),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_notification"),
        sa.UniqueConstraint("account_id", "dedupe_key", name="uq_notification_account_dedupe"),
        sa.CheckConstraint(
            "kind IN ('deadline_reminder', 'deadline_overdue', 'deadline_escalation', 'deadline_assigned')",
            name="ck_notification_kind",
        ),
    )
    op.create_index("ix_notification_account_read", "notification", ["account_id", "read_at"])

    op.create_table(
        "notification_outbox",
        _pk(),
        *_org("notification_outbox"),
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification.id", name="fk_notification_outbox_notification_id_notification", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("ics", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_notification_outbox"),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_notification_outbox_status"),
    )
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])

    op.create_table(
        "account_deputy",
        _pk(),
        *_org("account_deputy"),
        _account_fk("account_deputy", "account_id", nullable=False, ondelete="CASCADE"),
        _account_fk("account_deputy", "deputy_account_id", nullable=False, ondelete="CASCADE"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_account_deputy"),
        sa.CheckConstraint("valid_to >= valid_from", name="ck_account_deputy_period"),
        sa.CheckConstraint("account_id <> deputy_account_id", name="ck_account_deputy_not_self"),
    )
    op.create_index("ix_account_deputy_account_period", "account_deputy", ["account_id", "valid_from", "valid_to"])

    op.create_table(
        "job_run",
        _pk(),
        sa.Column("job_name", sa.String(64), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", name="fk_job_run_organization_id_organization", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("host", sa.String(255), nullable=True),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counts", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_job_run"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="ck_job_run_status"),
    )
    op.create_index("ix_job_run_name_started", "job_run", ["job_name", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_job_run_name_started", table_name="job_run")
    op.drop_table("job_run")
    op.drop_index("ix_account_deputy_account_period", table_name="account_deputy")
    op.drop_table("account_deputy")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_index("ix_notification_account_read", table_name="notification")
    op.drop_table("notification")
    op.drop_index("ix_contract_deadline_assignee", table_name="contract_deadline")
    op.drop_index("ix_contract_deadline_org_status_remind", table_name="contract_deadline")
    op.drop_index("ix_contract_deadline_contract_status", table_name="contract_deadline")
    op.drop_index("uq_contract_deadline_open_system_key", table_name="contract_deadline")
    op.drop_table("contract_deadline")
    op.drop_constraint("fk_account_default_deputy_account_id_account", "account", type_="foreignkey")
    op.drop_column("account", "default_deputy_account_id")
    op.drop_column("account", "receives_reminders")
    op.drop_column("account", "receives_notifications")
