"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { formatDate } from "@/lib/format";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import {
  createContractDeadline,
  deadlineAction,
  listContractDeadlines,
  updateDeadline,
  type DeadlineDto,
} from "@/lib/domain-api/deadlines";

const EMPTY_FORM = { title: "", kind: "pruefung", due_date: "", remind_on: "", assignee_account_id: "", escalation_account_id: "", todo_text: "", send_email: true, send_ics: false };

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function dueLabel(item: DeadlineDto) {
  if (item.status !== "open") return null;
  if (item.overdue) return `seit ${Math.abs(item.days_until_due)} Tag(en) überfällig`;
  if (item.days_until_due === 0) return "heute fällig";
  return `in ${item.days_until_due} Tag(en)`;
}

export default function ContractDeadlinesPanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [items, setItems] = useState<DeadlineDto[] | null>(null);
  const [kinds, setKinds] = useState<LookupDto[]>([]);
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await listContractDeadlines(orgSlug, contractId))?.items ?? []);
    } catch (error) {
      setItems([]);
      setMessage({ tone: "error", text: errorText(error, "Termine konnten nicht geladen werden.") });
    }
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!editable) return;
    let cancelled = false;
    Promise.allSettled([listLookups(orgSlug, "deadline_kind"), listOwnershipAssignees(orgSlug)]).then(([kindResult, assigneeResult]) => {
      if (cancelled) return;
      if (kindResult.status === "fulfilled") setKinds(kindResult.value.items);
      if (assigneeResult.status === "fulfilled") setAssignees(assigneeResult.value.items);
    });
    return () => { cancelled = true; };
  }, [editable, orgSlug]);

  async function run(action: () => Promise<{ items: DeadlineDto[] }>, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      setItems((await action()).items);
      setMessage({ tone: "ok", text: success });
      return true;
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Die Änderung konnte nicht gespeichert werden.") });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    const ok = await run(() => createContractDeadline(orgSlug, contractId, {
      title: form.title,
      kind: form.kind,
      due_date: form.due_date,
      remind_on: form.remind_on || undefined,
      assignee_account_id: form.assignee_account_id || undefined,
      escalation_account_id: form.escalation_account_id || null,
      todo_text: form.todo_text || null,
      send_email: form.send_email,
      send_ics: form.send_ics,
    }), "Termin angelegt.");
    if (ok) {
      setForm(EMPTY_FORM);
      setShowForm(false);
    }
  }

  const open = (items ?? []).filter((item) => item.status === "open");
  const closed = (items ?? []).filter((item) => item.status !== "open");
  const kindLabel = (code: string) => kinds.find((item) => item.code === code)?.label ?? code;

  function renderItem(item: DeadlineDto) {
    return <li key={item.id} className={`rg-deadline${item.overdue ? " rg-deadline-overdue" : ""}${item.status !== "open" ? " rg-inactive" : ""}`}>
      <div className="rg-deadline-main">
        <strong>{item.title}</strong>
        <span>Fällig {formatDate(item.due_date)}{dueLabel(item) ? ` · ${dueLabel(item)}` : ""} · Erinnerung {formatDate(item.remind_on)}</span>
        <span className="cw-muted">{kindLabel(item.kind)} · Zuständig: {item.assignee_name ?? "Verantwortliche Person des Vertrags"}{item.escalation_name ? ` · Eskalation: ${item.escalation_name}` : ""}</span>
        {item.todo_text ? <span>ToDo: {item.todo_text}</span> : null}
        {item.note ? <span className="cw-muted">Bemerkung: {item.note}</span> : null}
        <span className="rg-period">
          {item.source === "system" ? <span className="rg-origin">Aus Stammdaten berechnet</span> : <span className="rg-origin rg-origin-manual">Manuell</span>}
          {item.basis_unconfirmed ? <span className="rg-origin rg-origin-ai_corrected" title="Mindestens ein zugrunde liegender Wert stammt aus der KI und ist noch nicht bestätigt.">Basiert auf ungeprüften KI-Werten</span> : null}
          {item.send_email ? <span className="rg-origin">E-Mail</span> : null}
          {item.send_ics ? <span className="rg-origin">Kalender</span> : null}
          {item.status === "done" ? <span className="rg-origin rg-origin-ai_confirmed">Erledigt{item.done_by_name ? ` von ${item.done_by_name}` : ""}</span> : null}
          {item.status === "cancelled" ? <span className="rg-origin">Abgebrochen</span> : null}
        </span>
      </div>
      {editable ? <div className="rg-actions">
        {item.status === "open" ? <>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run(() => deadlineAction(orgSlug, item.id, "done"), "Termin erledigt.")}>Erledigt</button>
          <button type="button" className="btn" disabled={busy} aria-pressed={item.send_ics} onClick={() => void run(() => updateDeadline(orgSlug, item.id, { send_ics: !item.send_ics }), "Gespeichert.")}>{item.send_ics ? "Kalender aus" : "Kalender an"}</button>
          {item.source === "manual" ? <button type="button" className="btn" disabled={busy} onClick={() => void run(() => deadlineAction(orgSlug, item.id, "cancel"), "Termin abgebrochen.")}>Abbrechen</button> : null}
        </> : <button type="button" className="btn" disabled={busy} onClick={() => void run(() => deadlineAction(orgSlug, item.id, "reopen"), "Termin wieder geöffnet.")}>Wieder öffnen</button>}
      </div> : null}
    </li>;
  }

  return <section className="cw-section" aria-labelledby="rg-deadlines-heading">
    <div className="cw-section-head">
      <div><h2 id="rg-deadlines-heading">Termine & Wiedervorlagen</h2><p>Fristen aus den Stammdaten werden automatisch angelegt und nachgeführt. Erinnerungen erscheinen im Postfach und auf Wunsch per E-Mail.</p></div>
      {editable && !showForm ? <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>Termin hinzufügen</button> : null}
    </div>
    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}
    {showForm ? <form className="rg-transition" aria-label="Neuer Termin" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <div className="rg-form-grid">
        <label>Bezeichnung *<input required maxLength={255} value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} /></label>
        <label>Art<select value={form.kind} onChange={(event) => setForm((current) => ({ ...current, kind: event.target.value }))}>{kinds.length === 0 ? <option value="pruefung">Prüfung</option> : kinds.map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}</select></label>
        <label>Fällig am *<input type="date" required value={form.due_date} onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))} /></label>
        <label>Erinnern am<input type="date" value={form.remind_on} max={form.due_date || undefined} onChange={(event) => setForm((current) => ({ ...current, remind_on: event.target.value }))} /></label>
        <label>Zuständig<select value={form.assignee_account_id} onChange={(event) => setForm((current) => ({ ...current, assignee_account_id: event.target.value }))}><option value="">Ich selbst</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label>Eskalation an<select value={form.escalation_account_id} onChange={(event) => setForm((current) => ({ ...current, escalation_account_id: event.target.value }))}><option value="">Niemand</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label className="span-full">ToDo<input maxLength={500} value={form.todo_text} onChange={(event) => setForm((current) => ({ ...current, todo_text: event.target.value }))} /></label>
        <label className="rg-check"><input type="checkbox" checked={form.send_email} onChange={(event) => setForm((current) => ({ ...current, send_email: event.target.checked }))} />Erinnerungs-E-Mail</label>
        <label className="rg-check"><input type="checkbox" checked={form.send_ics} onChange={(event) => setForm((current) => ({ ...current, send_ics: event.target.checked }))} />Kalendereinladung (ICS)</label>
      </div>
      <div className="rg-actions"><button type="button" className="btn" onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Termin anlegen</button></div>
    </form> : null}
    {items === null ? <p role="status">Termine werden geladen…</p> : <>
      {open.length === 0 ? <p className="cw-muted">Keine offenen Termine. Fristen erscheinen automatisch, sobald Vertragsart, Beginn und Kündigungsfrist erfasst sind.</p> : <ul className="rg-deadlines">{open.map(renderItem)}</ul>}
      {closed.length > 0 ? <details><summary>Erledigte und abgebrochene Termine ({closed.length})</summary><ul className="rg-deadlines">{closed.map(renderItem)}</ul></details> : null}
    </>}
  </section>;
}
