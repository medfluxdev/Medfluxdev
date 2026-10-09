import {
  createPartner,
  findSimilarPartners,
  listLookups,
  listPartners,
  updatePartner,
  type LookupDto,
  type PartnerDto,
  type PartnerValues,
} from "@/lib/domain-api/catalogs";
import { optional, text, type EntityDefinition, type FieldDef, type FormValues } from "../types";

export interface PartnerContext {
  industries: LookupDto[];
}

const PAGE = 500;

// Alle Vertragspartner seitenweise laden (die API liefert hoechstens 500 je Abruf).
export async function loadAllPartners(organizationSlug: string, includeInactive = true): Promise<PartnerDto[]> {
  const rows: PartnerDto[] = [];
  for (let offset = 0; ; offset += PAGE) {
    const page = await listPartners(organizationSlug, { includeInactive, limit: PAGE, offset });
    rows.push(...page.items);
    if (page.items.length < PAGE || rows.length >= page.total) return rows;
  }
}

const TEXT_FIELDS: (FieldDef & { key: keyof PartnerValues })[] = [
  { key: "short_name", label: "Kurzname", required: true, maxLength: 120, section: "Name", hint: "Eindeutig; erscheint in Listen und Auswahlfeldern." },
  { key: "name1", label: "Name", required: true, maxLength: 255, section: "Name" },
  { key: "name2", label: "Namenszusatz", maxLength: 255, section: "Name" },
  { key: "street", label: "Straße", maxLength: 255, section: "Adresse", wide: true },
  { key: "postal_code", label: "PLZ", maxLength: 16, section: "Adresse" },
  { key: "city", label: "Ort", maxLength: 120, section: "Adresse" },
  { key: "country", label: "Land", maxLength: 80, section: "Adresse" },
  { key: "po_box", label: "Postfach", maxLength: 40, section: "Adresse" },
  { key: "po_box_postal_code", label: "PLZ Postfach", maxLength: 16, section: "Adresse" },
  { key: "phone", label: "Telefon", maxLength: 80, section: "Kontakt" },
  { key: "fax", label: "Fax", maxLength: 80, section: "Kontakt" },
  { key: "email", label: "E-Mail", kind: "email", maxLength: 320, section: "Kontakt" },
  { key: "website", label: "Internet", kind: "url", maxLength: 255, section: "Kontakt" },
  { key: "vat_id", label: "USt-IdNr.", maxLength: 40, section: "Weiteres" },
  { key: "partner_type", label: "Partnerart", maxLength: 64, section: "Weiteres", hint: "z. B. Lieferant, Dienstleister, Kooperationspartner" },
];

const VALUE_KEYS = [...TEXT_FIELDS.map((field) => field.key), "industry_code", "note"] as const;

function toValues(form: FormValues): PartnerValues {
  const values: Record<string, string | null> = {};
  for (const key of VALUE_KEYS) values[key] = optional(form, key);
  return values as PartnerValues;
}

export function partnerFields(context: PartnerContext): FieldDef[] {
  return [
    ...TEXT_FIELDS,
    {
      key: "industry_code", label: "Branche", kind: "select", section: "Weiteres", emptyOption: "Keine Angabe",
      options: context.industries.map((item) => ({ value: item.code, label: item.label })),
    },
    { key: "note", label: "Notiz", kind: "textarea", section: "Weiteres" },
  ];
}

export function emptyPartnerForm(preset?: FormValues): FormValues {
  const form: FormValues = {};
  for (const key of VALUE_KEYS) form[key] = "";
  return { ...form, ...preset };
}

export async function createPartnerFromForm(organizationSlug: string, form: FormValues, force: boolean) {
  const values = toValues(form);
  if (!values.name1) values.name1 = values.short_name;
  return createPartner(organizationSlug, values, force);
}

export async function similarPartnerNames(organizationSlug: string, form: FormValues) {
  const name = text(form, "name1") || text(form, "short_name");
  if (!name) return [];
  const found = await findSimilarPartners(organizationSlug, name);
  return found.items.map((item) => `${item.short_name}${item.city ? ` (${item.city})` : ""}`);
}

export async function loadPartnerContext(organizationSlug: string): Promise<PartnerContext> {
  const lookups = await listLookups(organizationSlug, "industry").catch(() => ({ items: [] as LookupDto[], field_keys: [] }));
  return { industries: lookups.items };
}

export const partnerDefinition: EntityDefinition<PartnerDto, PartnerContext> = {
  kind: "partner",
  singular: "Vertragspartner",
  plural: "Vertragspartner",
  objectType: "contract_partner",
  load: async (organizationSlug) => {
    const [rows, context] = await Promise.all([loadAllPartners(organizationSlug), loadPartnerContext(organizationSlug)]);
    return { rows, context };
  },
  loadContext: loadPartnerContext,
  id: (row) => row.id,
  label: (row) => row.short_name,
  formLabel: (form) => text(form, "short_name"),
  active: (row) => row.is_active,
  searchText: (row) => [row.short_name, row.name1, row.name2, row.city, row.postal_code, row.email, row.vat_id].filter(Boolean).join(" "),
  columns: () => [
    { key: "short_name", label: "Kurzname", rowHeader: true, sortValue: (row) => row.short_name.toLocaleLowerCase("de"), render: (row) => row.short_name },
    { key: "name", label: "Name", sortValue: (row) => row.display_name.toLocaleLowerCase("de"), render: (row) => row.display_name },
    { key: "city", label: "Ort", sortValue: (row) => row.city ?? "", render: (row) => [row.postal_code, row.city].filter(Boolean).join(" ") || "–" },
    { key: "contact", label: "Kontakt", render: (row) => [row.phone, row.email].filter(Boolean).join(" · ") || "–" },
  ],
  fields: (context) => partnerFields(context),
  emptyForm: (_context, preset) => emptyPartnerForm(preset),
  toForm: (row) => {
    const form: FormValues = {};
    for (const key of VALUE_KEYS) form[key] = String(row[key] ?? "");
    return form;
  },
  create: async (organizationSlug, form, { force }) => createPartnerFromForm(organizationSlug, form, force),
  update: (organizationSlug, row, form) => updatePartner(organizationSlug, row.id, toValues(form)),
  setActive: (organizationSlug, row, active) => updatePartner(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "partner", value: row.short_name }),
  findSimilar: similarPartnerNames,
  importKind: "partner",
  importColumns: [
    { key: "short_name", label: "Kurzname", aliases: ["kurzbezeichnung", "kürzel", "suchname"], required: true },
    { key: "name1", label: "Name", aliases: ["name 1", "firma", "firmenname"] },
    { key: "name2", label: "Namenszusatz", aliases: ["name 2"] },
    { key: "street", label: "Straße", aliases: ["strasse", "anschrift"] },
    { key: "postal_code", label: "PLZ", aliases: ["postleitzahl"] },
    { key: "city", label: "Ort", aliases: ["stadt"] },
    { key: "country", label: "Land" },
    { key: "phone", label: "Telefon", aliases: ["tel", "tel."] },
    { key: "fax", label: "Fax" },
    { key: "email", label: "E-Mail", aliases: ["email", "mail"] },
    { key: "website", label: "Internet", aliases: ["webseite", "homepage", "web"] },
    { key: "vat_id", label: "USt-IdNr.", aliases: ["ust-idnr", "ustid", "umsatzsteuer-id"] },
    { key: "partner_type", label: "Partnerart" },
    { key: "note", label: "Notiz", aliases: ["bemerkung"] },
  ],
  exportHeader: ["Kurzname", "Name", "Namenszusatz", "Straße", "PLZ", "Ort", "Land", "Telefon", "E-Mail", "Internet", "USt-IdNr.", "Partnerart", "Aktiv"],
  exportRow: (row) => [row.short_name, row.name1, row.name2, row.street, row.postal_code, row.city, row.country, row.phone, row.email, row.website, row.vat_id, row.partner_type, row.is_active ? "ja" : "nein"],
  intro: "Doppelte Partner lassen sich zusammenführen; deaktivierte Partner bleiben an bestehenden Verträgen erhalten.",
};
