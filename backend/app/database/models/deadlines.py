"""Fristen, Benachrichtigungen, E-Mail-Warteschlange, Vertretungen und
Joblaeufe (H5).

- `contract_deadline`: manuelle und systemerzeugte Termine eines Vertrags.
  Systemtermine (`source='system'`) entstehen deterministisch aus den
  Register-Fristen und werden bei Datenaenderungen nachgefuehrt.
- `notification`: persoenliches Postfach (gelesen/ungelesen), idempotent ueber
  `dedupe_key`.
- `notification_outbox`: E-Mail-Warteschlange mit Wiederholungen.
- `account_deputy`: zeitlich begrenzte Vertretung.
- `job_run`: Protokoll/Monitoring des Tageslaufs.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

DEADLINE_STATUS_ALLOWED = ("open", "done", "cancelled")
DEADLINE_SOURCE_ALLOWED = ("manual", "system")
NOTIFICATION_KIND_ALLOWED = ("deadline_reminder", "deadline_overdue", "deadline_escalation", "deadline_assigned")
OUTBOX_STATUS_ALLOWED = ("pending", "sent", "failed")
JOB_STATUS_ALLOWED = ("running", "succeeded", "failed")


class ContractDeadline(OrgOwnedMixin, Base):
    __tablename__ = "contract_deadline"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    system_key: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    remind_on: Mapped[date] = mapped_column(Date, nullable=False)
    assignee_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    escalation_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    todo_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    send_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    send_ics: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    done_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    done_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in DEADLINE_STATUS_ALLOWED)})", name="status"),
        CheckConstraint(f"source IN ({', '.join(repr(v) for v in DEADLINE_SOURCE_ALLOWED)})", name="source"),
        CheckConstraint("source = 'manual' OR system_key IS NOT NULL", name="system_key_required"),
        Index(
            "uq_contract_deadline_open_system_key",
            "contract_id",
            "system_key",
            unique=True,
            postgresql_where=text("source = 'system' AND status = 'open'"),
        ),
        Index("ix_contract_deadline_contract_status", "contract_id", "status"),
        Index("ix_contract_deadline_org_status_remind", "organization_id", "status", "remind_on"),
        Index("ix_contract_deadline_assignee", "assignee_account_id"),
    )


class Notification(OrgOwnedMixin, Base):
    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=True
    )
    deadline_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_deadline.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    on_behalf_of_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"kind IN ({', '.join(repr(v) for v in NOTIFICATION_KIND_ALLOWED)})", name="kind"),
        UniqueConstraint("account_id", "dedupe_key", name="uq_notification_account_dedupe"),
        Index("ix_notification_account_read", "account_id", "read_at"),
    )


class NotificationOutbox(OrgOwnedMixin, Base):
    __tablename__ = "notification_outbox"

    id: Mapped[uuid.UUID] = uuid_pk()
    notification_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("notification.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="email")
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in OUTBOX_STATUS_ALLOWED)})", name="status"),
        Index("ix_notification_outbox_status", "status"),
    )


class AccountDeputy(OrgOwnedMixin, Base):
    __tablename__ = "account_deputy"

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    deputy_account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        CheckConstraint("valid_to >= valid_from", name="period"),
        CheckConstraint("account_id <> deputy_account_id", name="not_self"),
        Index("ix_account_deputy_account_period", "account_id", "valid_from", "valid_to"),
    )


class JobRun(Base):
    __tablename__ = "job_run"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # NULL = globaler Lauf (Zeitplan); sonst manuell fuer eine Organisation.
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=True
    )
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduler")
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    counts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in JOB_STATUS_ALLOWED)})", name="status"),
        Index("ix_job_run_name_started", "job_name", "started_at"),
    )
