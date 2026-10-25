// Deterministische deutsche Präsentations-Helfer. Keine Geschäftslogik hängt
// von diesen formatierten Strings ab – sie sind reine Anzeige.

const dateFmt = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function formatDate(value: string | null | undefined): string {
  if (!value) return "–";
  const source = value.trim();
  if (!source) return "–";
  if (/^\d{4}-\d{2}-\d{2}$/.test(source)) {
    // Reine Datumsangabe: lokal auswerten (bisheriges Verhalten beibehalten).
    const d = new Date(`${source}T00:00:00`);
    if (Number.isNaN(d.getTime())) return "–";
    return dateFmt.format(d);
  }
  // Vollständiger Zeitstempel (z. B. archived_at / created_at mit Zeitzone):
  // ein künstlich angehängtes "T00:00:00" würde den Wert unlesbar machen und
  // zu "Invalid time value" führen – daher direkt parsen.
  const d = new Date(source);
  if (Number.isNaN(d.getTime())) return "–";
  return dateFmt.format(d);
}

const dateTimeFmt = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "–";
  return dateTimeFmt.format(d);
}

/**
 * Betrag oder Prozentwert aus freier Eingabe lesen: „2 060,00 €“, „2.060,00“, „2060.5“, „19 %“ → „2060.00“ / „19“.
 * Leerzeichen jeder Art (auch geschützte), Währungs- und Prozentzeichen werden ignoriert; nicht lesbar → null.
 */
export function parseDecimalInput(raw: string | null | undefined): string | null {
  const value = String(raw ?? "").replace(/[\s  €%]|EUR/gi, "");
  if (!value) return null;
  const normalized = value.includes(",") ? value.replace(/\./g, "").replace(",", ".") : value;
  return /^-?\d+(\.\d+)?$/.test(normalized) ? normalized : null;
}

export function formatCurrency(amount: string, currency: string): string {
  const number = Number(amount);
  if (!Number.isFinite(number)) return "–";
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency,
  }).format(number);
}

// Abdeckung einer Summe: wie viele Verträge einen gepflegten Wert haben.
// Leer, wenn alle bekannt sind oder es keine Verträge gibt.
export function coverageNote(known: number | undefined, missing: number | undefined, valueUnknown = false): string {
  const k = known ?? 0;
  const m = missing ?? 0;
  if (k + m === 0) return "";
  if (valueUnknown && k === 0) return `Keine gepflegten Kostendaten (${m} ${m === 1 ? "Vertrag" : "Verträge"})`;
  if (m === 0) return "";
  return `bekannt für ${k} von ${k + m} Verträgen`;
}

// "in 14 Tagen" / "heute" / "seit 3 Tagen überfällig"
export function formatDaysRemaining(days: number | null | undefined): string {
  if (days == null) return "Termin unbekannt";
  if (days === 0) return "heute";
  if (days > 0) return `in ${days} Tagen`;
  return `seit ${Math.abs(days)} Tagen überfällig`;
}

export function formatISODateOnly(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export type AnnualCostInput = {
  currency: string | null;
  amount: string | number | null;
  unreliable: boolean;
};

// Fehlende/ungeeignete Jahreskosten NIE als 0 € anzeigen.
export function formatAnnualCost(
  finance: AnnualCostInput | null | undefined
): string {
  if (!finance || finance.unreliable || finance.amount == null || !finance.currency) {
    return finance && finance.unreliable
      ? "Nicht eindeutig"
      : "Nicht verfügbar";
  }
  return formatCurrency(String(finance.amount), finance.currency);
}

export const STATUS_LABEL: Record<string, string> = {
  active: "Aktiv",
  expiring_soon: "Bald auslaufend",
  expired: "Ausgelaufen",
  terminated: "Gekündigt",
  unknown: "Unbekannt",
};

export const RISK_LABEL: Record<string, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  unknown: "Unbekannt",
};

