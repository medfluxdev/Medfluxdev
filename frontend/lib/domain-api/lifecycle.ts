import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

export type ContractLifecycleDecisionKind = "renew" | "renegotiate" | "terminate" | "monitor";
export type ContractLifecycleStatus = "planned" | "in_progress" | "completed" | "cancelled";
export type EquipmentLifecycleStatus = "active" | "maintenance_due" | "out_of_service" | "retired";

/** Erinnerung, die mit der Entscheidung angelegt wurde (ein Termin unter „Fristen & Aufgaben“). */
export interface DecisionReminder {
  id: string;
  title: string;
  due_date: string;
  status: "open" | "done" | "cancelled";
}

export interface DecisionReminderInput {
  title: string;
  due_date: string;
  kind?: string;
  todo_text?: string | null;
}

/** Umsetzungsschritt einer offenen Entscheidung (Backend: app/reports/decision_steps.py). */
export interface DecisionStep {
  key: string;
  title: string;
  detail: string;
  due: string | null;
  done: boolean;
  /** auto = aus den Vertragsdaten erkannt, manual = von einer Person abgehakt. */
  done_how: "auto" | "manual" | null;
  done_by: string | null;
  done_at: string | null;
  /** Ort in der Vertragsakte oder `{ action: "change_decision" }`. */
  target: Record<string, string> | null;
}

export interface ContractLifecycleDecision {
  id: string;
  contract_id: string;
  decision: ContractLifecycleDecisionKind;
  status: ContractLifecycleStatus;
  effective_date: string | null;
  note: string | null;
  actor_display_name: string;
  created_at: string | null;
  updated_at: string | null;
  reminder?: DecisionReminder | null;
  /** Nur bei offenen Entscheidungen (geplant / in Bearbeitung). */
  steps?: DecisionStep[] | null;
}

export interface ContractLifecycleResponse {
  items: ContractLifecycleDecision[];
}

export interface EquipmentLifecycle {
  equipment_id: string;
  status: EquipmentLifecycleStatus;
  next_service_date: string | null;
  note: string | null;
  updated_by_display_name: string | null;
  updated_at: string | null;
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getContractLifecycle(organizationSlug: string, contractId: string) {
  return apiGet<ContractLifecycleResponse>(`/api/lifecycle/contracts/${encodeURIComponent(contractId)}?${orgQuery(organizationSlug)}`);
}

export function createContractLifecycleDecision(
  organizationSlug: string,
  contractId: string,
  input: { decision: ContractLifecycleDecisionKind; status?: ContractLifecycleStatus; effective_date?: string | null; note?: string | null; reminder?: DecisionReminderInput | null },
) {
  return apiPost<ContractLifecycleDecision>(`/api/lifecycle/contracts/${encodeURIComponent(contractId)}?${orgQuery(organizationSlug)}`, input);
}

export function updateContractLifecycleDecision(
  organizationSlug: string,
  contractId: string,
  decisionId: string,
  input: { status: ContractLifecycleStatus; decision?: ContractLifecycleDecisionKind; effective_date?: string | null; note?: string | null; reminder?: DecisionReminderInput | null; remove_reminder?: boolean },
) {
  return apiPatch<ContractLifecycleDecision>(`/api/lifecycle/contracts/${encodeURIComponent(contractId)}/${encodeURIComponent(decisionId)}?${orgQuery(organizationSlug)}`, input);
}

/** Umsetzungsschritt abhaken oder zurücknehmen; der erste Haken setzt die Entscheidung auf „in Bearbeitung“. */
export function updateDecisionStep(organizationSlug: string, contractId: string, decisionId: string, stepKey: string, done: boolean) {
  return apiPost<ContractLifecycleDecision>(`/api/lifecycle/contracts/${encodeURIComponent(contractId)}/${encodeURIComponent(decisionId)}/steps/${encodeURIComponent(stepKey)}?${orgQuery(organizationSlug)}`, { done });
}

/** Löscht die Entscheidung; ihre offene Erinnerung wird abgebrochen, außer keepReminder. */
export function deleteContractLifecycleDecision(organizationSlug: string, contractId: string, decisionId: string, keepReminder = false) {
  return apiDelete<{ deleted: boolean; id: string }>(`/api/lifecycle/contracts/${encodeURIComponent(contractId)}/${encodeURIComponent(decisionId)}?${orgQuery(organizationSlug)}${keepReminder ? "&keep_reminder=true" : ""}`);
}

export function getEquipmentLifecycle(organizationSlug: string, equipmentId: string) {
  return apiGet<EquipmentLifecycle>(`/api/lifecycle/equipment/${encodeURIComponent(equipmentId)}?${orgQuery(organizationSlug)}`);
}

export function updateEquipmentLifecycle(
  organizationSlug: string,
  equipmentId: string,
  input: { status: EquipmentLifecycleStatus; next_service_date?: string | null; note?: string | null },
) {
  return apiPut<EquipmentLifecycle>(`/api/lifecycle/equipment/${encodeURIComponent(equipmentId)}?${orgQuery(organizationSlug)}`, input);
}
