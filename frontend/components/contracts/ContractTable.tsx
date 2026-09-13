"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type MouseEvent } from "react";
import type { ContractListItem } from "@/lib/contract-types";
import {
  RISK_LABEL,
  STATUS_LABEL,
  formatAnnualCost,
  formatDate,
} from "@/lib/format";

interface Props {
  items: ContractListItem[];
  extraHeader?: string;
  extra?: (item: ContractListItem) => React.ReactNode;
}

type ColumnKey = "number" | "title" | "supplier" | "status" | "risk" | "annualCost" | "endDate" | "cancellation" | "warning";
type Density = "comfortable" | "compact";

const COLUMN_OPTIONS: Array<{ key: ColumnKey; label: string }> = [
  { key: "number", label: "Nr." },
  { key: "title", label: "Vertrag" },
  { key: "supplier", label: "Lieferant" },
  { key: "status", label: "Status" },
  { key: "risk", label: "Risiko" },
  { key: "annualCost", label: "Jährl. Kosten" },
  { key: "endDate", label: "Vertragsende" },
  { key: "cancellation", label: "Künd. bis" },
  { key: "warning", label: "Warnung" },
];

const DEFAULT_COLUMNS: Record<ColumnKey, boolean> = {
  number: true,
  title: true,
  supplier: true,
  status: true,
  risk: true,
  annualCost: true,
  endDate: true,
  cancellation: true,
  warning: true,
};

const severityLabel: Record<string, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  info: "Info",
};

function EmptyRow({ colSpan }: { colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="contracts-empty">
        Keine Verträge gefunden. Passen Sie Ihre Suche oder Filter an.
      </td>
    </tr>
  );
}

export default function ContractTable({ items, extraHeader, extra }: Props) {
  const router = useRouter();
  const [density, setDensity] = useState<Density>("comfortable");
  const [visibleColumns, setVisibleColumns] = useState<Record<ColumnKey, boolean>>(DEFAULT_COLUMNS);
  const [preferencesOpen, setPreferencesOpen] = useState(false);

  useEffect(() => {
    try {
      const storedDensity = localStorage.getItem("medflux.contractTable.density");
      if (storedDensity === "compact" || storedDensity === "comfortable") setDensity(storedDensity);
      const storedColumns = localStorage.getItem("medflux.contractTable.columns");
      if (storedColumns) {
        const parsed = JSON.parse(storedColumns) as Partial<Record<ColumnKey, boolean>>;
        setVisibleColumns({ ...DEFAULT_COLUMNS, ...parsed });
      }
    } catch {
      // Ungültige lokale Präferenzen ignorieren und sichere Defaults verwenden.
    }
  }, []);

  function updateDensity(next: Density) {
    setDensity(next);
    localStorage.setItem("medflux.contractTable.density", next);
  }

  function toggleColumn(key: ColumnKey) {
    setVisibleColumns((current) => {
      const next = { ...current, [key]: !current[key] };
      if (!Object.values(next).some(Boolean)) return current;
      localStorage.setItem("medflux.contractTable.columns", JSON.stringify(next));
      return next;
    });
  }

  function resetColumns() {
    setVisibleColumns(DEFAULT_COLUMNS);
    localStorage.removeItem("medflux.contractTable.columns");
  }

  const visibleCount = useMemo(() => Object.values(visibleColumns).filter(Boolean).length, [visibleColumns]);
  const colSpan = visibleCount + (extra ? 1 : 0);

  return (
    <div className={`contract-table-shell density-${density}`}>
      <div className="contract-table-preferences" aria-label="Tabellendarstellung">
        <div className="contract-density" role="group" aria-label="Tabellendichte">
          <button type="button" className={density === "comfortable" ? "btn-ghost active" : "btn-ghost"} aria-pressed={density === "comfortable"} onClick={() => updateDensity("comfortable")}>Komfortabel</button>
          <button type="button" className={density === "compact" ? "btn-ghost active" : "btn-ghost"} aria-pressed={density === "compact"} onClick={() => updateDensity("compact")}>Kompakt</button>
        </div>
        <div className="contract-column-menu">
          <button type="button" className="btn-ghost" aria-expanded={preferencesOpen} onClick={() => setPreferencesOpen((value) => !value)}>Spalten</button>
          {preferencesOpen ? (
            <div className="contract-column-popover" role="group" aria-label="Sichtbare Spalten">
              {COLUMN_OPTIONS.map((column) => (
                <label key={column.key}>
                  <input type="checkbox" checked={visibleColumns[column.key]} onChange={() => toggleColumn(column.key)} />
                  <span>{column.label}</span>
                </label>
              ))}
              <button type="button" className="btn-ghost btn-sm" onClick={resetColumns}>Standard wiederherstellen</button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="contract-table-scroll" tabIndex={0} aria-label="Vertragstabelle horizontal scrollen">
        <table className="contract-table">
          <thead>
            <ContractHeaderRow visibleColumns={visibleColumns} extraHeader={extraHeader} />
          </thead>
          <tbody>
            {items.length === 0 ? <EmptyRow colSpan={colSpan} /> : items.map((c) => {
              const statusLabel = STATUS_LABEL[c.status ?? ""] ?? c.status;
              const riskLabel = RISK_LABEL[c.risk_level ?? ""] ?? c.risk_level;
              const w = c.primary_warning;

              function openContract360(e: MouseEvent<HTMLTableRowElement>) {
                const target = e.target as HTMLElement;
                if (target.closest("a, button, input, select, textarea, [role='button']")) return;
                router.push(`/contracts/${c.contract_id}`);
              }

              return (
                <tr key={c.contract_id} className="contract-row" onClick={openContract360}>
                  {visibleColumns.number ? (
                    <th scope="row" className="contract-number">
                      <Link href={`/contracts/${c.contract_id}`} className="contract-number-link" aria-label={`${c.contract_number ?? "Vertrag"} öffnen`}>
                        {c.contract_number ?? "–"}
                      </Link>
                    </th>
                  ) : null}
                  {visibleColumns.title ? (
                    <td className="contract-title">
                      <Link href={`/contracts/${c.contract_id}`} className="contract-title-link" aria-label={`${c.contract_title ?? "Vertrag"} öffnen`}>
                        {c.contract_title ?? "–"}
                      </Link>
                      {c.supplier && <span className="contract-supplier">{c.supplier}</span>}
                    </td>
                  ) : null}
                  {visibleColumns.supplier ? <td>{c.supplier ?? "–"}</td> : null}
                  {visibleColumns.status ? <td><span className={`badge badge-${c.status ?? "unknown"}`}>{statusLabel}</span></td> : null}
                  {visibleColumns.risk ? <td>{c.risk_level ? <span className={`risk-badge risk-${c.risk_level}`}>{riskLabel}</span> : "–"}</td> : null}
                  {visibleColumns.annualCost ? <td className={c.annual_cost?.unreliable ? "cost unreliable" : "cost"}>{formatAnnualCost(c.annual_cost)}</td> : null}
                  {visibleColumns.endDate ? <td>{formatDate(c.contract_end_date)}</td> : null}
                  {visibleColumns.cancellation ? <td>{formatDate(c.latest_cancellation_date)}</td> : null}
                  {visibleColumns.warning ? (
                    <td className="warning-cell">
                      {w?.title_de ? <><span className={`severity-tag severity-${w.severity}`}>{severityLabel[w.severity ?? ""] ?? w.severity}</span><span className="warning-title">{w.title_de}</span></> : "–"}
                    </td>
                  ) : null}
                  {extra ? <td className="row-actions">{extra(c)}</td> : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ContractHeaderRow({ visibleColumns, extraHeader }: { visibleColumns: Record<ColumnKey, boolean>; extraHeader?: string }) {
  return (
    <tr>
      {visibleColumns.number ? <th scope="col">Nr.</th> : null}
      {visibleColumns.title ? <th scope="col">Vertrag</th> : null}
      {visibleColumns.supplier ? <th scope="col">Lieferant</th> : null}
      {visibleColumns.status ? <th scope="col">Status</th> : null}
      {visibleColumns.risk ? <th scope="col">Risiko</th> : null}
      {visibleColumns.annualCost ? <th scope="col">Jährl. Kosten</th> : null}
      {visibleColumns.endDate ? <th scope="col">Vertragsende</th> : null}
      {visibleColumns.cancellation ? <th scope="col">Künd. bis</th> : null}
      {visibleColumns.warning ? <th scope="col">Warnung</th> : null}
      {extraHeader ? <th scope="col">{extraHeader}</th> : null}
    </tr>
  );
}