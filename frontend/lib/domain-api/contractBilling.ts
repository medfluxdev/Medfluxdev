import { apiGet, apiPost } from "@/lib/api";

export interface BillingCharge {
  label: string;
  amount: string | number;
  currency: string;
  charge_type: string;
  condition: string | null;
  applicable: boolean | null;
}

export interface BillingBasisResponse {
  contract_id: string;
  available: boolean;
  items: BillingCharge[];
}

export interface BillingInvoiceLine {
  label: string;
  amount: string | number;
  currency: string;
  quantity?: string | number | null;
  unit?: string | null;
}

export interface BillingFinding {
  outcome: "matched" | "overbilled" | "underbilled" | "unknown" | string;
  invoice_label: string;
  invoice_amount: string | number;
  contract_amount: string | number | null;
  currency: string;
  explanation: string;
  requires_review: boolean;
}

export interface BillingReconciliationResponse {
  contract_id: string;
  billing_basis: BillingCharge[];
  findings: BillingFinding[];
  value_leakage: Record<string, string>;
  requires_review: boolean;
  message: string | null;
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getContractBillingBasis(organizationSlug: string, contractId: string) {
  return apiGet<BillingBasisResponse>(
    `/api/intelligence/billing/contracts/${encodeURIComponent(contractId)}/basis?${orgQuery(organizationSlug)}`,
  );
}

export function reconcileContractInvoice(
  organizationSlug: string,
  contractId: string,
  lines: BillingInvoiceLine[],
) {
  return apiPost<BillingReconciliationResponse>(
    `/api/intelligence/billing/contracts/${encodeURIComponent(contractId)}/reconcile?${orgQuery(organizationSlug)}`,
    { lines },
  );
}
