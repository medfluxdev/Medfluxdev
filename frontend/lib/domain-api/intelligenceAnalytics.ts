import { apiGet, apiPost } from "@/lib/api";

export interface RiskFinding {
  key: string;
  severity: string;
  explanation: string;
  evidence_refs: string[];
}

export interface ContractRiskAnalysis {
  contract_id: string;
  projected_risk_level: string | null;
  level: string;
  score: number | null;
  reasons: RiskFinding[];
  finding_count: number;
}

export interface TerminationScenario {
  contract_id: string;
  known: boolean;
  estimated_avoided_cost: string | number | null;
  reason: string;
  currency: string | null;
  basis: {
    termination_date: string;
    contract_end: string | null;
    annual_cost: string | number | null;
    annual_cost_status: string | null;
    annual_cost_inputs: Record<string, unknown>;
    contract_end_inputs: Record<string, unknown>;
  };
}

export interface AuthorityIssue {
  kind: string;
  relation_id: string | null;
  message: string;
  evidence_refs: string[];
}

export interface AuthorityDiagnostics {
  contract_id: string;
  relation_count: number;
  issue_count: number;
  issues: AuthorityIssue[];
}

export interface PortfolioMatch {
  contract_id: string;
  contract_number: string | null;
  supplier: string | null;
  status: string | null;
  risk_level: string | null;
  end_date: string | null;
}

export interface PortfolioQueryResult {
  answer: string;
  contract_ids: string[];
  evidence: unknown[];
  unknowns: string[];
  matches: PortfolioMatch[];
  source: "accepted_contract_state" | string;
}

export interface SupplierPerformanceItem {
  supplier: string;
  contract_count: number;
  total_obligations: number;
  breached_obligations: number;
  breach_rate: number | null;
  status_counts: Record<string, number>;
}

export interface SupplierPerformanceResponse {
  items: SupplierPerformanceItem[];
  total: number;
}

export interface InvoiceLineInput {
  label: string;
  amount: string | number;
  currency: string;
  quantity?: string | number | null;
  unit?: string | null;
}

export interface ContractChargeInput {
  label: string;
  amount: string | number;
  currency: string;
  charge_type: "fixed" | "scheduled" | "variable" | string;
  condition?: string | null;
  applicable?: boolean | null;
}

export interface InvoiceReconciliationFinding {
  outcome: string;
  invoice_label: string;
  invoice_amount: string | number;
  contract_amount: string | number | null;
  currency: string;
  explanation: string;
  requires_review: boolean;
}

export interface InvoiceReconciliationResult {
  findings: InvoiceReconciliationFinding[];
  value_leakage: Record<string, string>;
  persisted: boolean;
  requires_review: boolean;
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getContractRiskAnalysis(organizationSlug: string, contractId: string) {
  return apiGet<ContractRiskAnalysis>(
    `/api/intelligence/analytics/contracts/${encodeURIComponent(contractId)}/risk?${orgQuery(organizationSlug)}`,
  );
}

export function simulateContractTermination(
  organizationSlug: string,
  contractId: string,
  terminationDate: string,
) {
  return apiPost<TerminationScenario>(
    `/api/intelligence/analytics/contracts/${encodeURIComponent(contractId)}/termination-scenario?${orgQuery(organizationSlug)}`,
    { termination_date: terminationDate },
  );
}

export function getAuthorityDiagnostics(organizationSlug: string, contractId: string) {
  return apiGet<AuthorityDiagnostics>(
    `/api/intelligence/analytics/contracts/${encodeURIComponent(contractId)}/authority-diagnostics?${orgQuery(organizationSlug)}`,
  );
}

export function queryPortfolio(
  organizationSlug: string,
  payload: {
    query: string;
    supplier?: string | null;
    contract_ids?: string[];
    equipment_id?: string | null;
    as_of_date?: string | null;
  },
) {
  return apiPost<PortfolioQueryResult>(
    `/api/intelligence/analytics/portfolio/query?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function getSupplierPerformance(organizationSlug: string) {
  return apiGet<SupplierPerformanceResponse>(
    `/api/intelligence/analytics/suppliers/performance?${orgQuery(organizationSlug)}`,
  );
}

export function reconcileInvoice(
  organizationSlug: string,
  lines: InvoiceLineInput[],
  charges: ContractChargeInput[],
) {
  return apiPost<InvoiceReconciliationResult>(
    `/api/intelligence/analytics/invoices/reconcile?${orgQuery(organizationSlug)}`,
    { lines, charges },
  );
}

export function fingerprintClause(organizationSlug: string, text: string) {
  return apiPost<{ normalized_text: string; fingerprint: string }>(
    `/api/intelligence/analytics/clauses/fingerprint?${orgQuery(organizationSlug)}`,
    { text },
  );
}
