import { apiGet } from "@/lib/api";

export type SetupItemStatus = "ok" | "todo" | "optional";

export interface SetupItem {
  key: string;
  label: string;
  status: SetupItemStatus;
  detail: string;
  href: string;
}

export interface SetupStatus {
  items: SetupItem[];
  done: number;
  total: number;
  required: number;
  required_open: number;
}

export function getSetupStatus(organizationSlug: string) {
  return apiGet<SetupStatus>(`/api/admin/setup-status?organization_slug=${encodeURIComponent(organizationSlug)}`);
}
