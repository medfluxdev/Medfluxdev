/**
 * Abschnitte je Vertragstyp (Plan docs/architecture/VERTRAGSPROFIL_ABSCHNITTE_PLAN_20261011.md).
 * Nur Darstellung: ein nicht vorgesehener Abschnitt wird ausgeblendet, solange er leer ist.
 */

export type SectionKey = "scope" | "sla" | "maintenance" | "equipment";

export const SECTION_KEYS: SectionKey[] = ["scope", "sla", "maintenance", "equipment"];

export const SECTION_LABELS: Record<SectionKey, string> = {
  scope: "Leistungsumfang",
  sla: "SLA",
  maintenance: "Wartung",
  equipment: "Geräte",
};

/** Lesemodell der Vertragsakte; null = kein Vertragstyp (alle Abschnitte). */
export type ContractSections = { type_label: string } & Record<SectionKey, boolean>;

/** Sichtbar, wenn ohne Typ, vom Typ vorgesehen oder mit Inhalt (Daten nie verstecken). */
export function sectionVisible(key: SectionKey, sections: ContractSections | null | undefined, hasData: boolean): boolean {
  return !sections || sections[key] || hasData;
}
