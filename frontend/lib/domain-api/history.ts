import { apiDownload, apiGet } from "@/lib/api";

export interface HistoryEntry {
  id: string;
  kind: "activity" | "fact_review" | "override" | "document" | "mail";
  category: string;
  at: string | null;
  actor: string | null;
  event: string;
  label: string;
  details: Record<string, unknown>;
  role?: string;
  object_type?: string;
  object_id?: string | null;
  contract_number?: string | null;
  contract_title?: string | null;
}

export interface HistoryFilters {
  account_id?: string;
  category?: string;
  contract_id?: string;
  date_from?: string;
  date_to?: string;
  object_type?: string;
  object_id?: string;
}

export interface HistoryPage {
  total: number;
  items: HistoryEntry[];
  actors: { account_id: string; display_name: string }[];
  categories: { key: string; label: string }[];
}

function params(organizationSlug: string, filters: HistoryFilters, extra: Record<string, string> = {}) {
  const query = new URLSearchParams({ organization_slug: organizationSlug, ...extra });
  for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
  return query.toString();
}

export function listHistory(organizationSlug: string, filters: HistoryFilters, page: { limit: number; offset: number }) {
  return apiGet<HistoryPage>(`/api/history?${params(organizationSlug, filters, { limit: String(page.limit), offset: String(page.offset) })}`);
}

export function downloadHistoryCsv(organizationSlug: string, filters: HistoryFilters) {
  return apiDownload(`/api/history/export?${params(organizationSlug, filters)}`, 60000);
}

export function getContractHistory(organizationSlug: string, contractId: string) {
  return apiGet<{ items: HistoryEntry[] }>(`/api/contracts/${encodeURIComponent(contractId)}/history?organization_slug=${encodeURIComponent(organizationSlug)}`);
}
