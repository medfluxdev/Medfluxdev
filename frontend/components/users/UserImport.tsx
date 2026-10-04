"use client";

import { useState, type ChangeEvent } from "react";
import Badge from "@/components/ui/Badge";
import { ROLE_LABELS } from "@/lib/auth-types";
import { importUsers, type UserImportResult, type UserImportRow } from "@/lib/domain-api/users";
import { generatePassword, parseUserCsv, USER_IMPORT_TEMPLATE } from "@/lib/user-import-csv";

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, "utf-8");
  });
}

function csvCell(value: string) {
  return /[;"\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

// Mehrere Benutzer auf einmal anlegen. Der Administrator vergibt jedem Benutzer
// sein Erstpasswort (aus der Liste, von Hand oder erzeugt) und gibt es ihm weiter.
export default function UserImport({ organizationSlug, onImported }: { organizationSlug: string; onImported: () => void }) {
  const [rows, setRows] = useState<UserImportRow[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [check, setCheck] = useState<UserImportResult | null>(null);
  const [checkedFor, setCheckedFor] = useState<string | null>(null);
  const [showPasswords, setShowPasswords] = useState(false);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [imported, setImported] = useState<UserImportRow[] | null>(null);

  const signature = JSON.stringify(rows);
  const checkCurrent = check !== null && checkedFor === signature;
  const errorsByLine = new Map((checkCurrent ? check.rows : []).map((item) => [item.line, item]));
  const errorCount = checkCurrent ? check.rows.filter((item) => item.errors.length > 0).length : 0;

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    let parsed: ReturnType<typeof parseUserCsv>;
    try {
      parsed = parseUserCsv(await readText(file));
    } catch {
      parsed = { rows: [], error: "Die Datei konnte nicht gelesen werden." };
    }
    setFileError(parsed.error);
    setRows(parsed.rows);
    setCheck(null);
    setImported(null);
    setRequestError(null);
  }

  function setPassword(index: number, password: string) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, password } : row)));
  }

  function fillMissingPasswords() {
    setRows((current) => current.map((row) => (row.password ? row : { ...row, password: generatePassword() })));
    setShowPasswords(true);
  }

  async function submit(dryRun: boolean) {
    setBusy(true);
    setRequestError(null);
    try {
      const result = await importUsers(organizationSlug, rows, dryRun);
      setCheck(result);
      setCheckedFor(signature);
      if (!dryRun && result.created > 0) {
        setImported(rows);
        setRows([]);
        setCheck(null);
        onImported();
      }
    } catch (err) {
      setRequestError(err instanceof Error && err.message ? err.message : "Die Liste konnte nicht geprüft werden.");
    } finally {
      setBusy(false);
    }
  }

  function downloadAccess() {
    if (!imported) return;
    const lines = ["E-Mail;Name;Erstpasswort", ...imported.map((row) => [row.email.trim().toLowerCase(), row.display_name.trim(), row.password].map(csvCell).join(";"))];
    download("zugangsdaten.csv", lines.join("\r\n") + "\r\n");
  }

  return (
    <section className="card card-pad user-import" aria-labelledby="user-import-heading">
      <div className="section-head">
        <div>
          <h2 id="user-import-heading">Mehrere Benutzer importieren</h2>
          <p>CSV-Liste mit den Spalten E-Mail, Name, Rolle, Krankenhaus, Bereich und Erstpasswort (Excel: „Speichern unter → CSV“). Sie vergeben die Erstpasswörter und geben sie den Benutzern weiter.</p>
        </div>
        <button type="button" className="btn btn-sm" onClick={() => download("benutzer-vorlage.csv", USER_IMPORT_TEMPLATE)}>Vorlage herunterladen</button>
      </div>

      <label className="user-import-file">Liste auswählen
        <input type="file" accept=".csv,.txt,text/csv" onChange={(event) => void readFile(event)} />
      </label>
      {fileError ? <p className="alert alert--critical" role="alert">{fileError}</p> : null}
      {requestError ? <p className="alert alert--critical" role="alert">{requestError}</p> : null}

      {imported ? (
        <div className="alert alert--success" role="status">
          <p>{imported.length} Benutzer angelegt. Geben Sie jedem Benutzer sein Erstpasswort persönlich oder auf einem sicheren Weg weiter.</p>
          <button type="button" className="btn btn-sm" onClick={downloadAccess}>Zugangsdaten herunterladen</button>
          <p className="field-hint">Die Datei enthält Passwörter – nach der Weitergabe löschen.</p>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <>
          <div className="user-import-tools">
            <span>{rows.length} Benutzer in der Liste{checkCurrent ? (errorCount ? ` · ${errorCount} mit Fehlern` : " · geprüft, keine Fehler") : ""}</span>
            <button type="button" className="btn btn-sm" onClick={fillMissingPasswords}>Fehlende Passwörter erzeugen</button>
            <label className="shell-check"><input type="checkbox" checked={showPasswords} onChange={(event) => setShowPasswords(event.target.checked)} />Passwörter anzeigen</label>
          </div>
          {checkCurrent && check.errors.length ? <p className="alert alert--critical" role="alert">{check.errors.join(" ")}</p> : null}
          <div className="table-scroll">
            <table className="data-table user-import-table">
              <caption className="visually-hidden">Vorschau der zu importierenden Benutzer</caption>
              <thead>
                <tr><th scope="col">Nr.</th><th scope="col">E-Mail</th><th scope="col">Name</th><th scope="col">Rolle</th><th scope="col">Krankenhaus / Bereich</th><th scope="col">Erstpasswort</th><th scope="col">Prüfung</th></tr>
              </thead>
              <tbody>
                {rows.map((row, index) => {
                  const checked = errorsByLine.get(index + 1);
                  return (
                    <tr key={index} className={checked?.errors.length ? "is-flagged" : undefined}>
                      <td>{index + 1}</td>
                      <th scope="row">{row.email || "–"}</th>
                      <td>{row.display_name || "–"}</td>
                      <td>{checked?.role ? ROLE_LABELS[checked.role] : row.role || "Leser"}</td>
                      <td>{checked?.hospital ?? row.hospital ?? (checked?.role === "admin" ? "Organisationsweit" : "–")}{(checked?.department ?? row.department) ? ` / ${checked?.department ?? row.department}` : ""}</td>
                      <td>
                        <input
                          type={showPasswords ? "text" : "password"}
                          autoComplete="new-password"
                          aria-label={`Erstpasswort für ${row.email || `Zeile ${index + 1}`}`}
                          value={row.password}
                          onChange={(event) => setPassword(index, event.target.value)}
                        />
                      </td>
                      <td>{checked ? (checked.errors.length ? <ul className="user-import-errors">{checked.errors.map((error) => <li key={error}>{error}</li>)}</ul> : <Badge tone="success">In Ordnung</Badge>) : <span className="field-hint">noch nicht geprüft</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="btn-group">
            <button type="button" className="btn" disabled={busy} onClick={() => void submit(true)}>Liste prüfen</button>
            <button type="button" className="btn btn-primary" disabled={busy || !checkCurrent || !check.valid} onClick={() => void submit(false)}>{rows.length} Benutzer anlegen</button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => { setRows([]); setCheck(null); }}>Verwerfen</button>
          </div>
          {!checkCurrent ? <p className="field-hint">Erst prüfen: Angelegt wird nur, wenn keine Zeile einen Fehler hat.</p> : null}
        </>
      ) : null}
    </section>
  );
}
