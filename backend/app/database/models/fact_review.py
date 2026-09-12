"""Fakt-Prüfung & Vertragsreview (Customer-Demo-Readiness).

`fact_review`  – Append-only, faktgenaue Prüf-Aktionen eines Menschen zu einem
                einzelnen materialen Vertragsfakt (BESTÄTIGT / KORRIGIERT /
                VERWORFEN / WIEDER GEÖFFNET). Zeilen sind IMMUTABLE.
`contract_review` – Ein aktueller Review-Status pro Vertrag (Nicht geprüft /
                In Prüfung / Geprüft / Änderung nach Prüfung). Eine explizite
                menschliche Abschluss-Aktion ist erforderlich; eine Änderung
                eines materialen Fakt nach Abschluss setzt den Status auf
                „Änderung nach Prüfung".

Identitäts-Provenienz (STEP 16 ist NICHT implementiert):
- `reviewer_display_name` = selbst angegebener Anzeigename (manuell, unverifiziert),
- `reviewer_identity_type` = "manual_unverified",
- `authenticated_actor_id`  = NULL (RBAC-bereit für spätere STEP-16-Anbindung).
Es wird KEINE authentifizierte/erfundene Mitarbeiter-Identität behauptet.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

FACT_REVIEW_ACTION_ALLOWED = {"confirmed", "corrected", "voided", "reopened"}

CONTRACT_REVIEW_STATUS_ALLOWED = {
    "unreviewed",
    "in_review",
    "reviewed",
    "changed_after_review",
    "manual_review_required",
}


class FactReview(Base):
    """Append-only Prüf-Aktion eines Menschen zu einem materialen Vertragsfakt."""

    __tablename__ = "fact_review"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Stabiler materialer Fakt-Key im `field_ref`-Stil, z. B. costs.monthly_net.
    fact_key: Mapped[str] = mapped_column(String(120), nullable=False)
    # confirmed | corrected | voided | reopened
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    # Vom System extrahierter/angezeigter Wert zum Zeitpunkt der Aktion.
    original_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Vorher wirksamer effektiver Wert (nach bisherigen Reviews) zum Zeitpunkt.
    previous_effective_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Neue effektiver Wert (bei corrected; sonst = original).
    new_effective_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Selbst angegebener (NICHT authentifizierter) Anzeigename des Prüfers.
    reviewer_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Provenienz der Identität: "manual_unverified" (bis STEP 16 immer).
    reviewer_identity_type: Mapped[str] = mapped_column(
        String(32), default="manual_unverified", nullable=False
    )
    # RBAC-bereit: NULL bis STEP 16 authentifizierte Akteure liefert.
    authenticated_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            f"action IN ({', '.join(repr(v) for v in sorted(FACT_REVIEW_ACTION_ALLOWED))})",
            name="action",
        ),
        Index("ix_fact_review_contract_key_created", "contract_id", "fact_key", "created_at"),
        Index("ix_fact_review_contract_created", "contract_id", "created_at"),
    )


class ContractReview(Base):
    """Aktueller menschlicher Review-Status eines Vertrags (ein Eintrag je Vertrag).

    Wird nur durch explizite menschliche Aktionen geschrieben (start/complete).
    Eine materiale Fakt-Änderung nach Abschluss setzt `status=changed_after_review`
    und vermeidet so ein irreführend grünes „Geprüft".
    """

    __tablename__ = "contract_review"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
    reviewer_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewer_identity_type: Mapped[str] = mapped_column(
        String(32), default="manual_unverified", nullable=False
    )
    authenticated_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # Zeitpunkt des letzten expliziten Prüf-Abschlusses (status='reviewed').
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Zeitpunkt einer nachträglichen materialen Änderung (changed_after_review).
    change_noted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(CONTRACT_REVIEW_STATUS_ALLOWED))})",
            name="status",
        ),
    )

    @property
    def is_material_reviewed(self) -> bool:
        return self.status == "reviewed" and self.reviewed_at is not None