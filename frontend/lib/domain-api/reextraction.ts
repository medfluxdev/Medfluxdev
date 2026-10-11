import { apiGet, apiPost } from "@/lib/api";

// Erneute Erfassung aus dem Vertragsdokument (Plan ERNEUT_ERFASSEN_PLAN_20261011).
// Ein Lauf erzeugt nur einen Kandidaten; übernommen wird erst nach Auswahl im Vergleich.

export type ReextractionStatus = "queued" | "running" | "ready" | "failed" | "applied" | "discarded" | "cancelled";
export type ReextractionMode = "full" | "missing_fields";
export type FactGroup = "new" | "changed" | "same" | "missing_again";

export interface ReextractionRun {
  id: string;
  status: ReextractionStatus;
  mode: ReextractionMode;
  fields: { key: string; label: string }[];
  page_hint: number[];
  reread_document: boolean;
  model_id: string | null;
  summary: Partial<Record<FactGroup, number>>;
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

export interface FactRow {
  key: string;
  label: string;
  group: FactGroup;
  current: string | null;
  proposed: string | null;
  evidence: { page: number | null; quote: string | null }[];
  register_keys: string[];
  preselected: boolean;
}

export interface ReextractionState {
  can_start: boolean;
  blocked_reason: string | null;
  missing: { key: string; label: string }[];
  /** Vertragsdaten-Feld → Angaben, nach denen „Im Dokument suchen“ sucht. */
  field_search?: Record<string, { key: string; label: string }[]>;
  reread_suggested: boolean;
  run: ReextractionRun | null;
  rows: FactRow[];
}

export interface ReextractionModel {
  model_id: string;
  label: string;
  parameter_size: string | null;
  vision: boolean;
  current: boolean;
}

export interface StartReextraction {
  mode: ReextractionMode;
  fields?: string[];
  page_hint?: number[];
  reread_document?: boolean;
  model_id?: string | null;
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

export function discardReextraction(organizationSlug: string, contractId: string, runId: string) {
  return apiPost<{ status: ReextractionStatus }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/discard`), {});
}

export function cancelReextraction(organizationSlug: string, contractId: string, runId: string) {
  return apiPost<{ status: ReextractionStatus; cancel_requested: boolean }>(path(contractId, organizationSlug, `/${encodeURIComponent(runId)}/cancel`), {});
}
