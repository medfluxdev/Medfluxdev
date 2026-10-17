/**
 * „Weitere inklusive Leistungen“ thematisch zusammenfassen – feste Stichwörter, nichts geraten:
 * eine Leistung landet in der ersten Gruppe, deren Stichwort im Text vorkommt, sonst unter „Weitere“.
 * Reihenfolge der Leistungen bleibt wie im Dokument.
 */
const GROUPS: { label: string; words: string[] }[] = [
  { label: "Prüfung & Sicherheit", words: ["prüf", "sicherheit", "test", "kontroll", "messung", "iec", "dguv", "stk", "mtk", "inspektion", "sichtprüf", "funktionsprüf"] },
  { label: "Wartung & Verschleißteile", words: ["wartung", "austausch", "verschleiß", "verschleiss", "akku", "batterie", "ersatzteil", "filter", "reinig", "kalibrier", "justier", "leuchte", "lüfter"] },
  { label: "Software & Hardware", words: ["software", "update", "firmware", "hardware", "fcn", "field change", "upgrade", "patch"] },
  { label: "Service & Support", words: ["support", "hotline", "fernwartung", "remote", "schulung", "einweisung", "dokumentation", "bericht", "anfahrt", "reise", "notdienst", "techniker"] },
];
export const OTHER_GROUP = "Weitere";

export function groupServices(items: string[]): { label: string; items: string[] }[] {
  const buckets = new Map<string, string[]>();
  for (const item of items) {
    const text = item.toLocaleLowerCase("de-DE");
    const label = GROUPS.find((group) => group.words.some((word) => text.includes(word)))?.label ?? OTHER_GROUP;
    buckets.set(label, [...(buckets.get(label) ?? []), item]);
  }
  return [...GROUPS.map((group) => group.label), OTHER_GROUP]
    .filter((label) => buckets.has(label))
    .map((label) => ({ label, items: buckets.get(label)! }));
}
