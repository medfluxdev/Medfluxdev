"use client";

import { useState } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { reviewContractFact } from "@/lib/domain-api/contracts";
import { formatDate } from "@/lib/format";
import type { DetailWarning, EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";

const NOTE = "Widerspruch geklärt";

/**
 * „Widerspruch klären“ (Übersicht): was sich widerspricht, beide Werte mit Herkunft, und die Entscheidung.
 * Gespeichert wird in der Faktprüfung (Vertragsende bestätigt bzw. korrigiert); eine Korrektur zieht das
 * feste Vertragsende in den Vertragsdaten nach. Danach gilt die Warnung als geklärt (Risiko neu berechnet).
 */
export default function ConflictCard({ contractId, orgSlug, warnings, facts, evidence, canDecide, onOpenEvidence, onOpenTarget, onSaved }: {
  contractId: string;
  orgSlug: string;
  warnings: DetailWarning[];
  facts: Map<string, FactReviewStateDto>;
  evidence: EvidenceRef[];
  canDecide: boolean;
  onOpenEvidence: (ref: EvidenceRef) => void;
  onOpenTarget: (section: "term" | "documents") => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [other, setOther] = useState<string | null>(null);
  const open = warnings.filter((warning) => warning.conflict && warning.requires_review);
  if (!open.length) return null;
  const evidenceById = new Map(evidence.map((ref) => [ref.evidence_id, ref]));
  const sources = (keys: string[]) => keys.flatMap((key) => facts.get(key)?.linked_evidence_refs ?? []).map((id) => evidenceById.get(id)).filter((ref): ref is EvidenceRef => Boolean(ref));

  async function decide(factKey: string, value: string, label: string) {
    const fact = facts.get(factKey);
    setBusy(true);
    try {
      const sameAsDocument = String(fact?.original_value ?? "") === value;
      await reviewContractFact(contractId, orgSlug, {
        fact_key: factKey,
        action: sameAsDocument ? "confirmed" : "corrected",
        ...(sameAsDocument ? {} : { corrected_value: value }),
        note: `${NOTE}: ${label}.`,
        expected_reviewed_at: fact?.reviewed_at ?? null,
      });
      toast("Widerspruch geklärt.", "success");
      setOther(null);
      onSaved();
    } catch (err) {
      toast(err instanceof ApiError && err.message ? err.message : "Die Entscheidung konnte nicht gespeichert werden.", "error");
    } finally {
      setBusy(false);
    }
  }

  return <section className="cw-section conflict-card" aria-labelledby="conflict-heading">
    <div className="cw-section-head">
      <div>
        <h2 id="conflict-heading">Widerspruch klären</h2>
        <p>Die Angaben aus dem Dokument passen nicht zusammen. Entscheiden Sie, welcher Wert gilt.</p>
      </div>
    </div>
    {open.map((warning, index) => {
      const conflict = warning.conflict!;
      return <div key={`${conflict.topic}-${index}`} className="conflict-item">
        <p className="conflict-title"><Signal tone="warning" size="sm">Prüfen</Signal><strong>{conflict.title_de}</strong></p>
        <p className="conflict-question">{conflict.question_de}</p>
        <p className="conflict-why">{conflict.explanation_de}</p>
        {conflict.options.length ? <div className="conflict-options">
          {conflict.options.map((option) => <div key={option.key} className="conflict-option">
            <span className="conflict-option-label">{option.label_de}</span>
            <strong className="conflict-option-value">{formatDate(option.value)}</strong>
            <span className="conflict-option-detail">{option.detail_de}</span>
            <span className="conflict-option-sources">
              {sources(option.fact_keys).map((ref) => <button key={ref.evidence_id} type="button" className="cw-source-button" onClick={() => onOpenEvidence(ref)} aria-label={`Quelle für ${option.label_de}: Seite ${ref.page ?? "?"}`}>Quelle{ref.page != null ? ` · S. ${ref.page}` : ""}</button>)}
            </span>
            {canDecide && conflict.fact_key ? <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void decide(conflict.fact_key!, option.value, `${option.label_de} (${formatDate(option.value)})`)}>Dieses Datum gilt</button> : null}
          </div>)}
        </div> : null}
        {conflict.inputs?.length ? <dl className="conflict-inputs">{conflict.inputs.map((item) => <div key={item.label_de}><dt>{item.label_de}</dt><dd>{item.value}</dd></div>)}</dl> : null}
        <div className="conflict-actions">
          {canDecide && conflict.fact_key && conflict.options.length ? (other === null
            ? <button type="button" className="rg-link" onClick={() => setOther("")}>Anderes Datum …</button>
            : <span className="conflict-other">
              <label>Vertragsende<input type="date" value={other} onChange={(event) => setOther(event.target.value)} /></label>
              <button type="button" className="btn btn-sm btn-primary" disabled={busy || !other} onClick={() => void decide(conflict.fact_key!, other, `eigenes Datum (${formatDate(other)})`)}>Speichern</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setOther(null)}>Abbrechen</button>
            </span>) : null}
          {!conflict.options.length ? <button type="button" className="btn btn-sm" onClick={() => onOpenTarget("term")}>In Vertragsdaten prüfen</button> : null}
        </div>
      </div>;
    })}
  </section>;
}
