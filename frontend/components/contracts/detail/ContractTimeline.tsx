"use client";

import { Fragment, useCallback, useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import ActionMenu, { type ActionMenuItem } from "@/components/ui/ActionMenu";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import EmptyState from "@/components/ui/EmptyState";
import Signal, { SignalIcon } from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import type { DetailWorkItem } from "@/lib/contract-detail-types";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { createContractDeadline, deadlineAction, listContractDeadlines, updateDeadline, type DeadlineDto, type DeadlineValues } from "@/lib/domain-api/deadlines";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import { getContractRegister, type ContractRegister, type ReminderLead } from "@/lib/domain-api/register";
import ContractReminderSettings, { LeadsEditor } from "./ContractReminderSettings";
import { leadsOf, standardLeads } from "@/lib/reminder-leads";
import { REVIEW_TARGET, workItemTarget, type FixTarget } from "@/lib/fix-targets";
import { formatDate } from "@/lib/format";
import { buildIcs, downloadIcs } from "@/lib/ics";
import { KindChip, TERMIN_KINDS, TERMIN_KIND_ORDER, deadlineKind, type TerminFilter, type TerminKind } from "@/components/deadlines/TerminKind";
import { formatRelativeDate } from "@/lib/relative-date";

type Filter = "all" | TerminFilter;

const icon = (path: ReactNode, className = "signal-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{path}</svg>;
const KINDS = TERMIN_KINDS;
const KIND_ORDER = TERMIN_KIND_ORDER;

const META_ICONS = {
  calendar: icon(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>, "tl-meta-icon"),
  escalate: icon(<path d="M12 19V5M5 12l7-7 7 7" />, "tl-meta-icon"),
  todo: icon(<><rect x="4" y="4" width="16" height="16" rx="2" /><path d="m8 12 3 3 5-6" /></>, "tl-meta-icon"),
  info: icon(<><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.5" /></>, "tl-meta-icon"),
  bell: icon(<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16M10 20a2 2 0 0 0 4 0" />, "tl-meta-icon"),
};
const MENU_ICONS = {
  edit: icon(<><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></>, "action-menu-icon"),
  assign: icon(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>, "action-menu-icon"),
  calendar: icon(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>, "action-menu-icon"),
  done: icon(<path d="M20 6 9 17l-5-5" />, "action-menu-icon"),
  cancel: icon(<path d="M6 6l12 12M18 6 6 18" />, "action-menu-icon"),
  bell: icon(<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16M10 20a2 2 0 0 0 4 0" />, "action-menu-icon"),
};
const BUTTON_ICONS = {
  done: icon(<path d="M20 6 9 17l-5-5" />, "btn-icon-svg"),
  reopen: icon(<><path d="M9 14 4 9l5-5" /><path d="M4 9h11a5 5 0 0 1 0 10h-3" /></>, "btn-icon-svg"),
  add: icon(<path d="M12 5v14M5 12h14" />, "btn-icon-svg"),
  cancelled: icon(<path d="M6 6l12 12M18 6 6 18" />),
};
const CARD_ICON = icon(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>);

/** Vergleich Dokument ↔ Vertragsdaten beim Vertragsende (KI-Prüfung ohne eigenen Arbeitsvorrat-Eintrag). */
export interface EndCheck {
  documented: string | null;
  maintained: string;
  /** Feste Laufzeit: der Dokumentwert kann als „Festes Vertragsende“ übernommen werden. */
  fixedTerm: boolean;
  onShowSource?: () => void;
  onAdopt: () => Promise<void>;
  onKeep: () => Promise<void>;
}

interface Row {
  key: string;
  date: string | null;
  kind: TerminKind;
  title: string;
  /** Zweite Zeile: kleine Angaben (Termin, Eskalation, Beschreibung, Hinweise). */
  meta: ReactNode[];
  person: string | null;
  personId: string | null;
  /** Automatische Erinnerungen dieses Termins (Unterzeile statt eigener Zeilen). */
  reminders?: { date: string; to: string | null }[];
  primary?: ReactNode;
  menu?: ActionMenuItem[];
  expand?: ReactNode;
  closed?: "done" | "cancelled";
  /** Für die Erkennung doppelt angelegter Aufgaben. */
  duplicateKey?: string;
}

type Editor = { id: string; mode: "edit" | "assign" | "cancel" | "remind" };

const EMPTY_FORM = { title: "", kind: "pruefung", due_date: "", remind_on: "", assignee_account_id: "", escalation_account_id: "", todo_text: "", send_email: true, send_ics: false };
type DeadlineForm = typeof EMPTY_FORM;

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

// Titel = Handlung bzw. Termin, nie eine Person (die steht in „Zuständig“). Systemtermine einheitlich benannt,
// auch solange ältere Zeilen noch den alten Titel tragen (der nächste Fristenabgleich übernimmt ihn).
const SYSTEM_TITLES: Record<string, string> = { cancel_by: "Kündigung prüfen", contract_end: "Vertragsende", retention_review: "Löschprüfung" };
function deadlineTitle(item: DeadlineDto) {
  return (item.system_key && SYSTEM_TITLES[item.system_key]) || item.title;
}

// Vorschläge für eigene Termine (frei änderbar).
const TITLE_SUGGESTIONS = ["Kündigung prüfen", "Kündigung versenden", "Verlängerung umsetzen", "Neu verhandeln", "Angebot einholen", "Vertragsende", "Wartung abstimmen", "Rechnung prüfen", "Löschprüfung"];

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

function Person({ name }: { name: string | null }) {
  if (!name) return <span className="tl-none" aria-label="Niemand zugewiesen">–</span>;
  return <span className="tl-person"><span className="tl-avatar" aria-hidden="true">{initials(name)}</span><span className="tl-person-name">{name}</span></span>;
}

const REMINDER_FIELDS = new Set(["reminder_lead_months", "reminder_extra_leads", "reminder_recipient_account_id", "escalation_recipient_account_id"]);

const normalizeTitle = (value: string) => value.trim().toLocaleLowerCase("de-DE");

// Am Termin angepasst (Erinnerungen bzw. bei Systemterminen der Empfänger); sonst gilt der Vertrag.
const assigneeOverridden = (item: DeadlineDto) => item.source === "system" && Boolean(item.custom_fields?.includes("assignee_account_id"));
const remindersOverridden = (item: DeadlineDto) => Boolean(item.custom_fields?.includes("reminder_leads")) || assigneeOverridden(item);

function formFromDeadline(item: DeadlineDto): DeadlineForm {
  return {
    title: item.title, kind: item.kind, due_date: item.due_date, remind_on: item.remind_on ?? "",
    assignee_account_id: item.assignee_account_id ?? "", escalation_account_id: item.escalation_account_id ?? "",
    todo_text: item.todo_text ?? "", send_email: item.send_email, send_ics: item.send_ics,
  };
}

/**
 * Fristen & Aufgaben → „Termine & Aufgaben“: alle Termine, Erinnerungen und Aufgaben eines Vertrags auf einer Zeitachse.
 * Feste Spalten, eine Hauptaktion je Zeile (Rest im „⋯“-Menü), Jahresgruppen und relative Zeit; Erledigtes eingeklappt.
 */
export default function ContractTimeline({ contractId, orgSlug, workItems, endCheck, onOpenTarget, version = 0 }: {
  contractId: string;
  /** Erhöhen, um neu zu laden (z. B. nach geänderten Erinnerungen). */
  version?: number;
  orgSlug: string;
  workItems: DetailWorkItem[];
  endCheck?: EndCheck | null;
  onOpenTarget: (target: FixTarget) => void;
}) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const toast = useToast();
  const [items, setItems] = useState<DeadlineDto[] | null>(null);
  const [register, setRegister] = useState<ContractRegister | null>(null);
  // Sprung auf ein Erinnerungsfeld (?feld=…) öffnet die Einstellungen.
  const targetField = useSearchParams()?.get("feld") ?? null;
  const settingsTarget = targetField !== null && REMINDER_FIELDS.has(targetField);
  const [today, setToday] = useState(localToday);
  const [kinds, setKinds] = useState<LookupDto[]>([]);
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [form, setForm] = useState<DeadlineForm | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [editForm, setEditForm] = useState<DeadlineForm | null>(null);
  const [remindDraft, setRemindDraft] = useState<{ leads: ReminderLead[]; assignee: string } | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [mine, setMine] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [deadlines, register] = await Promise.allSettled([listContractDeadlines(orgSlug, contractId), getContractRegister(orgSlug, contractId)]);
    if (deadlines.status === "fulfilled") setItems(deadlines.value?.items ?? []);
    else { setItems([]); setError(errorText(deadlines.reason, "Termine konnten nicht geladen werden.")); }
    if (register.status === "fulfilled" && register.value) {
      setRegister(register.value);
      if (register.value.as_of) setToday(register.value.as_of);
    }
  }, [contractId, orgSlug, version]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void load(); }, [load]);

  const needsLists = form !== null || (editor !== null && editor.mode !== "cancel");
  useEffect(() => {
    if (!editable || !needsLists) return;
    let cancelled = false;
    Promise.allSettled([listLookups(orgSlug, "deadline_kind"), listOwnershipAssignees(orgSlug)]).then(([kindResult, assigneeResult]) => {
      if (cancelled) return;
      if (kindResult.status === "fulfilled") setKinds(kindResult.value.items);
      if (assigneeResult.status === "fulfilled") setAssignees(assigneeResult.value.items);
    });
    return () => { cancelled = true; };
  }, [editable, orgSlug, needsLists]);

  async function act(action: () => Promise<{ items: DeadlineDto[] }>, success: string) {
    setBusy(true);
    setError(null);
    try {
      setItems((await action()).items);
      toast(success, "success");
      return true;
    } catch (err) {
      setError(errorText(err, "Die Änderung konnte nicht gespeichert werden."));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!form) return;
    const ok = await act(() => createContractDeadline(orgSlug, contractId, {
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
    if (ok) setForm(null);
  }

  function openEditor(item: DeadlineDto, mode: Editor["mode"]) {
    setEditor({ id: item.id, mode });
    setEditForm(formFromDeadline(item));
    if (mode === "remind") setRemindDraft({ leads: currentLeads(item), assignee: assigneeOverridden(item) || item.source === "manual" ? item.assignee_account_id ?? "" : "" });
  }

  // Ausgangswert für „Erinnerung anpassen“: eigene Erinnerungen des Termins, sonst die des Vertrags (Kündigung/Vertragsende).
  function currentLeads(item: DeadlineDto): ReminderLead[] {
    if (item.reminder_leads) return item.reminder_leads;
    if (register && (item.system_key === "cancel_by" || item.system_key === "contract_end")) {
      const own = leadsOf(register);
      const months = own.some((lead) => lead.unit === "months");
      const standard = standardLeads(register);
      return months ? own : [...standard, ...own];
    }
    return [];
  }

  async function saveReminders(item: DeadlineDto, reset = false) {
    if (!remindDraft) return;
    const values: DeadlineValues = reset
      ? { reminder_leads: null, ...(item.source === "system" ? { assignee_account_id: null } : {}) }
      : { reminder_leads: remindDraft.leads, ...(item.source === "system" || remindDraft.assignee !== (item.assignee_account_id ?? "") ? { assignee_account_id: remindDraft.assignee || null } : {}) };
    const ok = await act(() => updateDeadline(orgSlug, item.id, values), reset ? "Erinnerung folgt wieder dem Vertrag." : "Erinnerung angepasst.");
    if (ok) { setEditor(null); setRemindDraft(null); }
  }

  async function saveEdit(item: DeadlineDto) {
    if (!editForm || !editor) return;
    const allowed = new Set(item.editable_fields);
    const values: DeadlineValues = {};
    const keys = editor.mode === "assign" ? ["assignee_account_id"] : ["title", "kind", "due_date", "remind_on", "assignee_account_id", "escalation_account_id", "todo_text", "send_email", "send_ics"];
    for (const key of keys) {
      if (!allowed.has(key)) continue;
      const value = editForm[key as keyof DeadlineForm];
      (values as Record<string, unknown>)[key] = typeof value === "string" ? (value || null) : value;
    }
    const ok = await act(() => updateDeadline(orgSlug, item.id, values), editor.mode === "assign" ? "Zuständigkeit geändert." : "Termin geändert.");
    if (ok) { setEditor(null); setEditForm(null); }
  }

  async function cancelDeadline(item: DeadlineDto) {
    const ok = await act(() => deadlineAction(orgSlug, item.id, "cancel"), "Termin abgebrochen.");
    if (ok) setEditor(null);
  }

  function calendar(row: { date: string; title: string; key: string }, description?: string | null) {
    downloadIcs(`termin-${row.date}`, buildIcs({ uid: row.key.replace(/[^a-zA-Z0-9-]/g, "-"), date: row.date, title: row.title, description }));
    toast("Kalenderdatei heruntergeladen.", "success");
  }

  async function resolveEnd(run: () => Promise<void>, success: string) {
    setBusy(true);
    setError(null);
    try {
      await run();
      setComparing(false);
      toast(success, "success");
    } catch (err) {
      setError(errorText(err, "Die Prüfung konnte nicht gespeichert werden."));
    } finally {
      setBusy(false);
    }
  }

  function deadlineEditor(item: DeadlineDto) {
    if (!editor || editor.id !== item.id) return null;
    if (editor.mode === "remind" && remindDraft) {
      const custom = remindersOverridden(item);
      return <form className="rg-transition tl-editor tl-reminder-form" aria-label={`Erinnerung für „${deadlineTitle(item)}“ anpassen`} onSubmit={(event) => { event.preventDefault(); void saveReminders(item); }}>
        <fieldset>
          <legend>Erinnern</legend>
          <LeadsEditor leads={remindDraft.leads} onChange={(next) => setRemindDraft((current) => current && ({ ...current, leads: next }))} />
        </fieldset>
        <label>Erinnerung an<select value={remindDraft.assignee} onChange={(event) => setRemindDraft((current) => current && ({ ...current, assignee: event.target.value }))}>
          <option value="">{item.source === "system" ? "Wie im Vertrag eingestellt" : "Niemand"}</option>
          {assignees.map((entry) => <option key={entry.id} value={entry.id}>{entry.display_name}</option>)}
        </select></label>
        <p className="field-hint">Gilt nur für diesen Termin. Alle anderen folgen den Erinnerungen des Vertrags.</p>
        <div className="rg-actions">
          {custom ? <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void saveReminders(item, true)}>Zurück zum Standard</button> : null}
          <button type="button" className="btn" onClick={() => { setEditor(null); setRemindDraft(null); }}>Abbrechen</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button>
        </div>
      </form>;
    }
    if (editor.mode === "cancel") return <div className="tl-confirm" role="group" aria-label={`„${deadlineTitle(item)}“ abbrechen`}>
      <span>Termin „{deadlineTitle(item)}“ abbrechen? Er erscheint danach unter „Erledigte und abgebrochene“.</span>
      <button type="button" className="btn btn-sm btn-danger" disabled={busy} onClick={() => void cancelDeadline(item)}>Ja, abbrechen</button>
      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditor(null)}>Nein</button>
    </div>;
    if (!editForm) return null;
    const allowed = new Set(item.editable_fields);
    const set = (patch: Partial<DeadlineForm>) => setEditForm((current) => current && ({ ...current, ...patch }));
    const assigneeSelect = <label>Zuständig<select value={editForm.assignee_account_id} onChange={(event) => set({ assignee_account_id: event.target.value })}><option value="">Niemand</option>{assignees.map((entry) => <option key={entry.id} value={entry.id}>{entry.display_name}</option>)}</select></label>;
    return <form className="rg-transition tl-editor" aria-label={editor.mode === "assign" ? `„${deadlineTitle(item)}“ zuweisen` : `„${deadlineTitle(item)}“ bearbeiten`} onSubmit={(event) => { event.preventDefault(); void saveEdit(item); }}>
      {editor.mode === "assign" ? <div className="rg-form-grid">{assigneeSelect}</div> : <div className="rg-form-grid">
        {allowed.has("title") ? <label>Bezeichnung *<input required maxLength={255} list="tl-title-suggestions" value={editForm.title} onChange={(event) => set({ title: event.target.value })} /></label> : null}
        {allowed.has("kind") ? <label>Art<select value={editForm.kind} onChange={(event) => set({ kind: event.target.value })}>{kinds.length === 0 ? <option value={editForm.kind}>{editForm.kind === "pruefung" ? "Prüfung" : editForm.kind}</option> : kinds.map((entry) => <option key={entry.id} value={entry.code}>{entry.label}</option>)}</select></label> : null}
        {allowed.has("due_date") ? <label>Fällig am *<input type="date" required value={editForm.due_date} onChange={(event) => set({ due_date: event.target.value })} /></label> : null}
        {allowed.has("remind_on") ? <label>Erinnern am<input type="date" value={editForm.remind_on} max={editForm.due_date || undefined} onChange={(event) => set({ remind_on: event.target.value })} /></label> : null}
        {allowed.has("assignee_account_id") ? assigneeSelect : null}
        {allowed.has("escalation_account_id") ? <label>Eskalation an<select value={editForm.escalation_account_id} onChange={(event) => set({ escalation_account_id: event.target.value })}><option value="">Niemand</option>{assignees.map((entry) => <option key={entry.id} value={entry.id}>{entry.display_name}</option>)}</select></label> : null}
        {allowed.has("todo_text") ? <label className="span-full">Was zu tun ist<input maxLength={500} value={editForm.todo_text} onChange={(event) => set({ todo_text: event.target.value })} /></label> : null}
        {allowed.has("send_email") ? <label className="rg-check"><input type="checkbox" checked={editForm.send_email} onChange={(event) => set({ send_email: event.target.checked })} />Erinnerungs-E-Mail</label> : null}
        {allowed.has("send_ics") ? <label className="rg-check"><input type="checkbox" checked={editForm.send_ics} onChange={(event) => set({ send_ics: event.target.checked })} />Kalendereinladung (ICS) mit der Erinnerung</label> : null}
        {item.source === "system" ? <p className="cw-muted span-full">Datum und Zuständigkeit kommen aus den Vertragsdaten (Laufzeit, Erinnerungen). Leer lassen = Standardtext.</p> : null}
      </div>}
      <div className="rg-actions"><button type="button" className="btn" onClick={() => { setEditor(null); setEditForm(null); }}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button></div>
    </form>;
  }

  const open: Row[] = [];
  const closed: Row[] = [];

  if (endCheck) {
    const where = endCheck.documented ? `Im Dokument steht ${formatDate(endCheck.documented)}` : "Im Dokument wurde kein Enddatum gefunden";
    open.push({
      key: "end-check", date: null, kind: "KI-Prüfung", person: null, personId: null,
      title: "Abweichung beim Vertragsende prüfen",
      meta: [<span key="why" className="tl-meta-text">{`${where}; in den Vertragsdaten steht ${formatDate(endCheck.maintained)}.`}</span>],
      primary: <button type="button" className="btn btn-sm btn-ghost" aria-expanded={comparing} aria-controls="tl-compare" onClick={() => setComparing((value) => !value)}>Prüfen</button>,
      expand: comparing ? <div className="tl-compare" id="tl-compare">
        <dl className="tl-compare-cols">
          <div className="tl-cmp"><dt>Im Dokument{endCheck.onShowSource ? <button type="button" className="cw-source-button" onClick={endCheck.onShowSource}>Quelle</button> : null}</dt><dd className={endCheck.documented ? "num" : "tl-none"}>{endCheck.documented ? formatDate(endCheck.documented) : "–"}</dd>{endCheck.documented ? null : <small>Kein Enddatum im Dokument gefunden</small>}</div>
          <div className="tl-cmp"><dt>In den Vertragsdaten</dt><dd className="num">{formatDate(endCheck.maintained)}</dd><small>{endCheck.fixedTerm ? "Festes Vertragsende" : "Berechnet aus der Laufzeit"}</small></div>
        </dl>
        {editable ? <div className="rg-actions">
          {endCheck.documented && endCheck.fixedTerm ? <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void resolveEnd(endCheck.onAdopt, "Vertragsende aus dem Dokument übernommen.")}>Übernehmen</button> : null}
          <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={() => void resolveEnd(endCheck.onKeep, "Vertragsende beibehalten.")}>Beibehalten</button>
        </div> : <p className="cw-muted">Nur Lesen – geprüft wird über das Vertragsmanagement.</p>}
      </div> : null,
    });
  }

  for (const item of workItems) {
    const target = workItemTarget(item.item_type, item.requires_review) ?? (item.requires_review ? REVIEW_TARGET : null);
    const kind: TerminKind = item.requires_review ? "KI-Prüfung" : "Aufgabe";
    const row: Row = {
      key: `work:${item.work_item_id}`, date: item.target_date, kind, title: item.title_de, person: null, personId: null,
      meta: item.why_de ? [<span key="why" className="tl-meta-text" title={item.why_de}>{item.why_de}</span>] : [],
      duplicateKey: kind === "Aufgabe" ? normalizeTitle(item.title_de) : undefined,
    };
    if (item.status === "resolved") { closed.push({ ...row, closed: "done", duplicateKey: undefined }); continue; }
    if (target && target.tab !== "deadlines") row.primary = <button type="button" className="btn btn-sm btn-ghost" onClick={() => onOpenTarget(target)}>{item.requires_review ? "Prüfen" : "Öffnen"}</button>;
    open.push(row);
  }

  for (const item of items ?? []) {
    const kind = deadlineKind(item);
    const title = deadlineTitle(item);
    // Vom Fristenabgleich ersetzte Systemtermine (Grundlage geändert) sind keine Handlung des Nutzers: nicht als „Abgebrochen“ zeigen.
    if (item.status === "cancelled" && item.source === "system" && item.note?.startsWith("Automatisch entfernt")) continue;
    if (item.status !== "open") {
      const by = item.done_by_name ? ` von ${item.done_by_name}` : "";
      const when = item.done_at ? ` am ${formatDate(item.done_at.slice(0, 10))}` : "";
      closed.push({
        key: `deadline:${item.id}`, date: item.done_at?.slice(0, 10) ?? item.due_date, kind, title,
        meta: [<span key="by" className="tl-meta-text">{`${item.status === "cancelled" ? "abgebrochen" : "erledigt"}${when}${by}`}</span>],
        person: item.done_by_name ?? item.assignee_name, personId: item.assignee_account_id,
        closed: item.status === "cancelled" ? "cancelled" : "done",
        primary: editable ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => void act(() => deadlineAction(orgSlug, item.id, "reopen"), "Termin wieder geöffnet.")}>{BUTTON_ICONS.reopen}Wieder öffnen</button> : null,
      });
      continue;
    }
    const meta: ReactNode[] = [];
    if (item.system_key === "contract_end") meta.push(<span key="what" className="tl-meta-text">Feste Laufzeit, endet ohne Kündigung</span>);
    else if (item.system_key === "cancel_by") meta.push(<span key="what" className="tl-meta-text">Kündbar bis – spätester Eingang der Kündigung beim Vertragspartner</span>);
    if (item.todo_text && kind !== "Frist") meta.push(<span key="todo" className="tl-meta-chip tl-meta-text" title={item.todo_text}>{META_ICONS.todo}{item.todo_text}</span>);
    // Eskalation steht einmal in den Erinnerungseinstellungen; hier nur, wenn sie ausgelöst wurde.
    if (item.escalated_at) meta.push(<span key="esc" className="tl-meta-chip">{META_ICONS.escalate}Eskaliert{item.escalation_name ? ` an ${item.escalation_name}` : ""} am {formatDate(item.escalated_at.slice(0, 10))}</span>);
    if (remindersOverridden(item)) meta.push(<span key="custom" className="rg-origin rg-origin-manual" title="Erinnerung für diesen Termin angepasst">Angepasst</span>);
    if (item.basis_unconfirmed) meta.push(<button key="ai" type="button" className="signal-link" onClick={() => onOpenTarget(REVIEW_TARGET)}><Signal tone="ai" size="sm">Basiert auf ungeprüften KI-Werten</Signal></button>);

    const termTarget: FixTarget | null = item.system_key === "cancel_by" || item.system_key === "contract_end" ? { tab: "register", section: "term" } : null;
    const done = () => void act(() => deadlineAction(orgSlug, item.id, "done"), "Termin erledigt.");
    const assign = () => openEditor(item, "assign");
    const description = item.todo_text;
    // Erinnerungen gehören zum Termin: erste und weitere Erinnerungstage vor der Fälligkeit, an die zuständige Person.
    const reminders = [...new Set([item.remind_on, ...(item.extra_remind_on ?? [])])]
      .filter((value) => value && value < item.due_date)
      .sort()
      .map((value) => ({ date: value, to: item.assignee_name }));
    const menu: ActionMenuItem[] = editable ? [
      { label: "Bearbeiten", icon: MENU_ICONS.edit, onSelect: () => openEditor(item, "edit") },
      { label: "Zuweisen …", icon: MENU_ICONS.assign, onSelect: assign },
      ...(item.editable_fields.includes("reminder_leads") ? [{ label: "Erinnerung anpassen", icon: MENU_ICONS.bell, onSelect: () => openEditor(item, "remind") }] : []),
      { label: "In Kalender eintragen", icon: MENU_ICONS.calendar, onSelect: () => calendar({ date: item.due_date, title, key: item.id }, description) },
      ...(termTarget ? [{ label: "Erledigt", icon: MENU_ICONS.done, onSelect: done }] : []),
      ...(item.source === "manual" ? ["separator" as const, { label: "Abbrechen", icon: MENU_ICONS.cancel, danger: true, onSelect: () => setEditor({ id: item.id, mode: "cancel" }) }] : []),
    ] : [{ label: "In Kalender eintragen", icon: MENU_ICONS.calendar, onSelect: () => calendar({ date: item.due_date, title, key: item.id }, description) }];
    open.push({
      key: `deadline:${item.id}`, date: item.due_date, kind, title, meta,
      person: item.assignee_name, personId: item.assignee_account_id,
      primary: termTarget
        ? <button type="button" className="btn btn-sm btn-ghost" onClick={() => onOpenTarget(termTarget)}>Öffnen</button>
        : editable ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={done}>{BUTTON_ICONS.done}Erledigt</button> : null,
      menu,
      expand: deadlineEditor(item),
      duplicateKey: kind === "Aufgabe" ? normalizeTitle(title) : undefined,
      reminders,
    });
  }

  // Doppelt angelegte offene Aufgaben (gleicher Titel): ab der zweiten ein Hinweis, nichts wird gelöscht.
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const row of [...open].sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""))) {
    if (!row.duplicateKey) continue;
    if (seen.has(row.duplicateKey)) duplicates.add(row.key);
    seen.add(row.duplicateKey);
  }

  const counts: Record<Filter, number> = { all: open.length, aufgaben: 0, erinnerungen: 0, fristen: 0 };
  // „Erinnerungen“: eigene Erinnerungen und Termine, die erinnern.
  const inFilter = (row: Row, key: Filter) => key === "all" || KINDS[row.kind].filter === key || (key === "erinnerungen" && Boolean(row.reminders?.length));
  for (const key of ["aufgaben", "erinnerungen", "fristen"] as const) counts[key] = open.filter((row) => inFilter(row, key)).length;
  const matches = (row: Row) => inFilter(row, filter) && (!mine || (row.personId != null && row.personId === account?.id));
  const visible = open.filter(matches);
  const closedVisible = closed.filter(matches);
  const filtered = filter !== "all" || mine;

  // Ohne Datum („offen“) zuerst, dann chronologisch; „Heute“ trennt Vergangenes von Kommendem.
  const undated = visible.filter((row) => !row.date);
  const dated = visible.filter((row) => row.date).sort((a, b) => a.date!.localeCompare(b.date!) || KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
  const past = dated.filter((row) => row.date! < today);
  const upcoming = dated.filter((row) => row.date! >= today);
  closed.sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
  const allUpcoming = open.filter((row) => row.date && row.date >= today).sort((a, b) => a.date!.localeCompare(b.date!));
  const overdueCount = open.filter((row) => row.date && row.date < today).length;
  const nothing = items !== null && open.length === 0 && closed.length === 0;

  function dotClass(row: Row) {
    if (row.closed) return "tl-dot tl-dot--closed";
    if (row.date && row.date < today) return "tl-dot tl-dot--overdue";
    if (row.date === today) return "tl-dot tl-dot--today";
    return `tl-dot tl-dot--t-${KINDS[row.kind].slug}`;
  }

  const renderRow = (row: Row) => {
    const overdue = !row.closed && row.date != null && row.date < today;
    const relative = row.closed || !row.date ? null : formatRelativeDate(row.date, today);
    const meta = [...row.meta];
    if (duplicates.has(row.key)) meta.push(<span key="dup" className="tl-dup"><SignalIcon tone="warning" />Doppelt angelegt – eine Aufgabe genügt</span>);
    return <li key={row.key} className={`tl-row${row.closed ? " tl-row--closed" : ""}`}>
      <span className={dotClass(row)} aria-hidden="true" />
      <span className="tl-when">
        <span className="tl-date">{row.date ? formatDate(row.date) : "offen"}</span>
        {relative ? <small className={overdue ? "tl-rel tl-rel--overdue" : "tl-rel"}>{overdue ? `überfällig · ${relative}` : relative}</small> : null}
      </span>
      <span className="tl-kind">{row.closed
        ? <Signal tone={row.closed === "done" ? "done" : "neutral"} size="sm" icon={row.closed === "cancelled" ? BUTTON_ICONS.cancelled : undefined}>{row.closed === "done" ? "Erledigt" : "Abgebrochen"}</Signal>
        : <KindChip kind={row.kind} />}</span>
      <span className="tl-what">
        <span className="tl-title" title={row.title}>{row.title}</span>
        {meta.length || row.person ? <span className="tl-meta">{meta}{row.person ? <span className="tl-meta-chip tl-meta-person">{row.person}</span> : null}</span> : null}
        {row.reminders?.length && !row.closed ? <span className="tl-subreminders">{row.reminders.map((reminder) => <span key={reminder.date} className={reminder.date < today ? "tl-meta-chip tl-subreminder tl-subreminder--sent" : "tl-meta-chip tl-subreminder"}>
          {META_ICONS.bell}{reminder.date < today ? "Erinnert am" : "Erinnerung am"} {formatDate(reminder.date)}{reminder.to ? ` an ${reminder.to}` : ""}
        </span>)}</span> : null}
      </span>
      <span className="tl-who"><Person name={row.person} /></span>
      <span className="tl-act">{row.primary}{row.menu && row.menu.length ? <ActionMenu items={row.menu} label={`Weitere Aktionen: ${row.title}`} disabled={busy} /> : null}</span>
      {row.expand}
    </li>;
  };

  // Jahresüberschrift bei jedem Jahreswechsel; nach „Heute“ beginnt die Zählung neu.
  function withYears(rows: Row[]) {
    const out: ReactNode[] = [];
    let year: string | null = null;
    for (const row of rows) {
      const next = row.date!.slice(0, 4);
      if (next !== year) {
        out.push(<li key={`year:${next}:${row.key}`} className="tl-year" aria-hidden="true">{next}</li>);
        year = next;
      }
      out.push(renderRow(row));
    }
    return out;
  }

  const filterChip = (key: Filter, label: string) => <button type="button" className="tl-filter" aria-pressed={filter === key} onClick={() => setFilter(key)}>
    {key !== "all" ? <span className={`tl-swatch tl-swatch--${key}`} aria-hidden="true" /> : null}{label} <span className="tl-filter-count">{counts[key]}</span>
  </button>;

  return <CollapsibleSection
    id="tl"
    title="Termine & Aufgaben"
    description="Was ansteht, wer zuständig ist und wann erinnert wird"
    summary={items === null ? null : nothing ? "Keine Termine" : <span>{`${open.length} offen`}{allUpcoming[0]?.date ? <> · nächster: <b>{formatDate(allUpcoming[0].date)}</b> {allUpcoming[0].title}</> : null}{overdueCount ? ` · ${overdueCount} überfällig` : ""}</span>}
    icon={CARD_ICON}
    iconClassName="section-tile--type"
    actions={editable && !form ? <button type="button" className="btn btn-sm" onClick={() => setForm(EMPTY_FORM)}>{BUTTON_ICONS.add}Termin hinzufügen</button> : null}
  >
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {editable && !form ? <datalist id="tl-title-suggestions">{TITLE_SUGGESTIONS.map((value) => <option key={value} value={value} />)}</datalist> : null}
    {form ? <form className="rg-transition" aria-label="Neuer Termin" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <div className="rg-form-grid">
        <label>Bezeichnung *<input required maxLength={255} list="tl-title-suggestions" placeholder="z. B. Kündigung prüfen" value={form.title} onChange={(event) => setForm((current) => current && ({ ...current, title: event.target.value }))} /></label>
        <datalist id="tl-title-suggestions">{TITLE_SUGGESTIONS.map((value) => <option key={value} value={value} />)}</datalist>
        <label>Art<select value={form.kind} onChange={(event) => setForm((current) => current && ({ ...current, kind: event.target.value }))}>{kinds.length === 0 ? <option value="pruefung">Prüfung</option> : kinds.map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}</select></label>
        <label>Fällig am *<input type="date" required value={form.due_date} onChange={(event) => setForm((current) => current && ({ ...current, due_date: event.target.value }))} /></label>
        <label>Erinnern am<input type="date" value={form.remind_on} max={form.due_date || undefined} onChange={(event) => setForm((current) => current && ({ ...current, remind_on: event.target.value }))} /></label>
        <label>Zuständig<select value={form.assignee_account_id} onChange={(event) => setForm((current) => current && ({ ...current, assignee_account_id: event.target.value }))}><option value="">Ich selbst</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label>Eskalation an<select value={form.escalation_account_id} onChange={(event) => setForm((current) => current && ({ ...current, escalation_account_id: event.target.value }))}><option value="">Niemand</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label className="span-full">Was zu tun ist<input maxLength={500} value={form.todo_text} onChange={(event) => setForm((current) => current && ({ ...current, todo_text: event.target.value }))} /></label>
        <label className="rg-check"><input type="checkbox" checked={form.send_email} onChange={(event) => setForm((current) => current && ({ ...current, send_email: event.target.checked }))} />Erinnerungs-E-Mail</label>
        <label className="rg-check"><input type="checkbox" checked={form.send_ics} onChange={(event) => setForm((current) => current && ({ ...current, send_ics: event.target.checked }))} />Kalendereinladung (ICS)</label>
      </div>
      <div className="rg-actions"><button type="button" className="btn" onClick={() => setForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Termin anlegen</button></div>
    </form> : null}

    {register ? <ContractReminderSettings key={targetField ?? "settings"} register={register} contractId={contractId} orgSlug={orgSlug} editable={editable} openInitially={settingsTarget && editable}
      onSaved={(next) => { setRegister(next); void load(); }} /> : null}
    {items === null ? <p role="status" aria-busy="true">Termine werden geladen…</p> : nothing
      ? <EmptyState variant="calm" action={<button type="button" className="rg-link" onClick={() => onOpenTarget({ tab: "register", section: "term" })}>Vertragsdaten öffnen</button>}>Keine Termine. Sie entstehen automatisch aus den Vertragsdaten.</EmptyState>
      : <>
        {open.length > 0 ? <div className="tl-filters" role="group" aria-label="Termine filtern">
          <span className="tl-filters-label">Anzeigen:</span>
          {filterChip("all", "Alle")}
          {filterChip("aufgaben", "Aufgaben")}
          {filterChip("erinnerungen", "Erinnerungen")}
          {filterChip("fristen", "Fristen")}
          <span className="tl-filters-gap" />
          <button type="button" className="tl-filter" aria-pressed={mine} onClick={() => setMine((value) => !value)}>{icon(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>, "tl-filter-icon")}Nur meine</button>
        </div> : null}
        {filtered && visible.length === 0
          ? <p className="tl-filter-empty" role="status">Keine Einträge für diesen Filter. <button type="button" className="rg-link" onClick={() => { setFilter("all"); setMine(false); }}>Filter zurücksetzen</button></p>
          : <ol className="tl" aria-label="Termine und Aufgaben">
            {undated.map(renderRow)}
            {withYears(past)}
            <li className="tl-row tl-row--today" aria-label={`Heute, ${formatDate(today)}`}>
              <span className="tl-dot tl-dot--today" aria-hidden="true" />
              <span className="tl-today"><span className="tl-today-chip">Heute · {formatDate(today)}</span></span>
            </li>
            {withYears(upcoming)}
          </ol>}
        {closedVisible.length > 0 ? <details className="tl-done"><summary>{icon(<path d="m9 6 6 6-6 6" />, "tl-done-chevron")}Erledigte und abgebrochene ({closedVisible.length})</summary>
          <ol className="tl tl--closed" aria-label="Erledigte und abgebrochene">{closedVisible.map((row) => <Fragment key={row.key}>{renderRow(row)}</Fragment>)}</ol>
        </details> : null}
        <div className="tl-legend" aria-label="Kennfarben der Typen">
          <span>Typen:</span>
          {KIND_ORDER.map((kind) => <KindChip key={kind} kind={kind} />)}
          <span className="tl-legend-note">Farbe = Typ · Status (überfällig, heute, erledigt) nur am Punkt</span>
        </div>
      </>}
  </CollapsibleSection>;
}
