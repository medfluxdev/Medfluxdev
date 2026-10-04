"""calculation_run, calculation_result & calculation_review_flag – deterministische
Berechnungslaeufe (STEP 9, Code nicht KI).

STEP 10A §6/§7/§9/§11/§14:
- Jeder Lauf bindet `extraction_id` (Fakt-Quelle), `as_of_date` (PERSISTENTES,
  explizites Stichtags-Datum; „heutiges Datum" wird NIE in eine gespeicherte
  Berechnung substituiert) und `calculation_version`.
- `calculation_run.result_snapshot` (JSONB) = immutablable vollstaendige
  `ContractCalculationResult`; `calculation_result` = relationale Schlüssel +
  ggf. begrenzte JSONB-Bloecke je §7 (abfragbare Felder).
- Review-/Konflikt-/Erklaerungs-Zeilen relational (`calculation_review_flag`).
- Berechnung + Ergebnis + Flags werden atomar geschrieben (§14).
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
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

CALCULATION_STATUS_ALLOWED = {"computed", "failed", "partial"}
FLAG_SEVERITY_ALLOWED = {"info", "warning", "critical"}


class CalculationRun(OrgOwnedMixin, Base):
    """Ein deterministischer STEP-9-Berechnungs-Lauf (immutablable je Ergebnis)."""

    __tablename__ = "calculation_run"

    id: Mapped[uuid.UUID] = uuid_pk()
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="RESTRICT"),
        nullable=False,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    calculation_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    overall_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    result_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    review_flags: Mapped[list["CalculationReviewFlag"]] = relationship(
        back_populates="calculation_run",
        cascade="all, delete-orphan",
        order_by="CalculationReviewFlag.severity",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(CALCULATION_STATUS_ALLOWED))})",
            name="status",
        ),
        Index("ix_calculation_run_extraction_date", "extraction_id", "as_of_date"),
    )


class CalculationResult(OrgOwnedMixin, Base):
    """Berechnete Felder eines Runs (relationale Schlüssel + begrenzte JSONB-Bloecke)."""

    __tablename__ = "calculation_result"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calculation_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_calculation_result_run_id", "run_id"),
    )


class CalculationReviewFlag(OrgOwnedMixin, Base):
    """Review-/Konflikt-/Erklaerungs-Zeile eines Berechnungslaufs."""

    __tablename__ = "calculation_review_flag"

    id: Mapped[uuid.UUID] = uuid_pk()
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calculation_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    flag_key: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inputs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    calculation_run: Mapped["CalculationRun"] = relationship(back_populates="review_flags")

    __table_args__ = (
        CheckConstraint(
            f"severity IN ({', '.join(repr(v) for v in sorted(FLAG_SEVERITY_ALLOWED))})",
            name="severity",
        ),
        Index("ix_calculation_review_flag_run_id", "calculation_run_id"),
    )
