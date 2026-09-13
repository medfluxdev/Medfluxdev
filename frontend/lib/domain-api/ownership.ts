import { apiGet, apiPatch } from "@/lib/api";

export interface ContractOwnershipDto {
  contract_id: string;
  hospital_id: string | null;
  department_ids: string[];
  cost_center_id: string | null;
  responsible_account_id: string | null;
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
  },
) {
  return apiPatch<ContractOwnershipDto>(
    `/api/ownership/contracts/${encodeURIComponent(contractId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}
