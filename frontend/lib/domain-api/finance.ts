import { apiDelete, apiDownload, apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

export type FinanceDirection = "expense" | "income";
export type FinanceInterval = "monthly" | "quarterly" | "semi_annual" | "annual" | "once";
export type PaymentTiming = "in_advance" | "in_arrears";

export const PAYMENT_TIMING_LABEL: Record<PaymentTiming, string> = {
  in_advance: "im Voraus",
  in_arrears: "nachträglich",
};

export interface FinanceEntryDto {
  id: string;
  direction: FinanceDirection;
  label: string;
  cost_type_code: string | null;
  amount: string;
  amount_basis: "net" | "gross";
  vat_rate: string;
  currency: string;
  interval: FinanceInterval;
  valid_from: string;
  valid_to: string | null;
  apply_price_adjustment: boolean;
  payment_timing: PaymentTiming | null;
  payment_reminder: boolean;
  note: string | null;
  origin: "manual" | "ai_confirmed" | "imported_legacy";
  source_key: string | null;
  created_by_name: string | null;
}

export interface ServiceItemDto {
  id: string;
  label: string;
  service_kind: string | null;
  amount: string | null;
  unit: string | null;
  plus_vat: boolean;
  currency: string;
  valid_from: string | null;
  valid_to: string | null;
  note: string | null;
  origin: string;
  source_key: string | null;
}

export interface Money2 { net: string; gross: string }

export interface DirectionSummaryDto {
  current_year: Money2;
  to_date: Money2;
  remaining_to_end: Money2 | null;
  total_term: Money2 | null;
  annual_run_rate: Money2;
}

export interface FinanceSummaryDto {
  currency: string;
  expense: DirectionSummaryDto;
  income: DirectionSummaryDto;
  contract_end: string | null;
  projected_adjustment: boolean;
  notes: string[];
}

export interface AllocationDto {
  cost_center_id: string;
  code: string;
  name: string;
  share_percent: string;
  recharge_mode: string | null;
  annual_net: string | null;
}

export interface SuggestionDto {
  key: string;
  values: Record<string, string | boolean | null>;
  assumptions?: string[];
  source_field: string;
}

export interface FinanceDto {
  contract_id: string;
  as_of: string;
  entries: FinanceEntryDto[];
  summaries: FinanceSummaryDto[];
  services: ServiceItemDto[];
  allocations: AllocationDto[];
  primary_cost_center_id: string | null;
  price_adjustment: { kind: string | null; percent: string | null; index_name: string | null; next_date: string | null; interval_months: number | null };
  suggestions: { entries: SuggestionDto[]; services: SuggestionDto[] };
}

export const INTERVAL_LABEL: Record<FinanceInterval, string> = {
  monthly: "monatlich",
  quarterly: "quartalsweise",
  semi_annual: "halbjährlich",
  annual: "jährlich",
  once: "einmalig",
};

export const PRICE_ADJUSTMENT_LABEL: Record<string, string> = {
  fixed: "Festpreis",
  percent: "Prozentual",
  index: "Nach Index",
  negotiation: "Nach Verhandlung",
};

function base(contractId: string, suffix: string, organizationSlug: string) {
  return `/api/contracts/${encodeURIComponent(contractId)}/finance${suffix}?organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getFinance(organizationSlug: string, contractId: string) {
  return apiGet<FinanceDto>(base(contractId, "", organizationSlug));
}

export function createFinanceEntry(organizationSlug: string, contractId: string, values: Record<string, unknown>) {
  return apiPost<FinanceDto>(base(contractId, "/entries", organizationSlug), { values });
}

export function updateFinanceEntry(organizationSlug: string, contractId: string, entryId: string, values: Record<string, unknown>) {
  return apiPatch<FinanceDto>(base(contractId, `/entries/${encodeURIComponent(entryId)}`, organizationSlug), { values });
}

export function deleteFinanceEntry(organizationSlug: string, contractId: string, entryId: string) {
  return apiDelete<FinanceDto>(base(contractId, `/entries/${encodeURIComponent(entryId)}`, organizationSlug));
}

export function createServiceItem(organizationSlug: string, contractId: string, values: Record<string, unknown>) {
  return apiPost<FinanceDto>(base(contractId, "/services", organizationSlug), { values });
}

export function deleteServiceItem(organizationSlug: string, contractId: string, serviceId: string) {
  return apiDelete<FinanceDto>(base(contractId, `/services/${encodeURIComponent(serviceId)}`, organizationSlug));
}

export function setCostAllocations(organizationSlug: string, contractId: string, items: { cost_center_id: string; share_percent: string; recharge_mode?: string | null }[]) {
  return apiPut<FinanceDto>(base(contractId, "/allocations", organizationSlug), { items });
}

export function acceptFinanceSuggestion(organizationSlug: string, contractId: string, scope: "finance" | "service", key: string, values: Record<string, unknown> = {}) {
  return apiPost<FinanceDto>(base(contractId, `/suggestions/${scope}/${encodeURIComponent(key)}/accept`, organizationSlug), { values });
}

export function dismissFinanceSuggestion(organizationSlug: string, contractId: string, scope: "finance" | "service", key: string) {
  return apiPost<FinanceDto>(base(contractId, `/suggestions/${scope}/${encodeURIComponent(key)}/dismiss`, organizationSlug), {});
}

export function downloadFinanceCsv(organizationSlug: string, contractId: string, options: { expenses: boolean; income: boolean }) {
  const params = new URLSearchParams({ organization_slug: organizationSlug, expenses: String(options.expenses), income: String(options.income) });
  return apiDownload(`/api/contracts/${encodeURIComponent(contractId)}/finance/export.csv?${params.toString()}`);
}
