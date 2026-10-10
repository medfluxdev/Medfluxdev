import Badge from "@/components/ui/Badge";
import {
  LOOKUP_FIELD_LABEL,
  createContractCategory,
  createContractType,
  createLookup,
  listContractTypes,
  listLookups,
  updateContractCategory,
  updateContractType,
  updateLookup,
  type ContractCategoryDto,
  type ContractTypeDto,
  type LookupDto,
} from "@/lib/domain-api/catalogs";
import { optional, text, type EntityDefinition } from "../types";

export interface TypeContext {
  types: ContractTypeDto[];
  categories: ContractCategoryDto[];
}

async function loadTypes(organizationSlug: string): Promise<TypeContext> {
  const data = await listContractTypes(organizationSlug);
  return { types: data.contract_types, categories: data.contract_categories };
}

function retention(form: Record<string, unknown>): number | null {
  const raw = typeof form.retention_years === "string" ? form.retention_years.trim() : "";
  return raw === "" ? null : Number(raw);
}

export const contractTypeDefinition: EntityDefinition<ContractTypeDto, TypeContext> = {
  kind: "contract_type",
  singular: "Vertragstyp",
  plural: "Vertragstypen",
  objectType: "catalog_contract_type",
  load: async (organizationSlug) => {
    const context = await loadTypes(organizationSlug);
    return { rows: context.types, context };
  },
  loadContext: loadTypes,
  id: (row) => row.id,
  label: (row) => row.label,
  formLabel: (form) => text(form, "label"),
  active: (row) => row.is_active,
  searchText: (row) => `${row.label} ${row.code} ${row.description ?? ""}`,
  columns: (context) => [
    { key: "label", label: "Bezeichnung", rowHeader: true, sortValue: (row) => row.label.toLocaleLowerCase("de"), render: (row) => row.label },
    { key: "confidential", label: "Vertraulich", sortValue: (row) => (row.is_confidential ? 0 : 1), render: (row) => (row.is_confidential ? <Badge tone="info">Vertraulich</Badge> : "–") },
    { key: "retention", label: "Aufbewahrung", numeric: true, sortValue: (row) => row.retention_years ?? -1, render: (row) => (row.retention_years == null ? "Standard" : `${row.retention_years} Jahre`) },
    { key: "categories", label: "Kategorien", numeric: true, render: (row) => context.categories.filter((item) => item.contract_type_ids.includes(row.id) && item.is_active).length },
  ],
  fields: () => [
    { key: "label", label: "Bezeichnung", required: true, maxLength: 160, wide: true },
    { key: "description", label: "Beschreibung", kind: "textarea", maxLength: 500 },
    { key: "is_confidential", label: "Vertraulich", kind: "checkbox", hint: "Verträge dieses Typs sehen nur Administration und freigegebene Personen." },
    { key: "retention_years", label: "Aufbewahrung nach Vertragsende (Jahre)", kind: "number", min: 0, max: 100, hint: "Leer = Standard der Organisation." },
  ],
  emptyForm: (_context, preset) => ({ label: "", description: "", is_confidential: false, retention_years: "", ...preset }),
  toForm: (row) => ({ label: row.label, description: row.description ?? "", is_confidential: row.is_confidential, retention_years: row.retention_years == null ? "" : String(row.retention_years) }),
  create: (organizationSlug, form) => createContractType(organizationSlug, {
    label: text(form, "label"), description: optional(form, "description"), is_confidential: form.is_confidential === true, retention_years: retention(form),
  }),
  update: (organizationSlug, row, form) => updateContractType(organizationSlug, row.id, {
    label: text(form, "label"), description: optional(form, "description"), is_confidential: form.is_confidential === true, retention_years: retention(form),
  }),
  setActive: (organizationSlug, row, active) => updateContractType(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "contract_type", value: row.label }),
  exportHeader: ["Bezeichnung", "Code", "Vertraulich", "Aufbewahrung (Jahre)", "Aktiv"],
  exportRow: (row) => [row.label, row.code, row.is_confidential ? "ja" : "nein", row.retention_years, row.is_active ? "ja" : "nein"],
};

export const contractCategoryDefinition: EntityDefinition<ContractCategoryDto, TypeContext> = {
  kind: "contract_category",
  singular: "Kategorie",
  plural: "Kategorien",
  objectType: "catalog_contract_category",
  load: async (organizationSlug) => {
    const context = await loadTypes(organizationSlug);
    return { rows: context.categories, context };
  },
  loadContext: loadTypes,
  id: (row) => row.id,
  label: (row) => row.label,
  formLabel: (form) => text(form, "label"),
  active: (row) => row.is_active,
  searchText: (row, context) => `${row.label} ${row.description ?? ""} ${context.types.filter((type) => row.contract_type_ids.includes(type.id)).map((type) => type.label).join(" ")}`,
  columns: (context) => [
    { key: "label", label: "Kategorie", rowHeader: true, sortValue: (row) => row.label.toLocaleLowerCase("de"), render: (row) => row.label },
    { key: "types", label: "Vertragstypen", render: (row) => context.types.filter((type) => row.contract_type_ids.includes(type.id)).map((type) => type.label).join(", ") || <span className="field-hint">Keinem Typ zugeordnet</span> },
  ],
  fields: (context, _form, row) => [
    { key: "label", label: "Bezeichnung", required: true, maxLength: 160, wide: true },
    { key: "description", label: "Beschreibung", kind: "textarea", maxLength: 500 },
    {
      key: "contract_type_ids", label: "Gilt für Vertragstypen", kind: "checks",
      options: context.types.filter((type) => type.is_active || row?.contract_type_ids.includes(type.id)).map((type) => ({ value: type.id, label: type.label })),
      hint: "Beim Vertrag steht die Kategorie nur zu den hier gewählten Vertragstypen zur Auswahl.",
    },
  ],
  emptyForm: (_context, preset) => ({ label: "", description: "", contract_type_ids: [], ...preset }),
  toForm: (row) => ({ label: row.label, description: row.description ?? "", contract_type_ids: [...row.contract_type_ids] }),
  create: async (organizationSlug, form) => {
    const label = text(form, "label");
    const result = await createContractCategory(organizationSlug, {
      label, description: optional(form, "description"), contract_type_ids: Array.isArray(form.contract_type_ids) ? form.contract_type_ids : [],
    });
    const created = result.contract_categories.find((item) => item.label.toLocaleLowerCase("de") === label.toLocaleLowerCase("de"));
    return { id: created?.id ?? "" };
  },
  update: (organizationSlug, row, form) => updateContractCategory(organizationSlug, row.id, {
    label: text(form, "label"), description: optional(form, "description"), contract_type_ids: Array.isArray(form.contract_type_ids) ? form.contract_type_ids : [],
  }),
  setActive: (organizationSlug, row, active) => updateContractCategory(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "contract_category", value: row.label }),
  exportHeader: ["Kategorie", "Code", "Vertragstypen", "Aktiv"],
  exportRow: (row, context) => [row.label, row.code, context.types.filter((type) => row.contract_type_ids.includes(type.id)).map((type) => type.label).join(", "), row.is_active ? "ja" : "nein"],
};

// Auswahllisten teilen eine Definition; die Liste (field_key) kommt von der Seite.
export function lookupDefinition(fieldKey: string): EntityDefinition<LookupDto, null> {
  const label = LOOKUP_FIELD_LABEL[fieldKey] ?? fieldKey;
  return {
    kind: "lookup",
    singular: "Eintrag",
    plural: `Einträge „${label}“`,
    objectType: "lookup_value",
    load: async (organizationSlug) => {
      const data = await listLookups(organizationSlug, fieldKey, true);
      return { rows: data.items.filter((item) => item.field_key === fieldKey), context: null };
    },
    loadContext: async () => null,
    id: (row) => row.id,
    label: (row) => row.label,
    formLabel: (form) => text(form, "label"),
    active: (row) => row.is_active,
    searchText: (row) => `${row.label} ${row.code} ${row.description ?? ""}`,
    columns: () => [
      { key: "label", label: "Bezeichnung", rowHeader: true, sortValue: (row) => row.label.toLocaleLowerCase("de"), render: (row) => row.label },
      { key: "description", label: "Beschreibung", render: (row) => row.description || "–" },
      { key: "order", label: "Reihenfolge", numeric: true, sortValue: (row) => row.sort_order, render: (row) => row.sort_order },
    ],
    fields: () => [
      { key: "label", label: "Bezeichnung", required: true, maxLength: 160, wide: true },
      { key: "description", label: "Beschreibung", kind: "textarea", maxLength: 500 },
      { key: "sort_order", label: "Reihenfolge", kind: "number", min: 0, max: 9999, hint: "Kleinere Zahlen stehen in Auswahlfeldern weiter oben." },
    ],
    emptyForm: (_context, preset) => ({ label: "", description: "", sort_order: "", ...preset }),
    toForm: (row) => ({ label: row.label, description: row.description ?? "", sort_order: String(row.sort_order) }),
    create: (organizationSlug, form) => createLookup(organizationSlug, {
      field_key: fieldKey, label: text(form, "label"), description: optional(form, "description"),
      ...(text(form, "sort_order") ? { sort_order: Number(text(form, "sort_order")) } : {}),
    }),
    update: (organizationSlug, row, form) => updateLookup(organizationSlug, row.id, {
      label: text(form, "label"), description: optional(form, "description"),
      ...(text(form, "sort_order") ? { sort_order: Number(text(form, "sort_order")) } : {}),
    }),
    setActive: (organizationSlug, row, active) => updateLookup(organizationSlug, row.id, { is_active: active }),
    registerFilter: fieldKey === "storage_location" ? (row) => ({ column: "storage_location", value: row.label }) : undefined,
    importKind: "lookup",
    importColumns: [
      { key: "label", label: "Bezeichnung", aliases: ["name", "eintrag", "wert"], required: true },
      { key: "code", label: "Code", aliases: ["kürzel", "schlüssel"] },
      { key: "description", label: "Beschreibung", aliases: ["erläuterung", "hinweis"] },
    ],
    exportHeader: ["Bezeichnung", "Code", "Beschreibung", "Reihenfolge", "Aktiv"],
    exportRow: (row) => [row.label, row.code, row.description, row.sort_order, row.is_active ? "ja" : "nein"],
  };
}
