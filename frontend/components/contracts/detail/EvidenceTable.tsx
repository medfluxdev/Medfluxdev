"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { EvidenceRef } from "@/lib/contract-detail-types";
import { LEVEL_NAME, type ReviewLevel } from "@/lib/field-review";
import FilterSelect from "./FilterSelect";
import { EVIDENCE_SECTIONS, STATUS_VIEW, matchKey, type EvidenceRow, type EvidenceStatus } from "@/lib/evidence";

const FILTERS: { value: "" | EvidenceStatus; label: string }[] = [
  { value: "", label: "Alle" },
  { value: "open", label: "Offen" },
  { value: "confirmed", label: "Entschieden" },
  { value: "deviation", label: "Widerspruch" },
  { value: "skipped", label: "Zurückgestellt" },
  { value: "excluded", label: "Ausgeschlossen" },
  { value: "extra", label: "Weitere Info" },
];

/** Auswahl in „Alle Nachweise“: Prüfstand, Abschnitt und Suchtext (leer = alle). */
export interface EvidenceFilter {
  /** Prüfstufe: Pflicht oder Optional (leer = beide). */
  level?: "" | ReviewLevel;
  status: "" | EvidenceStatus;
  section: string;
  query: string;
}

export const NO_FILTER: EvidenceFilter = { level: "", status: "", section: "", query: "" };

export function isFiltered(filter: EvidenceFilter): boolean {
  return Boolean(filter.level || filter.status || filter.section || filter.query.trim());
}

export function matchesFilter(row: EvidenceRow, filter: EvidenceFilter): boolean {
  const needle = matchKey(filter.query);
  return (!filter.level || row.level === filter.level)
    && (!filter.status || row.status === filter.status)
    && (!filter.section || row.section.key === filter.section)
    && (!needle || matchKey(`${row.title} ${row.section.label} ${row.ref.snippet ?? ""}`).includes(needle));
}

/** Kurzbeschreibung einer Auswahl, z. B. „Offen · Kosten · „Preis““. */
export function filterLabel(filter: EvidenceFilter, rows: EvidenceRow[]): string {
  const status = FILTERS.find((option) => option.value === filter.status && option.value)?.label;
  const section = filter.section ? rows.find((row) => row.section.key === filter.section)?.section.label : null;
  const query = filter.query.trim() ? `„${filter.query.trim()}“` : null;
  const level = filter.level ? LEVEL_NAME[filter.level] : null;
  return [level, status, section, query].filter(Boolean).join(" · ");
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
  excluded: ico(<><circle cx="12" cy="12" r="9" /><path d="m6 6 12 12" /></>, "evf-icon evf-icon--skipped"),
  extra: ico(<><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.5" /></>, "evf-icon evf-icon--skipped"),
};
/** Treffer der Suche im Feldnamen hervorheben (nur wenn der Text unverändert vorkommt). */
function highlight(text: string, query: string): ReactNode {
  const needle = query.trim();
  const at = needle ? text.toLowerCase().indexOf(needle.toLowerCase()) : -1;
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark className="evi-mark">{text.slice(at, at + needle.length)}</mark>{text.slice(at + needle.length)}</>;
}
const DOT_CHECK = <svg viewBox="0 0 24 24" focusable="false"><path d="m7 12.5 3.2 3.2L17 8.5" /></svg>;
const DOT_CHEVRON = <svg viewBox="0 0 24 24" focusable="false"><path d="m9 6 6 6-6 6" /></svg>;
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
 * Filter für die Nachweise-Liste in der Seitenleiste (wirkt sofort, kein „Anwenden“). Passend zur Prüfung mit zwei Stufen:
 * Suche · Stand als Schalter „Offen“ / „Entschieden“ (nochmals klicken hebt auf). Zähler beachten die jeweils anderen Einschränkungen – so führt kein Knopf zu einer leeren Liste.
 */
export function EvidenceFilterInline({ rows, filter, onFilter, onNextOpen, searchOpen, onSearchOpen }: {
  rows: EvidenceRow[]; filter: EvidenceFilter; onFilter: (filter: EvidenceFilter) => void; onNextOpen?: () => void;
  /** Suchfeld sichtbar (geöffnet über die Lupe im Reiterkopf) und Schließen. */
  searchOpen: boolean; onSearchOpen: (open: boolean) => void;
}) {
  const statusCounts = useMemo(() => {
    const scoped = rows.filter((row) => matchesFilter(row, { ...filter, status: "" }));
    const out: Record<string, number> = {};
    for (const row of scoped) out[row.status] = (out[row.status] ?? 0) + 1;
    return out;
  }, [rows, filter]);
  // Kategorie = Karte der Vertragsakte (Vertragsdaten, Finanzen …) mit Zähler; Zähler beachten die übrigen Einschränkungen.
  const sections = useMemo(() => {
    const scoped = rows.filter((row) => matchesFilter(row, { ...filter, section: "" }));
    const seen = new Map<string, { label: string; count: number }>();
    for (const row of scoped) seen.set(row.section.key, { label: row.section.label, count: (seen.get(row.section.key)?.count ?? 0) + 1 });
    if (filter.section && !seen.has(filter.section)) seen.set(filter.section, { label: rows.find((row) => row.section.key === filter.section)?.section.label ?? filter.section, count: 0 });
    const rank = (key: string) => EVIDENCE_SECTIONS.findIndex((section) => section.key === key);
    return [...seen.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));
  }, [rows, filter]);
  const hits = rows.filter((row) => matchesFilter(row, filter)).length;
  const active = isFiltered(filter);
  return <div className="evi" role="search" aria-label="Nachweise filtern">
    {searchOpen || filter.query ? <span className="evi-search">{SEARCH_ICON}
      <input type="search" autoFocus aria-label="Nachweise durchsuchen" placeholder="Feld oder Wortlaut suchen" value={filter.query} onChange={(event) => onFilter({ ...filter, query: event.target.value })}
        onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); if (filter.query) onFilter({ ...filter, query: "" }); else onSearchOpen(false); } }} />
      <button type="button" className="evi-clear" aria-label="Suche schließen" onClick={() => { onFilter({ ...filter, query: "" }); onSearchOpen(false); }}>×</button>
    </span> : null}
    <div className="evi-picks">
      <FilterSelect label="Status" value={filter.status} onChange={(value) => onFilter({ ...filter, status: value as "" | EvidenceStatus })}
        options={[{ value: "", label: "Alle" }, ...FILTERS.filter((option) => option.value && option.value !== "skipped" && option.value !== "extra"
          && (["open", "confirmed"].includes(option.value) || (statusCounts[option.value] ?? 0) > 0 || filter.status === option.value))
          .map((option) => ({ value: option.value, label: option.value === "confirmed" ? "Erledigt" : option.label, count: statusCounts[option.value] ?? 0,
            lead: <span className={`evl-dot evl-dot--${option.value} evi-dot`}>{option.value === "confirmed" ? DOT_CHECK : null}</span> }))]} />
      <FilterSelect label="Kategorie" value={filter.section} align="end" onChange={(value) => onFilter({ ...filter, section: value })}
        options={[{ value: "", label: "Alle" }, ...sections.map(([key, info]) => ({ value: key, label: info.label, count: info.count }))]} />
    </div>
    <div className="evi-foot">
      <span className="evi-hits" role="status">{active ? `${hits} von ${rows.length}` : `${rows.length} Nachweise`}</span>
      {active ? <button type="button" className="evi-reset" onClick={() => onFilter(NO_FILTER)}>Zurücksetzen</button> : null}
      {onNextOpen && (statusCounts.open ?? 0) > 0 ? <button type="button" className="evi-next" onClick={onNextOpen}>Nächster offener<span aria-hidden="true"> ↓</span></button> : null}
    </div>
  </div>;
}

/**
 * Nachweise als kompakte Liste (Statuspunkt · Feld mit Nr., Seite und Stand darunter · Pfeil), ohne Zitate. Im Reiter Dokumente
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
  // Bei jeder Änderung des Filters beginnt die Liste wieder oben (sonst steht man mitten in einer anderen Auswahl).
  const scroller = useRef<HTMLDivElement | null>(null);
  const filterKey = `${filter.level ?? ""}|${filter.status}|${filter.section}|${filter.query}`;
  useEffect(() => { scroller.current?.scrollTo?.({ top: 0 }); }, [filterKey]);
  // Gruppen nach Stufe (Pflicht, dann Optional), darin nach Abschnitt; einklappbar; Optional ist zu Beginn eingeklappt (bei Suche/Filter und für den gewählten Nachweis offen).
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(["optional"]));
  const searching = isFiltered(filter);
  const groups = useMemo(() => {
    const rank = (key: string) => EVIDENCE_SECTIONS.findIndex((section) => section.key === key);
    return (["pflicht", "optional"] as ReviewLevel[])
      .map((key) => ({
        key, label: LEVEL_NAME[key],
        rows: visible.filter((row) => row.level === key).sort((a, b) => rank(a.section.key) - rank(b.section.key) || a.number - b.number),
      }))
      .filter((group) => group.rows.length > 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, filter]);

  return <div className="evt" ref={scroller}>
    {/* Gleicher Filter wie im Aufklapper „Nachweise“; key setzt den Entwurf zurück, wenn die Auswahl von außen wechselt. */}
    {filters ? <div className="evt-panel"><EvidenceFilterPanel key={`${filter.status}|${filter.section}|${filter.query}`} rows={rows} filter={filter} onApply={setFilter} /></div> : null}
    <div className="evl" role="group" aria-label={caption}>{groups.map((group) => {
      const closed = !searching && collapsed.has(group.key) && !group.rows.some((row) => row.ref.evidence_id === currentId);
      return <section key={group.key} className="evl-group">
        <h2 className="evl-head"><button type="button" aria-expanded={!closed} onClick={() => setCollapsed((before) => { const next = new Set(before); if (next.has(group.key)) next.delete(group.key); else next.add(group.key); return next; })}>
          <span className="evl-caret" aria-hidden="true">{DOT_CHEVRON}</span>{group.label}<span className="evl-head-count">{group.rows.length}</span>
        </button></h2>
        {closed ? null : <ul className="evl-list">{group.rows.map((row) => {
          const view = STATUS_VIEW[row.status];
          const current = row.ref.evidence_id === currentId;
          return <li key={row.ref.evidence_id} className={current ? "evl-item is-current" : "evl-item"}>
            <button type="button" className="evl-btn" aria-current={current ? "true" : undefined} onClick={() => onPick(row.ref)}>
              <span className={`evl-dot evl-dot--${row.status}`} aria-hidden="true">{row.status === "confirmed" ? DOT_CHECK : null}</span>
              <span className="evl-text">
                <span className="evl-title">{highlight(row.title, filter.query)}</span>
                {/* Nr. entspricht der Nummer des Rahmens im Original. */}
                <span className="evl-sub">{row.section.label} · Nr. {row.number} · Seite {row.ref.page ?? "–"} · {view.label}{current ? " · Aktuell ausgewählt" : ""}</span>
              </span>
              <span className="evl-chevron" aria-hidden="true">{DOT_CHEVRON}</span>
            </button>
          </li>;
        })}</ul>}
      </section>;
    })}</div>
    {visible.length === 0 ? <p className="evt-empty">Keine Nachweise für diese Auswahl. <button type="button" className="evi-reset" onClick={() => setFilter(NO_FILTER)}>Filter zurücksetzen</button></p> : null}
  </div>;
}
