import type { GridFilter } from "@/lib/domain-api/registerGrid";

// „Direkt zur Stelle“: jede Meldung über eine fehlende Angabe trägt ein Ziel, an dem sie behoben wird.
// Alle Links in eine Vertragsakte oder in die gefilterte Vertragsliste entstehen hier.

export type ContractTab = "overview" | "register" | "deadlines" | "finance" | "documents" | "relations" | "history";
export type DocumentSubtab = "document" | "evidence" | "review" | "attachments" | "history";

export interface FixTarget {
  tab: ContractTab;
  subtab?: DocumentSubtab;
  /** Feld in „Vertragsdaten“ (öffnet die Bearbeitung und setzt den Cursor), z. B. "term_start_date". */
  field?: string;
  /** Abschnitt auf dem Reiter, z. B. "entries" unter „Finanzen“. */
  section?: string;
}

/** Adressparameter für Feld und Abschnitt in der Vertragsakte. */
export const FIELD_PARAM = "feld";
export const SECTION_PARAM = "abschnitt";

const PERIOD_KEYS = new Set(["initial_term", "minimum_term", "notice_period", "renewal_period"]);

/** Zeiträume bestehen aus Anzahl und Einheit; Meldungen nennen „notice_period_value“, das Feld heißt „notice_period“. */
export function baseFieldKey(key: string): string {
  const base = key.replace(/_(value|unit)$/, "");
  return PERIOD_KEYS.has(base) ? base : key;
}

export function registerField(key: string): FixTarget {
  return { tab: "register", field: baseFieldKey(key) };
}

export const REVIEW_TARGET: FixTarget = { tab: "documents", subtab: "review" };
export const FINANCE_ENTRIES_TARGET: FixTarget = { tab: "finance", section: "entries" };

export function contractHref(contractId: string, target?: FixTarget): string {
  const params = new URLSearchParams();
  if (target && target.tab !== "overview") params.set("tab", target.tab);
  if (target?.tab === "documents" && target.subtab) params.set("subtab", target.subtab);
  if (target?.field) params.set(FIELD_PARAM, baseFieldKey(target.field));
  if (target?.section) params.set(SECTION_PARAM, target.section);
  const query = params.toString();
  return `/contracts/${encodeURIComponent(contractId)}${query ? `?${query}` : ""}`;
}

/** Vertragsliste mit Filtern (und optional Reiter), gleiche Adressform wie die Liste selbst. */
export function registerHref(filters: GridFilter[], extra?: Record<string, string>): string {
  const params = new URLSearchParams(extra);
  if (filters.length) params.set("filter", JSON.stringify(filters));
  const query = params.toString();
  return `/register${query ? `?${query}` : ""}`;
}
