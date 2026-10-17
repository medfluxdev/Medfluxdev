/**
 * Einheiten von Einzelpreisen auf Deutsch. Die KI liefert teils Rohwerte wie `per_call`
 * (backend/app/models/contract.py: per_call, per_hour, per_device oder wörtliche Einheit);
 * die Oberfläche zeigt nie einen Rohwert.
 */
const UNIT_LABELS: Record<string, string> = {
  per_call: "je Abruf",
  per_visit: "je Einsatz",
  per_hour: "je Stunde",
  hourly: "je Stunde",
  per_day: "je Tag",
  daily: "je Tag",
  per_week: "je Woche",
  per_month: "je Monat",
  monthly: "je Monat",
  per_year: "je Jahr",
  yearly: "je Jahr",
  annual: "je Jahr",
  per_device: "je Gerät",
  per_piece: "je Stück",
  per_unit: "je Stück",
  per_km: "je km",
  per_kilometer: "je km",
  flat: "Pauschale",
  flat_rate: "Pauschale",
  lump_sum: "Pauschale",
};

const RAW_CODE = /^[a-z]+(?:[_ ][a-z]+)*$/;

function key(raw: string): string {
  return raw.trim().toLowerCase().replace(/[\s-]+/g, "_");
}

/**
 * Deutsche Einheit; ein deutscher Text („pro Stunde“) bleibt, wie er ist.
 * Unbekannter Rohcode (englisch, mit Unterstrich) → null, damit die Oberfläche „Einheit unbekannt“ zeigt statt des Codes.
 */
export function unitLabel(raw: string | null | undefined): string | null {
  if (!raw || !raw.trim()) return null;
  const known = UNIT_LABELS[key(raw)];
  if (known) return known;
  const value = raw.trim();
  if (value.includes("_") || (/^per\b/i.test(value) && RAW_CODE.test(value.toLowerCase()))) return null;
  return value;
}

/**
 * Bezeichnung eines Einzelpreises: Rohtitel wie „per call: 2.226,00 EUR“ (Einheit + Betrag statt Name)
 * werden zu „Einzelpreis je Abruf“; sonst bleibt die Bezeichnung aus dem Dokument bzw. der Pflege.
 */
export function serviceTitle(label: string, unit?: string | null): string {
  const match = /^\s*(per[\s_][a-z_ ]+?)\s*:\s*[\d.,\s]*(?:eur|€)?\s*$/i.exec(label);
  if (!match) return label;
  const fromLabel = unitLabel(match[1]);
  const fromUnit = unitLabel(unit);
  const text = fromLabel ?? fromUnit;
  return text ? `Einzelpreis ${text}` : "Einzelpreis";
}
