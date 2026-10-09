import { LOOKUP_FIELD_LABEL } from "@/lib/lookup-fields";
import type { MasterDataKind } from "@/lib/domain-api/masterData";
import type { PermissionKey } from "@/lib/use-permissions";

// Alle Stammdaten an einem Ort: Bereiche, Adressen und Rechte.

export type MasterDataGroup = "Partner" | "Organisation" | "Vertragsdaten";

export interface MasterDataSection {
  slug: string;
  href: string;
  kind: MasterDataKind;
  group: MasterDataGroup;
  label: string;
  description: string;
  permission: PermissionKey;
  /** Wer pflegen darf, in Worten (Hinweis fuer Benutzer ohne Recht). */
  editors: string;
  fieldKey?: string;
}

export const MASTER_DATA_HOME = "/stammdaten";

const PARTNER_EDITORS = "Vertragsmanagement und Administration";
const ADMINS = "Administration";

export const MASTER_DATA_SECTIONS: MasterDataSection[] = [
  {
    slug: "vertragspartner", href: "/stammdaten/vertragspartner", kind: "partner", group: "Partner",
    label: "Vertragspartner", description: "Lieferanten, Dienstleister und Kooperationspartner",
    permission: "partner.edit", editors: PARTNER_EDITORS,
  },
  {
    slug: "krankenhaeuser", href: "/stammdaten/krankenhaeuser", kind: "hospital", group: "Organisation",
    label: "Krankenhäuser", description: "Gesellschaften und Standorte",
    permission: "organization.admin", editors: ADMINS,
  },
  {
    slug: "abteilungen", href: "/stammdaten/abteilungen", kind: "department", group: "Organisation",
    label: "Abteilungen", description: "Kliniken, Abteilungen, Stationen und Bereiche",
    permission: "organization.admin", editors: ADMINS,
  },
  {
    slug: "kostenstellen", href: "/stammdaten/kostenstellen", kind: "cost_center", group: "Organisation",
    label: "Kostenstellen", description: "Kostenstellen für die Kostenaufteilung",
    permission: "organization.admin", editors: ADMINS,
  },
  {
    slug: "vertragstypen", href: "/stammdaten/vertragstypen", kind: "contract_type", group: "Vertragsdaten",
    label: "Vertragstypen", description: "Einordnung, Vertraulichkeit und Aufbewahrung",
    permission: "catalog.admin", editors: ADMINS,
  },
  {
    slug: "kategorien", href: "/stammdaten/kategorien", kind: "contract_category", group: "Vertragsdaten",
    label: "Kategorien", description: "Feinere Einordnung je Vertragstyp",
    permission: "catalog.admin", editors: ADMINS,
  },
  {
    slug: "vertragsregeln", href: "/stammdaten/vertragsregeln", kind: "rule", group: "Vertragsdaten",
    label: "Vertragsregeln", description: "Anforderungen, die jeder Vertrag erfüllen soll",
    permission: "catalog.admin", editors: ADMINS,
  },
  ...Object.entries(LOOKUP_FIELD_LABEL).map(([fieldKey, label]): MasterDataSection => ({
    slug: `auswahllisten/${fieldKey}`, href: `/stammdaten/auswahllisten/${fieldKey}`, kind: "lookup", group: "Vertragsdaten",
    label, description: "Auswahlliste", permission: "catalog.admin", editors: ADMINS, fieldKey,
  })),
];

export const MASTER_DATA_GROUPS: MasterDataGroup[] = ["Partner", "Organisation", "Vertragsdaten"];

export function masterDataSection(slug: string): MasterDataSection | undefined {
  return MASTER_DATA_SECTIONS.find((section) => section.slug === slug);
}

export function masterDataSectionForLookup(fieldKey: string): MasterDataSection | undefined {
  return MASTER_DATA_SECTIONS.find((section) => section.fieldKey === fieldKey);
}

// Link in die Vertragsliste, gefiltert auf einen Stammdaten-Wert (Spalte der Registeransicht).
export function registerLink(column: string, value: string, op: "in" | "contains" = "in"): string {
  const filter = op === "contains" ? { column, op, value } : { column, op, value: [value] };
  return `/register?filter=${encodeURIComponent(JSON.stringify([filter]))}`;
}
