import {
  DEPARTMENT_UNIT_TYPE_LABELS,
  createCostCenter,
  createDepartment,
  createHospital,
  getOrganizationStructure,
  listCostCenters,
  updateCostCenter,
  updateDepartment,
  updateHospital,
  type CostCenterDto,
  type DepartmentDto,
  type DepartmentUnitType,
  type HospitalDto,
} from "@/lib/domain-api/organizations";
import { departmentDescendantIds, departmentFullPath } from "@/lib/organization-tree";
import { optional, text, type EntityDefinition, type FieldOption, type FilterDef } from "../types";

export interface OrganizationContext {
  hospitals: HospitalDto[];
  departments: DepartmentDto[];
  costCenters: CostCenterDto[];
}

export async function loadOrganization(organizationSlug: string): Promise<OrganizationContext> {
  const [structure, centers] = await Promise.all([getOrganizationStructure(organizationSlug), listCostCenters(organizationSlug)]);
  return { hospitals: structure.hospitals, departments: structure.departments, costCenters: centers.items };
}

function hospitalName(context: OrganizationContext, id: string | null | undefined) {
  return context.hospitals.find((item) => item.id === id)?.name ?? "–";
}

function hospitalOptions(context: OrganizationContext, includeId?: string): FieldOption[] {
  return context.hospitals
    .filter((item) => item.is_active || item.id === includeId)
    .map((item) => ({ value: item.id, label: `${item.name} (${item.code})` }));
}

function defaultHospital(context: OrganizationContext): string {
  const active = context.hospitals.filter((item) => item.is_active);
  return active.length === 1 ? active[0].id : "";
}

const UNIT_TYPE_OPTIONS: FieldOption[] = Object.entries(DEPARTMENT_UNIT_TYPE_LABELS).map(([value, label]) => ({ value, label }));

function hospitalFilter<T>(hospitalOf: (row: T) => string): FilterDef<T, OrganizationContext> {
  return {
    key: "haus",
    label: "Krankenhaus",
    allLabel: "Alle Krankenhäuser",
    options: (context) => context.hospitals.map((item) => ({ value: item.id, label: item.name })),
    match: (row, value) => hospitalOf(row) === value,
  };
}

// --------------------------------------------------------------------------- Krankenhaeuser

export const hospitalDefinition: EntityDefinition<HospitalDto, OrganizationContext> = {
  kind: "hospital",
  singular: "Krankenhaus",
  plural: "Krankenhäuser",
  objectType: "hospital",
  load: async (organizationSlug) => {
    const context = await loadOrganization(organizationSlug);
    return { rows: context.hospitals, context };
  },
  loadContext: loadOrganization,
  id: (row) => row.id,
  label: (row) => row.name,
  formLabel: (form) => text(form, "name"),
  active: (row) => row.is_active,
  searchText: (row) => `${row.name} ${row.code} ${row.address ?? ""}`,
  columns: (context) => [
    { key: "code", label: "Kürzel", sortValue: (row) => row.code, render: (row) => <code>{row.code}</code> },
    { key: "name", label: "Name", rowHeader: true, sortValue: (row) => row.name.toLocaleLowerCase("de"), render: (row) => row.name },
    { key: "address", label: "Adresse", render: (row) => row.address || "–" },
    { key: "departments", label: "Abteilungen", numeric: true, sortValue: (row) => context.departments.filter((item) => item.hospital_id === row.id).length, render: (row) => context.departments.filter((item) => item.hospital_id === row.id && item.is_active).length },
  ],
  fields: () => [
    { key: "name", label: "Name", required: true, maxLength: 255, wide: true },
    { key: "code", label: "Kürzel", required: true, maxLength: 40, hint: "Eindeutig in der Organisation, z. B. KHN." },
    { key: "address", label: "Adresse", wide: true },
  ],
  emptyForm: (_context, preset) => ({ name: "", code: "", address: "", ...preset }),
  toForm: (row) => ({ name: row.name, code: row.code, address: row.address ?? "" }),
  create: (organizationSlug, form) => createHospital(organizationSlug, { name: text(form, "name"), code: text(form, "code"), address: optional(form, "address") }),
  update: (organizationSlug, row, form) => updateHospital(organizationSlug, row.id, { name: text(form, "name"), code: text(form, "code"), address: text(form, "address") }),
  setActive: (organizationSlug, row, active) => updateHospital(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "hospital", value: row.name }),
  exportHeader: ["Kürzel", "Name", "Adresse", "Aktiv"],
  exportRow: (row) => [row.code, row.name, row.address ?? "", row.is_active ? "ja" : "nein"],
};

// --------------------------------------------------------------------------- Abteilungen

export function departmentParentOptions(context: OrganizationContext, hospitalId: string, self: DepartmentDto | null): FieldOption[] {
  const blocked = self ? departmentDescendantIds(self.id, context.departments) : new Set<string>();
  return context.departments
    .filter((item) => item.hospital_id === hospitalId && item.is_active && item.id !== self?.id && !blocked.has(item.id))
    .map((item) => ({ value: item.id, label: departmentFullPath(item, context.departments) }))
    .sort((a, b) => a.label.localeCompare(b.label, "de"));
}

export const departmentDefinition: EntityDefinition<DepartmentDto, OrganizationContext> = {
  kind: "department",
  singular: "Abteilung",
  plural: "Abteilungen",
  objectType: "department",
  load: async (organizationSlug) => {
    const context = await loadOrganization(organizationSlug);
    return { rows: context.departments, context };
  },
  loadContext: loadOrganization,
  id: (row) => row.id,
  label: (row) => row.name,
  formLabel: (form) => text(form, "name"),
  active: (row) => row.is_active,
  searchText: (row, context) => `${row.code} ${departmentFullPath(row, context.departments)} ${hospitalName(context, row.hospital_id)}`,
  columns: (context) => [
    { key: "code", label: "Kürzel", sortValue: (row) => row.code, render: (row) => <code>{row.code}</code> },
    { key: "name", label: "Name", rowHeader: true, sortValue: (row) => departmentFullPath(row, context.departments).toLocaleLowerCase("de"), render: (row) => {
      const path = departmentFullPath(row, context.departments);
      return path === row.name ? row.name : <span className="md-path"><span>{row.name}</span><small>{path}</small></span>;
    } },
    { key: "type", label: "Typ", sortValue: (row) => row.unit_type ?? "", render: (row) => (row.unit_type ? DEPARTMENT_UNIT_TYPE_LABELS[row.unit_type] : "–") },
    { key: "hospital", label: "Krankenhaus", sortValue: (row) => hospitalName(context, row.hospital_id), render: (row) => hospitalName(context, row.hospital_id) },
    { key: "centers", label: "Kostenstellen", numeric: true, render: (row) => context.costCenters.filter((item) => item.department_id === row.id && item.is_active).length },
  ],
  fields: (context, form, row) => [
    { key: "hospital_id", label: "Krankenhaus", kind: "select", required: true, createOnly: true, options: hospitalOptions(context, row?.hospital_id) },
    {
      key: "parent_id", label: "Übergeordnete Einheit", kind: "select", emptyOption: "Keine (direkt im Krankenhaus)",
      options: departmentParentOptions(context, text(form, "hospital_id"), row),
      hint: "Bildet die Struktur ab, z. B. Station unter Klinik.",
    },
    { key: "name", label: "Name", required: true, maxLength: 255 },
    { key: "code", label: "Kürzel", required: true, maxLength: 40, hint: "Eindeutig im Krankenhaus." },
    { key: "unit_type", label: "Einheitentyp", kind: "select", emptyOption: "Nicht festgelegt", options: UNIT_TYPE_OPTIONS },
  ],
  emptyForm: (context, preset) => ({ hospital_id: defaultHospital(context), parent_id: "", name: "", code: "", unit_type: "", ...preset }),
  toForm: (row) => ({ hospital_id: row.hospital_id, parent_id: row.parent_id ?? "", name: row.name, code: row.code, unit_type: row.unit_type ?? "" }),
  create: (organizationSlug, form) => createDepartment(organizationSlug, {
    hospital_id: text(form, "hospital_id"),
    parent_id: optional(form, "parent_id"),
    name: text(form, "name"),
    code: text(form, "code"),
    unit_type: (optional(form, "unit_type") as DepartmentUnitType | null),
  }),
  update: (organizationSlug, row, form) => updateDepartment(organizationSlug, row.id, {
    ...(optional(form, "parent_id") !== (row.parent_id ?? null) ? { parent_id: optional(form, "parent_id") } : {}),
    name: text(form, "name"),
    code: text(form, "code"),
    unit_type: (optional(form, "unit_type") as DepartmentUnitType | null),
  }),
  setActive: (organizationSlug, row, active) => updateDepartment(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "department", value: row.name }),
  filters: [hospitalFilter((row) => row.hospital_id)],
  importKind: "department",
  importColumns: [
    { key: "hospital", label: "Krankenhaus", aliases: ["haus", "gesellschaft", "standort"], required: true },
    { key: "name", label: "Name", aliases: ["bezeichnung", "abteilung"], required: true },
    { key: "code", label: "Kürzel", aliases: ["code", "kurzzeichen"], required: true },
    { key: "parent", label: "Übergeordnete Einheit", aliases: ["übergeordnet", "eltern", "parent"] },
    { key: "unit_type", label: "Einheitentyp", aliases: ["typ", "art"] },
  ],
  exportHeader: ["Krankenhaus", "Name", "Kürzel", "Übergeordnete Einheit", "Einheitentyp", "Pfad", "Aktiv"],
  exportRow: (row, context) => [
    context.hospitals.find((item) => item.id === row.hospital_id)?.code ?? "",
    row.name,
    row.code,
    context.departments.find((item) => item.id === row.parent_id)?.code ?? "",
    row.unit_type ? DEPARTMENT_UNIT_TYPE_LABELS[row.unit_type] : "",
    departmentFullPath(row, context.departments),
    row.is_active ? "ja" : "nein",
  ],
  intro: "Abteilungen mit aktiven Verträgen lassen sich erst deaktivieren, wenn die Verträge einer anderen Einheit zugeordnet sind.",
};

// --------------------------------------------------------------------------- Kostenstellen

function costCenterDepartmentOptions(context: OrganizationContext, hospitalId: string, currentId?: string | null): FieldOption[] {
  return context.departments
    .filter((item) => item.hospital_id === hospitalId && (item.is_active || item.id === currentId))
    .map((item) => ({ value: item.id, label: departmentFullPath(item, context.departments) }))
    .sort((a, b) => a.label.localeCompare(b.label, "de"));
}

export const costCenterDefinition: EntityDefinition<CostCenterDto, OrganizationContext> = {
  kind: "cost_center",
  singular: "Kostenstelle",
  plural: "Kostenstellen",
  objectType: "cost_center",
  load: async (organizationSlug) => {
    const context = await loadOrganization(organizationSlug);
    return { rows: context.costCenters, context };
  },
  loadContext: loadOrganization,
  id: (row) => row.id,
  label: (row) => `${row.code} – ${row.name}`,
  formLabel: (form) => text(form, "code"),
  active: (row) => row.is_active,
  searchText: (row, context) => {
    const department = context.departments.find((item) => item.id === row.department_id);
    return `${row.code} ${row.name} ${department ? departmentFullPath(department, context.departments) : ""} ${hospitalName(context, row.hospital_id)}`;
  },
  columns: (context) => [
    { key: "code", label: "Kostenstelle", rowHeader: true, sortValue: (row) => row.code, render: (row) => <code>{row.code}</code> },
    { key: "name", label: "Bezeichnung", sortValue: (row) => row.name.toLocaleLowerCase("de"), render: (row) => row.name },
    { key: "department", label: "Abteilung", sortValue: (row) => context.departments.find((item) => item.id === row.department_id)?.name ?? "", render: (row) => {
      const department = context.departments.find((item) => item.id === row.department_id);
      return department ? departmentFullPath(department, context.departments) : <span className="field-hint">Krankenhausweit</span>;
    } },
    { key: "hospital", label: "Krankenhaus", sortValue: (row) => hospitalName(context, row.hospital_id), render: (row) => hospitalName(context, row.hospital_id) },
  ],
  fields: (context, form, row) => [
    { key: "hospital_id", label: "Krankenhaus", kind: "select", required: true, createOnly: true, options: hospitalOptions(context, row?.hospital_id) },
    {
      key: "department_id", label: "Abteilung", kind: "select", emptyOption: "Krankenhausweit",
      options: costCenterDepartmentOptions(context, text(form, "hospital_id"), row?.department_id),
    },
    { key: "code", label: "Kostenstelle (Nummer)", required: true, maxLength: 80, hint: "Eindeutig in der Organisation." },
    { key: "name", label: "Bezeichnung", required: true, maxLength: 255 },
  ],
  emptyForm: (context, preset) => ({ hospital_id: defaultHospital(context), department_id: "", code: "", name: "", ...preset }),
  toForm: (row) => ({ hospital_id: row.hospital_id, department_id: row.department_id ?? "", code: row.code, name: row.name }),
  create: (organizationSlug, form) => createCostCenter(organizationSlug, {
    hospital_id: text(form, "hospital_id"),
    department_id: optional(form, "department_id"),
    code: text(form, "code"),
    name: text(form, "name"),
  }),
  update: (organizationSlug, row, form) => updateCostCenter(organizationSlug, row.id, {
    department_id: optional(form, "department_id"),
    code: text(form, "code"),
    name: text(form, "name"),
  }),
  setActive: (organizationSlug, row, active) => updateCostCenter(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "cost_center", value: row.name }),
  filters: [hospitalFilter((row) => row.hospital_id)],
  importKind: "cost_center",
  importColumns: [
    { key: "code", label: "Kostenstelle", aliases: ["nummer", "kst", "kostenstellennummer", "code"], required: true },
    { key: "name", label: "Bezeichnung", aliases: ["name"], required: true },
    { key: "hospital", label: "Krankenhaus", aliases: ["haus", "gesellschaft", "standort"], required: true },
    { key: "department", label: "Abteilung", aliases: ["bereich", "einheit"] },
  ],
  exportHeader: ["Kostenstelle", "Bezeichnung", "Krankenhaus", "Abteilung", "Aktiv"],
  exportRow: (row, context) => [
    row.code,
    row.name,
    context.hospitals.find((item) => item.id === row.hospital_id)?.code ?? "",
    context.departments.find((item) => item.id === row.department_id)?.code ?? "",
    row.is_active ? "ja" : "nein",
  ],
};
