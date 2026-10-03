export type AccountRole = "admin" | "contract_manager" | "reviewer" | "viewer";

export interface OrganizationMembershipDto {
  organization_id: string;
  organization_slug: string;
  organization_name: string;
  role: AccountRole;
  hospital_id?: string | null;
  department_id?: string | null;
  is_default?: boolean;
}

export interface CurrentAccountDto {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_developer?: boolean;
  last_login_at: string | null;
  profile_photo_data_url?: string | null;
  phone?: string | null;
  job_title?: string | null;
  department?: string | null;
  bio?: string | null;
  memberships: OrganizationMembershipDto[];
}

export interface ManagedUserDto {
  id: string;
  email: string;
  display_name: string;
  role: AccountRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface UserProfileDto {
  id: string;
  email: string;
  display_name: string;
  phone: string | null;
  job_title: string | null;
  department: string | null;
  bio: string | null;
  profile_photo_data_url: string | null;
}

export const ROLE_LABELS: Record<AccountRole, string> = {
  admin: "Administrator",
  contract_manager: "Vertragsmanager",
  reviewer: "Prüfer",
  viewer: "Leser",
};
