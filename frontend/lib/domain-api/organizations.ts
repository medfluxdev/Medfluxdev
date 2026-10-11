import { apiGet, apiPatch, apiPost } from "@/lib/api";

export interface HospitalDto {
  id: string;
  name: string;
  code: string;
  address?: string | null;
  is_active: boolean;
}

export type DepartmentUnitType = "klinik" | "abteilung" | "bereich" | "einheit" | "station" | "funktionsbereich";

export const DEPARTMENT_UNIT_TYPE_LABELS: Record<DepartmentUnitType, string> = {
  klinik: "Klinik",
  abteilung: "Abteilung",
  bereich: "Bereich",
  einheit: "Einheit",
  station: "Station",
  funktionsbereich: "Funktionsbereich",
};

export interface DepartmentDto {
  id: string;
  hospital_id: string;
  parent_id?: string | null;
  name: string;
  code: string;
  unit_type?: DepartmentUnitType | null;
  is_active: boolean;
  /** Einordnung passt nicht zu den Strukturregeln (bestehende Daten); Text = Regel. */
  placement_issue?: string | null;
}

/** Erlaubte übergeordnete Typen je Typ (`null` = direkt unter dem Krankenhaus). */
export type PlacementRules = Partial<Record<DepartmentUnitType, { parents: (DepartmentUnitType | null)[]; text: string }>>;

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
  unit_types?: DepartmentUnitType[];
  placement_rules?: PlacementRules;
}

export interface StructureSearchHitDto {
  kind: "department" | "cost_center";
  id: string;
  code: string;
  name: string;
  hospital_id: string;
  hospital_name: string;
  path: string[];
  path_label: string;
  unit_type: DepartmentUnitType | null;
  department_id: string | null;
  is_active: boolean;
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

export function createDepartment(organizationSlug: string, payload: { hospital_id: string; parent_id?: string | null; name: string; code: string; unit_type?: DepartmentUnitType | null; cost_center_code?: string | null }) {
  return apiPost<Pick<DepartmentDto, "id" | "hospital_id" | "name" | "code">>(
    `/api/organization-structure/departments?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function updateDepartment(organizationSlug: string, departmentId: string, payload: Partial<Pick<DepartmentDto, "parent_id" | "name" | "code" | "unit_type" | "is_active">> & { cost_center_code?: string | null }) {
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

export function updateCostCenter(organizationSlug: string, costCenterId: string, payload: Partial<Pick<CostCenterDto, "department_id" | "code" | "name" | "is_active">>) {
  return apiPatch<CostCenterDto>(
    `/api/cost-centers/${encodeURIComponent(costCenterId)}?${orgQuery(organizationSlug)}`,
    payload,
  );
}

export function searchOrganizationStructure(organizationSlug: string, query: string, signal?: AbortSignal) {
  return apiGet<{ query: string; items: StructureSearchHitDto[] }>(
    `/api/organization-structure/search?${orgQuery(organizationSlug)}&q=${encodeURIComponent(query)}`,
    signal,
  );
}
