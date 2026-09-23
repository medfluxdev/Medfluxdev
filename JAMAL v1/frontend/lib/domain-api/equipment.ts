import { apiGet } from "@/lib/api";
import type { EquipmentDetail, EquipmentSummary } from "@/lib/pr4-types";

export function listEquipment(
  organizationSlug: string,
  options: { q?: string; limit?: number } = {},
) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  if (options.q) params.set("q", options.q);
  if (options.limit != null) params.set("limit", String(options.limit));
  return apiGet<EquipmentSummary[]>(`/api/equipment?${params.toString()}`);
}

export function getEquipment(equipmentId: string, organizationSlug: string) {
  return apiGet<EquipmentDetail>(
    `/api/equipment/${encodeURIComponent(equipmentId)}?organization_slug=${encodeURIComponent(organizationSlug)}`,
  );
}
