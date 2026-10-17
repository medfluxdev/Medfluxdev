import type { GridFilter } from "@/lib/domain-api/registerGrid";

// „Direkt zur Stelle“: jede Meldung über eine fehlende Angabe trägt ein Ziel, an dem sie behoben wird.
// Alle Links in eine Vertragsakte oder in die gefilterte Vertragsliste entstehen hier.

export type ContractTab = "overview" | "register" | "services" | "deadlines" | "finance" | "documents" | "relations" | "history";
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
export const FINANCE_SUGGESTIONS_TARGET: FixTarget = { tab: "finance", section: "suggestions" };
/** Reiter „Leistungen & SLA“: Leistungsumfang bzw. SLA. */
export const SCOPE_TARGET: FixTarget = { tab: "services", section: "leistungsumfang" };
export const SLA_TARGET: FixTarget = { tab: "services", section: "sla" };

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

/** Parameter: Dialog „Erneut aus dem Dokument erfassen“ für dieses Vertragsdaten-Feld öffnen. */
export const SEARCH_PARAM = "suchen";
/** Wert für SEARCH_PARAM: alle fehlenden Angaben („Was fehlt noch?“, Strg+K). */
export const MISSING_SEARCH = "fehlende";

/** „Im Dokument suchen“: Dokumente → Dokument, Dialog mit diesem Feld vorausgewählt. */
export function documentSearchHref(contractId: string, fieldKey: string): string {
  return `${contractHref(contractId, { tab: "documents", subtab: "document", section: "reextraction" })}&${SEARCH_PARAM}=${encodeURIComponent(baseFieldKey(fieldKey))}`;
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

// Felder der Erinnerungseinstellungen in „Fristen & Aufgaben“ → „Termine & Aufgaben“ (nicht in den Vertragsdaten).
const DEADLINE_FIELDS = new Set(["reminder_lead_months", "reminder_extra_leads", "reminder_recipient_account_id", "escalation_recipient_account_id"]);
const DEADLINE_SECTIONS = new Set(["reminder"]);
// Felder des Reiters „Leistungen & SLA“ (nie in den Vertragsdaten).
const SERVICE_FIELDS = new Set(["service_scope_text", "sla_availability_percent", "penalty_terms"]);
const SERVICE_SECTIONS = new Set(["service", "leistungsumfang", "sla"]);

/** Ziele vereinheitlichen: Zuständigkeitsfelder führen zum Abschnitt „Zuständigkeit“, Erinnerungen zu „Fristen & Aufgaben“. */
// Statuswechsel und Kündigungsdaten stehen in der Karte „Vertragsstatus“ auf der Übersicht.
const STATUS_FIELDS = new Set(["business_status", "terminated_on", "terminated_effective"]);

export function normalizeTarget(target: FixTarget): FixTarget {
  if (target.field && STATUS_FIELDS.has(target.field)) return { tab: "overview", section: "status" };
  if ((target.tab === "register" || target.tab === "overview") && !target.field && target.section === "status") return { tab: "overview", section: "status" };
  if (target.field && OWNERSHIP_FIELDS.has(target.field)) return { tab: "register", section: "ownership" };
  if (target.tab === "register" && target.field && DEADLINE_FIELDS.has(target.field)) return { ...target, tab: "deadlines" };
  if (target.tab === "register" && !target.field && target.section && DEADLINE_SECTIONS.has(target.section)) return { ...target, tab: "deadlines" };
  if (target.field && SERVICE_FIELDS.has(target.field)) return { ...target, tab: "services" };
  if ((target.tab === "register" || target.tab === "overview") && !target.field && target.section && SERVICE_SECTIONS.has(target.section)) return { ...target, tab: "services" };
  return target;
}

// Abschnitt → Element (Überschrift) auf dem Reiter; sonst die Überschrift eines Vertragsdaten-Abschnitts.
const SECTION_ANCHORS: Record<string, string> = {
  ownership: "cw-ownership-heading",
  entries: "fin-entries-heading",
  suggestions: "fin-ai-heading",
  terms: "rg-term-heading",
  rules: "rules-heading",
  renewal: "dec-heading",
  decision: "dec-heading",
  deadlines: "tl-heading",
  intelligence: "contract-intelligence-heading",
  "offene-punkte": "open-points-heading",
  widerspruch: "conflict-heading",
  leistungsumfang: "leistungsumfang-heading",
  sla: "sla-heading",
};

export function sectionAnchor(section: string): string {
  return SECTION_ANCHORS[section] ?? `rg-${section}-heading`;
}

const TABS = new Set<ContractTab>(["overview", "register", "services", "deadlines", "finance", "documents", "relations", "history"]);

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
/** „Widerspruch klären“ auf der Übersicht. */
export const CONFLICT_TARGET: FixTarget = { tab: "overview", section: "widerspruch" };

const WARNING_TARGETS: Record<string, FixTarget> = {
  missing_cost_data: FINANCE_ENTRIES_TARGET,
  cost_conflict: FINANCE_ENTRIES_TARGET,
  currency_conflict: FINANCE_ENTRIES_TARGET,
  unclear_contract_data: REVIEW_TARGET,
  manual_review_required: REVIEW_TARGET,
  calculation_conflict: CONFLICT_TARGET,
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
  // Ein Widerspruch wird dort geklärt, wo beide Werte nebeneinander stehen.
  if (warningType === "calculation_conflict") return CONFLICT_TARGET;
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
