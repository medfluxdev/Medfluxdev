import { apiGet, apiPost, contentUrl } from "@/lib/api";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";
import type { ContractListResponse, ContractsQuery } from "@/lib/contract-types";

function appendValue(params: URLSearchParams, key: string, value: unknown) {
  if (value === null || value === undefined || value === "") return;
  if (Array.isArray(value)) {
    for (const item of value) params.append(key, String(item));
    return;
  }
  params.set(key, String(value));
}

export function listContracts(organizationSlug: string, query: Partial<ContractsQuery> = {}) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  for (const [key, value] of Object.entries(query)) appendValue(params, key, value);
  return apiGet<ContractListResponse>(`/api/contracts?${params.toString()}`);
}

export function getContract(contractId: string, organizationSlug: string) {
  return apiGet<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}?organization_slug=${encodeURIComponent(organizationSlug)}`,
  );
}

export function startContractReview(
  contractId: string,
  organizationSlug: string,
  payload: { note?: string | null },
) {
  return apiPost<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}/review/start?organization_slug=${encodeURIComponent(organizationSlug)}`,
    payload,
  );
}

export function completeContractReview(
  contractId: string,
  organizationSlug: string,
  payload: { note?: string | null; acknowledge_unreviewed?: boolean },
) {
  return apiPost<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}/review/complete?organization_slug=${encodeURIComponent(organizationSlug)}`,
    payload,
  );
}

export function reviewContractFact(
  contractId: string,
  organizationSlug: string,
  payload: {
    fact_key: string;
    action: "confirmed" | "corrected" | "voided" | "reopened";
    corrected_value?: unknown;
    system_value?: unknown;
    note?: string | null;
    evidence_ref?: string | null;
    /** Versionsstand; hat jemand die Angabe inzwischen geprüft, antwortet der Server mit 409. */
    expected_reviewed_at?: string | null;
  },
) {
  return apiPost<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}/fact-reviews?organization_slug=${encodeURIComponent(organizationSlug)}`,
    payload,
  );
}

export function setContractOverride(
  contractId: string,
  organizationSlug: string,
  payload: {
    key: string;
    action?: "set" | "void" | "confirm";
    value?: unknown;
    fact_ref?: string | null;
    note?: string | null;
  },
) {
  return apiPost<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}/overrides?organization_slug=${encodeURIComponent(organizationSlug)}`,
    payload,
  );
}

export function archiveContract(contractId: string, organizationSlug: string) {
  return apiPost<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}/archive?organization_slug=${encodeURIComponent(organizationSlug)}`,
    {},
  );
}

export function unarchiveContract(contractId: string, organizationSlug: string) {
  return apiPost<ContractDetailResponse>(
    `/api/contracts/${encodeURIComponent(contractId)}/unarchive?organization_slug=${encodeURIComponent(organizationSlug)}`,
    {},
  );
}


export type ContractDeletionCapabilities = {
  /** Löschung beantragen (Vertragsmanagement, Administration). */
  can_request?: boolean;
  /** Löschung bestätigen (Administration). */
  can_delete: boolean;
  can_restore: boolean;
  requires_confirmation: boolean;
};

export function getContractDeletionCapabilities(organizationSlug: string) {
  return apiGet<ContractDeletionCapabilities>(
    `/api/contracts/capabilities/deletion?organization_slug=${encodeURIComponent(organizationSlug)}`,
  );
}

export type ContractDeletionQueue = {
  items: Array<{
    contract_id: string;
    contract_number: string | null;
    register_number?: string | null;
    short_description?: string | null;
    lifecycle_state: "pending_deletion" | "deleted";
    /** Wer beantragt bzw. bestätigt hat. */
    by_name?: string | null;
    deleted_at?: string | null;
  }>;
  has_more: boolean;
  next_offset: number | null;
};

export function getContractDeletionQueue(organizationSlug: string, offset = 0) {
  const params = new URLSearchParams({ organization_slug: organizationSlug, offset: String(offset) });
  return apiGet<ContractDeletionQueue>("/api/contracts/deletion/queue?" + params.toString());
}

export type ContractDeletionReceipt = {
  contract_id: string;
  lifecycle_state: "pending_deletion" | "deleted" | "active";
};

// Destructive lifecycle transitions require server-side admin authorization
// and an explicit CONTRACTS_ALLOW_DELETE opt-in. UI capability checks are advisory.
export function requestContractDeletion(contractId: string, organizationSlug: string) {
  return apiPost<ContractDeletionReceipt>(
    `/api/contracts/${encodeURIComponent(contractId)}/delete/request?organization_slug=${encodeURIComponent(organizationSlug)}`, {},
  );
}

export function cancelContractDeletion(contractId: string, organizationSlug: string) {
  return apiPost<ContractDeletionReceipt>(
    `/api/contracts/${encodeURIComponent(contractId)}/delete/cancel?organization_slug=${encodeURIComponent(organizationSlug)}`, {},
  );
}

export function confirmContractDeletion(contractId: string, organizationSlug: string) {
  return apiPost<ContractDeletionReceipt>(
    `/api/contracts/${encodeURIComponent(contractId)}/delete/confirm?organization_slug=${encodeURIComponent(organizationSlug)}`, {},
  );
}

export function restoreDeletedContract(contractId: string, organizationSlug: string) {
  return apiPost<ContractDeletionReceipt>(
    `/api/contracts/${encodeURIComponent(contractId)}/delete/restore?organization_slug=${encodeURIComponent(organizationSlug)}`, {},
  );
}

export function contractDocumentUrl(
  contractId: string,
  documentVersionId: string,
  organizationSlug: string,
) {
  return contentUrl(contractId, documentVersionId, organizationSlug);
}
