// Relative Zeitangaben für Terminlisten („in 8 Wochen“, „4 Wochen vor Vertragsende“).
// Reine Funktionen auf ISO-Datumswerten (YYYY-MM-DD); „heute“ kommt immer von außen.

const DAY_MS = 86_400_000;

function utcDay(iso: string): number {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

/** Tage von `from` bis `to` (positiv = `to` liegt später). */
export function daysBetween(from: string, to: string): number {
  return Math.round((utcDay(to) - utcDay(from)) / DAY_MS);
}

type Unit = "day" | "week" | "month" | "year";

const WORDS: Record<Unit, { one: string; many: string }> = {
  day: { one: "Tag", many: "Tagen" },
  week: { one: "Woche", many: "Wochen" },
  month: { one: "Monat", many: "Monaten" },
  year: { one: "Jahr", many: "Jahren" },
};

// „vor“ bei Vorlauf: „4 Wochen vor …“ (Nominativ Plural).
const LEAD_WORDS: Record<Unit, { one: string; many: string }> = {
  day: { one: "Tag", many: "Tage" },
  week: { one: "Woche", many: "Wochen" },
  month: { one: "Monat", many: "Monate" },
  year: { one: "Jahr", many: "Jahre" },
};

function amount(days: number): { n: number; unit: Unit } {
  if (days <= 14) return { n: days, unit: "day" };
  if (days <= 84) return { n: Math.round(days / 7), unit: "week" };
  return { n: Math.round(days / 30.4375), unit: "month" };
}

/** Volle Kalendermonate zwischen zwei Daten (früheres zuerst). */
function calendarMonths(from: string, to: string): number {
  const [y1, m1, d1] = from.slice(0, 10).split("-").map(Number);
  const [y2, m2, d2] = to.slice(0, 10).split("-").map(Number);
  return (y2 - y1) * 12 + (m2 - m1) - (d2 < d1 ? 1 : 0);
}

/**
 * Zeit von heute bis zum Datum: „heute“, „morgen“, „gestern“, „in N Tagen“ (≤ 14 Tage),
 * „in N Wochen“ (≤ 12 Wochen), „in N Monaten“, „in N Jahren“; Vergangenes mit „vor …“.
 */
export function formatRelativeDate(date: string, today: string): string {
  const days = daysBetween(today, date);
  if (days === 0) return "heute";
  if (days === 1) return "morgen";
  if (days === -1) return "gestern";
  const prefix = days > 0 ? "in" : "vor";
  const { n, unit } = amount(Math.abs(days));
  if (unit !== "month" || n < 12) return `${prefix} ${n} ${n === 1 ? WORDS[unit].one : WORDS[unit].many}`;
  // Ab einem Jahr: „in 2 Jahren, 5 Monaten“ (volle Kalendermonate).
  const months = days > 0 ? calendarMonths(today, date) : calendarMonths(date, today);
  const years = Math.floor(months / 12);
  const rest = months % 12;
  const yearText = `${years} ${years === 1 ? WORDS.year.one : WORDS.year.many}`;
  return rest ? `${prefix} ${yearText}, ${rest} ${rest === 1 ? WORDS.month.one : WORDS.month.many}` : `${prefix} ${yearText}`;
}

function isMonthEnd(iso: string): boolean {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month, 0)).getUTCDate() === day;
}

/** Ganze Kalendermonate zwischen zwei Daten (gleicher Tag im Monat oder beide Monatsende), sonst null. */
function wholeMonths(from: string, to: string): number | null {
  const [y1, m1, d1] = from.slice(0, 10).split("-").map(Number);
  const [y2, m2, d2] = to.slice(0, 10).split("-").map(Number);
  if (d1 !== d2 && !(isMonthEnd(from) && isMonthEnd(to))) return null;
  return (y2 - y1) * 12 + (m2 - m1);
}

/**
 * Vorlauf einer Erinnerung vor ihrem Termin: „4 Wochen vor Vertragsende“, „3 Monate vor Kündbar bis“.
 * Ganze Monate und ganze Wochen werden als solche genannt, sonst Tage.
 */
export function formatLeadTime(date: string, anchor: string, anchorLabel: string): string {
  const days = daysBetween(date, anchor);
  if (days <= 0) return days === 0 ? `am Tag von ${anchorLabel}` : `nach ${anchorLabel}`;
  const months = days > 27 ? wholeMonths(date, anchor) : null;
  let n: number;
  let unit: Unit;
  if (months && months % 12 === 0) { n = months / 12; unit = "year"; }
  else if (months) { n = months; unit = "month"; }
  else if (days % 7 === 0) { n = days / 7; unit = "week"; }
  else { n = days; unit = "day"; }
  return `${n} ${n === 1 ? LEAD_WORDS[unit].one : LEAD_WORDS[unit].many} vor ${anchorLabel}`;
}
