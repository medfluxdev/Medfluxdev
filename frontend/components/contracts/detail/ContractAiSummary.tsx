"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import EmptyState from "@/components/ui/EmptyState";
import InlineAlert from "@/components/ui/InlineAlert";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Signal, { SignalIcon } from "@/components/ui/Signal";
import { askAssistant, type AssistantReply } from "@/lib/domain-api/assistant";

/** Feste Bitte an den Assistenten; der Server gibt nur die freigegebenen Angaben dieses Vertrags weiter. */
export const SUMMARY_PROMPT = "Fasse diesen Vertrag in drei bis fünf kurzen Sätzen auf Deutsch zusammen: Gegenstand, Vertragspartner, "
  + "Laufzeit und Vertragsende sowie wichtige Fristen oder Pflichten. Nutze nur die bereitgestellten Angaben; "
  + "fehlt etwas, schreibe „nicht angegeben“.";

const SPARK = "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z";
/** Dokument mit Funken (dekorativ). */
const SUMMARY_ART = <>
  <path d="M15 8h12l7 7v23a2 2 0 0 1-2 2H15a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2z" /><path d="M27 8v7h7M18 22h11M18 27h11M18 32h7" />
  <path className="empty-state-art-accent" d="M39 3l.9 2.6 2.6.9-2.6.9L39 10l-.9-2.6-2.6-.9 2.6-.9z" />
</>;

/**
 * Übersicht: Kurzfassung auf Wunsch vom lokalen KI-Modell (gleicher Weg wie der KI-Assistent).
 * Nur zur Orientierung – nichts wird gespeichert oder übernommen; maßgeblich bleiben die geprüften Angaben.
 */
export default function ContractAiSummary({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const [reply, setReply] = useState<AssistantReply | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);

  // Anderer Vertrag oder Seite verlassen: laufende Anfrage abbrechen, alte Kurzfassung verwerfen.
  useEffect(() => {
    setReply(null);
    setError(null);
    return () => request.current?.abort();
  }, [contractId]);

  async function create() {
    if (busy) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError(null);
    try {
      const result = await askAssistant(orgSlug, SUMMARY_PROMPT, contractId, controller.signal);
      if (!controller.signal.aborted) setReply(result);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error && failure.message ? failure.message : "Die Zusammenfassung konnte nicht erstellt werden.");
    } finally {
      if (request.current === controller) request.current = null;
      setBusy(false);
    }
  }

  function cancel() {
    request.current?.abort();
    request.current = null;
    setBusy(false);
  }

  const startButton = <button type="button" className="btn btn-primary" onClick={() => void create()}>
    <svg className="btn-symbol" viewBox="0 0 24 24" aria-hidden="true"><path d={SPARK} /></svg>Zusammenfassung erstellen
  </button>;

  return <CollapsibleSection id="ai-summary" className="ai-summary" title="KI-Zusammenfassung" tone="ai" description="Die wichtigsten Vertragsinhalte auf einen Blick."
    actions={busy ? <button type="button" className="btn btn-sm" onClick={cancel}>Abbrechen</button>
      : reply ? <button type="button" className="btn btn-sm" onClick={() => void create()}>Neu erstellen</button> : undefined}>
    {busy ? <p className="cw-muted" role="status">Zusammenfassung wird erstellt … Das lokale Modell kann bis zu drei Minuten brauchen.</p> : null}
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {!reply && !busy ? <EmptyState variant="illustrated" illustration={SUMMARY_ART} title="Noch keine Zusammenfassung erstellt." action={startButton} /> : null}
    {reply && !busy ? <div className="ai-summary-result">
      <Signal tone="ai" size="sm">KI-Text, nicht geprüft</Signal>
      <p className="ai-summary-text">{reply.answer}</p>
      {reply.evidence.length ? <details className="ai-summary-sources">
        <summary>Quellenauszüge ({reply.evidence.length})</summary>
        <ul>
          {reply.evidence.map((source) => <li key={source.evidence_id}>
            <span className="ai-summary-source-meta">{source.page == null ? "Keine Seitenangabe" : `Seite ${source.page}`} · {source.requires_review ? "Prüfung erforderlich" : "aus der Extraktion"}</span>
            <q>{source.source_text}</q>
            <Link href={`/contracts/${encodeURIComponent(contractId)}?tab=documents&subtab=evidence&source_evidence_id=${encodeURIComponent(source.evidence_id)}`}>Nachweis öffnen</Link>
          </li>)}
        </ul>
      </details> : <p className="cw-muted">Ohne Quellenauszüge – die Kurzfassung beruht nur auf den Stammangaben des Vertrags.</p>}
    </div> : null}
    <p className="card-foot-note"><SignalIcon tone="info" />Lokal generiert · Ungeprüft · Wird nicht gespeichert.</p>
  </CollapsibleSection>;
}
