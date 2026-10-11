import { apiGet, apiPatch, apiPut } from "@/lib/api";

export interface ContractOwnershipDto {
  contract_id: string;
  hospital_id: string | null;
  department_ids: string[];
  cost_center_id: string | null;
  responsible_account_id: string | null;
  /** Weitere verantwortliche Personen (bekommen dasselbe wie die Hauptverantwortliche). */
  further_responsible_account_ids?: string[];
  scope_type: "organization" | "hospital" | "department" | string;
}

export interface AssigneeDto {
  id: string;
  display_name: string;
  email: string;
  role: string;
  hospital_id: string | null;
  department_id: string | null;
}

export interface ContractDepartmentRolesDto {
  contract_id: string;
  responsible_department_id: string | null;
  beneficiary_department_ids: string[];
  unclassified_department_ids: string[];
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function listOwnershipAssignees(organizationSlug: string) {
  return apiGet<{ items: AssigneeDto[] }>(`/api/ownership/assignees?${orgQuery(organizationSlug)}`);
}

export function getContractOwnership(organizationSlug: string, contractId: string) {
  return apiGet<ContractOwnershipDto>(
    `/api/ownership/contracts/${encodeURIComponent(contractId)}?${orgQuery(organizationSlug)}`,
  );
}

export function updateContractOwnership(
  organizationSlug: string,
  contractId: string,
  payload: {
    hospital_id: string | null;
    department_ids: string[];
    cost_center_id: string | null;
    responsible_account_id?: string | null;
    further_responsible_account_ids?: string[];
  },
) {
  return apiPatch<ContractOwnershipDto>(
    `/api/ownership/contracts/${encodeURIComponent(contractId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function getContractDepartmentRoles(organizationSlug: string, contractId: string) {
  return apiGet<ContractDepartmentRolesDto>(
    `/api/ownership/contracts/${encodeURIComponent(contractId)}/department-roles?${orgQuery(organizationSlug)}`,
  );
}

export function updateContractDepartmentRoles(
  organizationSlug: string,
  contractId: string,
  payload: { responsible_department_id: string; beneficiary_department_ids: string[] },
) {
  return apiPut<ContractDepartmentRolesDto>(
    `/api/ownership/contracts/${encodeURIComponent(contractId)}/department-roles?${orgQuery(organizationSlug)}`,
    payload,
  );
}
