"use client";

import { useMemo, useState } from "react";
import Signal from "@/components/ui/Signal";
import type { EvidenceRef } from "@/lib/contract-detail-types";
import { EVIDENCE_SECTIONS, STATUS_VIEW, matchKey, type EvidenceRow, type EvidenceStatus } from "@/lib/evidence";

const FILTERS: { value: "" | EvidenceStatus; label: string }[] = [
  { value: "", label: "Alle" },
  { value: "open", label: "Offen" },
  { value: "confirmed", label: "Bestätigt" },
  { value: "deviation", label: "Abweichend" },
  { value: "skipped", label: "Übersprungen" },
];

/** Auswahl in „Alle Nachweise“: Prüfstand, Abschnitt und Suchtext (leer = alle). */
export interface EvidenceFilter {
  status: "" | EvidenceStatus;
  section: string;
  query: string;
}

export const NO_FILTER: EvidenceFilter = { status: "", section: "", query: "" };

export function isFiltered(filter: EvidenceFilter): boolean {
  return Boolean(filter.status || filter.section || filter.query.trim());
}

export function matchesFilter(row: EvidenceRow, filter: EvidenceFilter): boolean {
  const needle = matchKey(filter.query);
  return (!filter.status || row.status === filter.status)
    && (!filter.section || row.section.key === filter.section)
    && (!needle || matchKey(`${row.title} ${row.section.label} ${row.ref.snippet ?? ""}`).includes(needle));
}

/** Kurzbeschreibung einer Auswahl, z. B. „Offen · Kosten · „Preis““. */
export function filterLabel(filter: EvidenceFilter, rows: EvidenceRow[]): string {
  const status = FILTERS.find((option) => option.value === filter.status && option.value)?.label;
  const section = filter.section ? rows.find((row) => row.section.key === filter.section)?.section.label : null;
  const query = filter.query.trim() ? `„${filter.query.trim()}“` : null;
  return [status, section, query].filter(Boolean).join(" · ");
}

/** Filter-Bedienung (Prüfstand mit Zählern, Abschnitt, Suche): in „Alle Nachweise“ und im Aufklapper „Nachweise“. */
export function EvidenceFilterBar({ rows, filter, onFilter }: { rows: EvidenceRow[]; filter: EvidenceFilter; onFilter: (filter: EvidenceFilter) => void }) {
  const counts = useMemo(() => {
    const scoped = rows.filter((row) => matchesFilter(row, { ...filter, status: "" }));
    const out: Record<string, number> = { "": scoped.length };
    for (const row of scoped) out[row.status] = (out[row.status] ?? 0) + 1;
    return out;
  }, [rows, filter]);
  const sections = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of rows) if (!seen.has(row.section.key)) seen.set(row.section.key, row.section.label);
    // Reihenfolge wie die Reiter der Vertragsakte, nicht wie die Nachweise zufällig vorkommen.
    const rank = (key: string) => EVIDENCE_SECTIONS.findIndex((section) => section.key === key);
    return [...seen.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));
  }, [rows]);
  return <div className="evt-tools">
    <div className="evt-filter" role="group" aria-label="Nach Prüfstand filtern">
      {FILTERS.map((option) => <button key={option.value || "all"} type="button" aria-pressed={filter.status === option.value} onClick={() => onFilter({ ...filter, status: option.value })}>
        {option.label}<span className="evt-count" aria-hidden="true">{counts[option.value] ?? 0}</span>
      </button>)}
    </div>
    <div className="evt-row">
      <label className="evt-section">
        <span className="visually-hidden">Abschnitt</span>
        <select value={filter.section} onChange={(event) => onFilter({ ...filter, section: event.target.value })} aria-label="Nach Abschnitt filtern">
          <option value="">Alle Abschnitte</option>
          {sections.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <input type="search" className="evt-search" aria-label="Nachweise durchsuchen" placeholder="Feld oder Wortlaut suchen" value={filter.query} onChange={(event) => onFilter({ ...filter, query: event.target.value })} />
    </div>
  </div>;
}

/**
 * Nachweise als kompakte Tabelle (# · Feld [mit Abschnitt darunter] · Seite · Status), ohne Zitate. Im Reiter Dokumente
 * und in „Alle Nachweise“ der Prüfung; ein Klick wählt den Nachweis. Mit `filter`/`onFilter` steuert die Auswahl
 * von außen (die geführte Prüfung geht dann nur diese Nachweise durch); `filters` zeigt die Bedienung über der Tabelle.
 */
export default function EvidenceTable({ rows, currentId = null, onPick, withSection = false, filters = false, caption, filter: given, onFilter }: {
  rows: EvidenceRow[];
  currentId?: string | null;
  onPick: (ref: EvidenceRef) => void;
  withSection?: boolean;
  /** Prüfstand-, Abschnitt-Filter und Suche über der Tabelle (in „Alle Nachweise“). */
  filters?: boolean;
  caption: string;
  filter?: EvidenceFilter;
  onFilter?: (filter: EvidenceFilter) => void;
}) {
  const [own, setOwn] = useState<EvidenceFilter>(NO_FILTER);
  const filter = given ?? own;
  const setFilter = (next: EvidenceFilter) => (onFilter ? onFilter(next) : setOwn(next));
  const visible = rows.filter((row) => matchesFilter(row, filter));

  return <div className="evt">
    {filters ? <EvidenceFilterBar rows={rows} filter={filter} onFilter={setFilter} /> : null}
    <table className="evt-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead><tr>
        <th scope="col" className="evt-num">#</th>
        <th scope="col">{withSection ? "Feld · Abschnitt" : "Feld"}</th>
        <th scope="col">Seite</th>
        <th scope="col">Status</th>
      </tr></thead>
      <tbody>{visible.map((row) => {
        const view = STATUS_VIEW[row.status];
        const current = row.ref.evidence_id === currentId;
        return <tr key={row.ref.evidence_id} className={current ? "is-current" : undefined} aria-current={current ? "true" : undefined}>
          <td className="evt-num">{row.number}</td>
          <td><button type="button" className="evt-link" onClick={() => onPick(row.ref)}>{row.title}</button>
            {/* Abschnitt als zweite Zeile statt eigener Spalte: im schmalen Seitenfenster bleibt der Name lesbar. */}
            {withSection ? <span className="evt-sub">{row.section.label}</span> : null}</td>
          <td className="evt-muted">{row.ref.page ?? "–"}</td>
          <td><Signal tone={view.tone} size="sm">{view.label}</Signal></td>
        </tr>;
      })}</tbody>
    </table>
    {visible.length === 0 ? <p className="evt-empty">Keine Nachweise für diese Auswahl.</p> : null}
  </div>;
}
