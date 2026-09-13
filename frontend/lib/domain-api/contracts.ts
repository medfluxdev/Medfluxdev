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

export function contractDocumentUrl(
  contractId: string,
  documentVersionId: string,
  organizationSlug: string,
) {
  return contentUrl(contractId, documentVersionId, organizationSlug);
}
