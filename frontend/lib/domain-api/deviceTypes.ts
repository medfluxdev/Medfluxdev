import { apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

// Gerätearten (Plan docs/architecture/GERAETEARTEN_PLAN_20261011.md).

export type DeviceArea = "medizintechnik" | "it" | "haustechnik" | "sonstiges";

export interface DeviceTypeDto {
  id: string;
  code: string;
  label: string;
  area: DeviceArea;
  area_label: string;
  department_id: string | null;
  department_name: string | null;
  keywords: string | null;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface ContractDeviceTypeDto {
  device_type_id: string;
  label: string;
  area: DeviceArea;
  area_label: string;
  quantity: number | null;
  note: string | null;
}

export interface DeviceTypeSuggestion {
  device_type_id: string;
  label: string;
  reason: string;
}

export interface ContractDeviceTypes {
  items: ContractDeviceTypeDto[];
  suggestions: DeviceTypeSuggestion[];
}

export interface DeviceTypeSummaryItem {
  label: string;
  value: string;
  count: number;
  annual_cost: string | null;
  annual_known: number;
  annual_missing: number;
  devices_known: number;
  devices_missing: number;
}

export interface DeviceTypeContractItem {
  contract_id: string;
  register_number: string | null;
  short_description: string | null;
  partner: string | null;
  hospital: string | null;
  department: string | null;
  possible_end: string | null;
  currency: string;
  annual_cost: string | null;
  quantity: number | null;
  other_device_types: string[];
  cost_per_device: string | null;
  cost_per_device_reason: string | null;
}

export type DeviceTypeComparison =
  | { as_of: string; level: "types"; items: DeviceTypeSummaryItem[]; running_count: number; without_count: number }
  | {
    as_of: string; level: "contracts"; device_type: string; items: DeviceTypeContractItem[]; count: number; truncated: boolean;
    totals: { value: string | null; currency: string; known: number; missing: number };
    devices_known: number; devices_missing: number;
    register_filter: { column: string; op: "in"; value: string[] }[];
  };

const org = (organizationSlug: string) => `organization_slug=${encodeURIComponent(organizationSlug)}`;

export const DEVICE_AREAS: { value: DeviceArea; label: string }[] = [
  { value: "medizintechnik", label: "Medizintechnik" },
  { value: "it", label: "IT" },
  { value: "haustechnik", label: "Haustechnik" },
  { value: "sonstiges", label: "Sonstiges" },
];

export function listDeviceTypes(organizationSlug: string) {
  return apiGet<{ items: DeviceTypeDto[]; areas: Record<DeviceArea, string> }>(`/api/catalogs/device-types?${org(organizationSlug)}`);
}

export function createDeviceType(organizationSlug: string, values: Partial<DeviceTypeDto>) {
  return apiPost<DeviceTypeDto>(`/api/catalogs/device-types?${org(organizationSlug)}`, { values });
}

export function updateDeviceType(organizationSlug: string, id: string, values: Partial<DeviceTypeDto>) {
  return apiPatch<DeviceTypeDto>(`/api/catalogs/device-types/${encodeURIComponent(id)}?${org(organizationSlug)}`, { values });
}

export function getContractDeviceTypes(organizationSlug: string, contractId: string) {
  return apiGet<ContractDeviceTypes>(`/api/contracts/${encodeURIComponent(contractId)}/device-types?${org(organizationSlug)}`);
}

export function saveContractDeviceTypes(
  organizationSlug: string,
  contractId: string,
  items: { device_type_id: string; quantity: number | null; note: string | null }[],
) {
  return apiPut<ContractDeviceTypes>(`/api/contracts/${encodeURIComponent(contractId)}/device-types?${org(organizationSlug)}`, { items });
}

export function getDeviceTypeComparison(organizationSlug: string, deviceType?: string | null) {
  const extra = deviceType ? `&device_type=${encodeURIComponent(deviceType)}` : "";
  return apiGet<DeviceTypeComparison>(`/api/register/reports/device-types?${org(organizationSlug)}${extra}`);
}
