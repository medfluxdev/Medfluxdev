import { apiGet } from "@/lib/api";
import type { DashboardOverview } from "@/lib/dashboard-types";

export function getDashboardOverview(organizationSlug: string, asOfDate?: string) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  if (asOfDate) params.set("as_of_date", asOfDate);
  return apiGet<DashboardOverview>(`/api/dashboard/overview?${params.toString()}`);
}
