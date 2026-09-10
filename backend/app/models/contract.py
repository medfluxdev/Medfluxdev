"""Zentrale Vertrags-Datenmodelle für Medflux.

Hier ist der Unterschied zwischen EXTRACTED und CALCULATED Daten wichtig:
- EXTRACTED: direkt aus dem Vertragsdokument entnommen (KI/manuell).
- CALCULATED: später von Code bestimmt (Schritt 9), NICHT Teil des Extrakts.

Dieses Modul enthält NUR extrahierte/zu speichernde Daten.
Berechnete Felder (latest_cancellation_date, restliche Tage, Warnstufen)
sind bewusst NICHT enthalten.
"""

from __future__ import annotations

from typing import Optional, Any

from pydantic import BaseModel, Field

from app.models.enums import (
    BillingInterval,
    ContractStatus,
    ContractType,
    ExtractionStatus,
    ReviewFlag,
    ReviewStatus,
    RiskLevel,
    ValidationStatus,
)
from app.models.evidence import SourceEvidence
from app.models.values import Duration, FlexibleDate, Money, TimeValue


class ContractIdentity(BaseModel):
    """Identität eines Vertrags."""

    contract_title: Optional[str] = None
    contract_number: Optional[str] = None
    contract_type: ContractType = ContractType.UNKNOWN
    supplier: Optional[str] = None
    contractor: Optional[str] = None
    customer: Optional[str] = None
    contact_person: Optional[str] = None
    customer_number: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    evidence: Optional[SourceEvidence] = None


class Equipment(BaseModel):
    """Ein einzelnes Gerät/eine Anlage, das vom Vertrag abgedeckt wird.

    PR-4: um Identität/Abdeckung/Provenienz erweiterte Felder. `evidence`
    trägt den Quellen-Nachweis der Geräte-Zuordnung (Seite/Snippet/bbox),
    damit die PR-2-Quell-Navigation auch für einzelne Geräte belegt wird.
    Alle Felder sind optional – ungesicherte Identität wird in Code als
    `identification_quality` bewertet, nie erfunden.
    """

    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    inventory_number: Optional[str] = None
    system_name: Optional[str] = None
    equipment_category: Optional[str] = None
    equipment_type: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    service_scope: Optional[str] = None
    included_services: list[str] = Field(default_factory=list)
    excluded_services: list[str] = Field(default_factory=list)
    coverage_start: Optional[FlexibleDate] = None
    coverage_end: Optional[FlexibleDate] = None
    sla_notes: Optional[str] = None
    evidence: Optional[SourceEvidence] = None


class ContractDates(BaseModel):
    """Laufzeit- und Datumsangaben (explizit oder ereignisbasiert)."""

    start_date: Optional[FlexibleDate] = None
    end_date: Optional[FlexibleDate] = None
    duration: Optional[Duration] = None
    minimum_duration: Optional[Duration] = None
    start_condition: Optional[str] = None
    end_condition: Optional[str] = None
    evidence: Optional[SourceEvidence] = None


class Termination(BaseModel):
    """Kündigungsbedingungen (nur extrahiert, keine Berechnung)."""

    cancellation_period: Optional[Duration] = None
    cancellation_condition: Optional[str] = None
    cancellation_to_contract_end: Optional[str] = None
    automatic_renewal: Optional[bool] = None
    renewal_period: Optional[Duration] = None
    extraordinary_termination: Optional[str] = None
    evidence: Optional[SourceEvidence] = None


class ScheduledPrice(BaseModel):
    """Explizite Preisstufe fuer einen eindeutig benannten Vertragszeitraum.

    `period_index` ist 1-basiert (z. B. Vertragsjahr 1..4). Der Betrag wird
    niemals annualisiert oder mit bedingten Zusatzkosten vermischt.
    """

    period_index: Optional[int] = Field(default=None, ge=1)
    period_label: Optional[str] = None
    amount: Money
    condition: Optional[str] = None


class VariableCharge(BaseModel):
    """Bedingte/verbrauchsabhängige Preisposition, die nie blind addiert wird."""

    label: Optional[str] = None
    amount: Money
    unit: Optional[str] = None  # z. B. per_call, per_hour, per_device
    condition: Optional[str] = None


class Costs(BaseModel):
    """Kostenangaben. Einzelwerte als strukturierte Money-Objekte.

    Wiederkehrende Beträge tragen in `Money.period` ihre Bezugsperiode
    (monthly|quarterly|semi_annual|annual|once). Ein Mehrjahres-/Gesamtbetrag
    wird in `total_contract_value` geführt. `tax_basis` markiert die explizite
    Steuer-Basis (net/gross) NUR, wenn der Vertrag sie hergibt – nie erfunden.
    `tax_rate_percent` z. B. 19 für „pl. 19 % Mehrwertsteuer (netto)".
    """

    default_currency: Optional[str] = None
    total_contract_value: Optional[Money] = None
    annual_cost: Optional[Money] = None
    monthly_cost: Optional[Money] = None
    quarterly_cost: Optional[Money] = None
    semi_annual_cost: Optional[Money] = None
    one_time_cost: Optional[Money] = None
    setup_installation_cost: Optional[Money] = None
    maintenance_fee: Optional[Money] = None
    hourly_rate: Optional[Money] = None
    travel_cost: Optional[Money] = None
    material_cost: Optional[Money] = None
    spare_parts_cost: Optional[Money] = None
    additional_costs: Optional[Money] = None
    # Mehrstufige Preisplaene bleiben als einzelne, belegte Vertragsperioden
    # erhalten. Erst STEP 9 darf daraus unter strengen Vollstaendigkeitsregeln
    # einen Gesamtwert berechnen.
    scheduled_prices: list[ScheduledPrice] = Field(default_factory=list)
    # Verbrauchs-/ereignisabhaengige Positionen (z. B. "2.226 EUR pro Call")
    # werden separat modelliert und nie automatisch in den Fixwert addiert.
    variable_charges: list[VariableCharge] = Field(default_factory=list)
    discounts: Optional[Money] = None
    price_adjustment_clause: Optional[str] = None
    price_indexation: Optional[str] = None
    tax_basis: Optional[str] = None  # net|gross (nur explizit)
    tax_rate_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    evidence: Optional[SourceEvidence] = None


class Payment(BaseModel):
    """Zahlungsbedingungen."""

    payment_terms: Optional[str] = None
    payment_deadline_days: Optional[int] = Field(default=None, ge=0)
    billing_interval: BillingInterval = BillingInterval.OTHER
    advance_payment: Optional[Money] = None
    payment_notes: Optional[str] = None
    evidence: Optional[SourceEvidence] = None


class Services(BaseModel):
    """Leistungsumfang des Vertrags."""

    included_services: list[str] = Field(default_factory=list)
    excluded_services: list[str] = Field(default_factory=list)
    maintenance: Optional[bool] = None
    inspection: Optional[bool] = None
    repair: Optional[bool] = None
    calibration: Optional[bool] = None
    software_updates: Optional[bool] = None
    remote_support: Optional[bool] = None
    technical_support: Optional[bool] = None
    spare_parts_included: Optional[bool] = None
    consumables_included: Optional[bool] = None
    emergency_service: Optional[bool] = None
    evidence: Optional[SourceEvidence] = None


class SLA(BaseModel):
    """Service-Level (Antwort-/Auflösungszeiten, Servicezeiten)."""

    response_time: Optional[TimeValue] = None
    resolution_time: Optional[TimeValue] = None
    service_hours: Optional[TimeValue] = None
    emergency_availability: Optional[TimeValue] = None
    availability_24_7: Optional[bool] = None
    sla_notes: Optional[str] = None
    evidence: Optional[SourceEvidence] = None


class ReviewInfo(BaseModel):
    """Prüf- und Risikoinformationen.

    risk_level/risk_score werden später durch Code abgeleitet (Schritt 11).
    Hier werden nur Anhaltspunkte gespeichert.
    """

    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    requires_manual_review: bool = False
    review_reasons: list[ReviewFlag] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    risk_notes: Optional[str] = None


class AnalysisMetadata(BaseModel):
    """Metadata der lokalen KI-Analyse."""

    model_config = {"protected_namespaces": ()}

    model_name: Optional[str] = None
    analysis_timestamp: Optional[str] = None
    analysis_version: Optional[str] = None
    processing_duration: Optional[float] = Field(default=None, ge=0.0)
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    validation_status: ValidationStatus = ValidationStatus.UNKNOWN
    harness_version: Optional[str] = None
    harness: dict[str, Any] = Field(default_factory=dict)


class Contract(BaseModel):
    """Gesamtes extrahiertes Vertragsmodell.

    Enthält nur EXTRACTED Daten. Berechnete Felder folgen später (Schritt 9+).
    """

    # Fremde/erfundene Schlüssel (z. B. "parties", "terms", "fees") dürfen
    # nicht stillschweigend verworfen werden – sie führen zur Ablehnung und
    # (im Extractor) zu einem kontrollierten Retry (STEP 8B).
    model_config = {"extra": "forbid"}

    id: Optional[str] = None
    status: ContractStatus = ContractStatus.UNKNOWN

    identity: ContractIdentity = Field(default_factory=ContractIdentity)
    equipment: list[Equipment] = Field(default_factory=list)
    dates: ContractDates = Field(default_factory=ContractDates)
    termination: Termination = Field(default_factory=Termination)
    costs: Costs = Field(default_factory=Costs)
    payment: Payment = Field(default_factory=Payment)
    services: Services = Field(default_factory=Services)
    sla: SLA = Field(default_factory=SLA)
    review: ReviewInfo = Field(default_factory=ReviewInfo)
    analysis: AnalysisMetadata = Field(default_factory=AnalysisMetadata)
