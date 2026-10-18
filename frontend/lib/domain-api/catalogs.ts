import type { ReminderLead } from "@/lib/domain-api/register";
import type { SectionKey } from "@/lib/contract-sections";
import { apiGet, apiPatch, apiPost } from "@/lib/api";

export interface PartnerDto {
  id: string;
  short_name: string;
  name1: string;
  name2: string | null;
  street: string | null;
  postal_code: string | null;
  city: string | null;
  country: string | null;
  po_box: string | null;
  po_box_postal_code: string | null;
  phone: string | null;
  fax: string | null;
  email: string | null;
  website: string | null;
  vat_id: string | null;
  industry_code: string | null;
  partner_type: string | null;
  note: string | null;
  is_active: boolean;
  display_name: string;
  updated_at: string | null;
  contract_count?: number;
  score?: number;
}

export type PartnerValues = Partial<Omit<PartnerDto, "id" | "display_name" | "updated_at" | "contract_count" | "score">>;

export interface ContractTypeDto {
  id: string;
  code: string;
  label: string;
  description: string | null;
  is_confidential: boolean;
  is_active: boolean;
  sort_order: number;
  retention_years: number | null;
  /** Typspezifische Abschnitte der Vertragsakte (wirksam) und ob der Standard nach Code gilt. */
  sections?: SectionKey[];
  sections_default?: boolean;
  /** Erinnerungs-Standard für Verträge dieses Typs ohne eigene Einstellung; null = Standard der Organisation. */
  reminder_leads?: ReminderLead[] | null;
  /** Eskalation X Tage vor dem Termin, wenn nicht erledigt; null = erst bei Überfälligkeit. */
  escalation_days_before?: number | null;
}

export interface ContractCategoryDto {
  id: string;
  code: string;
  label: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  contract_type_ids: string[];
}

export interface LookupDto {
  id: string;
  field_key: string;
  code: string;
  label: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface NumberRangeDto {
  purpose: string;
  prefix: string;
  padding: number;
  next_value: number;
  next_formatted: string;
  used_count: number;
  reserved: { value: number; formatted: string; note: string | null }[];
}

// Bezeichnungen liegen in lib/lookup-fields.ts (ohne API-Abhaengigkeit, auch fuer die Navigation).
export { LOOKUP_FIELD_LABEL } from "@/lib/lookup-fields";

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function listPartners(
  organizationSlug: string,
  options: { q?: string; includeInactive?: boolean; limit?: number; offset?: number } = {},
) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  if (options.q) params.set("q", options.q);
  if (options.includeInactive) params.set("include_inactive", "true");
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  return apiGet<{ total: number; items: PartnerDto[] }>(`/api/catalogs/partners?${params.toString()}`);
}

/** Angabe, die eine Vertragsanalyse für den verknüpften Vertragspartner belegt gefunden hat. */
export interface PartnerSuggestion {
  field: "email" | "phone" | "street" | "postal_code" | "city" | "country";
  label: string;
  value: string;
  /** Bisher beim Partner gepflegt (nur bei „abweichend“). */
  current: string | null;
  kind: "new" | "deviating";
  page: number | null;
  quote: string | null;
  contract_id: string;
  register_number: string | null;
  contract_label: string | null;
  /** In wie vielen Verträgen derselbe Wert steht. */
  sources: number;
}

export function getPartnerSuggestions(organizationSlug: string, partnerId: string, contractId?: string) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  if (contractId) params.set("contract_id", contractId);
  return apiGet<{ partner: { id: string; short_name: string }; items: PartnerSuggestion[]; can_apply: boolean }>(
    `/api/catalogs/partners/${encodeURIComponent(partnerId)}/suggestions?${params.toString()}`,
  );
}

export function applyPartnerSuggestion(organizationSlug: string, partnerId: string, item: Pick<PartnerSuggestion, "field" | "value">) {
  return apiPost<PartnerDto>(`/api/catalogs/partners/${encodeURIComponent(partnerId)}/suggestions/apply?${orgQuery(organizationSlug)}`, { field: item.field, value: item.value });
}

export function dismissPartnerSuggestion(organizationSlug: string, partnerId: string, item: Pick<PartnerSuggestion, "field" | "value">) {
  return apiPost<{ dismissed: boolean }>(`/api/catalogs/partners/${encodeURIComponent(partnerId)}/suggestions/dismiss?${orgQuery(organizationSlug)}`, { field: item.field, value: item.value });
}

export function getPartner(organizationSlug: string, partnerId: string) {
  return apiGet<PartnerDto & { contracts: { id: string; register_number: string | null; short_description: string | null; business_status: string }[] }>(
    `/api/catalogs/partners/${encodeURIComponent(partnerId)}?${orgQuery(organizationSlug)}`,
  );
}

export function createPartner(organizationSlug: string, values: PartnerValues, allowSimilar = false) {
  return apiPost<PartnerDto & { similar: PartnerDto[] }>(`/api/catalogs/partners?${orgQuery(organizationSlug)}`, {
    values,
    allow_similar: allowSimilar,
  });
}

export function updatePartner(organizationSlug: string, partnerId: string, values: PartnerValues) {
  return apiPatch<PartnerDto>(`/api/catalogs/partners/${encodeURIComponent(partnerId)}?${orgQuery(organizationSlug)}`, { values });
}

export function findSimilarPartners(organizationSlug: string, name: string) {
  const params = new URLSearchParams({ organization_slug: organizationSlug, name });
  return apiGet<{ items: PartnerDto[] }>(`/api/catalogs/partners/similar?${params.toString()}`);
}

export interface UnlinkedSupplier {
  supplier: string;
  contracts: number;
  contract_ids: string[];
  suggestions: (PartnerDto & { score?: number })[];
}

/** Arbeitsliste „Lieferanten zuordnen“: Lieferantennamen aus Verträgen ohne Vertragspartner. */
export function listUnlinkedSuppliers(organizationSlug: string) {
  return apiGet<{ items: UnlinkedSupplier[]; total_contracts: number }>(`/api/catalogs/partners/unlinked?${orgQuery(organizationSlug)}`);
}

export function linkSupplierToPartner(organizationSlug: string, supplier: string, partnerId: string) {
  return apiPost<{ linked: number; partner: PartnerDto }>(`/api/catalogs/partners/link-supplier?${orgQuery(organizationSlug)}`, { supplier, partner_id: partnerId });
}

export function listPartnerDuplicates(organizationSlug: string) {
  return apiGet<{ groups: PartnerDto[][] }>(`/api/catalogs/partners/duplicates?${orgQuery(organizationSlug)}`);
}

export function listContractTypes(organizationSlug: string) {
  return apiGet<{ contract_types: ContractTypeDto[]; contract_categories: ContractCategoryDto[] }>(
    `/api/catalogs/contract-types?${orgQuery(organizationSlug)}`,
  );
}

export function createContractType(organizationSlug: string, values: Partial<ContractTypeDto>) {
  return apiPost<ContractTypeDto>(`/api/catalogs/contract-types?${orgQuery(organizationSlug)}`, { values });
}

export function updateContractType(organizationSlug: string, typeId: string, values: Partial<ContractTypeDto>) {
  return apiPatch<ContractTypeDto>(`/api/catalogs/contract-types/${encodeURIComponent(typeId)}?${orgQuery(organizationSlug)}`, { values });
}

export function createContractCategory(organizationSlug: string, values: Partial<ContractCategoryDto>) {
  return apiPost<{ contract_types: ContractTypeDto[]; contract_categories: ContractCategoryDto[] }>(
    `/api/catalogs/contract-categories?${orgQuery(organizationSlug)}`,
    { values },
  );
}

export function updateContractCategory(organizationSlug: string, categoryId: string, values: Partial<ContractCategoryDto>) {
  return apiPatch<{ contract_types: ContractTypeDto[]; contract_categories: ContractCategoryDto[] }>(
    `/api/catalogs/contract-categories/${encodeURIComponent(categoryId)}?${orgQuery(organizationSlug)}`,
    { values },
  );
}

export function listLookups(organizationSlug: string, fieldKey?: string, includeInactive = false) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  if (fieldKey) params.set("field_key", fieldKey);
  if (includeInactive) params.set("include_inactive", "true");
  return apiGet<{ field_keys: string[]; items: LookupDto[] }>(`/api/catalogs/lookups?${params.toString()}`);
}

export function createLookup(organizationSlug: string, values: Partial<LookupDto>) {
  return apiPost<LookupDto>(`/api/catalogs/lookups?${orgQuery(organizationSlug)}`, { values });
}

export function updateLookup(organizationSlug: string, lookupId: string, values: Partial<LookupDto>) {
  return apiPatch<LookupDto>(`/api/catalogs/lookups/${encodeURIComponent(lookupId)}?${orgQuery(organizationSlug)}`, { values });
}

export function getNumberRange(organizationSlug: string) {
  return apiGet<NumberRangeDto>(`/api/catalogs/number-range?${orgQuery(organizationSlug)}`);
}

export function updateNumberRange(organizationSlug: string, payload: { prefix?: string; padding?: number; next_value?: number }) {
  return apiPatch<NumberRangeDto>(`/api/catalogs/number-range?${orgQuery(organizationSlug)}`, payload);
}

export function reserveNumbers(organizationSlug: string, values: number[], note?: string) {
  return apiPost<NumberRangeDto>(`/api/catalogs/number-range/reserve?${orgQuery(organizationSlug)}`, { values, note });
}

export function loadDefaultCatalogs(organizationSlug: string) {
  return apiPost<{ created: Record<string, number> }>(`/api/catalogs/defaults?${orgQuery(organizationSlug)}`, {});
}
