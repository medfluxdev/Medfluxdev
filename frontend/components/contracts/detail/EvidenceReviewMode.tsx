"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import ActionMenu from "@/components/ui/ActionMenu";
import Dialog from "@/components/ui/Dialog";
import Drawer from "@/components/ui/Drawer";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import { reviewContractFact } from "@/lib/domain-api/contracts";
import { startReextraction } from "@/lib/domain-api/reextraction";
import { getDocumentPageText, logEvidenceRound, saveEvidenceReview, type EvidenceReviewItem, type EvidenceReviewStatus } from "@/lib/domain-api/register";
import {
  PRECISION, STATUS_VIEW, confidenceOf, documentValue, evidenceRows, evidenceStatus, guidedOrder, percent, precisionOf,
  roundSummary, sameText, sectionOf, storedValue, titleOf, wordDiff, type EvidenceSection, type EvidenceStatus,
} from "@/lib/evidence";
import EvidenceTable from "./EvidenceTable";

const icon = (body: ReactNode, className = "erm-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const BACK = icon(<path d="m15 6-6 6 6 6" />);
const LIST = icon(<path d="M8 6h13M8 12h13M8 18h13M3 6h.5M3 12h.5M3 18h.5" />);
const FILE = icon(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></>);
const CHECK = icon(<path d="M20 6 9 17l-5-5" />);
const CHECK_CIRCLE = icon(<><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>);
const WARN = icon(<><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>);
const SKIP = icon(<path d="M5 5l9 7-9 7zM19 5v14" />);
const PIN = icon(<><path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10z" /><circle cx="12" cy="11" r="2" /></>);
const DB = icon(<><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>);
const SPARK = icon(<path d="M12 3v4M12 17v4M3 12h4M17 12h4M12 8l2 4-2 4-2-4z" />);
const PEN = icon(<><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></>);
const PREV = icon(<path d="M19 12H5M11 6l-6 6 6 6" />);
const NEXT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);
const SECTION_ICON: Record<string, ReactNode> = {
  partner: <><rect x="4" y="3" width="16" height="18" rx="1.5" /><path d="M8 7h3M13 7h3M8 11h3M13 11h3M8 15h3M13 15h3M10 21v-3h4v3" /></>,
  term: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  cost: <><circle cx="12" cy="12" r="9" /><path d="M15 8.5a4 4 0 1 0 0 7M7 11h6M7 13.5h6" /></>,
  services: <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z" />,
  device: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>,
  other: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></>,
};
const DEVIATION_LABEL: Record<Choice, string> = { document: "Dokument übernommen", medflux: "Abweichung geklärt", manual: "Wert eingetragen" };
const SAFE_CONFIDENCE = 0.95;
const HUMAN_DONE = new Set(["confirmed", "corrected"]);

type Choice = "document" | "medflux" | "manual";
interface Deviation { choice: Choice; value: string; note: string; picker: boolean }

function Kbd({ children }: { children: string }) {
  return <kbd className="erm-kbd" aria-hidden="true">{children}</kbd>;
}

function SectionChip({ section }: { section: EvidenceSection }) {
  return <span className={`erm-section erm-tone--${section.tone}`}>{icon(SECTION_ICON[section.key] ?? SECTION_ICON.other, "erm-section-icon")}{section.label}</span>;
}

function Diff({ tokens }: { tokens: { text: string; changed: boolean }[] }) {
  return <>{tokens.map((token, index) => <span key={index}>{index ? " " : ""}{token.changed ? <mark className="erm-diff">{token.text}</mark> : token.text}</span>)}</>;
}

/**
 * „Nachweise prüfen“: ein Nachweis nach dem anderen. Links das Original mit der Fundstelle, rechts der Abgleich
 * „Im Dokument (erkannt)“ ↔ „In MedFlux gespeichert“ und eine Entscheidung (Bestätigen, Abweichung, Überspringen).
 * Werte werden über die Faktprüfung gespeichert, das Ergebnis je Nachweis über `/evidence-reviews`.
 */
export default function EvidenceReviewMode({
  contractId, orgSlug, contractTitle, evidence, numbers, factByEvidence, reviews, startId, canReview, viewer,
  onShow, onExit, onReload, canRecognize = false, onRecognizeStarted,
}: {
  contractId: string;
  orgSlug: string;
  contractTitle: string | null;
  /** In Lesereihenfolge (Nummern wie in der Liste). */
  evidence: EvidenceRef[];
  numbers: Map<string, number>;
  factByEvidence: Map<string, FactReviewStateDto>;
  reviews: Map<string, EvidenceReviewItem>;
  startId: string | null;
  canReview: boolean;
  /** Die Ansicht des Originals (vom Arbeitsplatz, damit Zoom/Seite erhalten bleiben). */
  viewer: ReactNode;
  /** Nachweis im Original zeigen (Datei, Seite, Rahmen). */
  onShow: (ref: EvidenceRef) => void;
  onExit: () => void;
  /** Vertrag und Prüfstand neu laden. */
  onReload: () => void;
  /** „Nachweis neu erkennen“ erlaubt (Recht `contract.reanalyze`, kein Lauf aktiv). */
  canRecognize?: boolean;
  /** Ein Lauf wurde gestartet (Stand der erneuten Erfassung neu laden). */
  onRecognizeStarted?: () => void;
}) {
  const toast = useToast();
  const order = useMemo(() => guidedOrder(evidence, factByEvidence), [evidence, factByEvidence]);
  // Entscheidungen dieser Runde (sofort sichtbar, auch bevor der Stand neu geladen ist).
  const [round, setRound] = useState<Map<string, EvidenceReviewStatus>>(() => new Map());
  const statusOf = (ref: EvidenceRef): EvidenceStatus => {
    const local = round.get(ref.evidence_id);
    if (local) return local === "confirmed" ? "confirmed" : local === "skipped" ? "skipped" : "deviation";
    return evidenceStatus(ref, factByEvidence.get(ref.evidence_id), reviews.get(ref.evidence_id));
  };
  const firstOpen = () => Math.max(0, order.findIndex((ref) => statusOf(ref) === "open"));
  const [index, setIndex] = useState(() => {
    const start = startId ? order.findIndex((ref) => ref.evidence_id === startId) : -1;
    return start >= 0 ? start : firstOpen();
  });
  const [deviation, setDeviation] = useState<Deviation | null>(null);
  const [done, setDone] = useState(() => order.length === 0);
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const [announce, setAnnounce] = useState("");
  const [roundLog, setRoundLog] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const deviationRef = useRef<HTMLFormElement | null>(null);

  const current = order[index] ?? null;
  const fact = current ? factByEvidence.get(current.evidence_id) : undefined;
  const status = current ? statusOf(current) : "open";
  const section = current ? sectionOf(current, fact) : null;
  const precision = current ? precisionOf(current) : "none";
  const confidence = current ? confidenceOf(current, fact) : null;
  const doc = current ? documentValue(current, fact) : null;
  const stored = storedValue(fact);
  const matches = doc != null && stored != null && sameText(doc, stored);
  const diff = doc != null && stored != null && !matches ? wordDiff(doc, stored) : null;
  const review = current ? reviews.get(current.evidence_id) : undefined;
  // Wortlaut nachweislich an der markierten Stelle (Backend `text_verified`, genaue Lage).
  const verified = Boolean(current?.text_verified) && precision === "exact";

  const rows = evidenceRows(order, numbers, factByEvidence, statusOf);
  const totals = { confirmed: rows.filter((row) => row.status === "confirmed").length, deviation: rows.filter((row) => row.status === "deviation").length, skipped: rows.filter((row) => row.status === "skipped").length, open: rows.filter((row) => row.status === "open").length };
  const nextOpenIndex = (from: number) => {
    for (let step = 1; step <= order.length; step += 1) {
      const candidate = (from + step) % order.length;
      if (statusOf(order[candidate]) === "open" && candidate !== from) return candidate;
    }
    return -1;
  };
  const upcoming = nextOpenIndex(index);
  const following = order[index + 1] ?? null;
  const safe = canReview ? order.filter((ref) => {
    const item = factByEvidence.get(ref.evidence_id);
    const value = documentValue(ref, item);
    const kept = storedValue(item);
    return statusOf(ref) === "open" && (confidenceOf(ref, item) ?? 0) >= SAFE_CONFIDENCE && precisionOf(ref) === "exact" && (kept == null || sameText(value, kept));
  }) : [];

  // Im Original zeigen; Fokus auf die Überschrift (Screenreader hört den neuen Nachweis).
  useEffect(() => {
    if (!current || done) return;
    onShow(current);
    setDeviation(null);
    headingRef.current?.focus();
    // onShow wechselt nur die Ansicht; neu auslösen soll nur ein anderer Nachweis.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.evidence_id, done]);

  // Kasten „Abweichung“ geöffnet: Fokus auf die gewählte Option.
  const deviationOpen = deviation != null;
  useEffect(() => { if (deviationOpen) deviationRef.current?.querySelector<HTMLInputElement>("input[type=radio]:checked")?.focus(); }, [deviationOpen]);

  // Ende der Runde: Zusammenfassung in den Verlauf (einmal je Runde).
  useEffect(() => {
    if (!done || !canReview || round.size === 0 || roundLog) return;
    const counts = countRound(round);
    setRoundLog(roundSummary(counts));
    logEvidenceRound(orgSlug, contractId, counts).catch(() => toast("Die Zusammenfassung konnte nicht im Verlauf gespeichert werden.", "error"));
  }, [done, canReview, round, roundLog, orgSlug, contractId, toast]);

  function exit() {
    if (canReview && round.size > 0 && !roundLog) {
      logEvidenceRound(orgSlug, contractId, countRound(round)).catch(() => undefined);
    }
    onExit();
  }

  function go(target: number) {
    if (target < 0) return;
    if (target >= order.length) { setDone(true); return; }
    setDone(false);
    setIndex(target);
  }

  function advance(after: Map<string, EvidenceReviewStatus>, saidLabel: string) {
    const open = (candidate: number) => {
      const ref = order[candidate];
      return !after.has(ref.evidence_id) && evidenceStatus(ref, factByEvidence.get(ref.evidence_id), reviews.get(ref.evidence_id)) === "open";
    };
    let next = -1;
    for (let step = 1; step < order.length; step += 1) {
      const candidate = (index + step) % order.length;
      if (open(candidate)) { next = candidate; break; }
    }
    if (next < 0) {
      setAnnounce(`${saidLabel} · alle Nachweise bearbeitet`);
      setDone(true);
      return;
    }
    setAnnounce(`${saidLabel} · weiter zu ${titleOf(order[next], factByEvidence)}`);
    setIndex(next);
  }

  async function decide(ref: EvidenceRef, outcome: EvidenceReviewStatus, options: { factAction?: "confirmed" | "corrected"; value?: unknown; note?: string } = {}) {
    const item = factByEvidence.get(ref.evidence_id);
    const note = options.note?.trim() || null;
    if (item && options.factAction && !(options.factAction === "confirmed" && HUMAN_DONE.has(item.state))) {
      await reviewContractFact(contractId, orgSlug, {
        fact_key: item.fact_key,
        action: options.factAction,
        ...(options.factAction === "corrected" ? { corrected_value: options.value, note: note ?? "Bei der Nachweisprüfung korrigiert." } : note ? { note } : {}),
        evidence_ref: ref.evidence_id,
        expected_reviewed_at: item.reviewed_at ?? null,
      });
    }
    await saveEvidenceReview(orgSlug, contractId, { evidence_id: ref.evidence_id, status: outcome, fact_key: item?.fact_key ?? null, note });
  }

  async function run(outcome: EvidenceReviewStatus, options: { factAction?: "confirmed" | "corrected"; value?: unknown; note?: string }, saidLabel: string) {
    if (!current || busy) return;
    setBusy(true);
    try {
      await decide(current, outcome, options);
      const after = new Map(round).set(current.evidence_id, outcome);
      setRound(after);
      setDeviation(null);
      onReload();
      advance(after, saidLabel);
    } catch (err) {
      const conflict = err instanceof ApiError && err.status === 409;
      const readable = err instanceof ApiError && err.status === 422 && err.message ? err.message : null;
      toast(conflict ? "Die Angabe wurde inzwischen geändert – Stand neu geladen." : readable ?? "Die Prüfung konnte nicht gespeichert werden.", "error");
      if (conflict) onReload();
    } finally {
      setBusy(false);
    }
  }

  const confirm = () => void run("confirmed", { factAction: "confirmed" }, "Bestätigt");
  const skip = () => void run("skipped", {}, "Übersprungen");

  function submitDeviation() {
    if (!deviation) return;
    const note = deviation.note;
    if (deviation.choice === "document") {
      // Angabe mit Feld: der Text wird wie eine Dokumentstelle gelesen; sonst der erkannte Rohwert.
      const value = fact?.register_field ? doc : fact?.original_value ?? doc;
      void run("document", fact?.is_evidence_item ? { factAction: "confirmed", note } : { factAction: "corrected", value, note }, DEVIATION_LABEL.document);
    } else if (deviation.choice === "medflux") {
      void run("medflux", { factAction: "confirmed", note }, DEVIATION_LABEL.medflux);
    } else if (deviation.value.trim()) {
      void run("manual", { factAction: "corrected", value: deviation.value.trim(), note }, DEVIATION_LABEL.manual);
    }
  }

  async function confirmSafe() {
    setConfirmAll(false);
    setBusy(true);
    const after = new Map(round);
    let failed = 0;
    for (const ref of safe) {
      try {
        await decide(ref, "confirmed", { factAction: "confirmed" });
        after.set(ref.evidence_id, "confirmed");
      } catch {
        failed += 1;
      }
    }
    setRound(after);
    setBusy(false);
    onReload();
    const saved = safe.length - failed;
    toast(failed ? `${saved} bestätigt, ${failed} nicht gespeichert.` : `${saved} sichere Nachweise bestätigt.`, failed ? "error" : "success");
    if (current && after.has(current.evidence_id)) advance(after, `${saved} bestätigt`);
  }

  function openDeviation(choice: Choice = matches || stored == null ? "manual" : "document", value = stored ?? doc ?? "") {
    if (!canReview || !current) return;
    setDeviation({ choice, value, note: "", picker: false });
  }

  /**
   * „Nachweis neu erkennen“: die KI liest die Seite des Nachweises erneut – gezielt für diese Angabe, wenn sie als
   * eigene Angabe erfasst werden kann, sonst die ganze Seite. Das Ergebnis erscheint oben als „Neue Auswertung“
   * und wird erst nach Auswahl übernommen.
   */
  async function recognizeAgain() {
    if (!current) return;
    const base = (fact?.fact_key ?? current.field_ref ?? "").replace(/^evidence\./, "").split(".evidence")[0];
    const keys = Array.from(new Set([base, base.split(".").slice(0, 2).join(".")].filter(Boolean)));
    const pageHint = current.page != null ? [current.page] : [];
    const attempts = [
      ...keys.map((key) => ({ mode: "missing_fields" as const, fields: [key], page_hint: pageHint })),
      { mode: "full" as const, page_hint: pageHint },
    ];
    setBusy(true);
    try {
      for (const attempt of attempts) {
        try {
          await startReextraction(orgSlug, contractId, attempt);
          toast(`Erkennung gestartet${current.page != null ? ` (Seite ${current.page})` : ""}. Das Ergebnis erscheint oben unter „Neue Auswertung“.`, "success");
          onRecognizeStarted?.();
          return;
        } catch (err) {
          // Angabe nicht einzeln erfassbar: nächster Versuch (zuletzt die ganze Seite).
          if (!(err instanceof ApiError && err.status === 422)) throw err;
        }
      }
    } catch (err) {
      toast(err instanceof ApiError && err.message ? err.message : "Die Erkennung konnte nicht gestartet werden.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function copyQuote() {
    if (!current?.snippet) return;
    try {
      await navigator.clipboard.writeText(current.snippet);
      toast("Zitat kopiert.", "success");
    } catch {
      toast("Das Zitat konnte nicht kopiert werden.", "error");
    }
  }

  // Tasten: Enter bestätigt, A Abweichung, S überspringen, ←/→ blättern, Esc schließt den Kasten.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (drawer || confirmAll || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "Escape" && deviation) { event.preventDefault(); setDeviation(null); headingRef.current?.focus(); return; }
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) return;
      if (event.key === "ArrowRight") { event.preventDefault(); go(index + 1); return; }
      if (event.key === "ArrowLeft") { event.preventDefault(); if (done) setDone(false); else go(index - 1); return; }
      if (done || deviation || !canReview || !current || busy) return;
      if (event.key === "Enter" && tag !== "BUTTON" && tag !== "A") { event.preventDefault(); confirm(); return; }
      if (event.key === "a" || event.key === "A") { event.preventDefault(); openDeviation(); return; }
      if (event.key === "s" || event.key === "S") { event.preventDefault(); skip(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const number = current ? numbers.get(current.evidence_id) ?? index + 1 : 0;
  const roundCounts = countRound(round);
  const statusView = STATUS_VIEW[status];

  return <section className="erm" aria-labelledby="erm-title">
    <header className="erm-bar">
      <button type="button" className="btn btn-ghost erm-icon-btn" onClick={exit} aria-label="Zurück zum Vertrag">{BACK}</button>
      <h2 id="erm-title">Nachweise prüfen</h2>
      <span className="erm-file">{FILE}{[current?.original_filename, contractTitle].filter(Boolean).join(" · ")}</span>
      <div className="erm-progress">
        <span>{done ? `${order.length} von ${order.length}` : `Nachweis ${index + 1} von ${order.length}`}</span>
        <span className="erm-seg" aria-hidden="true">{rows.map((row, position) => <i key={row.ref.evidence_id} className={!done && position === index ? "is-current" : `is-${row.status}`} />)}</span>
        <Signal tone={totals.deviation ? "warning" : totals.confirmed ? "done" : "neutral"} size="sm">{`${totals.confirmed} bestätigt · ${totals.deviation} abweichend`}</Signal>
      </div>
      <button type="button" className="btn erm-all" onClick={() => setDrawer(true)}>{LIST}Alle Nachweise</button>
      <ActionMenu items={[
        { label: "Zitat kopieren", onSelect: () => void copyQuote(), disabled: !current?.snippet },
        { label: "Nachweis neu erkennen", onSelect: () => void recognizeAgain(), disabled: !canRecognize || !current || busy },
        { label: `Alle sicheren ≥ 0,95 bestätigen${safe.length ? ` (${safe.length})` : ""}`, onSelect: () => setConfirmAll(true), disabled: safe.length === 0 || busy },
      ]} />
    </header>

    <div className="erm-body">
      <div className="erm-viewer">
        {viewer}
        {!done && upcoming >= 0 ? <p className="erm-next-card">Nächster Nachweis: {order[upcoming].page != null ? `Seite ${order[upcoming].page} · ` : ""}{sectionOf(order[upcoming], factByEvidence.get(order[upcoming].evidence_id)).label}</p> : null}
      </div>

      <div className="erm-panel" role="region" aria-label="Aktueller Nachweis">
        <p className="visually-hidden" aria-live="polite">{announce}</p>
        {done || !current ? <div className="erm-done">
          <Signal tone={totals.open ? "info" : "done"}>{totals.open ? `${totals.open} noch offen` : "Alles geprüft"}</Signal>
          <h3 ref={headingRef} tabIndex={-1}>{round.size ? roundLog ?? roundSummary(roundCounts) : "Keine Entscheidung in dieser Runde"}</h3>
          <p>{totals.open
            ? "Offene und übersprungene Nachweise bleiben in der Liste und unter „Offene Punkte“."
            : "Jeder Nachweis ist bestätigt oder als Abweichung geklärt."}</p>
          <div className="erm-done-actions">
            <button type="button" className="btn btn-primary" onClick={exit}>Zum Vertrag</button>
            {totals.skipped ? <button type="button" className="btn" onClick={() => {
              const first = order.findIndex((ref) => statusOf(ref) === "skipped");
              setRound(new Map()); setRoundLog(null); setDone(false); setIndex(Math.max(0, first));
            }}>Übersprungene prüfen</button> : null}
          </div>
        </div> : <>
          <div className="erm-head">
            <div className="erm-head-top">
              {section ? <SectionChip section={section} /> : null}
              <span className="erm-pos">{index + 1} / {order.length}</span>
              <span className="erm-space" />
              <Signal tone={statusView.tone} size="sm">{status === "deviation" && review ? review.status_label : statusView.label}</Signal>
            </div>
            <h3 ref={headingRef} tabIndex={-1} className="erm-title">
              <span className={`erm-tile erm-tone--${section?.tone ?? "neutral"}`}>{icon(SECTION_ICON[section?.key ?? "other"] ?? SECTION_ICON.other, "erm-tile-icon")}</span>
              {titleOf(current, factByEvidence)}
            </h3>
            <p className="erm-where">
              <span>{PIN}<span className="erm-num" aria-label={`Nachweis ${number}`}>{number}</span> · {current.page != null ? `Seite ${current.page}` : "Ohne Seite"} · {section?.label}</span>
              {confidence != null ? <span>{SPARK}KI-Sicherheit {percent(confidence)}</span> : fact?.found_by_rule ? <span>{SPARK}Von festen Regeln gefunden</span> : null}
              {precision !== "exact" ? <Signal tone={PRECISION[precision].tone} size="sm" title={PRECISION[precision].hint}>{PRECISION[precision].label}</Signal> : null}
            </p>
          </div>

          <div className="erm-main">
            <div className="erm-compare">
              <div className="erm-box erm-box--doc">
                <span className="erm-box-label"><span>{FILE}Im Dokument (erkannt)</span></span>
                <span className="erm-box-value">{doc == null ? <span className="erm-muted">Kein Wert erkannt{current.snippet ? <> · Wortlaut: „{current.snippet}“</> : null}</span> : diff ? <Diff tokens={diff.a} /> : doc}</span>
              </div>
              <div className="erm-box erm-box--sys">
                <span className="erm-box-label"><span>{DB}In MedFlux gespeichert</span>
                  {canReview && fact && !fact.is_evidence_item && !deviation ? <button type="button" className="btn btn-ghost btn-sm erm-edit" onClick={() => openDeviation("manual", stored ?? doc ?? "")}>{PEN}Bearbeiten</button> : null}
                </span>
                <span className="erm-box-value">{stored == null ? <span className="erm-muted">Kein gespeicherter Wert</span> : diff ? <Diff tokens={diff.b} /> : stored}</span>
              </div>
            </div>
            {stored == null && verified
              ? <p className="erm-result erm-result--done">{CHECK_CIRCLE}Wortlaut steht an dieser Stelle im Dokument.</p>
              : stored == null
              ? <p className="erm-result erm-result--neutral">{CHECK_CIRCLE}{doc == null ? "Kein Wert zum Abgleichen – geprüft wird nur die Fundstelle." : "Nichts gespeichert – bestätigt wird die Fundstelle im Dokument."}</p>
              : matches
                ? <p className="erm-result erm-result--done">{CHECK_CIRCLE}Dokument und MedFlux stimmen überein.</p>
                : <p className="erm-result erm-result--warning">{WARN}{doc == null ? "Im Dokument wurde kein Wert erkannt – bitte die Stelle prüfen." : "Weicht ab – Unterschiede sind markiert."}</p>}
            {confidence != null ? <div className="erm-confidence">
              <span>KI-Sicherheit</span>
              <span className="erm-meter" aria-hidden="true"><i className={confidence >= 0.9 ? "is-high" : confidence >= 0.7 ? "is-mid" : "is-low"} style={{ width: `${Math.round(confidence * 100)}%` }} /></span>
              <span className="erm-meter-value">{percent(confidence)}</span>
            </div> : verified ? <div className="erm-confidence">
              {/* Keine KI-Sicherheit (feste Regel/Wortlaut): belegt ist die Fundstelle, keine Prozentzahl erfinden. */}
              <span>Fundstelle</span>
              <span className="erm-meter" aria-hidden="true"><i className="is-high" style={{ width: "100%" }} /></span>
              <span className="erm-meter-value">Wörtlich belegt</span>
            </div> : null}

            {!canReview ? <p className="erm-readonly">Nur Lesen – bestätigen und Abweichungen klären dürfen Prüfende und das Vertragsmanagement.</p>
              : deviation ? <form ref={deviationRef} className="erm-deviate" aria-labelledby="erm-deviate-title" onSubmit={(event) => { event.preventDefault(); submitDeviation(); }}>
                <h4 id="erm-deviate-title">{WARN}Abweichung – was gilt?</h4>
                <fieldset className="erm-options">
                  <legend className="visually-hidden">Was gilt?</legend>
                  {([
                    ["document", "Dokument hat recht → Wert in MedFlux übernehmen", "Erkannter Text wird gespeichert; Herkunft: KI · bestätigt"],
                    ["medflux", "MedFlux hat recht → Dokumentstelle ist falsch oder veraltet", "Wert bleibt; Nachweis wird als „abweichend, geklärt“ markiert"],
                    ["manual", "Beides falsch → selbst eingeben", "Herkunft: Manuell"],
                  ] as [Choice, string, string][]).map(([value, label, hint]) => <label key={value} className={`erm-option${deviation.choice === value ? " is-on" : ""}`}>
                    <input type="radio" name="erm-choice" value={value} checked={deviation.choice === value}
                      disabled={value === "document" && doc == null} onChange={() => setDeviation({ ...deviation, choice: value })} />
                    <span>{label}<small>{hint}</small></span>
                  </label>)}
                </fieldset>
                {deviation.choice === "manual" ? <div className="erm-manual">
                  <label className="erm-field">Richtiger Wert<input value={deviation.value} onChange={(event) => setDeviation({ ...deviation, value: event.target.value })} /></label>
                  {current.document_version_id && current.page != null
                    ? <button type="button" className="btn btn-ghost btn-sm" aria-expanded={deviation.picker} onClick={() => setDeviation({ ...deviation, picker: !deviation.picker })}>Text im Dokument markieren und übernehmen</button>
                    : null}
                  {deviation.picker && current.document_version_id && current.page != null
                    ? <PageTextPicker contractId={contractId} orgSlug={orgSlug} documentVersionId={current.document_version_id} page={current.page} onPick={(text) => setDeviation({ ...deviation, value: text, picker: false })} />
                    : null}
                </div> : null}
                <label className="erm-field">Notiz (optional)<input value={deviation.note} onChange={(event) => setDeviation({ ...deviation, note: event.target.value })} /></label>
                <div className="erm-row2">
                  <button type="submit" className="btn btn-primary" disabled={busy || (deviation.choice === "manual" && !deviation.value.trim())}>{busy ? "Wird gespeichert…" : "Übernehmen · Weiter"}</button>
                  <button type="button" className="btn" onClick={() => { setDeviation(null); headingRef.current?.focus(); }}>Abbrechen<Kbd>Esc</Kbd></button>
                </div>
              </form>
              : <div className="erm-actions">
                <button type="button" className="btn btn-primary erm-confirm" disabled={busy} onClick={confirm}>{CHECK}{busy ? "Wird gespeichert…" : "Bestätigen"}<Kbd>Enter</Kbd></button>
                <div className="erm-row2">
                  <button type="button" className="btn" disabled={busy} onClick={() => openDeviation()}>{WARN}Abweichung<Kbd>A</Kbd></button>
                  <button type="button" className="btn" disabled={busy} onClick={skip}>{SKIP}Überspringen<Kbd>S</Kbd></button>
                </div>
                <p className="erm-hint">Bestätigt wird der gespeicherte Wert; der Nachweis bleibt mit der Dokumentstelle verknüpft.</p>
              </div>}
          </div>
        </>}

        <nav className="erm-foot" aria-label="Nachweise blättern">
          <button type="button" className="btn btn-sm" disabled={!done && index === 0} onClick={() => (done ? setDone(false) : go(index - 1))}>{PREV}Zurück</button>
          <span className="erm-foot-next">{done ? "" : following ? `Nächster: ${titleOf(following, factByEvidence)}${following.page != null ? ` · Seite ${following.page}` : ""}` : "Letzter Nachweis"}</span>
          <button type="button" className="btn btn-sm" disabled={done} onClick={() => go(index + 1)}>Weiter{NEXT}</button>
        </nav>
      </div>
    </div>

    <Drawer open={drawer} title="Alle Nachweise" onClose={() => setDrawer(false)} wide>
      <EvidenceTable rows={rows} currentId={done ? null : current?.evidence_id ?? null} withSection filters caption="Alle Nachweise dieses Vertrags"
        onPick={(ref) => { setDrawer(false); go(order.findIndex((item) => item.evidence_id === ref.evidence_id)); }} />
    </Drawer>
    <Dialog open={confirmAll} title="Alle sicheren Nachweise bestätigen?" onClose={() => setConfirmAll(false)}
      description={`${safe.length} offene ${safe.length === 1 ? "Nachweis hat" : "Nachweise haben"} eine KI-Sicherheit ab 95 %, eine genau belegte Fundstelle und keinen abweichenden gespeicherten Wert.`}
      actions={<><button type="button" className="btn" onClick={() => setConfirmAll(false)}>Abbrechen</button><button type="button" className="btn btn-primary" onClick={() => void confirmSafe()}>{safe.length} bestätigen</button></>} />
  </section>;
}

function countRound(round: Map<string, EvidenceReviewStatus>): Partial<Record<EvidenceReviewStatus, number>> {
  const out: Partial<Record<EvidenceReviewStatus, number>> = {};
  for (const outcome of round.values()) out[outcome] = (out[outcome] ?? 0) + 1;
  return out;
}

/** Seitentext, wie MedFlux ihn gelesen hat: eine Stelle markieren und als Wert übernehmen. */
function PageTextPicker({ contractId, orgSlug, documentVersionId, page, onPick }: {
  contractId: string; orgSlug: string; documentVersionId: string; page: number; onPick: (text: string) => void;
}) {
  const [text, setText] = useState<string | null | undefined>(undefined);
  const [selection, setSelection] = useState("");
  const boxRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    let alive = true;
    getDocumentPageText(orgSlug, contractId, documentVersionId, page)
      .then((result) => { if (alive) setText(result.text); })
      .catch(() => { if (alive) setText(null); });
    return () => { alive = false; };
  }, [contractId, orgSlug, documentVersionId, page]);
  function take() {
    const current = window.getSelection();
    if (current && !current.isCollapsed && current.anchorNode && boxRef.current?.contains(current.anchorNode)) setSelection(current.toString().trim());
  }
  if (text === undefined) return <p className="erm-muted" role="status">Seitentext wird geladen …</p>;
  if (text === null) return <p className="erm-muted">Für diese Seite liegt kein gelesener Text vor.</p>;
  return <div className="erm-picker">
    <div ref={boxRef} className="erm-picker-text" tabIndex={0} role="document" aria-label={`Text der Seite ${page}`} onMouseUp={take} onKeyUp={take}>{text}</div>
    <button type="button" className="btn btn-sm" disabled={!selection} onClick={() => onPick(selection)}>{selection ? `„${selection.length > 40 ? `${selection.slice(0, 40)}…` : selection}“ übernehmen` : "Text markieren"}</button>
  </div>;
}
