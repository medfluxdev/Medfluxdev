import { apiGet, apiPatch, apiPost } from "@/lib/api";

export type RuleKind = "min_notice_months" | "max_term_months" | "max_renewal_months" | "max_price_increase_percent" | "max_annual_cost" | "required_field";
export type RuleOutcome = "pass" | "fail" | "unknown" | "na";

export interface ContractRuleDto {
  id: string;
  label: string;
  description: string | null;
  rule_kind: RuleKind;
  threshold: string | null;
  field_key: string | null;
  contract_type_ids: string[];
  is_active: boolean;
  sort_order: number;
  updated_at: string | null;
}

export interface RuleCatalog {
  items: ContractRuleDto[];
  kinds: { key: RuleKind; label: string; unit: string | null }[];
  required_fields: { key: string; label: string }[];
}

export interface ContractRuleResult {
  rule_id: string;
  label: string;
  outcome: RuleOutcome;
  detail: string;
}

export type RuleValues = Partial<Omit<ContractRuleDto, "id" | "updated_at" | "threshold">> & { threshold?: string | null };

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function listRules(organizationSlug: string) {
  return apiGet<RuleCatalog>(`/api/rules?${orgQuery(organizationSlug)}`);
}

export function createRule(organizationSlug: string, values: RuleValues) {
  return apiPost<ContractRuleDto>(`/api/rules?${orgQuery(organizationSlug)}`, { values });
}

export function updateRule(organizationSlug: string, ruleId: string, values: RuleValues) {
  return apiPatch<ContractRuleDto>(`/api/rules/${encodeURIComponent(ruleId)}?${orgQuery(organizationSlug)}`, { values });
}

export function getContractRules(organizationSlug: string, contractId: string) {
  return apiGet<{ status: string | null; items: ContractRuleResult[] }>(`/api/contracts/${encodeURIComponent(contractId)}/rules?${orgQuery(organizationSlug)}`);
}

export const RULE_OUTCOME_LABEL: Record<RuleOutcome, string> = {
  pass: "Erfüllt",
  fail: "Verletzt",
  unknown: "Angabe fehlt",
  na: "Gilt nicht",
};
