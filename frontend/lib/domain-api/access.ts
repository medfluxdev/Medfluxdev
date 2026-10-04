import { apiGet } from "@/lib/api";

export interface PermissionMatrix {
  roles: { key: string; label: string }[];
  permissions: { key: string; label: string; area: string; roles: string[] }[];
  role: string;
  granted: string[];
}

export function getPermissionMatrix(organizationSlug: string) {
  return apiGet<PermissionMatrix>(`/api/permissions?organization_slug=${encodeURIComponent(organizationSlug)}`);
}
