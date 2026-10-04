"""warning_evaluation_run & contract_warning – durable Warn-Zustand/Historie (STEP 11).

Erweitert die STEP-10-Architektur (immutable Runs + accepted-Zeiger) sauber:
- `warning_evaluation_run`: EIN reproduzierbarer Warn-Evaluationslauf je
  (contract, calculation_run, as_of_date, policy_version). Header + optional
  kleines reproduzierbares Ergebnis-JSONB (§7-Policy: klein, ganzheitlich gelesen).
  Kein Lauf ist destruktiv – ein neuer Lauf FÜGT eine Zeile hinzu.
- `contract_warning`: AKTUELLER akkumulierter Warn-Zustand je logischem Problem
  (Schluessel = logical_fingerprint pro Vertrag). `active` = objektiv aktiv in
  der letzten Evaluation; Historie bleibt erhalten (active=False statt Löschung).
  `action_state` (open/acknowledged/resolved/dismissed) ist der MENSCHLICHE
  Lebenszyklus und bewusst UNABHÄNGIG vom Evaluations-Zustand `active`: eine
  weiterhin objektiv aktive Warnung kann zugleich acknowledged sein.

Erweiterungspunkt (Schicht C): spaetere owner/department/escalation/notification
als saubere FK-Migration, OHNE Warn-Identitaet/-Evaluation-Semantik zu ändern.
Keine Fake-User-Entitaeten; kein Notification-Delivery in STEP 11.
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

WARNING_RUN_STATUS_ALLOWED = {"computed", "failed"}
WARNING_TYPE_ALLOWED = {
    "contract_end_approaching",
    "contract_expired",
    "cancellation_deadline_approaching",
    "cancellation_deadline_today",
    "cancellation_deadline_passed",
    "automatic_renewal_attention",
    "unclear_contract_data",
    "calculation_conflict",
    "manual_review_required",
    "missing_cost_data",
    "cost_conflict",
    "currency_conflict",
}
SEVERITY_ALLOWED = {"info", "low", "medium", "high", "critical"}
TARGET_KIND_ALLOWED = {
    "contract_end",
    "cancellation_deadline",
    "renewal",
    "cost",
    "data_quality",
}
ACTION_STATE_ALLOWED = {"open", "acknowledged", "resolved", "dismissed"}


class WarningEvaluationRun(OrgOwnedMixin, Base):
    """Ein deterministischer, reproduzierbarer Warn-Evaluationslauf."""

    __tablename__ = "warning_evaluation_run"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calculation_run.id", ondelete="RESTRICT", name="fk_warn_run_calc_run"),
        nullable=False,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Kleines, deterministisch reproduzierbares Ergebnis-Snapshot (§7-Policy).
    result_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(WARNING_RUN_STATUS_ALLOWED))})",
            name="status",
        ),
        Index("ix_warning_run_contract_created", "contract_id", "created_at"),
        Index("ix_warning_run_calc_run", "calculation_run_id"),
    )


class ContractWarning(OrgOwnedMixin, Base):
    """Aktueller, akkumulierter Warn-Zustand eines logischen Problems (je Vertrag)."""

    __tablename__ = "contract_warning"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_evaluation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("warning_evaluation_run.id", ondelete="SET NULL", name="fk_warning_last_run"),
        nullable=True,
    )
    warning_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    days_remaining: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logical_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_action: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    requires_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Menschlicher Lebenszyklus (Schicht C-Bereitschaft; Uebergaenge spaeter).
    action_state: Mapped[str] = mapped_column(
        String(24), default="open", nullable=False
    )
    action_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Strukturierte Provenienz (stabile Referenzen; KEIN Vertragstext-Duplikat).
    calculation_field_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    source_field_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    references: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"warning_type IN ({', '.join(repr(v) for v in sorted(WARNING_TYPE_ALLOWED))})",
            name="warning_type",
        ),
        CheckConstraint(
            f"severity IN ({', '.join(repr(v) for v in sorted(SEVERITY_ALLOWED))})",
            name="severity",
        ),
        CheckConstraint(
            f"target_kind IN ({', '.join(repr(v) for v in sorted(TARGET_KIND_ALLOWED))})",
            name="target_kind",
        ),
        CheckConstraint(
            f"action_state IN ({', '.join(repr(v) for v in sorted(ACTION_STATE_ALLOWED))})",
            name="action_state",
        ),
        # Eine Zeile je logischem Problem pro Vertrag (Deduplikation über Laufzeiten).
        UniqueConstraint(
            "contract_id", "logical_fingerprint",
            name="uq_contract_warning_fingerprint",
        ),
        Index("ix_contract_warning_contract_active", "contract_id", "active"),
        Index("ix_contract_warning_type", "warning_type"),
        Index("ix_contract_warning_severity", "severity"),
        Index("ix_contract_warning_target_date", "target_date"),
        Index("ix_contract_warning_requires_action", "requires_action"),
    )
