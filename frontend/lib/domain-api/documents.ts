import { apiPost, apiUpload, sourceRegionUrl } from "@/lib/api";
import type { ImportBatchResponse } from "@/lib/types";

export interface DocumentProcessResult {
  document_id: string | null;
  document_version_id: string | null;
  status: string;
  message: string | null;
  analysis_status: string | null;
  requires_review: boolean;
  contract_id: string | null;
}

export function importDocuments(files: File[], organizationSlug: string) {
  return apiUpload<ImportBatchResponse>("/api/documents/import", files, organizationSlug);
}

export function retryDocument(documentVersionId: string, organizationSlug: string) {
  return apiPost<DocumentProcessResult>(
    `/api/documents/${encodeURIComponent(documentVersionId)}/retry?organization_slug=${encodeURIComponent(organizationSlug)}`,
    {},
    30 * 60 * 1000,
  );
}

export function reanalyzeDocument(documentVersionId: string, organizationSlug: string) {
  return apiPost<DocumentProcessResult>(
    `/api/documents/${encodeURIComponent(documentVersionId)}/reanalyze?organization_slug=${encodeURIComponent(organizationSlug)}`,
    {},
    30 * 60 * 1000,
  );
}

export function buildSourceRegionUrl(
  documentVersionId: string,
  organizationSlug: string,
  snippet: string,
  page: number | null,
) {
  return sourceRegionUrl(documentVersionId, organizationSlug, snippet, page);
}
