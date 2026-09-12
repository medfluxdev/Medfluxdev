// TS-Abbild der STEP-14-Contract-Detail-DTOs (Backend app/contracts/detail).
// Read-Only-Anzeige der AKZEPTIERTEN Wahrheit + Provenienz. Enthaelt KEINE
// storage_keys, Dateisystempfade, raw-OCR-Koerper, Prompts o. ae.
// Alle Berechnungen/Fristen kommen autoritativ vom Backend; das Frontend
// rechnet NICHTS neu und erfindet keine Geometrie.

export interface EvidenceBbox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface EvidenceRef {
  evidence_id: string;
  field_ref: string | null;
  document_version_id: string | null;
  original_filename: string | null;
  page: number | null;
  paragraph_index: number | null;
  table_index: number | null;
  source_type: string | null;
  snippet: string | null;
  confidence: number | null;
  requires_review: boolean;
  bbox: EvidenceBbox | null;
  precision: "coarse" | "none";
  geometry_normalized: boolean;
  /** Raum der `bbox`-Koordinaten: echte Benchmark-Bboxes sind PDF-Punkte
   *  der Original-Seite (`pdf_points`); `normalized` nur fuer Alt-/Testdaten. */
  bbox_space: "pdf_points" | "normalized";
  supports_exact_navigation: boolean;
}

export interface DetailField {
  value: unknown;
  status: string | null;
  explanation: string | null;
  evidence: string[];
}

export interface MoneyValue {
  amount: string | null;
  currency: string | null;
  status: string | null;
  explanation: string | null;
}

/** Berechnungsgrundlage eines autoritativen berechneten Feldes (aus dem
 *  akzeptierten STEP-9-Snapshot). Frontend rechnet nichts selbst. */
export interface CalcBasis {
  explanation: string | null;
  inputs: Record<string, string>;
}

export interface RenewalBoundaryDto {
  period_index: number;
  start_date: string | null;
  end_date: string | null;
  kind: string | null;
  explanation: string | null;
  review_required: boolean;
}

export interface CostCategoryDto {
  key: string;
  label: string;
  currency: string | null;
  amount: string | null;
  status: string | null;
  explanation: string | null;
  inputs: string[];
}

/** Netto/Brutto-Aufteilung der wiederkehrenden Kosten (deterministisch). */
export interface TaxBreakdownDto {
  computed: boolean;
  base_tax_basis: string | null;
  rate_percent: number | null;
  currency: string | null;
  monthly_net: string | null;
  monthly_gross: string | null;
  annual_net: string | null;
  annual_gross: string | null;
  monthly_tax: string | null;
  annual_tax: string | null;
  explanation: string | null;
  /**
   * Vertraglich direkt belegte Herkunft (z. B. "Zahlen direkt aus der
   * Vertragszusammenfassung übernommen (Seite 7)."). Nur gesetzt, wenn der
   * Zahlen-Satz deterministisch aus dem persistierten Dokumenttext wieder-
   * hergestellt wurde (keine KI-Berechnung, keine Erfindung).
   */
  source: string | null;
  /**
   * Verweist je Betrag auf den EvidenceRef fuer die Quell-Navigation
   * (monthly_net/anual_net/vat_rate/monthly_vat/annual_vat/monthly_gross/
   * annual_gross -> field_ref in data.evidence).
   */
  evidence_field_refs: Record<string, string>;
}

export interface PriceDevelopmentDto {
  key: string;
  label: string;
  text: string | null;
  evidence_field_ref: string | null;
  status: string | null;
  /** Deterministisch aus dem Fakten-Text geparste Fixpreis-Dauer (Jahre). */
  period_years: number | null;
}

export interface OverrideDto {
  key: string;
  value: Record<string, unknown> | null;
  note: string | null;
  created_at: string | null;
  is_development: boolean;
  /** UAT Re-Test (Defect 4): deutsche Bezeichnung statt rohem Key. */
  label_de: string | null;
}

export interface AuditEntryDto {
  id: string;
  key: string;
  action: string;
  value: Record<string, unknown> | null;
  fact_ref: string | null;
  note: string | null;
  created_at: string | null;
  is_development: boolean;
  actor_type: string | null;
  /** Vorheriger effektiver Wert desselben Feldes (fuer set/void-Ueberblick). */
  old_value: Record<string, unknown> | null;
  /** UAT Re-Test (Defect 4): deutsche Bezeichnung statt rohem Key. */
  label_de: string | null;
}

export interface ContractDatesSection {
  start_date: string | null;
  start_date_status: string | null;
  /** Ereignisbasierter Beginn (z. B. "Übergabedatum") – kein erfundener Termin. */
  start_condition: string | null;
  /** Manuell aufgelöstes (tatsächliches) Ereignis-Datum nach Bestätigung/Override. */
  overridden_start_date: string | null;
  calculated_end_date: string | null;
  calculated_end_status: string | null;
  calculated_end_basis: CalcBasis;
  latest_cancellation_date: string | null;
  latest_cancellation_status: string | null;
  latest_cancellation_basis: CalcBasis;
  next_renewal_date: string | null;
  next_renewal_status: string | null;
  next_renewal_basis: CalcBasis;
  automatic_renewal: boolean | null;
  current_status: string | null;
  current_status_explanation: string | null;
  days_until_end: number | null;
  days_until_latest_cancellation: number | null;
  renewal_boundaries: RenewalBoundaryDto[];
  review_required: boolean;
  /**
   * UAT Re-Test: Zahlungsbeginn (ereignisbasierte Bedingung, z. B. "3 Monate
   * nach Ablauf der Gewährleistung") + Mindestvertragslaufzeit – wiederher-
   * gestellt aus dem persistierten Dokumenttext mit Quell-Navigation.
   */
  payment_start_rule: string | null;
  payment_start_status: string | null;
  payment_start_evidence: string | null;
  minimum_duration_months: number | null;
  minimum_duration_evidence: string | null;
  /** UAT Re-Test: wörtlich dokumentiertes Vertragsende + Laufzeit (Jahre). */
  documented_end_date: string | null;
  duration_years: number | null;
  /** UAT Re-Test: kanonische Quell-Refs der Laufzeitdaten (recovered). */
  start_date_evidence: string | null;
  documented_end_evidence: string | null;
  duration_evidence: string | null;
  auto_renewal_evidence: string | null;
}

export interface ContractCostsSection {
  annual_recurring: MoneyValue;
  annual_recurring_basis: CalcBasis;
  source_period: string | null;
  monthly_recurring: MoneyValue;
  total_contract_value_status: string | null;
  currency_conflict: boolean;
  tax_basis: string | null;
  tax_rate_percent: number | null;
  category_totals: CostCategoryDto[];
  tax_breakdown: TaxBreakdownDto;
  price_development: PriceDevelopmentDto[];
  notes: string[];
  /**
   * UAT Re-Test (Defect Batch C): ehrliche, nachvollziehbare Erklärung, warum
   * die jährlichen Kosten gerade nicht automatisch stehen – gesetzt, wenn kein
   * verlässlicher Jahresbetrag vorliegt (z. B. Preise je Vertragsjahr).
   */
  availability: CostAvailabilityDto | null;
}

/** Ein belegter Kosten-Baustein der ehrlichen Kosten-Erklärung. */
export interface CostAvailabilityFactDto {
  key: string;
  label_de: string;
  value: string;
  period_hint: string | null;
  page: number | null;
  /** field_ref in data.evidence für die Quell-Navigation. */
  evidence_ref: string | null;
}

export interface CostAvailabilityDto {
  status: string;
  summary_de: string;
  currency_known: boolean;
  found_facts: CostAvailabilityFactDto[];
  missing_inputs: string[];
  manual_input_required: boolean;
  explanation_de: string | null;
}

export interface ScopeStatusItem {
  status: "included" | "excluded" | "not_established" | string;
  page: number | null;
  snippet: string | null;
  evidence_ref: string | null;
}

export interface ContractScopeSection {
  included_services: string[];
  excluded_services: string[];
  maintenance: boolean | null;
  inspection: boolean | null;
  repair: boolean | null;
  calibration: boolean | null;
  software_updates: boolean | null;
  remote_support: boolean | null;
  technical_support: boolean | null;
  spare_parts_included: boolean | null;
  consumables_included: boolean | null;
  emergency_service: boolean | null;
  /** UAT Re-Test (Defect 2): Drei-Zustand-Semantik des Leistungsumfangs. */
  scope_status: Record<string, ScopeStatusItem> | null;
  note_de: string | null;
}

export interface ContractSlaSection {
  response_time: string | null;
  resolution_time: string | null;
  service_hours: string | null;
  emergency_availability: string | null;
  availability_24_7: boolean | null;
  sla_notes: string | null;
}

export interface ContractEquipmentItem {
  id: string;
  equipment_id: string | null;
  device_name: string | null;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  inventory_number: string | null;
  system_name: string | null;
  equipment_category: string | null;
  equipment_type: string | null;
  location: string | null;
  department: string | null;
  service_scope: string | null;
  coverage_start: string | null;
  coverage_end: string | null;
  included_services: string[];
  excluded_services: string[];
  sla_notes: string | null;
  identification_quality: string | null;
  relationship_quality: string | null;
  requires_review: boolean;
  review_reasons: string[];
  field_ref: string | null;
  page: number | null;
  source_type: string | null;
}

export interface DetailWorkItem {
  work_item_id: string;
  item_type: string;
  severity: string;
  status: string;
  title_de: string;
  why_de: string | null;
  action_hint_de: string | null;
  target_date: string | null;
  days_remaining: number | null;
  requires_review: boolean;
  source_warning_id: string | null;
  contract_equipment_id: string | null;
  equipment_id: string | null;
}

export interface DetailWarning {
  warning_type: string;
  severity: string;
  title_de: string;
  target_kind: string | null;
  target_date: string | null;
  days_remaining: number | null;
  requires_action: boolean;
  requires_review: boolean;
  action_state: string | null;
}

export interface DetailDocument {
  document_version_id: string;
  role: string | null;
  original_filename: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  viewer_supported: boolean;
}

export interface ReviewSection {
  requires_manual_review: boolean;
  review_reasons: string[];
  data_freshness: "current" | "stale" | "none";
  warning_evaluation_as_of_date: string | null;
}

export type ImportStateKind =
  | "uploaded"
  | "processing"
  | "analysis_ok"
  | "analysis_failed";

/** Ehrlicher Verarbeitungs-/Importzustand des Vertrags (failure-safe). */
export interface ImportStateDto {
  import_state: ImportStateKind | string;
  state_label_de: string;
  document_version_id: string | null;
  can_retry: boolean;
  message: string | null;
  analysis_status: string | null;
  requires_review: boolean;
}

export type FactReviewAction = "confirmed" | "corrected" | "voided" | "reopened";

/** Eine historische, append-only Prüf-Aktion zu einem materialen Fakt. */
export interface FactReviewDto {
  id: string;
  fact_key: string;
  /** UAT Re-Test: deutsche Bezeichnung in der Historie (kein roher Key). */
  fact_label_de: string;
  is_critical: boolean;
  action: FactReviewAction | string;
  action_label_de: string;
  original_value: unknown;
  previous_effective_value: unknown;
  new_effective_value: unknown;
  reviewer_display_name: string | null;
  reviewer_identity_type: string;
  authenticated_actor_id: string | null;
  note: string | null;
  evidence_ref: string | null;
  created_at: string | null;
}

/** Evidenz-Beleg zu einem materialen Fakt (für Quell-Navigation). */
export interface LinkedEvidenceDto {
  evidence_id: string | null;
  page: number | null;
  snippet: string | null;
  requires_review: boolean;
  supports_exact_navigation: boolean;
}

/** Aktueller Prüfzustand eines materialen Fakt (inkl. Original/Aktuell). */
export interface FactReviewStateDto {
  fact_key: string;
  label_de: string;
  present: boolean;
  state: "unreviewed" | "needs_review" | "confirmed" | "corrected" | "voided" | string;
  state_label_de: string;
  original_value: unknown;
  effective_value: unknown;
  reviewer_display_name: string | null;
  reviewer_identity_type: string | null;
  reviewed_at: string | null;
  evidence_ref: string | null;
  has_history: boolean;
  /** UAT Re-Test (Defect Batch F): Fakten-getragene Evidenz + Material-Relevanz. */
  evidence_count: number;
  linked_evidence: LinkedEvidenceDto[];
  linked_evidence_refs: string[];
  needs_evidence: boolean;
  is_critical: boolean;
}

/** Vertragsebene: Prüfstatus + Abschluss-Metadaten + Vollständigkeit. */
export interface ContractReviewDto {
  status: string;
  status_label_de: string;
  reviewer_display_name: string | null;
  reviewer_identity_type: string;
  authenticated_actor_id: string | null;
  reviewed_at: string | null;
  changed_noted_at: string | null;
  completion_note: string | null;
  relevant_count: number;
  reviewed_count: number;
  unresolved_count: number;
  /** UAT Re-Test (Defect Batch E): kritische, material-relevante Angaben. */
  critical_count: number;
  critical_reviewed_count: number;
  critical_unreviewed_count: number;
}

/** Anforderungs-Payload für POST /api/contracts/{id}/fact-reviews. */
export interface FactReviewRequest {
  fact_key: string;
  action: FactReviewAction;
  corrected_value?: unknown;
  system_value?: unknown;
  reviewer_display_name?: string | null;
  note?: string | null;
  evidence_ref?: string | null;
}

/** Anforderungs-Payload für POST .../review/start bzw. /review/complete. */
export interface ReviewLifecycleRequest {
  reviewer_display_name?: string | null;
  note?: string | null;
  acknowledge_unreviewed?: boolean;
}

export interface ContractDetailResponse {
  organization_slug: string;
  contract_id: string;
  is_archived: boolean;
  archived_at: string | null;
  contract_number: string | null;
  contract_title: string | null;
  supplier: string | null;
  status: string | null;
  risk_level: string | null;
  identity: Record<string, unknown>;
  dates: ContractDatesSection;
  costs: ContractCostsSection;
  scope: ContractScopeSection;
  sla: ContractSlaSection;
  equipment: ContractEquipmentItem[];
  review: ReviewSection;
  warnings: DetailWarning[];
  work_items: DetailWorkItem[];
  documents: DetailDocument[];
  evidence: EvidenceRef[];
  overrides: OverrideDto[];
  audit_log: AuditEntryDto[];
  /** Customer-Demo-Readiness: ehrlicher Importzustand + faktgenaue Prüfung. */
  import_state: ImportStateDto;
  fact_review_states: FactReviewStateDto[];
  fact_reviews: FactReviewDto[];
  contract_review: ContractReviewDto;
}

// Auswahl eines Quellen-Elements: navigiert den PDF-Viewer plus Overlay.
export interface SourceNavigationTarget {
  document_version_id: string | null;
  page: number | null;
  bbox: EvidenceBbox | null;
  bbox_space: "pdf_points" | "normalized";
  supports_exact_navigation: boolean;
  label: string;
  /** Verweis auf die Quellen-Evidenz (field_ref bspw. `termination.evidence`). */
  field_ref?: string | null;
  evidence_id?: string | null;
}

// Deutsche Abschnitts-/Gruppen-Bezeichnungen fuer den Contract-360-Workspace.
// Mapping von Evidence-Gruppen (Praefix des field_ref) auf die Fach-Sektion.
export const EVIDENCE_GROUP_TO_SECTION: Record<string, string> = {
  identity: "Vertragsidentität",
  dates: "Laufzeit",
  termination: "Laufzeit & Kündigung",
  costs: "Finanzielle Konditionen",
  payment: "Finanzielle Konditionen",
  services: "Leistungsumfang",
  sla: "Service-Level",
};

export function evidenceGroup(ref: EvidenceRef | null | undefined): string | null {
  const fr = ref?.field_ref;
  if (!fr) return null;
  return fr.split(".")[0] ?? null;
}

export function evidenceGroupLabel(group: string | null): string {
  return (group && EVIDENCE_GROUP_TO_SECTION[group]) || "Quelle";
}

export const STATUS_LABEL_DETAIL: Record<string, string> = {
  active: "Aktiv",
  expiring_soon: "Bald auslaufend",
  expired: "Ausgelaufen",
  terminated: "Gekündigt",
  unknown: "Unbekannt",
};

export const RISK_LABEL_DETAIL: Record<string, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  unknown: "Unbekannt",
};

export const SEVERITY_LABEL: Record<string, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  info: "Info",
};
