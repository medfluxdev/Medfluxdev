import { getOrganizationStructure, type DepartmentDto } from "@/lib/domain-api/organizations";
import {
  DEVICE_AREAS,
  createDeviceType,
  listDeviceTypes,
  updateDeviceType,
  type DeviceArea,
  type DeviceTypeDto,
} from "@/lib/domain-api/deviceTypes";
import { departmentFullPath } from "@/lib/organization-tree";
import { optional, text, type EntityDefinition } from "../types";

// Gerätearten (Plan docs/architecture/GERAETEARTEN_PLAN_20261011.md): je Bereich, optional einer Abteilung zugeordnet.

type Department = DepartmentDto;

export interface DeviceTypeContext {
  departments: Department[];
}

async function loadContext(organizationSlug: string): Promise<DeviceTypeContext> {
  const structure = await getOrganizationStructure(organizationSlug).catch(() => null);
  return { departments: (structure?.departments ?? []) as Department[] };
}

function departmentLabel(context: DeviceTypeContext, id: string | null): string {
  const department = context.departments.find((item) => item.id === id);
  return department ? departmentFullPath(department, context.departments) : "–";
}

export const deviceTypeDefinition: EntityDefinition<DeviceTypeDto, DeviceTypeContext> = {
  kind: "device_type",
  singular: "Geräteart",
  plural: "Gerätearten",
  objectType: "catalog_device_type",
  load: async (organizationSlug) => {
    const [data, context] = await Promise.all([listDeviceTypes(organizationSlug), loadContext(organizationSlug)]);
    return { rows: data.items, context };
  },
  loadContext,
  id: (row) => row.id,
  label: (row) => row.label,
  formLabel: (form) => text(form, "label"),
  active: (row) => row.is_active,
  searchText: (row) => `${row.label} ${row.code} ${row.area_label} ${row.keywords ?? ""} ${row.department_name ?? ""}`,
  intro: <p className="field-hint">Gerätearten ordnen Verträge ein (z. B. alle Wartungsverträge für CTs) – für Filter in der Vertragsliste und den Vergleich unter Analysen. Jeder Bereich pflegt seine Liste; Suchbegriffe helfen, im Dokument gefundene Geräte als Vorschlag zuzuordnen.</p>,
  columns: (context) => [
    { key: "label", label: "Geräteart", rowHeader: true, sortValue: (row) => row.label.toLocaleLowerCase("de"), render: (row) => row.label },
    { key: "area", label: "Bereich", sortValue: (row) => row.area_label, render: (row) => row.area_label },
    { key: "department", label: "Zuständige Abteilung", sortValue: (row) => departmentLabel(context, row.department_id), render: (row) => departmentLabel(context, row.department_id) },
    { key: "keywords", label: "Suchbegriffe", render: (row) => row.keywords || "–" },
  ],
  filters: [{
    key: "area", label: "Bereich", allLabel: "Alle Bereiche",
    options: () => DEVICE_AREAS.map((item) => ({ value: item.value, label: item.label })),
    match: (row, value) => row.area === value,
  }],
  fields: (context) => [
    { key: "label", label: "Bezeichnung", required: true, maxLength: 160, wide: true },
    { key: "area", label: "Bereich", kind: "select", options: DEVICE_AREAS.map((item) => ({ value: item.value, label: item.label })) },
    {
      key: "department_id", label: "Zuständige Abteilung", kind: "select", emptyOption: "Keine",
      options: context.departments.filter((item) => item.is_active).map((item) => ({ value: item.id, label: departmentFullPath(item, context.departments) })),
      hint: "Die Abteilung, die diese Geräte betreut (z. B. Medizintechnik, IT). In der Vertragsakte stehen ihre Gerätearten zuerst.",
    },
    { key: "keywords", label: "Suchbegriffe (kommagetrennt)", maxLength: 500, wide: true, hint: "Andere Schreibweisen und Modellnamen, z. B. „Computertomograph, Somatom“. Daraus entstehen nur Vorschläge." },
    { key: "description", label: "Beschreibung", kind: "textarea", maxLength: 500 },
  ],
  emptyForm: (_context, preset) => ({ label: "", area: "medizintechnik", department_id: "", keywords: "", description: "", ...preset }),
  toForm: (row) => ({ label: row.label, area: row.area, department_id: row.department_id ?? "", keywords: row.keywords ?? "", description: row.description ?? "" }),
  create: (organizationSlug, form) => createDeviceType(organizationSlug, {
    label: text(form, "label"), area: (text(form, "area") || "sonstiges") as DeviceArea,
    department_id: optional(form, "department_id"), keywords: optional(form, "keywords"), description: optional(form, "description"),
  }),
  update: (organizationSlug, row, form) => updateDeviceType(organizationSlug, row.id, {
    label: text(form, "label"), area: (text(form, "area") || "sonstiges") as DeviceArea,
    department_id: optional(form, "department_id"), keywords: optional(form, "keywords"), description: optional(form, "description"),
  }),
  setActive: (organizationSlug, row, active) => updateDeviceType(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "device_types", value: row.label }),
  exportHeader: ["Geräteart", "Code", "Bereich", "Zuständige Abteilung", "Suchbegriffe", "Aktiv"],
  exportRow: (row, context) => [row.label, row.code, row.area_label, departmentLabel(context, row.department_id), row.keywords, row.is_active ? "ja" : "nein"],
};
