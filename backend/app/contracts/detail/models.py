"""STEP 14 – Contract-Detail-Read-Model DTOs (READ-ONLY, org-gebunden).

Liefert die Detail-Ansicht eines Vertrags AUS DEN AKZEPTIERTEN Laeufen
(Current-/Accepted-Wahrheit). Enthaelt NUR Präsentations-/Provenienz-Daten:
keine raw-OCR, keine storage_keys, keine Dateisystempfade, keine Prompts/
Chain-of-Thought, keine Modell-Secrets, keine vollen Dokumente.

Evidence-/Provenienz-Policy:
- `EvidenceRef` bindet ein extrahiertes Feld an seine Quelle (Seite + begrenzter
  Snippet + Geometrie). Geometrie wird NIE erfunden.
- `precision` ist ehrlich ueber die Herkunft: extraction_evidence traegt nur
  Element-/Seiten-Ebene (paragraph/table/page) – niemals Word-/Line-Level. Daher
  ist die feinste ehrliche Stufe "coarse"; ohne bbox "none".
- `bbox` liegt in PDF-Punkten der Original-Seite (Ursprung oben links, y nach
  unten). `bbox_space="pdf_points"` deklariert das ehrlich; `normalized` nur
  fuer Alt-/Testdaten. Der Client normalisiert die Punkte gegen die echten
  Seitenmaße des gerenderten PDFs (pdfjs getViewport(scale=1)).
- `supports_exact_navigation == True` genau dann, wenn bbox UND Seite vorhanden
  sind (regional exakt lokaliserbar). Fehlt eines, wird KEINE Hervorhebung
  gezeichnet – nur Seiten-/Snippet-Navigation mit ehrlichem Hinweis.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EvidenceBbox(BaseModel):
    """Validierte Seite-Bounding-Box (roh aus Evidence, Seite-normalisiert-checkbar)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def is_finite(self) -> bool:
        return all(
            v is not None and v == v and v != float("inf") and v != float("-inf")
            for v in (self.x0, self.y0, self.x1, self.y1)
        )

    @property
    def is_ordered(self) -> bool:
        return self.x1 >= self.x0 and self.y1 >= self.y0

    @property
    def is_negative(self) -> bool:
        return min(self.x0, self.y0, self.x1, self.y1) < 0

    @property
    def is_normalized(self) -> bool:
        return self.is_finite and self.is_ordered and not self.is_negative and (
            self.x0 <= 1.0 and self.x1 <= 1.0 and self.y0 <= 1.0 and self.y1 <= 1.0
        )


class EvidenceRef(BaseModel):
    """Provenienz eines extrahierten Feldes (Quelle + Seite + Geometrie).

    PR-2: `bbox` traegt die rohe Quell-Geometrie (PDF-Punkte der Original-Seite,
    Ursprung oben links, y nach unten – siehe app/documents/geometry.py). Der
    Client normalisiert gegen die echten Seitenmaße des gerenderten PDFs.
    `bbox_space` deklariert diesen Raum ehrlich (`pdf_points`); `normalized`
    bleibt nur fuer Alt-Daten/migrierte Tests, die bereits [0,1]-Koordinaten
    liefern. `supports_exact_navigation` heisst damit: bbox + Seite vorhanden
    -> der Client DARF eine regionale Hervorhebung zeichnen (niemals erfunden).
    `precision` bleibt die ehrliche Herkunftsstufe: "coarse" = Element-/Seiten-
    Region (feinste ehrliche Ebene), "none" = keine Geometrie.
    """

    evidence_id: str
    merged_evidence_ids: list[str] = Field(default_factory=list)
    field_ref: str
    document_version_id: Optional[str] = None
    original_filename: Optional[str] = None
    page: Optional[int] = Field(default=None, ge=1)
    paragraph_index: Optional[int] = Field(default=None, ge=1)
    table_index: Optional[int] = Field(default=None, ge=1)
    source_type: Optional[str] = None
    snippet: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    requires_review: bool = False
    bbox: Optional[EvidenceBbox] = None
    precision: Literal["coarse", "none"] = "none"
    geometry_normalized: bool = False
    bbox_space: Literal["pdf_points", "normalized"] = "pdf_points"
    supports_exact_navigation: bool = False


class DetailField(BaseModel):
    """Ein Detail-Abschnitts-Feld mit Wert + Status + Provenienz-Refs."""

    value: object = None
    status: Optional[str] = None
    explanation: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)  # field_refs -> EvidenceRef


class MoneyValue(BaseModel):
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    explanation: Optional[str] = None


class ScheduledPriceDto(BaseModel):
    """Explizite Preisstufe (belegtes Vertragsjahr), nie annualisiert."""

    period_index: Optional[int] = None
    period_label: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    condition: Optional[str] = None


class VariableChargeDto(BaseModel):
    """Bedingte/verbrauchsabhaengige Position, nie zum Fixwert addiert."""

    label: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    unit_label_de: Optional[str] = None
    condition: Optional[str] = None
    note_de: Optional[str] = None


class CalcBasis(BaseModel):
    """Berechnungsgrundlage eines autoritativen berechneten Feldes.

    Stammt deterministisch aus dem akzeptierten STEP-9-Snapshot (explanation +
    inputs) – das Frontend rechnet nichts selbst und erfindet keine Grundlage.
    """

    explanation: Optional[str] = None
    inputs: dict = Field(default_factory=dict)


class RenewalBoundaryDto(BaseModel):
    period_index: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    kind: Optional[str] = None
    explanation: Optional[str] = None
    review_required: bool = False


class ContractDatesSection(BaseModel):
    start_date: Optional[date] = None
    start_date_status: Optional[str] = None
    # UAT Defect Batch A: ereignisbasierter Beginn (Textbedingung) + ggf.
    # manuell aufgelöstes (tatsächliches) Ereignis-Datum.
    start_condition: Optional[str] = None
    overridden_start_date: Optional[date] = None
    calculated_end_date: Optional[date] = None
    calculated_end_status: Optional[str] = None
    calculated_end_basis: CalcBasis = Field(default_factory=CalcBasis)
    latest_cancellation_date: Optional[date] = None
    latest_cancellation_status: Optional[str] = None
    latest_cancellation_basis: CalcBasis = Field(default_factory=CalcBasis)
    next_renewal_date: Optional[date] = None
    next_renewal_status: Optional[str] = None
    next_renewal_basis: CalcBasis = Field(default_factory=CalcBasis)
    automatic_renewal: Optional[bool] = None
    current_status: Optional[str] = None
    current_status_explanation: Optional[str] = None
    days_until_end: Optional[int] = None
    days_until_latest_cancellation: Optional[int] = None
    renewal_boundaries: list[RenewalBoundaryDto] = Field(default_factory=list)
    review_required: bool = False
    # UAT Re-Test: Zahlungsbeginn (ereignisbasierte Bedingung, z. B. „3 Monate
    # nach Ablauf der Gewährleistung") + Mindestvertragslaufzeit – wiederher-
    # gestellt aus dem persistierten Dokumenttext mit Quell-Navigation.
    payment_start_rule: Optional[str] = None
    payment_start_status: Optional[str] = None
    payment_start_evidence: Optional[str] = None
    minimum_duration_months: Optional[int] = None
    minimum_duration_evidence: Optional[str] = None
    # UAT Defect Batch A (Re-Test): wörtlich dokumentiertes Vertragsende
    # (deterministisch aus dem persistierten Dokumenttext) + Laufzeit in Jahren.
    documented_end_date: Optional[date] = None
    duration_years: Optional[int] = None
    # UAT Re-Test (Defect 1): kanonische Evidence-Feld-Refs je Datumsfakt, damit
    # die Contract-360-Anzeige exakt die belegte Quell-Seite (z. B. p5) nutzt
    # und nicht fälschlich dekorative Sammel-Refs (z. B. `termination.evidence`).
    start_date_evidence: Optional[str] = None
    documented_end_evidence: Optional[str] = None
    duration_evidence: Optional[str] = None
    auto_renewal_evidence: Optional[str] = None


class CostCategoryDto(BaseModel):
    key: str
    label: str
    currency: Optional[str] = None
    amount: Optional[Decimal] = None
    status: Optional[str] = None
    explanation: Optional[str] = None
    inputs: list[str] = Field(default_factory=list)


class TaxBreakdownDto(BaseModel):
    """Netto/Brutto-Aufteilung (deterministisch; nur bei verlässlicher Basis+Satz)."""

    computed: bool = False
    base_tax_basis: Optional[str] = None
    rate_percent: Optional[float] = None
    currency: Optional[str] = None
    monthly_net: Optional[Decimal] = None
    monthly_gross: Optional[Decimal] = None
    annual_net: Optional[Decimal] = None
    annual_gross: Optional[Decimal] = None
    monthly_tax: Optional[Decimal] = None
    annual_tax: Optional[Decimal] = None
    explanation: Optional[str] = None
    # UAT Re-Test: vertraglich direkt belegter Zahlen-Satz (Recovery aus dem
    # persistierten Dokumenttext). `source` ist eine verständliche deutsche
    # Herkunfts-Angabe; `evidence_field_refs` verweist auf die wiedergefundenen
    # Evidence-Refs fuer die Quell-Navigation je Betrag (montly_*/annual_*/
    # vat_rate).
    source: Optional[str] = None
    evidence_field_refs: dict[str, str] = Field(default_factory=dict)


class PriceDevelopmentDto(BaseModel):
    """Preisfixierungs-/Entwicklungs-Fakt (evidence-getragen)."""

    key: str
    label: str
    text: Optional[str] = None
    evidence_field_ref: Optional[str] = None
    status: Optional[str] = None
    # Deterministisch aus dem Fakten-Text geparste Fixpreis-Dauer (Jahre).
    period_years: Optional[int] = None


class CostAvailabilityFactDto(BaseModel):
    """Ein belegter Kosten-Baustein fuer die ehrliche Kosten-Erklaerung."""

    key: str
    label_de: str
    value: str
    period_hint: Optional[str] = None
    page: Optional[int] = None
    evidence_ref: Optional[str] = None


class CostAvailabilityDto(BaseModel):
    """UAT Defect Batch C: nachvollziehbare ErklIdzung, warum die jaehrlichen
    Kosten nicht automatisch stehen (kein versteckter Fehler, keine Erfindung)."""

    status: str = "no_amount_cited"
    summary_de: str = ""
    currency_known: bool = False
    found_facts: list[CostAvailabilityFactDto] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    manual_input_required: bool = False
    explanation_de: Optional[str] = None


class OverrideDto(BaseModel):
    """Aktuell wirksamer manueller Override zu einem Fakt (keine Secrets)."""

    key: str
    value: Optional[dict] = None
    note: Optional[str] = None
    created_at: Optional[str] = None
    is_development: bool = False
    # UAT Re-Test (Defect 4): deutsche Bezeichnung (kein roher interner Key).
    label_de: Optional[str] = None


class AuditEntryDto(BaseModel):
    """Append-only Audit-/Override-Historie (RBAC-bereit, keine erfundene Identität)."""

    id: str
    key: str
    action: str
    value: Optional[dict] = None
    fact_ref: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None
    is_development: bool = False
    actor_type: Optional[str] = None
    # Vorheriger effektiver Wert desselben Feldes (fuer set/void-Ueberblick).
    old_value: Optional[dict] = None
    # UAT Re-Test (Defect 4): deutsche Bezeichnung (kein roher interner Key).
    label_de: Optional[str] = None


class ContractCostsSection(BaseModel):
    annual_recurring: MoneyValue = Field(default_factory=MoneyValue)
    annual_recurring_basis: CalcBasis = Field(default_factory=CalcBasis)
    source_period: Optional[str] = None
    monthly_recurring: MoneyValue = Field(default_factory=MoneyValue)
    total_contract_value_status: Optional[str] = None
    currency_conflict: bool = False
    tax_basis: Optional[str] = None
    tax_rate_percent: Optional[float] = None
    category_totals: list[CostCategoryDto] = Field(default_factory=list)
    # UAT Defect Batch A:
    tax_breakdown: TaxBreakdownDto = Field(default_factory=TaxBreakdownDto)
    price_development: list[PriceDevelopmentDto] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # UAT Defect Batch C: ehrliche Kosten-Erklaerung, wenn KEIN verlaesslicher
    # Jahresbetrag vorliegt (z. B. Preise je Vertragsjahr, kein Einheitsbetrag).
    availability: Optional[CostAvailabilityDto] = None
    # UAT Round 2: belegter Preisplan (Staffel) + bedingte Positionen sichtbar
    # und ehrlich getrennt vom wiederkehrenden Fixwert.
    scheduled_prices: list[ScheduledPriceDto] = Field(default_factory=list)
    variable_charges: list[VariableChargeDto] = Field(default_factory=list)


class ScopeStatusItem(BaseModel):
    """Deterministisches Leistungs-Verdikt je Scope-Merkmal (UAT Re-Test
    Defect 2): included | excluded | mentioned | not_established.

    `page`/`snippet` belegen das Verdikt im Vertragstext; `evidence_ref`
    verweist ggf. auf den kanonischen Evidence-Eintrag fuer Quell-Navigation.
    """

    status: str = "not_established"
    page: Optional[int] = None
    snippet: Optional[str] = None
    evidence_ref: Optional[str] = None


class ContractScopeSection(BaseModel):
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
    # UAT Re-Test (Defect 2): transparente Drei-Stufen-Semantik je Merkmal.
    scope_status: dict[str, ScopeStatusItem] = Field(default_factory=dict)
    note_de: Optional[str] = None


class ContractSlaSection(BaseModel):
    response_time: Optional[str] = None
    resolution_time: Optional[str] = None
    service_hours: Optional[str] = None
    emergency_availability: Optional[str] = None
    availability_24_7: Optional[bool] = None
    sla_notes: Optional[str] = None


class ContractEquipmentItem(BaseModel):
    id: Optional[str] = None
    equipment_id: Optional[str] = None
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
    coverage_start: Optional[date] = None
    coverage_end: Optional[date] = None
    included_services: list[str] = Field(default_factory=list)
    excluded_services: list[str] = Field(default_factory=list)
    sla_notes: Optional[str] = None
    identification_quality: Optional[str] = None
    relationship_quality: Optional[str] = None
    requires_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    # Provenienz -> ExtractionEvidence (Quell-Navigation, PR-2/PR-4).
    field_ref: Optional[str] = None
    page: Optional[int] = None
    source_type: Optional[str] = None


class DetailWorkItem(BaseModel):
    work_item_id: str
    item_type: str
    severity: str
    status: str
    title_de: str
    why_de: Optional[str] = None
    action_hint_de: Optional[str] = None
    target_date: Optional[date] = None
    days_remaining: Optional[int] = None
    requires_review: bool = False
    source_warning_id: Optional[str] = None
    contract_equipment_id: Optional[str] = None
    equipment_id: Optional[str] = None


class DetailWarning(BaseModel):
    warning_type: str
    severity: str
    title_de: str
    target_kind: Optional[str] = None
    target_date: Optional[date] = None
    days_remaining: Optional[int] = None
    requires_action: bool = False
    requires_review: bool = False
    action_state: Optional[str] = None


class DetailDocument(BaseModel):
    document_version_id: str
    role: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    # Kann aktuell nur PDF sicher im Viewer anzeigen (kein DOCX-Gefälschte).
    viewer_supported: bool = False


class ReviewSection(BaseModel):
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    data_freshness: str = "none"
    warning_evaluation_as_of_date: Optional[date] = None


# ---------------------------------------------------------------------------
# Customer-Demo-Readiness: Import-Zustand, faktgenaue Prüfung, Vertragsreview
# ---------------------------------------------------------------------------


class ImportStateDto(BaseModel):
    """Ehrlicher Verarbeitungs-/Importzustand des Vertrags (failure-safe)."""

    import_state: str = "uploaded"  # uploaded | processing | analysis_ok | analysis_failed
    state_label_de: str = "Hochgeladen"
    document_version_id: Optional[str] = None
    can_retry: bool = False
    message: Optional[str] = None
    analysis_status: Optional[str] = None
    requires_review: bool = False


class FactReviewDto(BaseModel):
    """Eine historische, append-only Prüf-Aktion zu einem materialen Fakt."""

    id: str
    fact_key: str
    # UAT Defect Batch D: deutsche Bezeichnung in der Historie (kein roher Key).
    fact_label_de: str = ""
    is_critical: bool = False
    action: str  # confirmed | corrected | voided | reopened
    action_label_de: str
    original_value: object = None
    previous_effective_value: object = None
    new_effective_value: object = None
    reviewer_display_name: Optional[str] = None
    reviewer_identity_type: str = "manual_unverified"
    authenticated_actor_id: Optional[str] = None
    note: Optional[str] = None
    evidence_ref: Optional[str] = None
    created_at: Optional[str] = None


class LinkedEvidenceDto(BaseModel):
    """Evidenz-Beleg zu einem materialen Fakt (fuer Quell-Navigation)."""

    evidence_id: Optional[str] = None
    page: Optional[int] = None
    snippet: Optional[str] = None
    requires_review: bool = False
    supports_exact_navigation: bool = False


class FactReviewStateDto(BaseModel):
    """Aktueller Prüfzustand eines materialen Fakt (inkl. Original/Aktuell)."""

    fact_key: str
    label_de: str
    present: bool = False
    state: str = "unreviewed"  # unreviewed | needs_review | confirmed | corrected | voided
    state_label_de: str = "Nicht geprüft"
    original_value: object = None
    effective_value: object = None
    reviewer_display_name: Optional[str] = None
    reviewer_identity_type: Optional[str] = None
    reviewed_at: Optional[str] = None
    evidence_ref: Optional[str] = None
    has_history: bool = False
    reopen_note: Optional[str] = None
    # UAT Defect Batch E/F: Fakten-getragene Evidenz + Material-Relevanz.
    evidence_count: int = 0
    linked_evidence: list[LinkedEvidenceDto] = Field(default_factory=list)
    linked_evidence_refs: list[str] = Field(default_factory=list)
    needs_evidence: bool = False
    is_critical: bool = False


class ContractReviewDto(BaseModel):
    """Vertragsebene: Prüfstatus + Abschluss-Metadaten + Vollständigkeit."""

    status: str = "unreviewed"
    status_label_de: str = "Nicht geprüft"
    reviewer_display_name: Optional[str] = None
    reviewer_identity_type: str = "manual_unverified"
    authenticated_actor_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    changed_noted_at: Optional[str] = None
    completion_note: Optional[str] = None
    relevant_count: int = 0
    reviewed_count: int = 0
    unresolved_count: int = 0
    # UAT Defect Batch E: kritische (material-relevante) Angaben prominent in
    # der Vollstaendigkeits-Zaehlung.
    critical_count: int = 0
    critical_reviewed_count: int = 0
    critical_unreviewed_count: int = 0


class ContractDetailResponse(BaseModel):
    organization_slug: str
    contract_id: uuid.UUID
    is_archived: bool = False
    archived_at: Optional[str] = None
    contract_number: Optional[str] = None
    contract_title: Optional[str] = None
    supplier: str | None
    register_number: Optional[str] = None
    business_status: Optional[str] = None
    # Fristen und gepflegte Jahreskosten aus dem Register (Vorrang im Vertragskopf).
    register_facts: Optional[dict] = None
    # Laufzeit/Kuendigung aus der Extraktion als Anzeige-Text (Pruefung „Angaben“).
    extracted_terms: Optional[dict] = None
    # Organisationszuordnung als Namen (Krankenhaus, Abteilungen, Kostenstelle, Verantwortliche).
    assignment: Optional[dict] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None

    identity: dict = Field(default_factory=dict)
    dates: ContractDatesSection = Field(default_factory=ContractDatesSection)
    costs: ContractCostsSection = Field(default_factory=ContractCostsSection)
    scope: ContractScopeSection = Field(default_factory=ContractScopeSection)
    sla: ContractSlaSection = Field(default_factory=ContractSlaSection)
    equipment: list[ContractEquipmentItem] = Field(default_factory=list)

    review: ReviewSection = Field(default_factory=ReviewSection)
    warnings: list[DetailWarning] = Field(default_factory=list)
    work_items: list[DetailWorkItem] = Field(default_factory=list)
    documents: list[DetailDocument] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    # UAT Defect Batch A: wirksame manuelle Overrides + append-only Audit-Historie.
    overrides: list[OverrideDto] = Field(default_factory=list)
    audit_log: list[AuditEntryDto] = Field(default_factory=list)
    # Customer-Demo-Readiness: Importzustand + faktgenaue menschliche Prüfung.
    import_state: ImportStateDto = Field(default_factory=ImportStateDto)
    fact_review_states: list[FactReviewStateDto] = Field(default_factory=list)
    fact_reviews: list[FactReviewDto] = Field(default_factory=list)
    contract_review: ContractReviewDto = Field(default_factory=ContractReviewDto)
