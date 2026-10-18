"use client";

import { useMemo, useState, type ReactNode } from "react";
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
        <span className="evf-select">
          <select value={filter.section} onChange={(event) => onFilter({ ...filter, section: event.target.value })} aria-label="Nach Abschnitt filtern">
            <option value="">Alle Abschnitte</option>
            {sections.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          {CHEVRON}
        </span>
      </label>
      <input type="search" className="evt-search" aria-label="Nachweise durchsuchen" placeholder="Feld oder Wortlaut suchen" value={filter.query} onChange={(event) => onFilter({ ...filter, query: event.target.value })} />
    </div>
  </div>;
}

const ico = (body: ReactNode, className: string) => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const STATUS_ICON: Record<"" | EvidenceStatus, ReactNode> = {
  "": null,
  open: ico(<circle cx="12" cy="12" r="6" />, "evf-icon evf-icon--open"),
  confirmed: ico(<><circle cx="12" cy="12" r="10" /><path d="m7.5 12.5 3 3 6-7" /></>, "evf-icon evf-icon--confirmed"),
  deviation: ico(<><path d="M12 2.5 22.5 21h-21z" /><path d="M12 9.5v5M12 17.5v.5" /></>, "evf-icon evf-icon--deviation"),
  skipped: ico(<path d="M3 5.5 11 12l-8 6.5zM12 5.5l8 6.5-8 6.5z" />, "evf-icon evf-icon--skipped"),
};
const FILTER_ICON = ico(<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M16 4v4M10 10v4M18 16v4" />, "evf-title-icon");
// Pfeil im Auswahlfeld: zeigt, dass sich hier eine Liste öffnet.
const CHEVRON = ico(<path d="m6 9 6 6 6-6" />, "evf-chevron");
const SEARCH_ICON = ico(<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>, "evf-search-icon");

/**
 * Aufklapper „Nachweise filtern“ (Entwurf 18.10.2026): Prüfstand als Karten mit Zählern, Abschnitt, Suche;
 * die Auswahl gilt erst mit „Filter anwenden“. Treffer und Zusammenfassung zeigen den Entwurf.
 */
export function EvidenceFilterPanel({ rows, filter, onApply }: { rows: EvidenceRow[]; filter: EvidenceFilter; onApply: (filter: EvidenceFilter) => void }) {
  const [draft, setDraft] = useState<EvidenceFilter>(filter);
  const counts = useMemo(() => {
    const scoped = rows.filter((row) => matchesFilter(row, { ...draft, status: "" }));
    const out: Record<string, number> = { "": scoped.length };
    for (const row of scoped) out[row.status] = (out[row.status] ?? 0) + 1;
    return out;
  }, [rows, draft]);
  const sections = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of rows) if (!seen.has(row.section.key)) seen.set(row.section.key, row.section.label);
    const rank = (key: string) => EVIDENCE_SECTIONS.findIndex((section) => section.key === key);
    return [...seen.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));
  }, [rows]);
  const hits = rows.filter((row) => matchesFilter(row, draft)).length;
  const label = filterLabel(draft, rows);
  return <form className="evf" onSubmit={(event) => { event.preventDefault(); onApply(draft); }}>
    <div className="evf-head">
      {FILTER_ICON}
      <p className="evf-title">Nachweise filtern</p>
      <span className="evf-hits" aria-live="polite">{hits} Treffer</span>
    </div>
    <div className="evf-status" role="group" aria-label="Nach Prüfstand filtern">
      {FILTERS.map((option) => <button key={option.value || "all"} type="button" className={`evf-card evf-card--${option.value || "all"}`} aria-pressed={draft.status === option.value} onClick={() => setDraft({ ...draft, status: option.value })}>
        {STATUS_ICON[option.value]}<span className="evf-card-label">{option.label}</span><span className="evf-card-count" aria-hidden="true">{counts[option.value] ?? 0}</span>
      </button>)}
    </div>
    <div className="evf-fields">
      <label className="evf-field">
        <span className="evf-label">Abschnitt</span>
        <span className="evf-select">
          <select value={draft.section} onChange={(event) => setDraft({ ...draft, section: event.target.value })} aria-label="Nach Abschnitt filtern">
            <option value="">Alle Abschnitte</option>
            {sections.map(([key, name]) => <option key={key} value={key}>{name}</option>)}
          </select>
          {CHEVRON}
        </span>
      </label>
      <label className="evf-field evf-field--search">
        <span className="evf-label">Suche</span>
        <span className="evf-search">{SEARCH_ICON}<input type="search" aria-label="Nachweise durchsuchen" placeholder="Feld oder Wortlaut suchen" value={draft.query} onChange={(event) => setDraft({ ...draft, query: event.target.value })} /></span>
      </label>
    </div>
    <div className="evf-foot">
      <p className="evf-summary">{isFiltered(draft) ? `Zeigt ${hits} von ${rows.length} Nachweisen · ${label}.` : `Zeigt alle ${rows.length} Nachweise.`}</p>
      <button type="button" className="btn btn-ghost" disabled={!isFiltered(draft)} onClick={() => setDraft(NO_FILTER)}>Zurücksetzen</button>
      <button type="submit" className="btn btn-primary">Filter anwenden</button>
    </div>
  </form>;
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
    {/* Gleicher Filter wie im Aufklapper „Nachweise“; key setzt den Entwurf zurück, wenn die Auswahl von außen wechselt. */}
    {filters ? <div className="evt-panel"><EvidenceFilterPanel key={`${filter.status}|${filter.section}|${filter.query}`} rows={rows} filter={filter} onApply={setFilter} /></div> : null}
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
