"use client";

import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import { evidenceGroupLabel } from "@/lib/contract-detail-types";
import { PRECISION, confidenceText, precisionOf, reviewStateOf, titleOf, where } from "./EvidencePane";

const icon = (body: JSX.Element) => <svg className="evd-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const PREV = icon(<path d="m15 6-6 6 6 6" />);
const NEXT = icon(<path d="m9 6 6 6-6 6" />);
const COPY = icon(<path d="M9 9h10v12H9zM5 15V3h10" />);
const REVIEW = icon(<path d="m5 12.5 4.5 4.5L19 7.5" />);

/**
 * Gewählter Nachweis über dem Original: voller Wortlaut, Fundort und Genauigkeit in Worten, Prüfstand –
 * und die nächsten Schritte (Zur Prüfung, vorheriger/nächster Nachweis, Zitat kopieren). Änderungen werden angesagt.
 */
export default function EvidenceDetail({ refItem, number, factByEvidence, position, total, onPrev, onNext, onOpenReview }: {
  refItem: EvidenceRef;
  /** Feste Nummer in Lesereihenfolge (wie in der Liste und auf der Seite). */
  number: number | null;
  factByEvidence: Map<string, FactReviewStateDto>;
  /** Stelle in der sichtbaren Liste (1-basiert), sonst null. */
  position: number | null;
  total: number;
  onPrev: (() => void) | null;
  onNext: (() => void) | null;
  onOpenReview: ((factKey: string) => void) | null;
}) {
  const toast = useToast();
  const fact = factByEvidence.get(refItem.evidence_id);
  const level = PRECISION[precisionOf(refItem)];
  const place = where(refItem);
  const confidence = confidenceText(refItem.confidence);
  const state = reviewStateOf(refItem, fact);
  const title = titleOf(refItem, factByEvidence);

  return <section className="evd" aria-labelledby="evd-title">
    <div className="evd-head">
      <div className="evd-title">
        <span className="evd-area">{number ? `Nachweis ${number}` : "Nachweis"}{refItem.page != null ? ` · Seite ${refItem.page}` : ""} · {evidenceGroupLabel(refItem.field_ref?.split(".")[0] ?? null)}</span>
        <h3 id="evd-title">{number ? <span className="evidence-number" aria-hidden="true">{number}</span> : null}{title}</h3>
      </div>
      <div className="evd-nav" role="group" aria-label="Nachweise blättern">
        <button type="button" className="btn btn-sm btn-ghost" disabled={!onPrev} onClick={() => onPrev?.()} aria-label="Vorheriger Nachweis">{PREV}</button>
        <span className="evd-pos">{position ? `${position} von ${total}` : `– von ${total}`}</span>
        <button type="button" className="btn btn-sm btn-ghost" disabled={!onNext} onClick={() => onNext?.()} aria-label="Nächster Nachweis">{NEXT}</button>
      </div>
    </div>
    {refItem.snippet ? <blockquote className="evd-quote">„{refItem.snippet}“</blockquote> : <p className="evd-quote evd-quote--none">Kein Wortlaut gespeichert.</p>}
    <p className="evd-facts" aria-live="polite">
      <span>{place ?? "Keine Seitenangabe"}</span>
      <Signal tone={level.tone} size="sm">{level.label}</Signal>
      <span className="evd-hint">{level.hint}</span>
    </p>
    <div className="evd-foot">
      <span className="evd-state">
        {state === "open" ? <Signal tone="ai" size="sm">Zu prüfen</Signal> : state === "done" ? <Signal tone="done" size="sm">Geprüft</Signal> : null}
        {fact && fact.effective_value != null && fact.effective_value !== "" ? <span>Wert: <strong>{String(fact.effective_value)}</strong></span> : null}
        {confidence ? <span title="Wie sicher die KI beim Auslesen war – kein Prüfergebnis.">{confidence}</span> : null}
      </span>
      <span className="evd-actions">
        {refItem.snippet ? <button type="button" className="btn btn-sm btn-ghost" onClick={() => { void navigator.clipboard?.writeText(refItem.snippet ?? "").then(() => toast("Zitat kopiert.", "success")).catch(() => undefined); }}>{COPY}Zitat kopieren</button> : null}
        {fact && onOpenReview ? <button type="button" className={`btn btn-sm${state === "open" ? " btn-primary" : ""}`} onClick={() => onOpenReview(fact.fact_key)}>{REVIEW}{state === "open" ? "Jetzt prüfen" : "Zur Prüfung"}</button> : null}
      </span>
    </div>
  </section>;
}
