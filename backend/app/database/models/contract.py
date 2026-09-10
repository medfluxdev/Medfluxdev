"""contract, contract_document & contract_equipment – Vertrags-Aggregat (Current State).

STEP 10A §5/§6/§11/§13:
- `contract` = materialisierter Current-/Accepted-Zustand. `accepted_extraction_id`
  + `accepted_calculation_run_id` zeigen auf die akzeptierten Laeufe (Zeiger,
  keine Kopie – Provenienz bleibt intakt). Die denormalisierten Projektions-Felder
  (supplier, contract_number, start_date, end_date) sind Projektion/Current-State,
  KEINE Provenienz-Quelle (§20 Entsch. 1).
- TERMINATED-Regel (§11): `contract.status == TERMINATED` ist einzige privilegierte
  Quelle; kein Term-Evidence erfunden; abgelaufenes Ende → EXPIRED.
- `contract_document`: n:m-Zuordnung (future-safe Mehrdokument, kein
  „1 Vertrag = 1 PDF"-Zwang).
- Loesch-Lebenszyklus (§13): soft-delete via lifecycle_state, nie harte Loeschung.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

LIFECYCLE_STATE_ALLOWED = {
    "active",
    "orphan",
    "pending_deletion",
    "deleted",
}

CONTRACT_DOCUMENT_ROLE_ALLOWED = {
    "main",
    "amendment",
    "appendix",
    "renewal_letter",
    "price_adjustment",
    "sla_attachment",
    "unknown",
}


class Contract(OrgOwnedMixin, Base):
    """Aktueller akzeptierter Vertrag (Current State) mit Zeigern + Projektion."""

    __tablename__ = "contract"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Akzeptierte (aktuelle) Laeufe – Zeiger, keine Kopie.
    accepted_extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_calculation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calculation_run.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Projektions-/Current-Felder (nicht Provenienz-Quelle).
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    # STEP 13: stored generated tsvector (Determinismus – immer synchron mit
    # Current-State). Abgeleitet aus contract_number (simple) + supplier (german)
    # + status (simple). Keine Stemmung auf Kennungen. Fuer FTS-Abfragen.
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        Computed(
            "(setweight(to_tsvector('simple', coalesce(contract_number, '')), 'A') || ' ' || "
            "setweight(to_tsvector('german', coalesce(supplier, '')), 'B') || ' ' || "
            "setweight(to_tsvector('simple', coalesce(status, '')), 'C'))",
            persisted=True,
        ),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    # Loesch-Lebenszyklus (§13, soft-delete).
    lifecycle_state: Mapped[str] = mapped_column(
        String(24), default="active", nullable=False
    )
    deletion_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # PR-5: Nicht-destruktives Archivieren (reversibel). Archivierte Verträge
    # bleiben vollständig erhalten (Nachweise, Prüfungen, Audit, Geräte-
    # beziehungen) und sind dauerhaft wiederherstellbar; ein hartes Löschen ist
    # eine getrennte, stark berechtigte Operation.
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document_links: Mapped[list["ContractDocument"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractDocument.role",
    )

    __table_args__ = (
        CheckConstraint(
            f"lifecycle_state IN ({', '.join(repr(v) for v in sorted(LIFECYCLE_STATE_ALLOWED))})",
            name="lifecycle_state",
        ),
        Index("ix_contract_status", "status"),
        Index("ix_contract_risk_level", "risk_level"),
        Index("ix_contract_accepted_extraction_id", "accepted_extraction_id"),
        Index("ix_contract_org_is_archived", "organization_id", "is_archived"),
    )


class ContractDocument(OrgOwnedMixin, Base):
    """n:m-Zuordnung logischer Vertrag <-> Dokument(en) mit Rolle."""

    __tablename__ = "contract_document"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="document_links")

    __table_args__ = (
        CheckConstraint(
            f"role IS NULL OR role IN ({', '.join(repr(v) for v in sorted(CONTRACT_DOCUMENT_ROLE_ALLOWED))})",
            name="role",
        ),
        UniqueConstraint(
            "contract_id", "document_version_id", name="uq_contract_document_pair"
        ),
        Index("ix_contract_document_contract_id", "contract_id"),
        Index("ix_contract_document_version_id", "document_version_id"),
    )


class ContractEquipment(OrgOwnedMixin, Base):
    """Geräte des akzeptierten Vertrags (abfragbar).

    PR-4: Ausbau zur n:m-Relation Gerät<->Vertrag mit Provenienz/Qualität.
    - `equipment_id` -> kanonische `equipment`-Master-Identität (ein Gerät,
      mehrere Verträge); NULL, solange keine eindeutige Kennung vorliegt.
    - Bei den *Data*-Spalten bleibt die Extraktions-Sicht (unverändert), die
      Qualität wird deterministisch in Code abgeleitet (`identification_quality`,
      `relationship_quality`, `requires_review`).
    - `extraction_id` bindet jede Relations-Zeile an genau den Extraktionslauf,
      aus dem sie stammt. Der aktuelle Geräte-Snapshot ergibt sich ausschließlich
      über `Contract.accepted_extraction_id`; alte Zeilen bleiben Historie.
    - `field_ref`/`equipment_index` binden die Zeile innerhalb dieses Laufs an
      ihren Quellen-Nachweis (`ExtractionEvidence.field_ref`).
    """

    __tablename__ = "contract_equipment"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="RESTRICT"),
        nullable=False,
    )
    equipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
    )
    device_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    inventory_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    system_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    equipment_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    service_scope: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    coverage_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    coverage_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    included_services: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    excluded_services: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    sla_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    identification_quality: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown"
    )
    relationship_quality: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ambiguous"
    )
    requires_review: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    review_reasons: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # Provenienz -> ExtractionEvidence (Quell-Navigation, PR-2).
    field_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    equipment_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Stabiler semantischer Fingerprint je Vertrag. Er enthält bewusst NICHT
    # extraction_id, damit dieselbe logische Gerätebeziehung über Reanalysen
    # hinweg dieselbe Work-Queue-Identität behält.
    logical_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "extraction_id",
            "logical_fingerprint",
            name="uq_contract_equipment_contract_extraction_fingerprint",
        ),
        Index("ix_contract_equipment_contract_id", "contract_id"),
        Index("ix_contract_equipment_extraction_id", "extraction_id"),
        Index("ix_contract_equipment_equipment_id", "equipment_id"),
        Index("ix_contract_equipment_org_requires_review", "organization_id", "requires_review"),
    )
