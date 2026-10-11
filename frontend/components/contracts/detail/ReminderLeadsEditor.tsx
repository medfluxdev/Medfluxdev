"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { saveReminderLeads, type ContractRegister, type ReminderLead, type ReminderUnit } from "@/lib/domain-api/register";
import { formatDate } from "@/lib/format";

const UNIT_LABEL: Record<ReminderUnit, [string, string]> = { days: ["Tag", "Tage"], weeks: ["Woche", "Wochen"], months: ["Monat", "Monate"] };
const UNIT_MAX: Record<ReminderUnit, number> = { days: 365, weeks: 104, months: 60 };

export function leadLabel(lead: ReminderLead): string {
  const [singular, plural] = UNIT_LABEL[lead.unit];
  return `${lead.value} ${lead.value === 1 ? singular : plural}`;
}

type Draft = { value: string; unit: ReminderUnit };

/**
 * Weitere Erinnerungen vor Kündigungstermin bzw. Vertragsende (z. B. 1 Monat und 2 Wochen vorher).
 * Die erste Erinnerung ist das Feld „Erinnerung (Monate vor Frist)“ (leer = Standard).
 */
export default function ReminderLeadsEditor({ contractId, orgSlug, register, editable, onSaved }: {
  contractId: string;
  orgSlug: string;
  register: ContractRegister;
  editable: boolean;
  onSaved: (register: ContractRegister) => void;
}) {
  const saved = register.reminders?.extra_leads ?? [];
  const [draft, setDraft] = useState<Draft[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setDraft(null); }, [register]);

  const dates = register.terms.reminder_dates ?? [];

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      const leads = draft.filter((item) => item.value.trim()).map((item) => ({ value: Number(item.value), unit: item.unit }));
      onSaved(await saveReminderLeads(orgSlug, contractId, leads));
      setDraft(null);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.message ? caught.message : "Erinnerungen konnten nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="reminder-leads" id="rg-field-reminder_extra_leads">
    <h3>Weitere Erinnerungen</h3>
    {draft === null ? <>
      {saved.length ? <p>{saved.map(leadLabel).join(", ")} vor der Frist</p> : <p className="cw-muted">Keine – nur die erste Erinnerung.</p>}
      {dates.length ? <p className="field-hint">Erinnerungen am {dates.map((value) => formatDate(value)).join(", ")}.</p> : null}
      {editable ? <button type="button" className="btn btn-sm" onClick={() => setDraft(saved.map((lead) => ({ value: String(lead.value), unit: lead.unit })))}>{saved.length ? "Weitere Erinnerungen ändern" : "Weitere Erinnerung hinzufügen"}</button> : null}
    </> : <>
      <ul className="reminder-lead-list">{draft.map((item, index) => <li key={index}>
        <label className="visually-hidden" htmlFor={`reminder-lead-${index}`}>Weitere Erinnerung {index + 1}: Anzahl</label>
        <input id={`reminder-lead-${index}`} type="number" min={1} max={UNIT_MAX[item.unit]} inputMode="numeric" value={item.value}
          onChange={(event) => setDraft((current) => current!.map((entry, position) => (position === index ? { ...entry, value: event.target.value } : entry)))} />
        <label className="visually-hidden" htmlFor={`reminder-unit-${index}`}>Weitere Erinnerung {index + 1}: Einheit</label>
        <select id={`reminder-unit-${index}`} value={item.unit} onChange={(event) => setDraft((current) => current!.map((entry, position) => (position === index ? { ...entry, unit: event.target.value as ReminderUnit } : entry)))}>
          <option value="days">Tage</option><option value="weeks">Wochen</option><option value="months">Monate</option>
        </select>
        <span>vor der Frist</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft((current) => current!.filter((_, position) => position !== index))} aria-label={`Weitere Erinnerung ${index + 1} entfernen`}>Entfernen</button>
      </li>)}</ul>
      <div className="rg-actions">
        {draft.length < 10 ? <button type="button" className="rg-link" onClick={() => setDraft((current) => [...current!, { value: "", unit: "weeks" }])}>+ Erinnerung hinzufügen</button> : null}
        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => { setDraft(null); setError(null); }}>Abbrechen</button>
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void save()}>{busy ? "Wird gespeichert…" : "Speichern"}</button>
      </div>
    </>}
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
  </div>;
}
