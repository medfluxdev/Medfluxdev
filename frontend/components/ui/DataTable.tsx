"use client";

import { useMemo, useState, type ReactNode } from "react";

export interface Column<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number | null;
  numeric?: boolean;
  rowHeader?: boolean;
}

interface Props<T> {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: ReactNode;
  initialSort?: { key: string; dir: "asc" | "desc" };
}

// Tabelle mit sortierbaren Spalten (aria-sort), fixierter Kopfzeile und
// Tabellenziffern. Fuer serverseitig sortierte Listen den Sortierwert weglassen.
export default function DataTable<T>({ caption, columns, rows, rowKey, empty, initialSort }: Props<T>) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = useMemo(() => {
    const column = sort ? columns.find((item) => item.key === sort.key) : null;
    if (!column?.sortValue || !sort) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = column.sortValue!(a);
      const right = column.sortValue!(b);
      if (left == null) return 1;
      if (right == null) return -1;
      return (left < right ? -1 : left > right ? 1 : 0) * factor;
    });
  }, [columns, rows, sort]);

  if (rows.length === 0 && empty) return <>{empty}</>;

  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => {
              const state = sort?.key === column.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none";
              return (
                <th key={column.key} scope="col" className={column.numeric ? "num" : undefined} aria-sort={column.sortValue ? state : undefined}>
                  {column.sortValue ? (
                    <button type="button" className="btn-link" onClick={() => setSort({ key: column.key, dir: sort?.key === column.key && sort.dir === "asc" ? "desc" : "asc" })}>
                      {column.label}{state === "ascending" ? " ▲" : state === "descending" ? " ▼" : ""}
                    </button>
                  ) : column.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => column.rowHeader
                ? <th key={column.key} scope="row">{column.render(row)}</th>
                : <td key={column.key} className={column.numeric ? "num" : undefined}>{column.render(row)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
