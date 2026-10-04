"use client";

import { useEffect, useState } from "react";
import { getGridValues, type FilterOp, type GridColumn, type GridFilter, type GridSpec } from "@/lib/domain-api/registerGrid";
import { OPS_BY_TYPE, OP_LABEL } from "./filters";

type Props = {
  organizationSlug: string;
  columns: GridColumn[];
  spec: Partial<GridSpec>;
  onApply: (filter: GridFilter) => void;
  onCancel: () => void;
};

export default function FilterEditor({ organizationSlug, columns, spec, onApply, onCancel }: Props) {
  const [columnKey, setColumnKey] = useState(columns[0]?.key ?? "");
  const column = columns.find((item) => item.key === columnKey);
  const ops = column ? OPS_BY_TYPE[column.type] : [];
  const [op, setOp] = useState<FilterOp>(ops[0] ?? "empty");
  const [text, setText] = useState("");
  const [days, setDays] = useState("90");
  const [range, setRange] = useState({ from: "", to: "" });
  const [selected, setSelected] = useState<string[]>([]);
  const [flag, setFlag] = useState(true);
  const [values, setValues] = useState<{ value: string; label: string; count: number }[] | null>(null);

  useEffect(() => {
    if (!column) return;
    setOp(OPS_BY_TYPE[column.type][0]);
    setSelected([]);
    setValues(null);
  }, [column]);

  useEffect(() => {
    if (!column || op !== "in") return;
    if (column.options) {
      setValues(column.options.map((item) => ({ ...item, count: 0 })));
      return;
    }
    let cancelled = false;
    getGridValues(organizationSlug, column.key, spec)
      .then((result) => { if (!cancelled) setValues(result.values); })
      .catch(() => { if (!cancelled) setValues([]); });
    return () => { cancelled = true; };
  }, [column, op, organizationSlug, spec]);

  function build(): GridFilter | null {
    if (!column) return null;
    switch (op) {
      case "contains": return text.trim() ? { column: column.key, op, value: text.trim() } : null;
      case "in": return selected.length ? { column: column.key, op, value: selected } : null;
      case "is": return { column: column.key, op, value: flag };
      case "within_days":
      case "due_within_days": return { column: column.key, op, value: Number(days) || 0 };
      case "range": return range.from || range.to ? { column: column.key, op, value: { from: range.from || null, to: range.to || null } } : null;
      default: return { column: column.key, op };
    }
  }

  const filter = build();
  const inputType = column?.type === "date" ? "date" : "text";

  return <form className="cw-section rg-filter-editor" aria-label="Filter hinzufügen" onSubmit={(event) => { event.preventDefault(); if (filter) onApply(filter); }}>
    <div className="hist-filters">
      <label>Spalte<select value={columnKey} onChange={(event) => setColumnKey(event.target.value)}>{columns.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
      <label>Bedingung<select value={op} onChange={(event) => setOp(event.target.value as FilterOp)}>{ops.map((item) => <option key={item} value={item}>{OP_LABEL[item]}</option>)}</select></label>
      {op === "contains" ? <label>Text<input value={text} onChange={(event) => setText(event.target.value)} /></label> : null}
      {op === "within_days" || op === "due_within_days" ? <label>Tage<input type="number" min={0} max={3650} value={days} onChange={(event) => setDays(event.target.value)} /></label> : null}
      {op === "range" ? <>
        <label>Von<input type={inputType} inputMode={inputType === "text" ? "decimal" : undefined} value={range.from} onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))} /></label>
        <label>Bis<input type={inputType} inputMode={inputType === "text" ? "decimal" : undefined} value={range.to} onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))} /></label>
      </> : null}
      {op === "is" ? <label>Wert<select value={flag ? "ja" : "nein"} onChange={(event) => setFlag(event.target.value === "ja")}><option value="ja">Ja</option><option value="nein">Nein</option></select></label> : null}
    </div>
    {op === "in" ? <fieldset className="rg-grants rg-values"><legend>Werte</legend>
      {values === null ? <p role="status">Werte werden geladen…</p> : values.length === 0 ? <p className="cw-muted">Keine Werte vorhanden.</p> : values.map((item) => <label key={item.value} className="rg-check">
        <input type="checkbox" checked={selected.includes(item.value)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, item.value] : current.filter((value) => value !== item.value))} />
        {item.label}{item.count ? <span className="cw-muted"> ({item.count})</span> : null}
      </label>)}
    </fieldset> : null}
    <div className="rg-actions"><button type="button" className="btn" onClick={onCancel}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={!filter}>Filter anwenden</button></div>
  </form>;
}
