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
from decimal import Decimal
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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

CONTRACT_SCOPE_ALLOWED = {"organization", "hospital", "department"}

BUSINESS_STATUS_ALLOWED = ("in_arbeit", "gueltig", "gekuendigt", "beendet", "geloescht")
TERM_MODEL_ALLOWED = ("fixed_term", "terminable", "terminable_min_term", "auto_renewal", "perpetual")
NOTICE_TO_ALLOWED = ("contract_end", "month_end", "quarter_end", "half_year_end", "year_end", "anytime")
DURATION_UNITS_ALLOWED = ("days", "weeks", "months", "years")
PRICE_ADJUSTMENT_ALLOWED = ("fixed", "percent", "index", "negotiation")

# H1: Registernummer + Kurzbeschreibung sind Teil der Volltextsuche.
SEARCH_VECTOR_EXPRESSION = (
    "(setweight(to_tsvector('simple', coalesce(contract_number, '')), 'A') || ' ' || "
    "setweight(to_tsvector('simple', coalesce(register_number, '')), 'A') || ' ' || "
    "setweight(to_tsvector('german', coalesce(supplier, '')), 'B') || ' ' || "
    "setweight(to_tsvector('german', coalesce(short_description, '')), 'B') || ' ' || "
    "setweight(to_tsvector('simple', coalesce(status, '')), 'C'))"
)

# Erfassungsart aus dem Import-Assistenten (NULL = vor dem Assistenten importiert).
INTAKE_MODE_ALLOWED = ("ai_human_review", "ai_direct", "manual")

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
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hospital.id", ondelete="SET NULL"), nullable=True
    )
    cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True
    )
    responsible_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="organization", server_default="organization"
    )
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
    # Risiko: berechnet aus den aktiven Warnungen; eine Person kann es bestaetigen oder mit
    # Begruendung festlegen (`risk_level` = festgelegt, sonst berechnet).
    risk_computed: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    risk_override: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    risk_override_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    risk_override_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_override_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_confirmed_level: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    risk_confirmed_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # STEP 13: stored generated tsvector (Determinismus – immer synchron mit
    # Current-State). Abgeleitet aus contract_number (simple) + supplier (german)
    # + status (simple). Keine Stemmung auf Kennungen. Fuer FTS-Abfragen.
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        Computed(
            SEARCH_VECTOR_EXPRESSION,
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

    # Vertragsregister (H1): editierbare Stammdaten unabhaengig von der KI.
    # Herkunft je Feld in `contract_field_provenance`; die Projektionsfelder
    # oben (supplier, contract_number, start_date, end_date, status) bleiben
    # reine KI-Projektion.
    register_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    internal_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    subject_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_framework: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    manual_billing: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    account_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    partner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_partner.id", ondelete="SET NULL"), nullable=True
    )
    contract_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("catalog_contract_type.id", ondelete="SET NULL"), nullable=True
    )
    contract_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("catalog_contract_category.id", ondelete="SET NULL"), nullable=True
    )
    storage_location_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    business_status: Mapped[str] = mapped_column(
        String(24), default="in_arbeit", server_default="in_arbeit", nullable=False
    )
    term_model: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    term_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    term_fixed_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    initial_term_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    initial_term_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    minimum_term_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minimum_term_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    notice_period_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notice_period_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    notice_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    renewal_period_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    renewal_period_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    reminder_lead_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Weitere Erinnerungen vor Kündigungstermin/Vertragsende, z. B. [{"value": 2, "unit": "weeks"}].
    reminder_extra_leads: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    reminder_recipient_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    escalation_recipient_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    # Frueher ToDo je Vertrag; seit 2026-10-15 gehoert "Was zu tun ist" zum Termin (contract_deadline.overrides). Nur noch gelesen.
    reminder_todo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Eskalationsregel: X Tage vor dem Termin, wenn nicht erledigt (NULL = Standard des Vertragstyps bzw. erst bei Ueberfaelligkeit).
    escalation_days_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    terminated_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    terminated_effective: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ended_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retention_years_after_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # H8 Vertraulichkeit (Sichtbarkeit nur Admin, Verantwortliche, Freigaben)
    # und Datenschutzbezug (AVV); H9 nutzt retention_years_after_end.
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    data_protection_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # H4.3 Preisanpassung (strukturiert; Projektion rechnet Code).
    price_adjustment_kind: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    price_adjustment_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    price_adjustment_index_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    price_adjustment_next_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    price_adjustment_interval_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Wartungstermine (Systemtermin "maintenance_due", Folgetermine im Intervall).
    maintenance_interval_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    maintenance_next_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Leistungen & SLA (von Hand gepflegt; die KI-Angaben zu Leistungsumfang/SLA bleiben in der Extraktion).
    service_scope_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sla_availability_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    penalty_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intake_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Zwischenspeicher der gepflegten Jahreskosten (netto) fuer Sortierung/Filter
    # der Vertragsliste; Quelle bleibt die Finanz-Engine.
    maintained_annual_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    maintained_annual_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    maintained_cost_as_of: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

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
        CheckConstraint(
            f"scope_type IN ({', '.join(repr(v) for v in sorted(CONTRACT_SCOPE_ALLOWED))})",
            name="scope_type",
        ),
        CheckConstraint(
            f"business_status IN ({', '.join(repr(v) for v in BUSINESS_STATUS_ALLOWED)})",
            name="business_status",
        ),
        Index("ix_contract_org_maintained_cost", "organization_id", "maintained_annual_cost"),
        CheckConstraint(
            f"term_model IS NULL OR term_model IN ({', '.join(repr(v) for v in TERM_MODEL_ALLOWED)})",
            name="term_model",
        ),
        CheckConstraint(
            f"notice_to IS NULL OR notice_to IN ({', '.join(repr(v) for v in NOTICE_TO_ALLOWED)})",
            name="notice_to",
        ),
        CheckConstraint(
            f"price_adjustment_kind IS NULL OR price_adjustment_kind IN ({', '.join(repr(v) for v in PRICE_ADJUSTMENT_ALLOWED)})",
            name="price_adjustment_kind",
        ),
        CheckConstraint(
            "maintenance_interval_months IS NULL OR (maintenance_interval_months >= 1 AND maintenance_interval_months <= 120)",
            name="maintenance_interval_months",
        ),
        CheckConstraint(
            f"intake_mode IS NULL OR intake_mode IN ({', '.join(repr(v) for v in INTAKE_MODE_ALLOWED)})",
            name="intake_mode",
        ),
        Index(
            "uq_contract_org_register_number",
            "organization_id",
            "register_number",
            unique=True,
            postgresql_where=text("register_number IS NOT NULL"),
        ),
        Index("ix_contract_org_business_status", "organization_id", "business_status"),
        Index("ix_contract_partner_id", "partner_id"),
        Index("ix_contract_status", "status"),
        Index("ix_contract_risk_level", "risk_level"),
        Index("ix_contract_accepted_extraction_id", "accepted_extraction_id"),
        Index("ix_contract_org_is_archived", "organization_id", "is_archived"),
        Index("ix_contract_org_hospital", "organization_id", "hospital_id"),
        Index("ix_contract_org_cost_center", "organization_id", "cost_center_id"),
        Index("ix_contract_responsible_account", "responsible_account_id"),
    )


class ContractDocumentRemoved(OrgOwnedMixin, Base):
    """Aus einem Vertrag entferntes Dokument (Prüfpfad, wiederherstellbar).

    Die Datei und ihre Versionen bleiben erhalten; nur die Zuordnung zum Vertrag
    ist aufgehoben. Beim Wiederherstellen entsteht die Zuordnung neu.
    """

    __tablename__ = "contract_document_removed"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="RESTRICT", name="fk_contract_document_removed_document_version"), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    attachment_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    added_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    added_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    removed_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


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
    # H3: fachliche Dokumentart (Auswahlliste `attachment_type`), Bezeichnung,
    # Hauptdokument- und Gueltigkeitskennzeichen.
    attachment_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    added_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="document_links")

    __table_args__ = (
        CheckConstraint(
            f"role IS NULL OR role IN ({', '.join(repr(v) for v in sorted(CONTRACT_DOCUMENT_ROLE_ALLOWED))})",
            name="role",
        ),
        UniqueConstraint(
            "contract_id", "document_version_id", name="uq_contract_document_pair"
        ),
        Index(
            "uq_contract_document_one_main",
            "contract_id",
            unique=True,
            postgresql_where=text("is_main"),
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
    # Unique per source-backed coverage/physical occurrence within one run.
    # Logical fingerprint remains for cross-reanalysis semantic lineage.
    occurrence_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "extraction_id",
            "occurrence_fingerprint",
            name="uq_contract_equipment_contract_extraction_occurrence",
        ),
        Index("ix_contract_equipment_contract_id", "contract_id"),
        Index("ix_contract_equipment_extraction_id", "extraction_id"),
        Index("ix_contract_equipment_equipment_id", "equipment_id"),
        Index("ix_contract_equipment_org_requires_review", "organization_id", "requires_review"),
    )
