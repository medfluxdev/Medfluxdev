import { apiPost } from "@/lib/api";

/** Quellenauszug aus der akzeptierten Extraktion (kein unabhängiger Beleg). */
export interface AssistantEvidence {
  evidence_id: string;
  field_ref: string;
  source_type: string;
  document_version_id: string;
  page: number | null;
  source_text: string;
  requires_review: boolean;
}

export interface AssistantReply {
  answer: string;
  contract_id: string | null;
  evidence: AssistantEvidence[];
}

/** Lokales Modell: Antworten können dauern (wie im schwebenden Assistenten). */
const ASSISTANT_TIMEOUT_MS = 180_000;

/** Frage an den lesenden lokalen Assistenten; der Server prüft Zugriff und gibt nur freigegebene Vertragsdaten weiter. */
export function askAssistant(organizationSlug: string, message: string, contractId: string | null, signal?: AbortSignal) {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return apiPost<AssistantReply>(`/api/ai/assistant?${query}`, { message, contract_id: contractId }, ASSISTANT_TIMEOUT_MS, signal);
}
