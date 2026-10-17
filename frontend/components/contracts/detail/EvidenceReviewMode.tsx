"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import { reviewContractFact } from "@/lib/domain-api/contracts";
import { PRECISION, precisionOf, titleOf, where } from "./EvidencePane";

const icon = (body: JSX.Element) => <svg className="erm-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const BACK = icon(<path d="m15 6-6 6 6 6" />);
const LIST = icon(<path d="M8 6h13M8 12h13M8 18h13M3 6h.5M3 12h.5M3 18h.5" />);
const ARROW_LEFT = icon(<path d="M19 12H5M11 6l-6 6 6 6" />);
const ARROW_RIGHT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);
const PEN = icon(<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" />);

const DONE_STATES = new Set(["confirmed", "corrected", "auto_accepted"]);
const STATE_LABEL: Record<string, string> = { confirmed: "Geprüft", corrected: "Korrigiert", auto_accepted: "Automatisch übernommen" };

/**
 * „Nachweise prüfen“: ein Nachweis nach dem anderen – links das Original an der Fundstelle, rechts die erkannte Angabe
 * mit einem Hauptschritt („Stimmt überein · Weiter“). Gespeichert wird wie in der Faktprüfung (`/fact-reviews`).
 */
export default function EvidenceReviewMode({ contractId, orgSlug, evidence, numbers, factByEvidence, startId, canReview, viewer, onShow, onExit, onReload }: {
  contractId: string;
  orgSlug: string;
  /** In Lesereihenfolge. */
  evidence: EvidenceRef[];
  numbers: Map<string, number>;
  factByEvidence: Map<string, FactReviewStateDto>;
  startId: string | null;
  canReview: boolean;
  /** Die Ansicht des Originals (vom Arbeitsplatz, damit Zoom/Seite erhalten bleiben). */
  viewer: ReactNode;
  /** Nachweis im Original zeigen (Datei, Seite, Markierung). */
  onShow: (ref: EvidenceRef) => void;
  onExit: () => void;
  onReload: () => void;
}) {
  const toast = useToast();
  const firstOpen = evidence.findIndex((ref) => { const fact = factByEvidence.get(ref.evidence_id); return fact ? !DONE_STATES.has(fact.state) : false; });
  const [index, setIndex] = useState(() => {
    const start = startId ? evidence.findIndex((ref) => ref.evidence_id === startId) : -1;
    return start >= 0 ? start : Math.max(0, firstOpen);
  });
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<{ value: string; note: string; deviation: boolean } | null>(null);
  const [done, setDone] = useState(false);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  const current = evidence[index] ?? null;
  const fact = current ? factByEvidence.get(current.evidence_id) : undefined;
  const value = fact ? String(fact.effective_value ?? fact.original_value ?? "") : "";
  const reviewed = fact ? DONE_STATES.has(fact.state) : false;
  const counts = useMemo(() => {
    const facts = evidence.map((ref) => factByEvidence.get(ref.evidence_id)).filter(Boolean) as FactReviewStateDto[];
    return { open: facts.filter((item) => !DONE_STATES.has(item.state)).length, total: evidence.length };
  }, [evidence, factByEvidence]);

  // Im Original zeigen und den Fokus auf die Überschrift setzen (Screenreader hört den neuen Nachweis).
  useEffect(() => {
    if (!current) return;
    onShow(current);
    setEditing(null);
    headingRef.current?.focus();
    // onShow wechselt nur die Ansicht; neu auslösen soll nur ein anderer Nachweis.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.evidence_id]);

  // ← / → blättern (nicht beim Tippen in Feldern).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT")) return;
      if (event.key === "ArrowRight") { event.preventDefault(); go(1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); go(-1); }
      if (event.key === "Escape") onExit();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function go(step: number) {
    const next = index + step;
    if (next < 0) return;
    if (next >= evidence.length) { setDone(true); return; }
    setDone(false);
    setIndex(next);
  }

  async function save(action: "confirmed" | "corrected") {
    if (!fact) return;
    setBusy(true);
    try {
      await reviewContractFact(contractId, orgSlug, {
        fact_key: fact.fact_key,
        action,
        ...(action === "corrected" && editing ? { corrected_value: editing.value.trim(), note: editing.note.trim() || "Bei der Nachweisprüfung korrigiert." } : {}),
        evidence_ref: current?.evidence_id ?? null,
        expected_reviewed_at: fact.reviewed_at ?? null,
      });
      toast(action === "confirmed" ? `„${fact.label_de}“ bestätigt.` : `„${fact.label_de}“ korrigiert.`, "success");
      onReload();
      go(1);
    } catch (err) {
      const conflict = err instanceof ApiError && err.status === 409;
      toast(conflict ? "Die Angabe wurde inzwischen geändert – Stand neu geladen." : "Die Prüfung konnte nicht gespeichert werden.", "error");
      if (conflict) onReload();
    } finally {
      setBusy(false);
    }
  }

  const number = current ? numbers.get(current.evidence_id) ?? index + 1 : 0;
  const level = current ? PRECISION[precisionOf(current)] : null;

  return <section className="erm" aria-labelledby="erm-heading">
    <header className="erm-bar">
      <button type="button" className="btn btn-ghost btn-sm erm-back" onClick={onExit} aria-label="Prüfen beenden">{BACK}</button>
      <h2 id="erm-heading">Nachweise prüfen</h2>
      {current?.original_filename ? <span className="erm-file">{current.original_filename}</span> : null}
      <button type="button" className="btn btn-sm erm-all" onClick={onExit}>{LIST}Alle Nachweise · {counts.total}</button>
    </header>

    <div className="erm-body">
      <div className="erm-viewer">{viewer}</div>

      <div className="erm-card" role="region" aria-label="Aktueller Nachweis" aria-live="polite">
        {done || !current ? <div className="erm-done">
          <Signal tone={counts.open ? "info" : "done"}>{counts.open ? `${counts.open} noch offen` : "Alles geprüft"}</Signal>
          <h3 ref={headingRef} tabIndex={-1}>Alle Nachweise durchgesehen</h3>
          <p>{counts.open ? "Übersprungene Angaben bleiben offen und erscheinen weiter unter „Zu prüfen“." : "Jede Angabe mit Nachweis ist bestätigt oder korrigiert."}</p>
          <div className="erm-done-actions">
            {counts.open ? <button type="button" className="btn" onClick={() => { setDone(false); setIndex(Math.max(0, firstOpen)); }}>Offene erneut durchgehen</button> : null}
            <button type="button" className="btn btn-primary" onClick={onExit}>Zur Übersicht</button>
          </div>
        </div> : <>
          <div className="erm-card-top">
            <span className="erm-pos">{index + 1} / {evidence.length}</span>
            {fact ? (reviewed ? <Signal tone="done" size="sm">{STATE_LABEL[fact.state] ?? "Geprüft"}</Signal> : <Signal tone="info" size="sm">Noch nicht geprüft</Signal>) : <Signal tone="neutral" size="sm">Nur Nachweis</Signal>}
          </div>
          <h3 ref={headingRef} tabIndex={-1} className="erm-title"><span className="evidence-number" aria-hidden="true">{number}</span>{titleOf(current, factByEvidence)}</h3>
          <p className="erm-where">{where(current) ?? "Keine Seitenangabe"}{level ? ` · ${level.label}` : ""}</p>

          {editing ? <form className="erm-edit" onSubmit={(event) => { event.preventDefault(); if (editing.value.trim() && (!editing.deviation || editing.note.trim())) void save("corrected"); }}>
            <label>Richtiger Wert<textarea rows={3} value={editing.value} autoFocus onChange={(event) => setEditing({ ...editing, value: event.target.value })} /></label>
            <label>{editing.deviation ? "Was weicht ab?" : "Begründung (optional)"}<input value={editing.note} required={editing.deviation} placeholder={editing.deviation ? "z. B. Dokument nennt eine andere Adresse" : "z. B. Tippfehler der Erkennung"} onChange={(event) => setEditing({ ...editing, note: event.target.value })} /></label>
            <div className="erm-edit-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>Abbrechen</button>
              <button type="submit" className="btn btn-primary" disabled={busy || !editing.value.trim() || (editing.deviation && !editing.note.trim())}>{busy ? "Wird gespeichert…" : "Korrigieren · Weiter"}</button>
            </div>
          </form> : <>
            <p className="erm-label">{fact ? "Erkannte Angabe" : "Wortlaut im Dokument"}</p>
            <div className="erm-value">{fact ? (value || <span className="cw-muted">Kein Wert erkannt</span>) : (current.snippet ? `„${current.snippet}“` : <span className="cw-muted">Kein Wortlaut gespeichert</span>)}</div>
            {fact && current.snippet && value && !current.snippet.includes(value) ? <p className="erm-snippet">Im Dokument: „{current.snippet}“</p> : null}
            {fact && canReview ? <button type="button" className="rg-link erm-edit-link" onClick={() => setEditing({ value, note: "", deviation: false })}>{PEN}Bearbeiten</button> : null}
            {fact && canReview && !reviewed
              ? <button type="button" className="btn btn-primary erm-primary" disabled={busy} onClick={() => void save("confirmed")}>{busy ? "Wird gespeichert…" : <>Stimmt überein · Weiter{ARROW_RIGHT}</>}</button>
              : <button type="button" className="btn btn-primary erm-primary" onClick={() => go(1)}>Weiter{ARROW_RIGHT}</button>}
            {fact && canReview ? <button type="button" className="rg-link erm-deviation" onClick={() => setEditing({ value, note: "", deviation: true })}>Abweichung melden</button> : null}
            {fact && !canReview ? <p className="erm-readonly">Nur Lesen – bestätigen und korrigieren dürfen Prüfende und das Vertragsmanagement.</p> : null}
          </>}
        </>}
      </div>
    </div>

    <nav className="erm-steps" aria-label="Nachweise blättern">
      <button type="button" className="btn" disabled={index === 0 && !done} onClick={() => (done ? setDone(false) : go(-1))}>{ARROW_LEFT}Zurück</button>
      <span className="erm-steps-pos" aria-live="polite">{done ? `${evidence.length} von ${evidence.length}` : `${index + 1} von ${evidence.length}`} Nachweisen</span>
      <button type="button" className="btn" disabled={done} onClick={() => go(1)}>Überspringen{ARROW_RIGHT}</button>
    </nav>
  </section>;
}
