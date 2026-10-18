"use client";

import Link from "next/link";
import { Fragment } from "react";
import StatusBadge from "@/components/ui/StatusBadge";
import { BUSINESS_STATUS_TONE, type BusinessStatus } from "@/lib/domain-api/register";
import type { GridColumn, GridResponse, GridSpec, MoneyTotals } from "@/lib/domain-api/registerGrid";
import { coverageNote, formatCurrency } from "@/lib/format";
import { rememberReviewQueue } from "@/lib/review-queue";
import { contractHref } from "@/lib/fix-targets";
import { formatCell } from "./register-state";

type Props = {
  data: GridResponse;
  spec: GridSpec;
  shown: GridColumn[];
  columnByKey: Map<string, GridColumn>;
  archiveMode: boolean;
  reviewMode: boolean;
  canRestore: boolean;
  busyRow: string | null;
  onSort: (key: string) => void;
  onRestore: (contractId: string) => void;
  onPreview: (contractId: string) => void;
};

// Gruppensumme mit Abdeckung: unbekannt bleibt „—“, Teilsummen sind gekennzeichnet.
function sumText(totals: MoneyTotals | undefined, key: string): string {
  if (!totals) return "—";
  const value = totals.sums[key];
  const coverage = totals.coverage?.[key];
  const others = Object.entries(totals.other_currencies?.[key] ?? {}).map(([code, amount]) => ` + ${formatCurrency(amount, code)}`).join("");
  if (value === null || value === undefined) return others ? others.slice(3) : "— (keine gepflegten Kosten)";
  const note = coverageNote(coverage?.known, coverage?.missing);
  return `${formatCurrency(value, totals.currency ?? "EUR")}${others}${note ? ` (${note})` : ""}`;
}

type Cell = { kind: "contract" } | { kind: "column"; column: GridColumn };

// Nr. und Kurzbeschreibung sind getrennte Felder (Suche, Sortierung, Export);
// sind beide sichtbar, zeigt die Liste sie als eine Spalte „Vertrag“.
function layout(shown: GridColumn[]): Cell[] {
  const combine = shown.some((item) => item.key === "register_number") && shown.some((item) => item.key === "short_description");
  const cells: Cell[] = [];
  for (const column of shown) {
    if (combine && (column.key === "register_number" || column.key === "short_description")) {
      if (!cells.some((cell) => cell.kind === "contract")) cells.push({ kind: "contract" });
      continue;
    }
    cells.push({ kind: "column", column });
  }
  return cells;
}

export default function RegisterTable({ data, spec, shown, columnByKey, archiveMode, reviewMode, canRestore, busyRow, onSort, onRestore, onPreview }: Props) {
  const cells = layout(shown);
  const hasContractCell = cells.some((cell) => cell.kind === "contract");
  // Nach einer Lücke gefiltert („ohne Kosten“ …): der Vertrag öffnet dort, wo sie behoben wird.
  const actionColumn = (archiveMode && canRestore) || reviewMode;
  const groupIndex = new Map((data.groups ?? []).map((item) => [JSON.stringify(item.path), item]));
  const width = cells.length + (actionColumn ? 1 : 0);
  const ariaSort = (keys: string[]) => {
    if (!spec.sort || !keys.includes(spec.sort.column)) return "none" as const;
    return spec.sort.dir === "asc" ? "ascending" as const : "descending" as const;
  };
  const arrow = (key: string) => (spec.sort?.column === key ? (spec.sort.dir === "asc" ? " ▲" : " ▼") : "");
  let previous: (string | number | boolean | null)[] | null = null;

  return <div className="reg-scroll"><table className="rg-table reg-table">
    <thead><tr>
      {cells.map((cell) => cell.kind === "contract"
        ? <th key="contract" scope="col" className="reg-contract" aria-sort={ariaSort(["display_title", "short_description", "register_number"])}>
          <button type="button" className="reg-sort" onClick={() => onSort("display_title")}>Vertrag{arrow("display_title")}</button>
          <span className="reg-sort-divider" aria-hidden="true">/</span>
          <button type="button" className="reg-sort reg-sort-sub" onClick={() => onSort("register_number")} aria-label="Nach Nr. sortieren">Nr.{arrow("register_number")}</button>
        </th>
        : <th key={cell.column.key} scope="col" aria-sort={ariaSort([cell.column.key])} className={cell.column.type === "money" || cell.column.type === "number" ? "num" : undefined}>
          <button type="button" className="reg-sort" onClick={() => onSort(cell.column.key)}>{cell.column.label}{arrow(cell.column.key)}</button>
        </th>)}
      {actionColumn ? <th scope="col">Aktion</th> : null}
    </tr></thead>
    <tbody>{data.items.map((row) => {
      const headers = spec.group_by.map((_, depth) => {
        const path = row.group.slice(0, depth + 1);
        const changed = !previous || JSON.stringify(previous.slice(0, depth + 1)) !== JSON.stringify(path);
        if (!changed) return null;
        const group = groupIndex.get(JSON.stringify(path));
        return <tr key={`g-${depth}-${JSON.stringify(path)}`} className={`reg-group reg-group-${depth}`}>
          <th scope="colgroup" colSpan={width}>
            {columnByKey.get(spec.group_by[depth])?.label}: {group?.labels[depth] ?? "(ohne)"} <span className="cw-muted">· {group?.count ?? 0} Verträge · {sumText(group, "annual_cost")} jährlich</span>
          </th>
        </tr>;
      });
      previous = row.group;
      const number = row.values.register_number == null ? "" : String(row.values.register_number);
      const shownTitle = row.values.display_title ?? row.values.contract_title ?? row.values.short_description;
      const description = shownTitle == null ? "" : String(shownTitle).trim();
      // Der Vertrag öffnet immer in der Übersicht; Offene Punkte führen von dort zur Stelle.
      const href = contractHref(row.contract_id);
      return <Fragment key={row.contract_id}>
        {headers}
        <tr>
          {cells.map((cell, index) => {
            if (cell.kind === "contract") {
              // Ohne Beschreibung eine neutrale Bezeichnung aus der echten Nummer – kein erfundener Inhalt.
              const title = description || `Vertrag ${number}`;
              return <td key="contract" className="reg-contract">
                <Link href={href}>{title}</Link>
                <span className="reg-sub">
                  {description ? <span>{number}</span> : null}
                  <button type="button" className="btn-link reg-preview" onClick={() => onPreview(row.contract_id)} aria-label={`${title} in der Schnellansicht öffnen`}>Vorschau</button>
                </span>
              </td>;
            }
            const { column } = cell;
            const text = formatCell(column, row.values[column.key]);
            if (column.type === "status") {
              // Die Liste liefert die Beschriftung; der Code kommt aus den Optionen der Spalte.
              const code = column.options?.find((option) => option.label === text || option.value === text)?.value as BusinessStatus | undefined;
              return <td key={column.key}>{text === "–" ? text : <StatusBadge label={text} tone={code ? BUSINESS_STATUS_TONE[code] ?? "neutral" : "neutral"} />}</td>;
            }
            if ((index === 0 && !hasContractCell) || column.key === "register_number") {
              return <td key={column.key}><Link href={href}>{text}</Link></td>;
            }
            if (column.key === "short_description") {
              return <td key={column.key} className="reg-wrap"><button type="button" className="btn-link reg-preview" onClick={() => onPreview(row.contract_id)} aria-label={`${text} in der Schnellansicht öffnen`}>{text}</button></td>;
            }
            // „Unvollständig“ / „Verstoß“ führen zur Stelle, an der es behoben wird.
            if (column.key === "term_status" && text === "Unvollständig") {
              return <td key={column.key}><Link href={contractHref(row.contract_id, { tab: "register", section: "term" })} aria-label={`Laufzeitangaben von ${description || number} ergänzen`}>{text}</Link></td>;
            }
            if (column.key === "rules_status" && (text === "Unvollständig" || text === "Verstoß")) {
              return <td key={column.key}><Link href={contractHref(row.contract_id, { tab: "register", section: "rules" })} aria-label={`Vertragsregeln von ${description || number} ansehen`}>{text}</Link></td>;
            }
            const numeric = column.type === "money" || column.type === "number";
            return <td key={column.key} className={numeric ? "num" : column.type === "text" || column.type === "enum" ? "reg-wrap" : undefined}>{text}</td>;
          })}
          {archiveMode && canRestore
            ? <td><button type="button" className="btn btn-sm" disabled={busyRow === row.contract_id} onClick={() => onRestore(row.contract_id)} aria-label={`Vertrag ${number} wiederherstellen`}>Wiederherstellen</button></td>
            : reviewMode ? <td><Link className="btn btn-sm btn-primary" href={`/contracts/${row.contract_id}?tab=documents&subtab=review`} onClick={() => rememberReviewQueue(data.items.map((item) => item.contract_id))} aria-label={`Vertrag ${number} prüfen`}>Prüfen</Link></td> : null}
        </tr>
      </Fragment>;
    })}</tbody>
  </table></div>;
}
