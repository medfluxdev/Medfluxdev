"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import { evidenceGroupLabel } from "@/lib/contract-detail-types";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import { evidencePrecision } from "@/lib/source-geometry";

interface Props {
  evidence: EvidenceRef[];
  activeEvidenceId: string | null;
  onNavigate: (ref: EvidenceRef) => void;
  /** Prüf-Angaben: ihr Name ist die beste Überschrift eines Nachweises, ihr Stand der Prüfstand. */
  facts?: FactReviewStateDto[];
  /** Meldet die sichtbare Reihenfolge (für „Vorheriger/Nächster“ in der Detailkarte). */
  onVisibleChange?: (ids: string[]) => void;
  /** Mehrere Dateien: Dateiname je Nachweis zeigen. */
  showFile?: boolean;
  /** Reihenfolge der Dateien (für die Lesereihenfolge der Nachweise). */
  documentIds?: string[];
}

type ReviewFilter = "" | "open" | "done";
const REVIEW_DONE = new Set(["confirmed", "corrected", "auto_accepted"]);

/** Prüfstand eines Nachweises: aus der zugehörigen Prüf-Angabe, sonst „zu prüfen“, wenn der Nachweis es verlangt. */
export function reviewStateOf(ref: EvidenceRef, fact: FactReviewStateDto | undefined): "done" | "open" | null {
  if (fact) return REVIEW_DONE.has(fact.state) ? "done" : fact.state === "voided" ? null : "open";
  return ref.requires_review ? "open" : null;
}

type Precision = "exact" | "approx" | "page" | "none";
export const PRECISION: Record<Precision, { label: string; tone: SignalTone; hint: string }> = {
  exact: { label: "Genau", tone: "done", hint: "Die Stelle ist im Original genau markiert." },
  approx: { label: "Ungefähr", tone: "neutral", hint: "Nur der Seitenbereich ist bekannt – die Stelle ist dort grob markiert." },
  page: { label: "Nur Seite", tone: "neutral", hint: "Die Seite ist bekannt, aber keine Position auf der Seite." },
  none: { label: "Ohne Seite", tone: "warning", hint: "Keine Seitenangabe – die Quelle lässt sich im Original nicht anzeigen." },
};
const PRECISION_FILTER: { value: "" | Precision; label: string }[] = [
  { value: "", label: "Alle Lagen" },
  { value: "exact", label: "Lage: Genau" },
  { value: "approx", label: "Lage: Ungefähr" },
  { value: "page", label: "Lage: Nur Seite" },
  { value: "none", label: "Lage: Ohne Seite" },
];

export function precisionOf(ref: EvidenceRef): Precision {
  if (ref.page == null) return "none";
  if (!ref.bbox) return "page";
  if (evidencePrecision(ref.bbox, ref.bbox_space) === "coarse") return "approx";
  return ref.supports_exact_navigation ? "exact" : "approx";
}

export function where(ref: EvidenceRef): string | null {
  if (ref.page != null) return `Seite ${ref.page}`;
  if (ref.paragraph_index != null) return `Absatz ${ref.paragraph_index}`;
  if (ref.table_index != null) return `Tabelle ${ref.table_index}`;
  return null;
}

/**
 * Lesereihenfolge der Nachweise: Datei (Reihenfolge der Dokumente), Seite, Lage auf der Seite (oben → unten),
 * Absatz/Tabelle; ohne Seite am Ende. Die Nummer (1 … N) ist fest – Filter und Suche ändern sie nicht.
 */
export function orderEvidence(evidence: EvidenceRef[], documentIds: string[] = []): EvidenceRef[] {
  const docIndex = (ref: EvidenceRef) => { const index = documentIds.indexOf(ref.document_version_id ?? ""); return index < 0 ? documentIds.length : index; };
  const top = (ref: EvidenceRef) => (ref.bbox ? Math.min(ref.bbox.y0, ref.bbox.y1) : Number.MAX_SAFE_INTEGER);
  return evidence.map((ref, index) => ({ ref, index })).sort((a, b) =>
    docIndex(a.ref) - docIndex(b.ref)
    || (a.ref.page ?? Number.MAX_SAFE_INTEGER) - (b.ref.page ?? Number.MAX_SAFE_INTEGER)
    || top(a.ref) - top(b.ref)
    || (a.ref.paragraph_index ?? Number.MAX_SAFE_INTEGER) - (b.ref.paragraph_index ?? Number.MAX_SAFE_INTEGER)
    || (a.ref.table_index ?? Number.MAX_SAFE_INTEGER) - (b.ref.table_index ?? Number.MAX_SAFE_INTEGER)
    || a.index - b.index).map((entry) => entry.ref);
}

/** Nummer je Nachweis (1-basiert, in Lesereihenfolge). */
export function evidenceNumbers(ordered: EvidenceRef[]): Map<string, number> {
  return new Map(ordered.map((ref, index) => [ref.evidence_id, index + 1]));
}

/** Prüf-Angabe zu jedem Nachweis (über die verknüpften Belege). */
export function factsByEvidence(facts: FactReviewStateDto[]): Map<string, FactReviewStateDto> {
  const map = new Map<string, FactReviewStateDto>();
  for (const fact of facts) for (const id of fact.linked_evidence_refs ?? []) if (id && !map.has(id)) map.set(id, fact);
  return map;
}

/** Lesbare Überschrift: Name der Prüf-Angabe, sonst aus dem Quellfeld (z. B. „Kostenposition 8“), nie eine Roh-ID. */
export function titleOf(ref: EvidenceRef, factByEvidence: Map<string, FactReviewStateDto>): string {
  const fact = factByEvidence.get(ref.evidence_id);
  if (fact) return fact.label_de;
  const parts = (ref.field_ref ?? "").split(".").filter((part) => part && part !== "evidence" && !/^\d+$/.test(part));
  const index = (ref.field_ref ?? "").match(/\.(\d+)(?:\.|$)/)?.[1];
  if ((ref.field_ref ?? "").includes("cost_line") && index != null) return `Kostenposition ${Number(index) + 1}`;
  const last = parts[parts.length - 1];
  if (!last) return "Nachweis";
  const words = last.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function confidenceText(value: number | null): string | null {
  if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return null;
  return `KI ${Math.round(value * 100)} %`;
}

/**
 * Nachweise: suchen, nach Bereich und Lage filtern, nach Bereich gruppiert. Ein Klick (oder ↑/↓ + Enter)
 * zeigt die Stelle rechts im Original; Erklärungen zur Genauigkeit stehen im Tooltip statt in jeder Zeile.
 */
export default function EvidencePane({ evidence, activeEvidenceId, onNavigate, facts = [], onVisibleChange, showFile = false, documentIds = [] }: Props) {
  const [query, setQuery] = useState("");
  const [area, setArea] = useState("");
  const [precision, setPrecision] = useState<"" | Precision>("");
  const [review, setReview] = useState<ReviewFilter>("");

  const factByEvidence = useMemo(() => factsByEvidence(facts), [facts]);
  const openCount = evidence.filter((ref) => reviewStateOf(ref, factByEvidence.get(ref.evidence_id)) === "open").length;
  const areas = useMemo(() => [...new Set(evidence.map((ref) => evidenceGroupLabel(ref.field_ref?.split(".")[0] ?? null)))], [evidence]);

  const ordered = useMemo(() => orderEvidence(evidence, documentIds), [evidence, documentIds]);
  const numbers = useMemo(() => evidenceNumbers(ordered), [ordered]);

  // Gruppen je Seite (bei mehreren Dateien je Datei und Seite), in Lesereihenfolge.
  const groups = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    const shown = ordered.filter((ref) => {
      const group = evidenceGroupLabel(ref.field_ref?.split(".")[0] ?? null);
      if (area && group !== area) return false;
      if (precision && precisionOf(ref) !== precision) return false;
      if (review && reviewStateOf(ref, factByEvidence.get(ref.evidence_id)) !== review) return false;
      if (!needle) return true;
      return `${titleOf(ref, factByEvidence)} ${ref.snippet ?? ""}`.toLocaleLowerCase("de-DE").includes(needle);
    });
    const byPage = new Map<string, EvidenceRef[]>();
    for (const ref of shown) {
      const page = ref.page != null ? `Seite ${ref.page}` : "Ohne Seitenangabe";
      const label = showFile && ref.original_filename ? `${page} · ${ref.original_filename}` : page;
      byPage.set(label, [...(byPage.get(label) ?? []), ref]);
    }
    return [...byPage.entries()];
  }, [ordered, query, area, precision, review, factByEvidence, showFile]);
  const shownCount = groups.reduce((sum, [, items]) => sum + items.length, 0);
  const visibleKey = groups.flatMap(([, items]) => items.map((ref) => ref.evidence_id)).join("|");
  useEffect(() => { onVisibleChange?.(visibleKey ? visibleKey.split("|") : []); }, [visibleKey, onVisibleChange]);

  if (evidence.length === 0) {
    return <p className="evidence-empty">Keine Quellenangaben vorhanden.</p>;
  }

  // ↑/↓ wechseln zwischen den Nachweisen der Liste.
  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>(".evidence-item"));
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = buttons[index + (event.key === "ArrowDown" ? 1 : -1)];
    if (next) { event.preventDefault(); next.focus(); }
  }

  return <div className="evidence-browser">
    <div className="evidence-tools">
      <label className="evidence-search">
        <svg className="evidence-tool-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M11 4a7 7 0 1 1 0 14a7 7 0 1 1 0-14zM20 20l-4-4" /></svg>
        <span className="visually-hidden">Nachweise durchsuchen</span>
        <input type="search" placeholder="Nachweise durchsuchen" value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <div className="evidence-filters">
        <label><span className="visually-hidden">Prüfstand</span>
          <select value={review} onChange={(event) => setReview(event.target.value as ReviewFilter)}>
            <option value="">Alle Stände</option>
            <option value="open">Stand: Zu prüfen ({openCount})</option>
            <option value="done">Stand: Geprüft</option>
          </select>
        </label>
        <label><span className="visually-hidden">Bereich</span>
          <select value={area} onChange={(event) => setArea(event.target.value)}>
            <option value="">Alle Bereiche</option>
            {areas.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label><span className="visually-hidden">Lage im Original</span>
          <select value={precision} onChange={(event) => setPrecision(event.target.value as "" | Precision)}>
            {PRECISION_FILTER.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>
      <p className="evidence-count" aria-live="polite">{shownCount === evidence.length ? `${evidence.length} Nachweise` : `${shownCount} von ${evidence.length} Nachweisen`}</p>
    </div>
    <div className="evidence-scroll" onKeyDown={onKey}>
      {groups.length === 0 ? <p className="evidence-empty">Kein Nachweis passt zur Auswahl.</p> : groups.map(([group, items]) => <section key={group} className="evidence-group" aria-label={group}>
        <h3>{group}<span>{items.length}</span></h3>
        <ul className="evidence-list">
          {items.map((ref) => {
            const active = ref.evidence_id === activeEvidenceId;
            const level = PRECISION[precisionOf(ref)];
            const place = where(ref);
            const confidence = confidenceText(ref.confidence);
            const state = reviewStateOf(ref, factByEvidence.get(ref.evidence_id));
            return <li key={ref.evidence_id}>
              <button type="button" className={`evidence-item${active ? " active" : ""}`} aria-pressed={active} onClick={() => onNavigate(ref)}>
                <span className="evidence-head">
                  <span className="evidence-number" aria-label={`Nachweis ${numbers.get(ref.evidence_id)}`}>{numbers.get(ref.evidence_id)}</span>
                  <span className="evidence-field">{titleOf(ref, factByEvidence)}</span>
                  <Signal tone={level.tone} size="sm" title={level.hint}>{level.label}</Signal>
                </span>
                {/* Erklärung der Lage auch für Screenreader (der Tooltip allein reicht nicht). */}
                <span className="visually-hidden">{level.hint}</span>
                {ref.snippet ? <span className="evidence-snippet">„{ref.snippet}“</span> : null}
                <span className="evidence-meta">
                  <span>{evidenceGroupLabel(ref.field_ref?.split(".")[0] ?? null)}</span>
                  {place && ref.page == null ? <span>{place}</span> : null}
                  {!place ? <span>Keine Seitenangabe</span> : null}
                  {showFile && ref.original_filename ? <span className="evidence-file">{ref.original_filename}</span> : null}
                  {confidence ? <span title="Wie sicher die KI beim Auslesen war – kein Prüfergebnis (das steht unter „Prüfung“).">{confidence}</span> : null}
                  {state === "open" ? <Signal tone="ai" size="sm">Zu prüfen</Signal> : state === "done" ? <Signal tone="done" size="sm">Geprüft</Signal> : null}
                </span>
              </button>
            </li>;
          })}
        </ul>
      </section>)}
    </div>
  </div>;
}
