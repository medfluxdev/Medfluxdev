import { apiGet } from "@/lib/api";

export interface PortfolioReport {
  contracts: {
    total: number;
    active: number;
    archived: number;
    by_risk: Record<string, number>;
  };
  work_queue: {
    by_status: Record<string, number>;
    by_severity: Record<string, number>;
  };
  scope: {
    hospital_id: string | null;
    department_id: string | null;
  };
}

export function getPortfolioReport(organizationSlug: string) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  return apiGet<PortfolioReport>(`/api/reports/portfolio?${params.toString()}`);
}
