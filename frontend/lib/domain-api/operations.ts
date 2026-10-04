import { apiDownload } from "@/lib/api";

export function downloadContractsCsv(
  organizationSlug: string,
  includeArchived = true,
) {
  const params = new URLSearchParams({
    organization_slug: organizationSlug,
    include_archived: String(includeArchived),
  });
  return apiDownload(`/api/operations/contracts.csv?${params.toString()}`, 60000);
}
