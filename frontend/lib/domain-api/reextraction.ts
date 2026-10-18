import { apiGet, apiPost } from "@/lib/api";

// Erneute Erfassung aus dem Vertragsdokument („Analyse #N“).
// Eine Analyse schreibt nie in die Vertragsdaten, nur Vorschläge; übernommen wird je Angabe durch eine Person.

export type ReextractionStatus = "queued" | "running" | "ready" | "failed" | "applied" | "discarded" | "cancelled";
/** supplement = Ergänzen, sections = Bereich neu erfassen, full = Vollständig neu bewerten; rollback = Zurücknahme im Verlauf. */
export type ReextractionMode = "supplement" | "sections" | "full" | "rollback";
export type ProposalKind = "new" | "deviating" | "missing" | "unchanged";
export type ProposalDecision = "pending" | "accepted" | "kept_old" | "manual" | "rejected" | "rolled_back";

export interface ReextractionRun {
  id: string;
  number: number;
  status: ReextractionStatus;
  mode: ReextractionMode;
  mode_label: string;
  sections: { key: string; label: string }[];
  fields: { key: string; label: string }[];
  page_hint: number[];
  hint: string | null;
  protect_manual: boolean;
  reset_confirmations: boolean;
  reread_document: boolean;
  model_id: string | null;
  /** Fortschritt je Schritt der Analyse (Bereiche des Modells), leer solange sie wartet. */
  progress: { step?: number; steps?: number; label?: string; found?: number };
  summary: Partial<Record<ProposalKind | "protected" | "accepted" | "decided", number>>;
  applied_keys: string[];
  requested_by_name: string | null;
  message: string | null;
  queue_position: number;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  /** Vertragsdaten haben sich seit dem Start geändert – Übernahme nicht mehr möglich. */
  stale: boolean;
}

export interface ProposalEvidence {
  page: number | null;
  quote: string | null;
  confidence: number | null;
  bbox: Record<string, number> | null;
}

export interface Proposal {
  id: string;
  key: string;
  label: string;
  /** Bereich wie in „Nachweise prüfen“: partner, term, cost, services, device. */
  section: string;
  kind: ProposalKind;
  /** Von Hand gepflegt und geschützt: kein Vorschlag, gilt als unverändert. */
  protected: boolean;
  current: string | null;
  proposed: string | null;
  confidence: number | null;
  evidence: ProposalEvidence[];
  register_keys: string[];
  decision: ProposalDecision;
  decided_by_name: string | null;
  decided_at: string | null;
}

export interface AnalysisHistoryItem {
  /** null = Erstanalyse beim Import (ohne eigenen Lauf). */
  id: string | null;
  number: number;
  mode: ReextractionMode | "initial";
  mode_label: string;
  status: ReextractionStatus;
  date: string | null;
  requested_by_name: string | null;
  summary: Partial<Record<string, number>>;
  accepted: number;
  /** „Auf diesen Stand zurück“: spätere Analysen haben Werte übernommen. */
  can_rollback: boolean;
}

export interface ReextractionState {
  can_start: boolean;
  blocked_reason: string | null;
  /** Noch keine KI-Analyse (z. B. von Hand erfasst): der erste Lauf vergleicht gegen leere Angaben. */
  first_analysis?: boolean;
  missing: { key: string; label: string }[];
  /** Vertragsdaten-Feld → Angaben, nach denen „Im Dokument suchen“ sucht. */
  field_search?: Record<string, { key: string; label: string }[]>;
  reread_suggested: boolean;
  run: ReextractionRun | null;
  rows: Proposal[];
  /** Angaben ohne Wert (Umfang von „Ergänzen“). */
  open_fields: number;
  /** Nachweise des Vertrags (Umfang von „Vollständig neu bewerten“) und geschätzte Prüfzeit. */
  evidence_count: number;
  review_minutes: number;
  /** Dauer der letzten Analyse (Schätzung), null ohne frühere Analyse. */
  duration_minutes: number | null;
  sections: { key: string; label: string }[];
  history: AnalysisHistoryItem[];
  /** Neues Hauptdokument seit der letzten Analyse. */
  new_document: { document_version_id: string; filename: string | null } | null;
  can_review: boolean;
}

export interface ReextractionModel {
  model_id: string;
  label: string;
  parameter_size: string | null;
  vision: boolean;
  current: boolean;
}

export interface StartReextraction {
  mode: Exclude<ReextractionMode, "rollback">;
  fields?: string[];
  sections?: string[];
  page_hint?: number[];
  hint?: string | null;
  protect_manual?: boolean;
  reset_confirmations?: boolean;
  reread_document?: boolean;
  model_id?: string | null;
}

export interface RollbackEntry {
  key: string;
  label: string;
  number: number;
  current: string | null;
  restored: string | null;
  /** Später geändert: bleibt unverändert. */
  conflict: boolean;
}

function path(contractId: string, organizationSlug: string, suffix = "") {
  return `/api/contracts/${encodeURIComponent(contractId)}/reextraction${suffix}?organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getReextraction(organizationSlug: string, contractId: string) {
  return apiGet<ReextractionState>(path(contractId, organizationSlug));
}

export function getReextractionModels(organizationSlug: string, contractId: string) {
  return apiGet<{ provider_id: string | null; current_model: string | null; models: ReextractionModel[] }>(path(contractId, organizationSlug, "/models"));
}

export function startReextraction(organizationSlug: string, contractId: string, body: StartReextraction) {
  return apiPost<ReextractionRun>(path(contractId, organizationSlug), body);
}

export function applyReextraction(organizationSlug: string, contractId: string, runId: string, keys: string[]) {
  // Die Übernahme rechnet Fristen, Kosten und Warnungen neu – großzügige Zeitgrenze.
  return apiPost<{ applied: number; keys: string[]; message: string }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/apply`), { keys }, 120_000);
}

export function decideReextraction(organizationSlug: string, contractId: string, runId: string, keys: string[], decision: "kept_old" | "manual" | "rejected") {
  return apiPost<{ decided: number; status: ReextractionStatus }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/decide`), { keys, decision });
}

export function confirmUnchanged(organizationSlug: string, contractId: string, runId: string) {
  return apiPost<{ confirmed: number; facts: number }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/confirm-unchanged`), {});
}

export function discardReextraction(organizationSlug: string, contractId: string, runId: string) {
  return apiPost<{ status: ReextractionStatus }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/discard`), {});
}

export function cancelReextraction(organizationSlug: string, contractId: string, runId: string) {
  return apiPost<{ status: ReextractionStatus; cancel_requested: boolean }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/cancel`), {});
}

export function getRollbackPreview(organizationSlug: string, contractId: string, number: number) {
  return apiGet<{ target: number; entries: RollbackEntry[] }>(path(contractId, organizationSlug, `/rollback/${number}`));
}

export function rollbackToAnalysis(organizationSlug: string, contractId: string, number: number) {
  return apiPost<{ number: number; restored: string[]; skipped: number; message: string }>(path(contractId, organizationSlug, `/rollback/${number}`), {}, 120_000);
}
