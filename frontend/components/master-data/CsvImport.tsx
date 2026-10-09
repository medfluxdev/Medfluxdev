"use client";

import { useState, type ChangeEvent } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { downloadCsv, mapCsvRows, readCsv, readFileText, toCsv } from "@/lib/csv";
import { importMasterData, type MasterDataImportKind, type MasterDataImportResult } from "@/lib/domain-api/masterData";
import type { ImportColumn } from "./types";

interface Props {
  organizationSlug: string;
  kind: MasterDataImportKind;
  columns: ImportColumn[];
  plural: string;
  fileName: string;
  fieldKey?: string;
  onImported: (count: number) => void;
}

type Row = Record<string, string | null>;

export function parseImportCsv(text: string, columns: ImportColumn[]): { rows: Row[]; error: string | null } {
  const table = readCsv(text);
  if (table.rows.length === 0) return { rows: [], error: "Die Datei braucht eine Kopfzeile und mindestens eine Zeile mit Daten." };
  const headers: Record<string, string> = {};
  for (const column of columns) {
    headers[column.label.toLowerCase()] = column.key;
    headers[column.key.toLowerCase()] = column.key;
    for (const alias of column.aliases ?? []) headers[alias.toLowerCase()] = column.key;
  }
  const mapped = mapCsvRows(table, headers);
  const missing = columns.filter((column) => column.required && !mapped.columns.includes(column.key));
  if (missing.length) return { rows: [], error: `Spalte fehlt: ${missing.map((column) => column.label).join(", ")}.` };
  const rows = mapped.rows.map((row) => {
    const out: Row = {};
    for (const column of columns) out[column.key] = row[column.key]?.trim() || null;
    return out;
  });
  return { rows, error: null };
}

// Liste aus Excel (CSV) pruefen und erst bei fehlerfreier Liste vollstaendig anlegen.
export default function CsvImport({ organizationSlug, kind, columns, plural, fileName, fieldKey, onImported }: Props) {
  const [rows, setRows] = useState<Row[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [check, setCheck] = useState<MasterDataImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [created, setCreated] = useState<number | null>(null);

  const errorsByLine = new Map((check?.rows ?? []).map((item) => [item.line, item]));
  const errorCount = check ? check.rows.filter((item) => item.errors.length > 0).length : 0;
  const shown = columns.slice(0, 4);

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    let parsed: ReturnType<typeof parseImportCsv>;
    try {
      parsed = parseImportCsv(await readFileText(file), columns);
    } catch {
      parsed = { rows: [], error: "Die Datei konnte nicht gelesen werden." };
    }
    setFileError(parsed.error);
    setRows(parsed.rows);
    setCheck(null);
    setCreated(null);
    setRequestError(null);
  }

  async function submit(dryRun: boolean) {
    setBusy(true);
    setRequestError(null);
    try {
      const result = await importMasterData(organizationSlug, kind, rows, dryRun, fieldKey);
      setCheck(result);
      if (!dryRun && result.created > 0) {
        setCreated(result.created);
        setRows([]);
        setCheck(null);
        onImported(result.created);
      }
    } catch (err) {
      setRequestError(err instanceof Error && err.message ? err.message : "Die Liste konnte nicht geprüft werden.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="md-import">
    <p>
      CSV-Liste aus Excel („Speichern unter → CSV“) mit den Spalten {columns.map((column) => column.label + (column.required ? " *" : "")).join(", ")}.
      Bestehende Einträge werden nicht verändert. Angelegt wird nur, wenn keine Zeile einen Fehler hat.
    </p>
    <div className="btn-group">
      <Button size="sm" onClick={() => downloadCsv(`${fileName}-vorlage.csv`, toCsv(columns.map((column) => column.label), []))}>Vorlage herunterladen</Button>
    </div>
    <label className="md-file">Liste auswählen
      <input type="file" accept=".csv,.txt,text/csv" onChange={(event) => void readFile(event)} />
    </label>
    {fileError ? <InlineAlert tone="critical" role="alert">{fileError}</InlineAlert> : null}
    {requestError ? <InlineAlert tone="critical" role="alert">{requestError}</InlineAlert> : null}
    {created !== null ? <InlineAlert tone="success" role="status">{created} {plural} angelegt.</InlineAlert> : null}

    {rows.length > 0 ? <>
      <p role="status">{rows.length} Zeilen in der Liste{check ? (errorCount ? ` · ${errorCount} mit Fehlern` : " · geprüft, keine Fehler") : ""}</p>
      {check && check.errors.length ? <InlineAlert tone="critical" role="alert">{check.errors.join(" ")}</InlineAlert> : null}
      <div className="table-scroll">
        <table className="data-table">
          <caption className="visually-hidden">Vorschau der zu importierenden {plural}</caption>
          <thead><tr><th scope="col">Zeile</th>{shown.map((column) => <th key={column.key} scope="col">{column.label}</th>)}<th scope="col">Prüfung</th></tr></thead>
          <tbody>
            {rows.map((row, index) => {
              const checked = errorsByLine.get(index + 1);
              return <tr key={index} className={checked?.errors.length ? "is-flagged" : undefined}>
                <td>{index + 1}</td>
                {shown.map((column, columnIndex) => columnIndex === 0
                  ? <th key={column.key} scope="row">{row[column.key] ?? "–"}</th>
                  : <td key={column.key}>{row[column.key] ?? "–"}</td>)}
                <td>{checked
                  ? checked.errors.length
                    ? <ul className="md-errors">{checked.errors.map((error) => <li key={error}>{error}</li>)}</ul>
                    : <>
                      <Badge tone="success">In Ordnung</Badge>
                      {checked.warnings.map((warning) => <span key={warning} className="field-hint md-warning">{warning}</span>)}
                    </>
                  : <span className="field-hint">noch nicht geprüft</span>}</td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
      <div className="btn-group">
        <Button disabled={busy} onClick={() => void submit(true)}>Liste prüfen</Button>
        <Button variant="primary" disabled={busy || !check || !check.valid} onClick={() => void submit(false)}>{rows.length} {plural} anlegen</Button>
        <Button disabled={busy} onClick={() => { setRows([]); setCheck(null); }}>Verwerfen</Button>
      </div>
      {!check ? <p className="field-hint">Erst prüfen: Angelegt wird nur, wenn keine Zeile einen Fehler hat.</p> : null}
    </> : null}
  </div>;
}
