// CSV lesen und schreiben, wie Excel sie erzeugt (Semikolon, Komma oder Tabulator,
// Anfuehrungszeichen, UTF-8 mit BOM). Gemeinsame Grundlage aller Listen-Importe.

export function splitCsvLine(line: string, delimiter: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (quoted) {
      if (char === '"' && line[i + 1] === '"') { current += '"'; i++; }
      else if (char === '"') quoted = false;
      else current += char;
    } else if (char === '"') quoted = true;
    else if (char === delimiter) { cells.push(current); current = ""; }
    else current += char;
  }
  cells.push(current);
  return cells.map((cell) => cell.trim());
}

export interface CsvTable {
  header: string[];
  rows: string[][];
}

// Kopfzeile + Datenzeilen; das Trennzeichen bestimmt die Kopfzeile.
export function readCsv(text: string): CsvTable {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) return { header: [], rows: [] };
  const head = lines[0];
  const delimiter = [";", "\t", ","].sort((a, b) => head.split(b).length - head.split(a).length)[0];
  return { header: splitCsvLine(head, delimiter), rows: lines.slice(1).map((line) => splitCsvLine(line, delimiter)) };
}

// Ordnet Spalten ueber bekannte Kopfzeilen-Namen (ohne Gross-/Kleinschreibung) Feldern zu.
export function mapCsvRows<K extends string>(table: CsvTable, headers: Record<string, K>): { columns: (K | null)[]; rows: Partial<Record<K, string>>[] } {
  const columns = table.header.map((cell) => headers[cell.toLowerCase()] ?? null);
  const rows = table.rows.map((cells) => {
    const row: Partial<Record<K, string>> = {};
    columns.forEach((key, index) => {
      if (key) row[key] = cells[index] ?? "";
    });
    return row;
  });
  return { columns, rows };
}

export function csvCell(value: string): string {
  return /[;"\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function toCsv(header: string[], rows: (string | number | null | undefined)[][]): string {
  return [header, ...rows].map((row) => row.map((value) => csvCell(value == null ? "" : String(value))).join(";")).join("\r\n") + "\r\n";
}

export function downloadCsv(name: string, text: string) {
  const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, "utf-8");
  });
}
