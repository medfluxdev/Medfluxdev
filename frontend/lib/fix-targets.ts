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

export function contractHref(contractId: string, raw?: FixTarget): string {
  const target = raw ? normalizeTarget(raw) : undefined;
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

// Felder, die nicht im Formular „Vertragsdaten“ stehen, sondern im Abschnitt „Zuständigkeit“ darunter.
const OWNERSHIP_FIELDS = new Set(["responsible_account_id", "cost_center_id", "hospital_id", "department_id"]);

/** Ziele vereinheitlichen: Zuständigkeitsfelder führen zum Abschnitt „Zuständigkeit“. */
export function normalizeTarget(target: FixTarget): FixTarget {
  if (target.field && OWNERSHIP_FIELDS.has(target.field)) return { tab: "register", section: "ownership" };
  return target;
}

// Abschnitt → Element (Überschrift) auf dem Reiter; sonst die Überschrift eines Vertragsdaten-Abschnitts.
const SECTION_ANCHORS: Record<string, string> = {
  ownership: "cw-ownership-heading",
  entries: "fin-entries-heading",
  suggestions: "fin-ai-heading",
  terms: "rg-terms-heading",
  rules: "rules-heading",
  renewal: "renewal-heading",
  deadlines: "rg-deadlines-heading",
  intelligence: "contract-intelligence-heading",
};

export function sectionAnchor(section: string): string {
  return SECTION_ANCHORS[section] ?? `rg-${section}-heading`;
}

const TABS = new Set<ContractTab>(["overview", "register", "deadlines", "finance", "documents", "relations", "history"]);

/** Ziel aus einer API-Antwort prüfen (unbekannte Werte werden ignoriert, nie geraten). */
export function asFixTarget(value: unknown): FixTarget | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  if (typeof raw.tab !== "string" || !TABS.has(raw.tab as ContractTab)) return null;
  return {
    tab: raw.tab as ContractTab,
    ...(typeof raw.subtab === "string" ? { subtab: raw.subtab as DocumentSubtab } : {}),
    ...(typeof raw.field === "string" ? { field: raw.field } : {}),
    ...(typeof raw.section === "string" ? { section: raw.section } : {}),
  };
}

/** Kurze Beschriftung für einen Link „dorthin“, passend zum Ort. */
export function fixLabel(target: FixTarget): string {
  const normalized = normalizeTarget(target);
  if (normalized.tab === "documents") return normalized.subtab === "review" ? "KI-Werte prüfen" : normalized.subtab === "attachments" ? "Dokument hinzufügen" : "Dokumente öffnen";
  if (normalized.tab === "finance") return "Kosten erfassen";
  if (normalized.section === "ownership") return "Zuständigkeit festlegen";
  if (normalized.section === "term") return "Laufzeit erfassen";
  if (normalized.field) return "Zum Feld";
  return "Öffnen";
}

// Aufgaben und Warnungen: wo sie erledigt werden (gleiche Zuordnung wie im Backend für Benachrichtigungen).
const DEADLINE_TARGET: FixTarget = { tab: "deadlines", section: "renewal" };
const WORK_ITEM_TARGETS: Record<string, FixTarget | null> = {
  manual_review: REVIEW_TARGET,
  missing_cost: FINANCE_ENTRIES_TARGET,
  equipment_coverage_review: { tab: "relations" },
  equipment_relationship_ambiguous: { tab: "relations" },
  cancellation_deadline: DEADLINE_TARGET,
  contract_expiry: DEADLINE_TARGET,
  automatic_renewal: DEADLINE_TARGET,
  contract_expired: DEADLINE_TARGET,
  sla_issue: null,
};
const WARNING_TARGETS: Record<string, FixTarget> = {
  missing_cost_data: FINANCE_ENTRIES_TARGET,
  cost_conflict: FINANCE_ENTRIES_TARGET,
  currency_conflict: FINANCE_ENTRIES_TARGET,
  unclear_contract_data: REVIEW_TARGET,
  manual_review_required: REVIEW_TARGET,
  calculation_conflict: REVIEW_TARGET,
  cancellation_deadline_approaching: DEADLINE_TARGET,
  cancellation_deadline_today: DEADLINE_TARGET,
  cancellation_deadline_passed: DEADLINE_TARGET,
  automatic_renewal_attention: DEADLINE_TARGET,
  contract_end_approaching: DEADLINE_TARGET,
  contract_expired: DEADLINE_TARGET,
};

/** Ziel einer Aufgabe; null = es gibt keinen Ort zum Beheben (z. B. SLA-Hinweis). */
export function workItemTarget(itemType: string, requiresReview = false): FixTarget | null {
  if (requiresReview) return REVIEW_TARGET;
  return itemType in WORK_ITEM_TARGETS ? WORK_ITEM_TARGETS[itemType] : null;
}

export function warningTarget(warningType: string, requiresReview = false): FixTarget | null {
  if (requiresReview) return REVIEW_TARGET;
  return WARNING_TARGETS[warningType] ?? null;
}

// Listenfilter für „fehlt“ an einem Ort (vorher mehrfach von Hand gebaut).
export const NOT_EVALUABLE_FILTERS: GridFilter[] = [{ column: "term_status", op: "in", value: ["Unvollständig"] }];
export const NO_FINANCE_FILTERS: GridFilter[] = [{ column: "cost_current_year", op: "empty" }];

/** Verträge ohne berechenbare Frist: ein einzelner direkt in seine Laufzeitangaben, sonst die gefilterte Liste. */
export function notEvaluableLink(items: { contract_id: string }[]): string {
  return items.length === 1 ? contractHref(items[0].contract_id, { tab: "register", section: "term" }) : registerHref(NOT_EVALUABLE_FILTERS);
}

const EMPTY_COLUMN_TARGETS: Record<string, FixTarget> = {
  annual_cost: FINANCE_ENTRIES_TARGET,
  cost_current_year: FINANCE_ENTRIES_TARGET,
  reminder_recipient: { tab: "register", field: "reminder_recipient_account_id" },
  responsible: { tab: "register", section: "ownership" },
  hospital: { tab: "register", section: "ownership" },
  department: { tab: "register", section: "ownership" },
  cost_center: { tab: "register", section: "ownership" },
  partner: { tab: "register", field: "partner_id" },
  contract_type: { tab: "register", field: "contract_type_id" },
  cancel_by: { tab: "register", section: "term" },
  possible_end: { tab: "register", section: "term" },
};

/**
 * Vertragsliste: wohin ein Vertrag aus einer gefilterten Liste führt. Ist die Liste nach einer Lücke gefiltert
 * („ohne Kosten“, „ohne Verantwortliche“, „Laufzeit unvollständig“ …), öffnet der Vertrag dort, wo sie behoben wird.
 */
export function listRowTarget(filters: GridFilter[]): FixTarget {
  for (const filter of filters) {
    if (filter.column === "review_pending" && filter.op === "is" && filter.value === true) return REVIEW_TARGET;
  }
  for (const filter of filters) {
    if (filter.op === "empty" && EMPTY_COLUMN_TARGETS[filter.column]) return EMPTY_COLUMN_TARGETS[filter.column];
  }
  for (const filter of filters) {
    if (filter.column === "term_status") return { tab: "register", section: "term" };
    if (filter.column === "rules_status" || filter.column === "rules_violated") return { tab: "register", section: "rules" };
    if (filter.column === "deletion_from") return { tab: "register", section: "protection" };
    if (filter.column === "cancel_by") return { tab: "deadlines", section: "renewal" };
  }
  return { tab: "register" };
}
