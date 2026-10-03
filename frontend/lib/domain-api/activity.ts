import { apiGet } from "@/lib/api";

export interface ActivityDto {
  id: string;
  account_id: string | null;
  hospital_id: string | null;
  department_id: string | null;
  display_name: string | null;
  role: string | null;
  event_name: string;
  object_type: string;
  object_id: string | null;
  context_data: Record<string, unknown> | null;
  created_at: string | null;
}

export function listActivity(
  organizationSlug: string,
  options: { objectId?: string; limit?: number } = {},
) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  if (options.objectId) params.set("object_id", options.objectId);
  if (options.limit != null) params.set("limit", String(options.limit));
  return apiGet<{ items: ActivityDto[] }>(`/api/activity?${params.toString()}`);
}
