import { apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

export type FieldOrigin = "ai" | "manual" | "ai_confirmed" | "ai_corrected" | "imported_legacy" | "system";
export type BusinessStatus = "in_arbeit" | "gueltig" | "gekuendigt" | "beendet" | "geloescht";
export type TermModel = "fixed_term" | "terminable" | "terminable_min_term" | "auto_renewal" | "perpetual";
export type NoticeTo = "contract_end" | "month_end" | "quarter_end" | "half_year_end" | "year_end" | "anytime";
export type DurationUnit = "days" | "weeks" | "months" | "years";
export type RegisterValue = string | number | boolean | null;

export interface RegisterField {
  value: RegisterValue;
  label: string;
  group: "identity" | "organisation" | "term" | "reminder" | "termination";
  display: string | null;
  origin: FieldOrigin | null;
  source_field: string | null;
  extraction_id: string | null;
  ai_proposed_value: { value: RegisterValue; source_field: string | null } | null;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  updated_by_name: string | null;
  updated_at: string | null;
}

export interface RegisterTerms {
  status: "complete" | "incomplete" | "not_applicable";
  earliest_end: string | null;
  cancel_by: string | null;
  possible_end: string | null;
  actual_end: string | null;
  reminder_date: string | null;
  missing: string[];
  explanation: string[];
}

export interface PartnerSuggestion {
  id: string;
  short_name: string;
  name1: string;
  city: string | null;
  score: number;
}

export interface ContractRegister {
  contract_id: string;
  register_number: string | null;
  business_status: BusinessStatus;
  business_status_label: string;
  allowed_transitions: { target: BusinessStatus; label: string }[];
  supplier_text: string | null;
  has_ai_analysis: boolean;
  review_pending: boolean;
  ended_on: string | null;
  fields: Record<string, RegisterField>;
  terms: RegisterTerms;
  missing_for_valid: string[];
  as_of: string;
  partner_suggestions: PartnerSuggestion[];
  type_suggestion: { id: string; label: string; reason: string } | null;
  storage_location_label: string | null;
}

export interface ContractRemark {
  id: string;
  author_name: string | null;
  body: string;
  created_at: string | null;
}

export interface ContractHospitalLink {
  hospital_id: string;
  name: string;
  code: string;
  is_primary: boolean;
}

export const BUSINESS_STATUS_LABEL: Record<BusinessStatus, string> = {
  in_arbeit: "In Arbeit",
  gueltig: "Gültig",
  gekuendigt: "Gekündigt",
  beendet: "Beendet",
  geloescht: "Gelöscht",
};

export const TERM_MODEL_LABEL: Record<TermModel, string> = {
  fixed_term: "Feste Laufzeit",
  terminable: "Kündbarer Vertrag",
  terminable_min_term: "Kündbarer Vertrag mit Mindestlaufzeit",
  auto_renewal: "Automatische Verlängerung",
  perpetual: "Unbefristet (ohne Ende)",
};

export const NOTICE_TO_LABEL: Record<NoticeTo, string> = {
  contract_end: "zum Vertrags-/Periodenende",
  month_end: "zum Monatsende",
  quarter_end: "zum Quartalsende",
  half_year_end: "zum Halbjahresende",
  year_end: "zum Jahresende",
  anytime: "jederzeit",
};

export const DURATION_UNIT_LABEL: Record<DurationUnit, string> = {
  days: "Tag(e)",
  weeks: "Woche(n)",
  months: "Monat(e)",
  years: "Jahr(e)",
};

export const ORIGIN_LABEL: Record<FieldOrigin, string> = {
  ai: "KI-Vorschlag",
  manual: "Manuell",
  ai_confirmed: "KI · bestätigt",
  ai_corrected: "KI · korrigiert",
  imported_legacy: "Importiert",
  system: "System",
};

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

function contractPath(contractId: string, suffix: string, organizationSlug: string) {
  return `/api/contracts/${encodeURIComponent(contractId)}/${suffix}?${orgQuery(organizationSlug)}`;
}

export function getContractRegister(organizationSlug: string, contractId: string) {
  return apiGet<ContractRegister>(contractPath(contractId, "register", organizationSlug));
}

export function updateContractRegister(
  organizationSlug: string,
  contractId: string,
  payload: { changes: Record<string, RegisterValue>; confirm?: string[] },
) {
  return apiPatch<ContractRegister>(contractPath(contractId, "register", organizationSlug), {
    changes: payload.changes,
    confirm: payload.confirm ?? [],
  });
}

export function acceptRegisterProposal(organizationSlug: string, contractId: string, fieldKey: string) {
  return apiPost<ContractRegister>(
    contractPath(contractId, `register/proposals/${encodeURIComponent(fieldKey)}/accept`, organizationSlug),
    {},
  );
}

export function changeContractStatus(
  organizationSlug: string,
  contractId: string,
  payload: {
    target: BusinessStatus;
    effective_date?: string | null;
    terminated_on?: string | null;
    note?: string | null;
    acknowledge_unreviewed?: boolean;
  },
) {
  return apiPost<ContractRegister>(contractPath(contractId, "status", organizationSlug), payload);
}

export function createRegisterContract(
  organizationSlug: string,
  payload: { hospital_id?: string | null; values: Record<string, RegisterValue> },
) {
  return apiPost<ContractRegister>(`/api/contracts?${orgQuery(organizationSlug)}`, payload);
}

export function listContractRemarks(organizationSlug: string, contractId: string) {
  return apiGet<{ items: ContractRemark[] }>(contractPath(contractId, "remarks", organizationSlug));
}

export function addContractRemark(organizationSlug: string, contractId: string, body: string) {
  return apiPost<{ items: ContractRemark[] }>(contractPath(contractId, "remarks", organizationSlug), { body });
}

export function getContractHospitals(organizationSlug: string, contractId: string) {
  return apiGet<{ items: ContractHospitalLink[] }>(contractPath(contractId, "hospitals", organizationSlug));
}

export function updateContractHospitals(
  organizationSlug: string,
  contractId: string,
  payload: { hospital_ids: string[]; primary_hospital_id: string | null },
) {
  return apiPut<{ items: ContractHospitalLink[] }>(contractPath(contractId, "hospitals", organizationSlug), payload);
}
