"use client";

import { useMemo, useState } from "react";
import Signal from "@/components/ui/Signal";
import type { EvidenceRef } from "@/lib/contract-detail-types";
import { STATUS_VIEW, matchKey, type EvidenceRow, type EvidenceStatus } from "@/lib/evidence";

const FILTERS: { value: "" | EvidenceStatus; label: string }[] = [
  { value: "", label: "Alle" },
  { value: "open", label: "Offen" },
  { value: "confirmed", label: "Bestätigt" },
  { value: "deviation", label: "Abweichend" },
  { value: "skipped", label: "Übersprungen" },
];

/**
 * Nachweise als kompakte Tabelle (# · Feld · [Abschnitt] · Seite · Status), ohne Zitate. Im Reiter Dokumente und
 * in „Alle Nachweise“ der Prüfung; ein Klick wählt den Nachweis.
 */
export default function EvidenceTable({ rows, currentId = null, onPick, withSection = false, filters = false, caption }: {
  rows: EvidenceRow[];
  currentId?: string | null;
  onPick: (ref: EvidenceRef) => void;
  withSection?: boolean;
  /** Prüfstand-Filter und Suche (in „Alle Nachweise“). */
  filters?: boolean;
  caption: string;
}) {
  const [status, setStatus] = useState<"" | EvidenceStatus>("");
  const [query, setQuery] = useState("");
  const counts = useMemo(() => {
    const out: Record<string, number> = { "": rows.length };
    for (const row of rows) out[row.status] = (out[row.status] ?? 0) + 1;
    return out;
  }, [rows]);
  const needle = matchKey(query);
  const visible = rows.filter((row) => (!status || row.status === status)
    && (!needle || matchKey(`${row.title} ${row.section.label} ${row.ref.snippet ?? ""}`).includes(needle)));

  return <div className="evt">
    {filters ? <div className="evt-tools">
      <div className="evt-filter" role="group" aria-label="Nach Prüfstand filtern">
        {FILTERS.map((option) => <button key={option.value || "all"} type="button" aria-pressed={status === option.value} onClick={() => setStatus(option.value)}>
          {option.label}<span className="evt-count" aria-hidden="true">{counts[option.value] ?? 0}</span>
        </button>)}
      </div>
      <input type="search" className="evt-search" aria-label="Nachweise durchsuchen" placeholder="Feld oder Wortlaut suchen" value={query} onChange={(event) => setQuery(event.target.value)} />
    </div> : null}
    <table className="evt-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead><tr>
        <th scope="col" className="evt-num">#</th>
        <th scope="col">Feld</th>
        {withSection ? <th scope="col">Abschnitt</th> : null}
        <th scope="col">Seite</th>
        <th scope="col">Status</th>
      </tr></thead>
      <tbody>{visible.map((row) => {
        const view = STATUS_VIEW[row.status];
        const current = row.ref.evidence_id === currentId;
        return <tr key={row.ref.evidence_id} className={current ? "is-current" : undefined} aria-current={current ? "true" : undefined}>
          <td className="evt-num">{row.number}</td>
          <td><button type="button" className="evt-link" onClick={() => onPick(row.ref)}>{row.title}</button></td>
          {withSection ? <td className="evt-muted">{row.section.label}</td> : null}
          <td className="evt-muted">{row.ref.page ?? "–"}</td>
          <td><Signal tone={view.tone} size="sm">{view.label}</Signal></td>
        </tr>;
      })}</tbody>
    </table>
    {visible.length === 0 ? <p className="evt-empty">Keine Nachweise für diese Auswahl.</p> : null}
  </div>;
}
