"""Human operational lifecycle records for contracts and equipment.

These records never replace deterministic Contract.status or extracted evidence.
They capture user decisions and equipment operational state as auditable workflow.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

CONTRACT_DECISIONS = {"renew", "renegotiate", "terminate", "monitor"}
DECISION_STATUS = {"planned", "in_progress", "completed", "cancelled"}
EQUIPMENT_LIFECYCLE = {"active", "maintenance_due", "out_of_service", "retired"}


class ContractLifecycleDecision(OrgOwnedMixin, Base):
    __tablename__ = "contract_lifecycle_decision"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="planned", server_default="planned", nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    actor_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Erinnerung, die mit der Entscheidung angelegt wurde (änderbar mit der Entscheidung).
    reminder_deadline_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_deadline.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(f"decision IN ({', '.join(repr(v) for v in sorted(CONTRACT_DECISIONS))})", name="decision"),
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in sorted(DECISION_STATUS))})", name="status"),
        Index("ix_contract_lifecycle_contract", "contract_id", "created_at"),
    )


class EquipmentLifecycleRecord(OrgOwnedMixin, Base):
    __tablename__ = "equipment_lifecycle"

    id: Mapped[uuid.UUID] = uuid_pk()
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active", nullable=False)
    next_service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in sorted(EQUIPMENT_LIFECYCLE))})", name="status"),
        UniqueConstraint("equipment_id", name="uq_equipment_lifecycle_equipment"),
        Index("ix_equipment_lifecycle_status", "organization_id", "status"),
        Index("ix_equipment_lifecycle_service", "next_service_date"),
    )
