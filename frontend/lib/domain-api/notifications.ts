import { apiGet } from "@/lib/api";

export interface NotificationItem {
  id: string;
  kind: "work_item" | "approval_required" | string;
  severity: string;
  title: string;
  message: string | null;
  contract_id: string | null;
  target_date: string | null;
  href: string;
}

export interface NotificationFeed {
  items: NotificationItem[];
  total: number;
}

export function listNotifications(organizationSlug: string, limit = 100) {
  const params = new URLSearchParams({ organization_slug: organizationSlug, limit: String(limit) });
  return apiGet<NotificationFeed>(`/api/notifications?${params.toString()}`);
}
