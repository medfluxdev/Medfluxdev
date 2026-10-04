import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type { AccountRole, ManagedUserDto } from "@/lib/auth-types";

export interface UserScopeDto {
  account_id: string;
  hospital_id: string | null;
  department_id: string | null;
  is_default: boolean;
}

export interface CreateUserPayload {
  email: string;
  display_name: string;
  password: string;
  role: AccountRole;
  hospital_id?: string | null;
  department_id?: string | null;
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function listUsers(organizationSlug: string) {
  return apiGet<{ items: ManagedUserDto[] }>(`/api/users?${orgQuery(organizationSlug)}`);
}

export function createUser(organizationSlug: string, payload: CreateUserPayload) {
  return apiPost<ManagedUserDto>(`/api/users?${orgQuery(organizationSlug)}`, payload);
}

export function updateUser(
  organizationSlug: string,
  accountId: string,
  payload: { display_name?: string; role?: AccountRole; is_active?: boolean; password?: string },
) {
  return apiPatch<ManagedUserDto>(
    `/api/users/${encodeURIComponent(accountId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function listUserScopes(organizationSlug: string) {
  return apiGet<{ items: UserScopeDto[] }>(`/api/user-scopes?${orgQuery(organizationSlug)}`);
}

export function updateUserScope(
  organizationSlug: string,
  accountId: string,
  payload: { hospital_id: string | null; department_id: string | null; is_default?: boolean },
) {
  return apiPatch<UserScopeDto>(
    `/api/user-scopes/${encodeURIComponent(accountId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export interface UserImportRow {
  email: string;
  display_name: string;
  role: string;
  hospital: string | null;
  department: string | null;
  password: string;
}

export interface UserImportCheckedRow {
  line: number;
  email: string;
  display_name: string;
  role: AccountRole | null;
  hospital: string | null;
  department: string | null;
  errors: string[];
}

export interface UserImportResult {
  valid: boolean;
  created: number;
  errors: string[];
  rows: UserImportCheckedRow[];
}

export function importUsers(organizationSlug: string, rows: UserImportRow[], dryRun: boolean) {
  return apiPost<UserImportResult>(`/api/users/import?${orgQuery(organizationSlug)}`, { rows, dry_run: dryRun });
}
