import type { DeviceTypeDto } from "@/lib/domain-api/deviceTypes";

// Welche Gerätearten zu den Abteilungen eines Vertrags passen – eine Regel für die Organisationszuordnung
// und den Kasten „Geräte“. Passend ist eine Geräteart, die einer gewählten Abteilung zugeordnet ist oder deren
// Bereich so heißt wie die Abteilung oder eine übergeordnete (z. B. „Medizintechnik › Radiologie“ → Medizintechnik,
// „IT-Abteilung“ → IT). Das ordnet nur die Auswahl; wählbar bleiben alle aktiven Gerätearten.

export type ContractDepartmentContext = { id: string | null; path: string };
export type DeviceTypeGroup = { label: string; items: DeviceTypeDto[] };

export const MATCHING_GROUP_LABEL = "Passend zu den Abteilungen";

function words(text: string) {
  return new Set(text.toLowerCase().split(/[^a-zäöüß]+/).filter(Boolean));
}

export function deviceTypeMatches(item: DeviceTypeDto, departments: ContractDepartmentContext[]) {
  const ids = new Set(departments.map((department) => department.id).filter(Boolean));
  if (item.department_id && ids.has(item.department_id)) return true;
  // Ohne Kennung (nur Name bekannt): Zuordnung über den Namen der zuständigen Abteilung.
  if (item.department_name && departments.some((department) => !department.id && department.path.split(" › ").pop() === item.department_name)) return true;
  if (item.area === "sonstiges") return false;
  const known = new Set<string>();
  departments.forEach((department) => words(department.path).forEach((word) => known.add(word)));
  return Array.from(words(item.area_label)).every((word) => known.has(word));
}

/** Auswahlgruppen: passende zuerst, dann die übrigen nach Bereich. Bereits gewählte fehlen. */
export function deviceTypeGroups(catalog: DeviceTypeDto[], chosen: Iterable<string>, departments: ContractDepartmentContext[]): DeviceTypeGroup[] {
  const taken = new Set(chosen);
  const available = catalog.filter((item) => item.is_active && !taken.has(item.id));
  const matching = departments.length ? available.filter((item) => deviceTypeMatches(item, departments)) : [];
  const rest = available.filter((item) => !matching.includes(item));
  const areas = Array.from(new Set(rest.map((item) => item.area_label)));
  return [
    ...(matching.length ? [{ label: MATCHING_GROUP_LABEL, items: matching }] : []),
    ...areas.map((area) => ({ label: area, items: rest.filter((item) => item.area_label === area) })),
  ];
}
