import type { UserImportRow } from "@/lib/domain-api/users";

// Liest eine Benutzerliste (CSV aus Excel: Semikolon, Komma oder Tabulator).
// Erkannte Spalten: E-Mail, Name, Rolle, Krankenhaus, Bereich/Abteilung, Passwort/Erstpasswort.

const HEADERS: Record<string, keyof UserImportRow> = {
  "e-mail": "email", email: "email", mail: "email", benutzername: "email", login: "email",
  name: "display_name", anzeigename: "display_name", "vollständiger name": "display_name",
  rolle: "role", role: "role",
  krankenhaus: "hospital", hospital: "hospital", klinik: "hospital", standort: "hospital",
  bereich: "department", abteilung: "department", department: "department",
  passwort: "password", erstpasswort: "password", kennwort: "password", password: "password",
};

export const USER_IMPORT_TEMPLATE = "E-Mail;Name;Rolle;Krankenhaus;Bereich;Erstpasswort\r\n";

function splitLine(line: string, delimiter: string): string[] {
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

export function parseUserCsv(text: string): { rows: UserImportRow[]; error: string | null } {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length < 2) return { rows: [], error: "Die Datei braucht eine Kopfzeile und mindestens einen Benutzer." };
  const head = lines[0];
  const delimiter = [";", "\t", ","].sort((a, b) => head.split(b).length - head.split(a).length)[0];
  const columns = splitLine(head, delimiter).map((cell) => HEADERS[cell.toLowerCase()] ?? null);
  const missing = (["email", "display_name"] as const).filter((key) => !columns.includes(key));
  if (missing.length) return { rows: [], error: `Spalte fehlt: ${missing.map((key) => (key === "email" ? "E-Mail" : "Name")).join(", ")}.` };
  const rows = lines.slice(1).map((line) => {
    const cells = splitLine(line, delimiter);
    const row: UserImportRow = { email: "", display_name: "", role: "", hospital: null, department: null, password: "" };
    columns.forEach((key, index) => {
      if (!key) return;
      const value = cells[index] ?? "";
      if (key === "hospital" || key === "department") row[key] = value || null;
      else row[key] = value;
    });
    return row;
  });
  return { rows, error: null };
}

// Zufaelliges Erstpasswort (16 Zeichen, ohne verwechselbare Zeichen) aus dem Zufallsgenerator des Browsers.
export function generatePassword(length = 16): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789-_!?";
  const values = new Uint32Array(length);
  crypto.getRandomValues(values);
  return Array.from(values, (value) => alphabet[value % alphabet.length]).join("");
}
