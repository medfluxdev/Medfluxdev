import { apiGet } from "@/lib/api";

export interface ContractRelation {
  id: string;
  relation_type: string;
  source_contract_id: string | null;
  target_contract_id: string | null;
  authority: string | null;
  rationale: string | null;
  evidence_refs: string[];
  requires_review: boolean;
}

export interface ContractGraphResponse {
  contract_id: string;
  relations: ContractRelation[];
}

export interface ContractObligation {
  id: string;
  key: string;
  title: string;
  description: string | null;
  owner_role: string | null;
  status: string;
  due_date: string | null;
  recurrence: string | null;
  conditions: unknown[];
  source_field_refs: string[];
  evidence_refs: string[];
  requires_review: boolean;
}

export interface ContractObligationsResponse {
  contract_id: string;
  items: ContractObligation[];
}

export interface PolicyDecision {
  policy_key: string;
  policy_version: string;
  outcome: string;
  explanation: string | null;
  evidence_refs: string[];
  requires_review: boolean;
  evaluated_at: string | null;
}

export interface ContractPoliciesResponse {
  contract_id: string;
  items: PolicyDecision[];
}

export interface IntelligenceActionProposal {
  id: string;
  kind: string;
  reason: string | null;
  status: string;
  assignee_role: string | null;
  payload: Record<string, unknown>;
  evidence_refs: string[];
  requires_human_approval: boolean;
}

export interface ContractActionsResponse {
  contract_id: string;
  items: IntelligenceActionProposal[];
}

export interface IntelligenceEventItem {
  id: string;
  contract_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string | null;
  processed_at: string | null;
}

export interface IntelligenceEventsResponse {
  items: IntelligenceEventItem[];
}

function orgQuery(organizationSlug: string): string {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getContractGraph(organizationSlug: string, contractId: string) {
  return apiGet<ContractGraphResponse>(
    `/api/intelligence/contracts/${encodeURIComponent(contractId)}/graph?${orgQuery(organizationSlug)}`
  );
}

export function getContractObligations(organizationSlug: string, contractId: string) {
  return apiGet<ContractObligationsResponse>(
    `/api/intelligence/contracts/${encodeURIComponent(contractId)}/obligations?${orgQuery(organizationSlug)}`
  );
}

export function getContractPolicies(organizationSlug: string, contractId: string) {
  return apiGet<ContractPoliciesResponse>(
    `/api/intelligence/contracts/${encodeURIComponent(contractId)}/policies?${orgQuery(organizationSlug)}`
  );
}

export function getContractActionProposals(organizationSlug: string, contractId: string) {
  return apiGet<ContractActionsResponse>(
    `/api/intelligence/contracts/${encodeURIComponent(contractId)}/actions?${orgQuery(organizationSlug)}`
  );
}

export function listIntelligenceEvents(organizationSlug: string, limit = 100) {
  const params = new URLSearchParams({
    organization_slug: organizationSlug,
    limit: String(limit),
  });
  return apiGet<IntelligenceEventsResponse>(`/api/intelligence/events?${params.toString()}`);
}
