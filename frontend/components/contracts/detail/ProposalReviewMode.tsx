"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { sameText, sectionByKey, wordDiff } from "@/lib/evidence";
import { applyReextraction, decideReextraction, type Proposal, type ProposalEvidence, type ReextractionRun } from "@/lib/domain-api/reextraction";
import { Diff, SectionChip } from "./EvidenceReviewMode";

const icon = (body: ReactNode, className = "erm-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const BACK = icon(<path d="m15 6-6 6 6 6" />);
const FILE = icon(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></>);
const DB = icon(<><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>);
const CHECK = icon(<path d="M20 6 9 17l-5-5" />);
const CHECK_CIRCLE = icon(<><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>);
const WARN = icon(<><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>);
const SKIP = icon(<path d="M5 5l9 7-9 7zM19 5v14" />);
const PEN = icon(<><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></>);
const PREV = icon(<path d="M19 12H5M11 6l-6 6 6 6" />);
const NEXT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);

const KIND_TEXT: Record<Proposal["kind"], string> = {
  new: "Neu gefunden",
  deviating: "Weicht ab",
  missing: "Nicht mehr gefunden",
  unchanged: "Unverändert",
};

function Kbd({ children }: { children: string }) {
  return <kbd className="erm-kbd" aria-hidden="true">{children}</kbd>;
}

/**
 * „Vorschläge prüfen“: die offenen Vorschläge einer Analyse einzeln, wie „Nachweise prüfen“.
 * Links das Original an der neuen Fundstelle, rechts gespeichert gegen neu erkannt.
 * Übernehmen schreibt den neuen Wert (normaler Akzeptanzweg); Behalten und Überspringen ändern nichts.
 */
export default function ProposalReviewMode({ contractId, orgSlug, contractTitle, run, proposals, startKey, viewer, canDecide, onShow, onExit, onChanged, onEditManually }: {
  contractId: string;
  orgSlug: string;
  contractTitle: string | null;
  run: ReextractionRun;
  /** Alle Vorschläge der Analyse (geprüft werden die offenen). */
  proposals: Proposal[];
  startKey: string | null;
  viewer: ReactNode;
  canDecide: boolean;
  /** Fundstelle des Vorschlags im Original zeigen. */
  onShow: (evidence: ProposalEvidence) => void;
  onExit: () => void;
  /** Nach einer Entscheidung: Vertrag und Analyse neu laden. */
  onChanged: () => void;
  /** „Selbst erfassen“: Feld in den Vertragsdaten öffnen. */
  onEditManually: (registerKey?: string) => void;
}) {
  const toast = useToast();
  // Reihenfolge einmal festhalten: entschiedene Vorschläge bleiben an ihrem Platz.
  const order = useMemo(() => proposals.filter((row) => row.kind !== "unchanged" && (row.decision === "pending" || row.key === startKey)), [run.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [local, setLocal] = useState<Map<string, string>>(() => new Map());
  const [index, setIndex] = useState(() => Math.max(0, order.findIndex((row) => row.key === startKey)));
  const [busy, setBusy] = useState(false);
  const [announce, setAnnounce] = useState("");
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const done = order.length === 0 || index >= order.length;
  const current = done ? null : order[index];
  const decision = (row: Proposal) => local.get(row.key) ?? proposals.find((item) => item.key === row.key)?.decision ?? row.decision;
  const decided = order.filter((row) => decision(row) !== "pending").length;

  useEffect(() => {
    if (!current) return;
    const evidence = current.evidence.find((item) => item.page != null);
    if (evidence) onShow(evidence);
    headingRef.current?.focus();
  }, [current?.key]); // eslint-disable-line react-hooks/exhaustive-deps

  function next(from: number) {
    for (let step = from + 1; step < order.length; step += 1) if (decision(order[step]) === "pending") return step;
    return order.length;
  }

  async function act(kind: "accept" | "keep" | "manual", said: string) {
    if (!current || busy) return;
    setBusy(true);
    try {
      if (kind === "accept") await applyReextraction(orgSlug, contractId, run.id, [current.key]);
      else await decideReextraction(orgSlug, contractId, run.id, [current.key], kind === "keep" ? "kept_old" : "manual");
      setLocal((prev) => new Map(prev).set(current.key, kind === "accept" ? "accepted" : kind === "keep" ? "kept_old" : "manual"));
      setAnnounce(`${current.label}: ${said}.`);
      onChanged();
      if (kind === "manual") { onEditManually(current.register_keys[0]); return; }
      setIndex(next(index));
    } catch (err) {
      toast(err instanceof ApiError && err.message ? err.message : "Die Entscheidung konnte nicht gespeichert werden.", "error");
    } finally {
      setBusy(false);
    }
  }

  const accept = () => void act("accept", "übernommen");
  const keep = () => void act("keep", "bisheriger Wert bleibt");
  const skip = () => { if (current) { setAnnounce(`${current.label}: übersprungen.`); setIndex(next(index)); } };

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable)) return;
      if (event.key === "Escape") { event.preventDefault(); onExit(); return; }
      if (event.key === "ArrowLeft") { event.preventDefault(); setIndex((value) => Math.max(0, Math.min(value, order.length) - 1)); return; }
      if (event.key === "ArrowRight") { event.preventDefault(); setIndex((value) => Math.min(order.length, value + 1)); return; }
      if (!current || busy || !canDecide || decision(current) !== "pending") return;
      if (event.key === "Enter" && !(target && target.tagName === "BUTTON")) { event.preventDefault(); if (current.kind === "missing") keep(); else accept(); return; }
      const key = event.key.toLowerCase();
      if (key === "b") { event.preventDefault(); keep(); return; }
      if (key === "s") { event.preventDefault(); skip(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const status = current ? decision(current) : "pending";
  const diff = current?.kind === "deviating" && current.current && current.proposed && !sameText(current.current, current.proposed) ? wordDiff(current.current, current.proposed) : null;
  const page = current?.evidence.find((item) => item.page != null)?.page ?? null;

  return <section className="erm" aria-labelledby="prm-title">
    <header className="erm-bar">
      <button type="button" className="btn btn-ghost erm-icon-btn" onClick={onExit} aria-label="Zurück zum Vertrag">{BACK}</button>
      <h2 id="prm-title">Vorschläge prüfen</h2>
      <span className="erm-file">{FILE}{[`Analyse #${run.number} · ${run.mode_label}`, contractTitle].filter(Boolean).join(" · ")}</span>
      <div className="erm-progress">
        <span>{done ? `${order.length} von ${order.length}` : `Vorschlag ${index + 1} von ${order.length}`}</span>
        <span className="erm-seg" aria-hidden="true">{order.map((row, position) => <i key={row.key} className={!done && position === index ? "is-current" : decision(row) === "pending" ? "is-open" : decision(row) === "accepted" ? "is-confirmed" : "is-skipped"} />)}</span>
        <Signal tone={decided ? "done" : "neutral"} size="sm">{`${decided} entschieden`}</Signal>
      </div>
    </header>

    <div className="erm-body">
      <div className="erm-viewer">{viewer}</div>
      <div className="erm-panel" role="region" aria-label="Aktueller Vorschlag">
        <p className="visually-hidden" aria-live="polite">{announce}</p>
        {done || !current ? <div className="erm-done">
          <p className="erm-done-eyebrow">Analyse #{run.number}</p>
          <h3 ref={headingRef} tabIndex={-1} className="erm-done-title"><span className="erm-done-mark" aria-hidden="true">{CHECK}</span>{order.length ? "Vorschläge entschieden" : "Keine offenen Vorschläge"}</h3>
          <p className="erm-done-lead">{order.length
            ? `${decided} von ${order.length} entschieden${order.length - decided ? `; ${order.length - decided} übersprungen – sie bleiben offen` : ""}.`
            : "Diese Analyse hat nichts zum Entscheiden."}</p>
          <div className="erm-done-actions"><button type="button" className="btn btn-primary" onClick={onExit}>Zum Vertrag{NEXT}</button></div>
        </div> : <>
          <div className="erm-head">
            <div className="erm-head-top">
              <SectionChip section={sectionByKey(current.section)} />
              <span className="erm-pos">{index + 1} / {order.length}</span>
              <span className="erm-space" />
              <Signal tone={status !== "pending" ? (status === "accepted" ? "done" : "neutral") : current.kind === "new" ? "info" : current.kind === "missing" ? "critical" : "warning"} size="sm">
                {status === "accepted" ? "Übernommen" : status === "kept_old" ? "Behalten" : status === "manual" ? "Selbst erfasst" : KIND_TEXT[current.kind]}
              </Signal>
            </div>
            <h3 ref={headingRef} tabIndex={-1} className="erm-title">{current.label}</h3>
            <p className="erm-where">
              <span>{page != null ? `Seite ${page}` : "Ohne Seite"} · {sectionByKey(current.section).label}</span>
              {current.confidence != null ? <span>KI-Sicherheit {Math.round(current.confidence * 100)} %</span> : null}
            </p>
          </div>

          <div className="erm-main">
            <div className="erm-compare">
              <div className="erm-box erm-box--sys">
                <span className="erm-box-label"><span>{DB}In MedFlux gespeichert</span></span>
                <span className="erm-box-value">{current.current == null ? <span className="erm-muted">Kein gespeicherter Wert</span> : diff ? <Diff tokens={diff.a} /> : current.current}</span>
              </div>
              <div className="erm-box erm-box--doc">
                <span className="erm-box-label"><span>{FILE}Im Dokument (neu erkannt)</span></span>
                <span className="erm-box-value">{current.proposed == null ? <span className="erm-muted">Nicht mehr gefunden</span> : diff ? <Diff tokens={diff.b} /> : current.proposed}</span>
              </div>
            </div>
            {current.kind === "new"
              ? <p className="erm-result erm-result--neutral">{CHECK_CIRCLE}Neu gefunden – bisher ist hier nichts gespeichert.</p>
              : current.kind === "missing"
                ? <p className="erm-result erm-result--warning">{WARN}Nicht mehr gefunden – der gespeicherte Wert bleibt, bis Sie entscheiden.</p>
                : <p className="erm-result erm-result--warning">{WARN}Weicht ab – Unterschiede sind markiert.</p>}
            {current.evidence[0]?.quote ? <p className="prm-quote">„{current.evidence[0].quote}“</p> : null}

            {!canDecide ? <p className="erm-readonly">Nur Lesen – entscheiden darf das Vertragsmanagement.</p>
              : status !== "pending" ? <p className="erm-readonly">Bereits entschieden.</p>
                : <div className="erm-actions">
                  {current.kind === "missing"
                    ? <button type="button" className="btn btn-primary erm-confirm" disabled={busy} onClick={keep}>{CHECK}Behalten<Kbd>Enter</Kbd></button>
                    : <button type="button" className="btn btn-primary erm-confirm" disabled={busy} onClick={accept}>{CHECK}Übernehmen<Kbd>Enter</Kbd></button>}
                  <div className="erm-row2">
                    {current.kind !== "missing" ? <button type="button" className="btn" disabled={busy} onClick={keep}>Behalten<Kbd>B</Kbd></button> : null}
                    <button type="button" className="btn" disabled={busy} onClick={() => void act("manual", "selbst erfassen")}>{PEN}Selbst erfassen</button>
                    <button type="button" className="btn" disabled={busy} onClick={skip}>{SKIP}Überspringen<Kbd>S</Kbd></button>
                  </div>
                  <p className="erm-hint">Übernehmen schreibt den neuen Wert in die Vertragsdaten (Herkunft: KI, Analyse #{run.number}). Von Hand gepflegte Werte bleiben und erhalten nur einen Vorschlag.</p>
                </div>}
          </div>
        </>}

        {done || !current ? null : <nav className="erm-foot" aria-label="Vorschläge blättern">
          <button type="button" className="btn btn-sm" disabled={index === 0} onClick={() => setIndex(index - 1)}>{PREV}Zurück</button>
          <span className="erm-foot-next">{index + 1 < order.length ? `Nächster: ${order[index + 1].label}` : "Letzter Vorschlag"}</span>
          <button type="button" className="btn btn-sm" onClick={() => setIndex(index + 1)}>Weiter{NEXT}</button>
        </nav>}
      </div>
    </div>
  </section>;
}
