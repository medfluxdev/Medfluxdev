"""work_item – Materialsierte, autoritative Arbeits-/Handlungsliste (PR-4).

Sammlung der Krankenhaus-weiten Arbeitspunkte, die deterministisch aus
AUTORITATIVEN Quellen abgeleitet werden (KEIN zweiter Warn-Engine):

- aus den persistenten, aktiven STEP-11-`contract_warning`-Zeilen
  (Kündigungsfrist, Vertragsende, automatische Verlängerung, ausgelaufen,
  manueller Review, fehlende Kosten) – mit `source_warning_id`-Linie,
- aus Geräten (`contract_equipment` mit `requires_review` /
  `relationship_quality` generisch/mehrdeutig), sofern kein Beam von Daten
  herleitbar ist.

Lebenszyklus:
- `status` (open/acknowledged/resolved) ist der MENSCHLICHE Lebenszyklus,
  unabhängig vom objektiven `active`-Zustand (paralleles Muster zu STEP-11).
- `active=False` => aus der Standard-Queue ausgeblendet, Zeile/Historie bleibt
  erhalten (kein stilles Löschen). Deterministisches Stale-Verhalten: Quelle
  nicht mehr aktiv => item `active=False`; Quelle wieder aktiv => gleiche
  `logical_fingerprint` reaktiviert (idempotent, kein Duplikat).

Org-gebunden; jede Zeile hat genau EINEN `contract_id`. `equipment_id` /
`contract_equipment_id` sind optional (nur gerätebezogene Punkte).
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

WORK_ITEM_TYPE_ALLOWED = {
    "cancellation_deadline",
    "contract_expiry",
    "automatic_renewal",
    "contract_expired",
    "manual_review",
    "missing_cost",
    "equipment_coverage_review",
    "equipment_relationship_ambiguous",
    "sla_issue",
}
SEVERITY_ALLOWED = {"info", "low", "medium", "high", "critical"}
STATUS_ALLOWED = {"open", "acknowledged", "resolved"}


class WorkItem(OrgOwnedMixin, Base):
    """Ein materialisierter, autoritativer Arbeitspunkt."""

    __tablename__ = "work_item"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
    )
    contract_equipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_equipment.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_warning_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_warning.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default="open", nullable=False
    )
    title_de: Mapped[str] = mapped_column(String(255), nullable=False)
    why_de: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_hint_de: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    days_remaining: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requires_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    logical_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    calc_field_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    source_field_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    references: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            f"item_type IN ({', '.join(repr(v) for v in sorted(WORK_ITEM_TYPE_ALLOWED))})",
            name="item_type",
        ),
        CheckConstraint(
            f"severity IN ({', '.join(repr(v) for v in sorted(SEVERITY_ALLOWED))})",
            name="severity",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(STATUS_ALLOWED))})",
            name="status",
        ),
        UniqueConstraint(
            "organization_id", "contract_id", "logical_fingerprint",
            name="uq_work_item_fingerprint",
        ),
        Index("ix_work_item_org_status", "organization_id", "status"),
        Index("ix_work_item_org_active", "organization_id", "active"),
        Index("ix_work_item_contract", "contract_id"),
        Index("ix_work_item_equipment", "equipment_id"),
        Index("ix_work_item_target_date", "target_date"),
        Index("ix_work_item_severity", "severity"),
        Index("ix_work_item_source_warning", "source_warning_id"),
    )
