import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from "@/lib/api";

export interface ContractDocumentDto {
  link_id: string;
  document_version_id: string;
  original_filename: string;
  title: string;
  attachment_type: string | null;
  role: string | null;
  is_main: boolean;
  is_valid: boolean;
  added_by_name: string | null;
  added_at: string | null;
  analyzable: boolean;
}

export interface RelatedContractDto {
  relation_id: string;
  contract_id: string;
  register_number: string | null;
  short_description: string | null;
  business_status: string | null;
  confirmed: boolean;
  rationale: string | null;
}

export interface ContractRelationsDto {
  is_framework: boolean;
  frameworks: RelatedContractDto[];
  members: RelatedContractDto[];
  framework_options: { contract_id: string; register_number: string | null; short_description: string | null }[];
}

export interface UploadResultDto {
  results: {
    original_filename: string;
    status: "attached" | "analyzed" | "analysis_failed" | "failed" | "rejected" | "duplicate";
    message: string | null;
    requires_review: boolean;
    document_version_id: string | null;
  }[];
  items: ContractDocumentDto[];
}

function path(contractId: string, suffix: string, organizationSlug: string) {
  return `/api/contracts/${encodeURIComponent(contractId)}/${suffix}?organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function listContractDocuments(organizationSlug: string, contractId: string) {
  return apiGet<{ items: ContractDocumentDto[]; attachment_types: string[] }>(path(contractId, "documents", organizationSlug));
}

export function uploadContractDocuments(
  organizationSlug: string,
  contractId: string,
  payload: { files: File[]; attachmentType: string; title?: string; analyze: boolean },
) {
  return apiUpload<UploadResultDto>(
    `/api/contracts/${encodeURIComponent(contractId)}/documents`,
    payload.files,
    organizationSlug,
    undefined,
    { attachment_type: payload.attachmentType, title: payload.title || null, analyze: payload.analyze ? "true" : "false" },
  );
}

export function updateContractDocument(
  organizationSlug: string,
  contractId: string,
  linkId: string,
  values: { attachment_type?: string; title?: string | null; is_main?: boolean; is_valid?: boolean },
) {
  return apiPatch<{ items: ContractDocumentDto[] }>(path(contractId, `documents/${encodeURIComponent(linkId)}`, organizationSlug), { values });
}

export function getContractRelations(organizationSlug: string, contractId: string) {
  return apiGet<ContractRelationsDto>(path(contractId, "relations", organizationSlug));
}

export function linkFramework(organizationSlug: string, contractId: string, frameworkContractId: string) {
  return apiPost<ContractRelationsDto>(path(contractId, "relations", organizationSlug), { framework_contract_id: frameworkContractId });
}

export function unlinkFramework(organizationSlug: string, contractId: string, relationId: string) {
  return apiDelete<ContractRelationsDto>(path(contractId, `relations/${encodeURIComponent(relationId)}`, organizationSlug));
}
