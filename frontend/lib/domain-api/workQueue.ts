import { apiGet, apiPatch } from "@/lib/api";
import type { WorkItemList, WorkItemSummary } from "@/lib/pr4-types";

export interface WorkQueueFilters {
  active?: boolean;
  status?: string[];
  severity?: string[];
  item_type?: string[];
  limit?: number;
}

export function listWorkItems(
  organizationSlug: string,
  filters: WorkQueueFilters = {},
) {
  const params = new URLSearchParams({
    organization_slug: organizationSlug,
    active: String(filters.active ?? true),
  });
  for (const value of filters.status ?? []) params.append("status", value);
  for (const value of filters.severity ?? []) params.append("severity", value);
  for (const value of filters.item_type ?? []) params.append("item_type", value);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  return apiGet<WorkItemList>(`/api/work-queue?${params.toString()}`);
}

export function setWorkItemStatus(
  workItemId: string,
  organizationSlug: string,
  status: "acknowledged" | "resolved",
) {
  return apiPatch<WorkItemSummary>(
    `/api/work-queue/${encodeURIComponent(workItemId)}?organization_slug=${encodeURIComponent(organizationSlug)}`,
    { status },
  );
}
