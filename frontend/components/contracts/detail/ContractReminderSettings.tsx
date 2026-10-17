"use client";

import { useEffect, useId, useState } from "react";
import Popover from "@/components/ui/Popover";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import { saveReminderLeads, updateContractRegister, type ContractRegister, type ReminderLead, type ReminderUnit } from "@/lib/domain-api/register";
import { LEAD_MAX, leadText, leadsOf, reminderChips, sameLeads, splitLeads, standardLeads } from "@/lib/reminder-leads";

const BELL = <svg className="tl-meta-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16M10 20a2 2 0 0 0 4 0" /></svg>;
const REMOVE = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6 6 18" /></svg>;

/**
 * Erinnerungen als Chips („1 Monat vorher“), entfernen und hinzufügen (Anzahl + Einheit).
 * `standard`: ohne eigene Erinnerung in Monaten erscheint der Standard als nicht entfernbarer Chip.
 */
export function LeadsEditor({ leads, onChange, standard }: { leads: ReminderLead[]; onChange: (next: ReminderLead[]) => void; standard?: ReminderLead[] }) {
  const [add, setAdd] = useState<{ value: string; unit: ReminderUnit } | null>(null);
  const id = useId();
  const chips = standard ? reminderChips(leads, standard) : leads.map((lead) => ({ label: leadText(lead), lead }));

  function addLead() {
    if (!add) return;
    const value = Number(add.value);
    if (!Number.isInteger(value) || value < 1 || value > LEAD_MAX[add.unit]) return;
    if (!leads.some((lead) => lead.value === value && lead.unit === add.unit)) onChange([...leads, { value, unit: add.unit }]);
    setAdd(null);
  }

  return <>
    <ul className="rg-chips" aria-label="Erinnerungen">
      {chips.map((chip) => <li key={chip.label} className={`rg-chip${chip.lead ? " rg-chip--edit" : ""}`}>{chip.label}{chip.lead ? null : " (Standard)"}
        {chip.lead ? <button type="button" aria-label={`${chip.label} entfernen`} onClick={() => onChange(leads.filter((lead) => lead !== chip.lead))}>{REMOVE}</button> : null}
      </li>)}
      {chips.length === 0 ? <li className="cw-muted">Keine Erinnerung vorher – nur am Termin selbst</li> : null}
      {!add && leads.length < 11 ? <li><button type="button" className="rg-chip-add" onClick={() => setAdd({ value: "", unit: "weeks" })}>+ Erinnerung</button></li> : null}
    </ul>
    {add ? <span className="rg-lead-add" role="group" aria-label="Erinnerung hinzufügen">
      <label className="visually-hidden" htmlFor={`${id}-value`}>Anzahl</label>
      <input id={`${id}-value`} type="number" min={1} max={LEAD_MAX[add.unit]} inputMode="numeric" value={add.value} autoFocus
        onChange={(event) => setAdd((current) => current && ({ ...current, value: event.target.value }))}
        onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addLead(); } }} />
      <label className="visually-hidden" htmlFor={`${id}-unit`}>Einheit</label>
      <select id={`${id}-unit`} value={add.unit} onChange={(event) => setAdd((current) => current && ({ ...current, unit: event.target.value as ReminderUnit }))}>
        <option value="days">Tage</option><option value="weeks">Wochen</option><option value="months">Monate</option>
      </select>
      <span>vorher</span>
      <button type="button" className="btn btn-sm" onClick={addLead}>Hinzufügen</button>
      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setAdd(null)}>Abbrechen</button>
    </span> : null}
  </>;
}

type Draft = { leads: ReminderLead[]; recipient: string; escalation: string; escalationDays: string };

function draftOf(register: ContractRegister): Draft {
  const value = (key: string) => {
    const raw = register.fields?.[key]?.value;
    return typeof raw === "string" ? raw : raw == null ? "" : String(raw);
  };
  return {
    leads: leadsOf(register),
    recipient: value("reminder_recipient_account_id"),
    escalation: value("escalation_recipient_account_id"),
    escalationDays: value("escalation_days_before"),
  };
}

/** Eigene Einstellung vorhanden (sonst gilt der Standard). */
export function remindersCustomized(register: ContractRegister): boolean {
  const draft = draftOf(register);
  return draft.leads.length > 0 || Boolean(draft.recipient) || Boolean(draft.escalation) || draft.escalationDays !== "";
}

const daysText = (days: number) => (days === 0 ? "am Termin" : `${days} ${days === 1 ? "Tag" : "Tage"} vorher`);

/**
 * „Termine & Aufgaben“: eine Zeile, wie das Programm erinnert (Vorlauf, Empfänger, Eskalation); „Ändern“ öffnet die
 * Einstellungen. Gilt für Kündigungstermin bzw. Vertragsende (deadlines/system.py); die Werte sind Felder der Vertragsdaten.
 * Einzelne Termine lassen sich über „⋯ → Erinnerung anpassen“ abweichend einstellen.
 */
export default function ContractReminderSettings({ register, contractId, orgSlug, editable, openInitially = false, onSaved }: {
  register: ContractRegister;
  contractId: string;
  orgSlug: string;
  editable: boolean;
  openInitially?: boolean;
  onSaved: (next: ContractRegister) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(register));
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setDraft(draftOf(register)); }, [register]);
  useEffect(() => {
    if (!editable) return;
    let cancelled = false;
    listOwnershipAssignees(orgSlug).then((result) => { if (!cancelled) setAssignees(result.items); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [editable, orgSlug]);

  const standard = standardLeads(register);
  const standardSource = register.reminders?.default_source === "contract_type" ? "Standard des Vertragstyps" : "Standard der Organisation";
  const customized = remindersCustomized(register);
  const leads = reminderChips(leadsOf(register), standard).map((chip) => chip.label).join(", ");
  const recipient = register.fields?.reminder_recipient_account_id?.display ?? null;
  const escalation = register.fields?.escalation_recipient_account_id?.display ?? null;
  const ownDays = register.fields?.escalation_days_before?.value;
  const escalationDays = ownDays != null && ownDays !== "" ? Number(ownDays) : register.reminders?.default_escalation_days ?? null;

  async function save(next: Draft, close: () => void) {
    const days = next.escalationDays.trim();
    if (days !== "" && (!/^\d+$/.test(days) || Number(days) > 365)) {
      setError("Eskalation: 0 bis 365 Tage vor dem Termin.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { first, extra } = splitLeads(next.leads);
      const changes = {
        reminder_lead_months: first,
        reminder_recipient_account_id: next.recipient || null,
        escalation_recipient_account_id: next.escalation || null,
        escalation_days_before: days === "" ? null : Number(days),
      };
      // Erste Erinnerung ist ein Feld der Vertragsdaten, weitere Erinnerungen haben einen eigenen Endpunkt.
      let saved = await updateContractRegister(orgSlug, contractId, { changes });
      if (!sameLeads(extra, register.reminders?.extra_leads ?? [])) saved = await saveReminderLeads(orgSlug, contractId, extra);
      onSaved(saved);
      close();
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "Die Erinnerungen konnten nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="tl-reminders" role="group" aria-label="Erinnerungen">
    {BELL}
    <span>{leads}</span>
    <span aria-hidden="true">·</span>
    <span>an {recipient ?? "Hauptverantwortliche Person"}</span>
    {escalation ? <><span aria-hidden="true">·</span><span>Eskalation an {escalation}{escalationDays != null ? `, ${daysText(escalationDays)}` : " bei Überfälligkeit"}</span></> : null}
    {customized
      ? <span className="rg-origin rg-origin-manual" title="Für diesen Vertrag geändert">Angepasst</span>
      : <span className="rg-origin rg-origin-system" title={`${standardSource}; für diesen Vertrag nicht geändert`}>Standard</span>}
    {editable ? <Popover label="Ändern" panelLabel="Erinnerungen ändern" caret={false} triggerClassName="rg-link" triggerLabel="Erinnerungen ändern" align="end" wide defaultOpen={openInitially}>
      {(close) => <form className="tl-reminder-form" onSubmit={(event) => { event.preventDefault(); void save(draft, close); }}>
        <fieldset>
          <legend>Erinnern</legend>
          <LeadsEditor leads={draft.leads} standard={standard} onChange={(next) => setDraft((current) => ({ ...current, leads: next }))} />
        </fieldset>
        <label>Erinnerung an<select value={draft.recipient} onChange={(event) => setDraft((current) => ({ ...current, recipient: event.target.value }))}>
          <option value="">Hauptverantwortliche Person (Standard)</option>
          {assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
        </select></label>
        <fieldset>
          <legend>Eskalation</legend>
          <label>Eskalation an<select value={draft.escalation} onChange={(event) => setDraft((current) => ({ ...current, escalation: event.target.value }))}>
            <option value="">Keine Eskalation</option>
            {assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
          </select></label>
          {draft.escalation ? <span className="tl-escalation-rule">
            <label htmlFor="tl-escalation-days">Wenn nicht erledigt</label>
            <input id="tl-escalation-days" type="number" min={0} max={365} inputMode="numeric" value={draft.escalationDays}
              placeholder={register.reminders?.default_escalation_days != null ? String(register.reminders.default_escalation_days) : ""}
              onChange={(event) => setDraft((current) => ({ ...current, escalationDays: event.target.value }))} />
            <span>Tage vor dem Termin</span>
          </span> : null}
          {draft.escalation ? <span className="field-hint">Leer = {register.reminders?.default_escalation_days != null ? `Standard (${daysText(register.reminders.default_escalation_days)})` : "erst, wenn der Termin überfällig ist"}.</span> : null}
        </fieldset>
        <p className="field-hint">Gilt für Kündigungstermin bzw. Vertragsende. Einzelne Termine: „⋯ → Erinnerung anpassen“.</p>
        {error ? <p role="alert" className="rg-error">{error}</p> : null}
        <div className="rg-actions">
          {customized ? <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void save({ leads: [], recipient: "", escalation: "", escalationDays: "" }, close)}>Auf Standard zurücksetzen</button> : null}
          <button type="button" className="btn" onClick={() => { setDraft(draftOf(register)); close(); }}>Abbrechen</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Wird gespeichert…" : "Speichern"}</button>
        </div>
      </form>}
    </Popover> : null}
  </div>;
}
