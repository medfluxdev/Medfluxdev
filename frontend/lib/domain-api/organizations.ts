import { apiGet, apiPatch, apiPost } from "@/lib/api";

export interface HospitalDto {
  id: string;
  name: string;
  code: string;
  address?: string | null;
  is_active: boolean;
}

export interface DepartmentDto {
  id: string;
  hospital_id: string;
  parent_id?: string | null;
  name: string;
  code: string;
  is_active: boolean;
}

export interface CostCenterDto {
  id: string;
  hospital_id: string;
  department_id: string | null;
  code: string;
  name: string;
  is_active: boolean;
}

export interface OrganizationStructureDto {
  hospitals: HospitalDto[];
  departments: DepartmentDto[];
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getOrganizationStructure(organizationSlug: string) {
  return apiGet<OrganizationStructureDto>(`/api/organization-structure?${orgQuery(organizationSlug)}`);
}

export function createHospital(organizationSlug: string, payload: { name: string; code: string; address?: string | null }) {
  return apiPost<Pick<HospitalDto, "id" | "name" | "code">>(
    `/api/organization-structure/hospitals?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function updateHospital(organizationSlug: string, hospitalId: string, payload: Partial<Pick<HospitalDto, "name" | "code" | "address" | "is_active">>) {
  return apiPatch<HospitalDto>(
    `/api/organization-structure/hospitals/${encodeURIComponent(hospitalId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function createDepartment(organizationSlug: string, payload: { hospital_id: string; parent_id?: string | null; name: string; code: string }) {
  return apiPost<Pick<DepartmentDto, "id" | "hospital_id" | "name" | "code">>(
    `/api/organization-structure/departments?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function updateDepartment(organizationSlug: string, departmentId: string, payload: Partial<Pick<DepartmentDto, "parent_id" | "name" | "code" | "is_active">>) {
  return apiPatch<DepartmentDto>(
    `/api/organization-structure/departments/${encodeURIComponent(departmentId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function listCostCenters(organizationSlug: string) {
  return apiGet<{ items: CostCenterDto[] }>(`/api/cost-centers?${orgQuery(organizationSlug)}`);
}

export function createCostCenter(organizationSlug: string, payload: { hospital_id: string; department_id?: string | null; code: string; name: string }) {
  return apiPost<Pick<CostCenterDto, "id" | "code" | "name">>(
    `/api/cost-centers?${orgQuery(organizationSlug)}`,
    payload,
  );
}
