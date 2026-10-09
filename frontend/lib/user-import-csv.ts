import { mapCsvRows, readCsv } from "@/lib/csv";
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

export function parseUserCsv(text: string): { rows: UserImportRow[]; error: string | null } {
  const table = readCsv(text);
  if (table.rows.length === 0) return { rows: [], error: "Die Datei braucht eine Kopfzeile und mindestens einen Benutzer." };
  const { columns, rows } = mapCsvRows(table, HEADERS);
  const missing = (["email", "display_name"] as const).filter((key) => !columns.includes(key));
  if (missing.length) return { rows: [], error: `Spalte fehlt: ${missing.map((key) => (key === "email" ? "E-Mail" : "Name")).join(", ")}.` };
  return {
    rows: rows.map((row) => ({
      email: row.email ?? "",
      display_name: row.display_name ?? "",
      role: row.role ?? "",
      hospital: row.hospital || null,
      department: row.department || null,
      password: row.password ?? "",
    })),
    error: null,
  };
}

// Zufaelliges Erstpasswort (16 Zeichen, ohne verwechselbare Zeichen) aus dem Zufallsgenerator des Browsers.
export function generatePassword(length = 16): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789-_!?";
  const values = new Uint32Array(length);
  crypto.getRandomValues(values);
  return Array.from(values, (value) => alphabet[value % alphabet.length]).join("");
}
