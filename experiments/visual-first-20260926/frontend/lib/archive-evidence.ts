import { apiGet } from "@/lib/api";

export type ArchiveEvidenceHit = {
  document_id: string;
  revision: string;
  page: number;
  field: string;
  label: string;
  value: string;
  source_quote: string;
  source_sha256: string;
};

export type ArchiveEvidenceResponse = {
  items: ArchiveEvidenceHit[];
  indexed_sources: number;
  experimental: true;
};

export function searchArchiveEvidence(
  organizationSlug: string,
  query: string,
  signal?: AbortSignal
): Promise<ArchiveEvidenceResponse> {
  const params = new URLSearchParams({
    organization_slug: organizationSlug,
    q: query.trim(),
    limit: "20",
  });
  return apiGet<ArchiveEvidenceResponse>(
    `/api/contracts/archive-evidence/search?${params.toString()}`,
    signal,
    45_000
  );
}
