"use client";

import { useEffect, useRef, useState } from "react";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import InfoTip from "@/components/ui/InfoTip";
import Signal from "@/components/ui/Signal";
import { formatDate } from "@/lib/format";
import type { ContractRegister } from "@/lib/domain-api/register";

const DELETION_HELP = "Ende des Kalenderjahres des Vertragsendes + Aufbewahrungsfrist (§ 257 HGB / § 147 AO). Es wird nichts automatisch gelöscht; an diesem Tag entsteht eine Aufgabe ‚Löschprüfung‘.";

export const ARCHIVE_ICON = <svg viewBox="0 0 24 24" focusable="false"><path d="M4 8h16v12H4z" /><path d="M3 4h18v4H3z" /><path d="M10 12h4" /></svg>;

const years = (value: number) => `${value} ${value === 1 ? "Jahr" : "Jahre"}`;

/**
 * Aufbewahrung & Löschung: eine Frist (am Vertrag oder aus dem Vertragstyp, `register.retention`),
 * daraus „Löschen ab“. Bearbeitet wird nur `retention_years_after_end`; leer = Standard des Vertragstyps.
 */
export default function ContractRetentionCard({ register, typeDefaultYears, canEdit, busy, onSaveYears, editRequest }: {
  register: ContractRegister;
  /** Frist des gewählten Vertragstyps (für „Auf Standard … zurücksetzen“). */
  typeDefaultYears: number | null;
  canEdit: boolean;
  busy: boolean;
  /** Speichert die Frist am Vertrag; null = Standard des Vertragstyps. */
  onSaveYears: (value: number | null) => Promise<boolean>;
  /** Ändert sich der Wert, öffnet sich die Eingabe (Sprung „Direkt zur Stelle“). */
  editRequest?: number;
}) {
  const retention = register.retention;
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function open() {
    setValue(retention.years == null ? "" : String(retention.years));
    setEditing(true);
  }
  useEffect(() => { if (editRequest && canEdit) open(); }, [editRequest]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  async function save(next: number | null) {
    if (await onSaveYears(next)) setEditing(false);
  }

  const parsed = value.trim() === "" ? null : Number(value);
  const valid = parsed !== null && Number.isInteger(parsed) && parsed >= 1 && parsed <= 100;
  const due = Boolean(retention.deletion_from && retention.deletion_from <= register.as_of);
  const endYear = retention.contract_end ? retention.contract_end.slice(0, 4) : null;

  return <CollapsibleSection
    id="rg-retention"
    title="Aufbewahrung & Löschung"
    description="Wie lange der Vertrag aufbewahrt werden muss und ab wann er gelöscht werden darf"
    summary={<>{retention.years == null ? <Signal tone="warning" size="sm">Aufbewahrung nicht festgelegt</Signal> : <span>{years(retention.years)} nach Vertragsende</span>}{retention.deletion_from ? <><span className="sep" aria-hidden="true">·</span><span>Löschen ab <b>{formatDate(retention.deletion_from)}</b></span></> : null}{due ? <Signal tone="warning" size="sm">Löschprüfung fällig</Signal> : null}</>}
    icon={ARCHIVE_ICON}
    iconClassName="section-tile--device"
    forceOpen={editing}
  >
    <dl className="rt-tiles">
      <div className={`rt-tile${retention.years == null ? " is-missing" : ""}`} id="rg-field-retention_years_after_end">
        <dt>Aufbewahrung</dt>
        <dd className="rt-value">
          {retention.years == null ? "Nicht festgelegt" : <>{years(retention.years)} nach Vertragsende</>}
          {retention.source ? <span className="rt-source">{retention.source === "contract" ? "am Vertrag festgelegt" : "aus Vertragstyp"}</span> : null}
          {retention.years == null && canEdit && !editing ? <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={open} aria-label="Aufbewahrung festlegen">Festlegen</button> : null}
        </dd>
        {editing ? <dd className="rt-inline-edit">
          <form onSubmit={(event) => { event.preventDefault(); if (valid) void save(parsed); }}>
            <label htmlFor="rg-retention_years_after_end">{retention.years == null ? "Frist:" : "Abweichend:"}</label>
            <input ref={inputRef} id="rg-retention_years_after_end" type="number" min={1} max={100} step={1} inputMode="numeric" aria-label="Aufbewahrung in Jahren" value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setEditing(false); }} />
            <span className="rt-unit">Jahre</span>
            <button type="submit" className="btn btn-sm btn-primary" disabled={busy || !valid}>Speichern</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(false)}>Abbrechen</button>
          </form>
          {value.trim() !== "" && !valid ? <span className="rt-error" role="alert">Bitte eine ganze Zahl von 1 bis 100 eingeben.</span> : null}
        </dd> : <dd className="rt-foot">
          {retention.years == null ? <span>{register.fields.contract_type_id?.value ? "Der Vertragstyp gibt keine Frist vor." : "Ohne Vertragstyp gibt es keine Standardfrist."}</span> : null}
          {retention.years != null && canEdit ? <button type="button" className="rg-link" disabled={busy} onClick={open}>Abweichend festlegen</button> : null}
          {retention.source === "contract" && canEdit
            ? <button type="button" className="rg-link" disabled={busy} onClick={() => void save(null)}>{typeDefaultYears != null ? `Auf Standard des Vertragstyps zurücksetzen (${years(typeDefaultYears)})` : "Festlegung am Vertrag entfernen"}</button>
            : null}
        </dd>}
      </div>
      <div className={`rt-tile${retention.deletion_from ? "" : " is-missing"}`}>
        <dt>Löschen ab <InfoTip label="Erläuterung zu Löschen ab" text={DELETION_HELP} /></dt>
        <dd className="rt-value">
          {retention.deletion_from ? <span className="mono">{formatDate(retention.deletion_from)}</span> : "–"}
          {due ? <Signal tone="warning" size="sm">Löschprüfung fällig</Signal> : null}
        </dd>
        <dd className="rt-foot">
          {retention.deletion_from && retention.contract_end && retention.years != null
            ? <span>Vertragsende {formatDate(retention.contract_end)} → Jahresende {endYear} + {years(retention.years)}</span>
            : !retention.contract_end ? <span>erst nach bekanntem Vertragsende</span> : <span>erst mit festgelegter Aufbewahrung</span>}
        </dd>
      </div>
    </dl>
  </CollapsibleSection>;
}
