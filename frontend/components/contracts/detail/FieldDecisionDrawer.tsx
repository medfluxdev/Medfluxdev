"use client";

import Drawer from "@/components/ui/Drawer";
import type { ContractDetailResponse, FieldEvidenceDto, FieldReviewDto } from "@/lib/contract-detail-types";
import { fieldByKey } from "@/lib/field-review";
import FieldDecision from "./FieldDecision";

/**
 * Entscheidung zu einem Feld direkt aus der Karte (KI-Plakette, Offene Punkte, Übersicht) – ohne die geführte Prüfung zu
 * starten. Gleiche Komponente, gleiche API, gleicher Stand wie dort.
 */
export default function FieldDecisionDrawer({ contractId, orgSlug, review, factKey, canReview, onClose, onReload, onShowEvidence, onShowPage, onOpenAnalysis, onStartGuided }: {
  contractId: string;
  orgSlug: string;
  review: FieldReviewDto | null | undefined;
  factKey: string | null;
  canReview: boolean;
  onClose: () => void;
  onReload: () => void;
  onShowEvidence?: (evidence: FieldEvidenceDto) => void;
  onShowPage?: (page: number | null, quote: string | null) => void;
  onOpenAnalysis?: () => void;
  /** Geführte Prüfung ab diesem Feld. */
  onStartGuided?: (factKey: string) => void;
}) {
  const field = fieldByKey(review, factKey);
  return <Drawer open={Boolean(factKey && field && review)} title={field?.label ?? "Angabe"} onClose={onClose} wide
    actions={field && onStartGuided ? <button type="button" className="btn btn-sm" onClick={() => { onClose(); onStartGuided(field.fact_key); }}>Geführt weiter prüfen</button> : undefined}>
    {field && review
      ? <FieldDecision key={`${field.fact_key}|${field.version ?? ""}|${field.status}`} contractId={contractId} orgSlug={orgSlug} field={field} review={review} canReview={canReview} level={2}
        onChanged={(detail: ContractDetailResponse | null, info) => { onReload(); if (info.decided && detail) onClose(); }}
        onShowEvidence={onShowEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis} />
      : null}
  </Drawer>;
}
