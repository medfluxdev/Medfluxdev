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
  type PlacementRules,
} from "@/lib/domain-api/organizations";
import Signal from "@/components/ui/Signal";
import { departmentDescendantIds, departmentFullPath } from "@/lib/organization-tree";
import { optional, text, type EntityDefinition, type FieldOption, type FilterDef } from "../types";

export interface OrganizationContext {
  hospitals: HospitalDto[];
  departments: DepartmentDto[];
  costCenters: CostCenterDto[];
  /** Strukturregeln vom Backend (organization_structure/placement.py). */
  placementRules?: PlacementRules;
}

export async function loadOrganization(organizationSlug: string): Promise<OrganizationContext> {
  const [structure, centers] = await Promise.all([getOrganizationStructure(organizationSlug), listCostCenters(organizationSlug)]);
  return { hospitals: structure.hospitals, departments: structure.departments, costCenters: centers.items, placementRules: structure.placement_rules };
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

export function departmentParentOptions(context: OrganizationContext, hospitalId: string, self: DepartmentDto | null, unitType?: string): FieldOption[] {
  const blocked = self ? departmentDescendantIds(self.id, context.departments) : new Set<string>();
  // Nur erlaubte übergeordnete Typen; Einheiten ohne Typ werden nicht beurteilt (bleiben wählbar).
  const allowed = unitType ? context.placementRules?.[unitType as DepartmentUnitType]?.parents : undefined;
  return context.departments
    .filter((item) => item.hospital_id === hospitalId && item.is_active && item.id !== self?.id && !blocked.has(item.id))
    .filter((item) => !allowed || !item.unit_type || allowed.includes(item.unit_type))
    .map((item) => ({ value: item.id, label: departmentFullPath(item, context.departments) }))
    .sort((a, b) => a.label.localeCompare(b.label, "de"));
}

// Aktive Kostenstellen einer Abteilung (Liste) bzw. die erste (Formular).
function departmentCenterCodes(context: OrganizationContext, departmentId: string): string {
  return context.costCenters.filter((item) => item.department_id === departmentId && item.is_active).map((item) => item.code).join(", ");
}

function firstCenterCode(context: OrganizationContext, departmentId: string): string {
  return context.costCenters.find((item) => item.department_id === departmentId && item.is_active)?.code ?? "";
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
    { key: "placement", label: "Einordnung", sortValue: (row) => (row.placement_issue ? 0 : 1), render: (row) => (row.placement_issue ? <span title={row.placement_issue}><Signal tone="warning" size="sm">Prüfen</Signal><span className="visually-hidden">: {row.placement_issue}</span></span> : "–") },
    { key: "hospital", label: "Krankenhaus", sortValue: (row) => hospitalName(context, row.hospital_id), render: (row) => hospitalName(context, row.hospital_id) },
    { key: "centers", label: "Kostenstelle", sortValue: (row) => departmentCenterCodes(context, row.id), render: (row) => departmentCenterCodes(context, row.id) || "–" },
  ],
  fields: (context, form, row) => [
    { key: "hospital_id", label: "Krankenhaus", kind: "select", required: true, createOnly: true, options: hospitalOptions(context, row?.hospital_id) },
    (() => {
      // Strukturregeln: Klinik nur oben, Abteilung unter Klinik oder oben, Station/Funktionsbereich darunter.
      const rule = context.placementRules?.[text(form, "unit_type") as DepartmentUnitType];
      const topAllowed = !rule || rule.parents.includes(null);
      return {
        key: "parent_id", label: "Übergeordnete Einheit", kind: "search" as const,
        emptyOption: topAllowed ? "Keine – direkt im Krankenhaus" : undefined,
        options: departmentParentOptions(context, text(form, "hospital_id"), row, text(form, "unit_type")),
        hint: rule ? `${rule.text} Es werden nur passende Einheiten angeboten.` : "Tippen zum Suchen. Mit einem Einheitentyp werden nur passende übergeordnete Einheiten angeboten.",
      };
    })(),
    { key: "name", label: "Name", required: true, maxLength: 255 },
    { key: "code", label: "Kürzel", required: true, maxLength: 40, hint: "Eindeutig im Krankenhaus." },
    { key: "unit_type", label: "Einheitentyp", kind: "select", emptyOption: "Nicht festgelegt", options: UNIT_TYPE_OPTIONS },
    {
      key: "cost_center_code", label: "Kostenstelle (optional)", maxLength: 80,
      hint: "Nummer eintragen: neue Nummern werden als Kostenstelle dieser Abteilung angelegt, eine freie bestehende wird verknüpft. In der Vertragszuordnung füllen sich Abteilung und Kostenstelle dann gegenseitig.",
    },
  ],
  emptyForm: (context, preset) => ({ hospital_id: defaultHospital(context), parent_id: "", name: "", code: "", unit_type: "", cost_center_code: "", ...preset }),
  toForm: (row, context) => ({ hospital_id: row.hospital_id, parent_id: row.parent_id ?? "", name: row.name, code: row.code, unit_type: row.unit_type ?? "", cost_center_code: firstCenterCode(context, row.id) }),
  create: (organizationSlug, form) => createDepartment(organizationSlug, {
    hospital_id: text(form, "hospital_id"),
    parent_id: optional(form, "parent_id"),
    name: text(form, "name"),
    code: text(form, "code"),
    unit_type: (optional(form, "unit_type") as DepartmentUnitType | null),
    cost_center_code: optional(form, "cost_center_code"),
  }),
  update: (organizationSlug, row, form) => updateDepartment(organizationSlug, row.id, {
    ...(optional(form, "parent_id") !== (row.parent_id ?? null) ? { parent_id: optional(form, "parent_id") } : {}),
    name: text(form, "name"),
    code: text(form, "code"),
    unit_type: (optional(form, "unit_type") as DepartmentUnitType | null),
    cost_center_code: text(form, "cost_center_code"),
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
