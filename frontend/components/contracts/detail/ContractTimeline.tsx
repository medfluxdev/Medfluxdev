"use client";

import { Fragment, useCallback, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import ActionMenu, { type ActionMenuItem } from "@/components/ui/ActionMenu";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import EmptyState from "@/components/ui/EmptyState";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import type { DetailWorkItem } from "@/lib/contract-detail-types";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { createContractDeadline, deadlineAction, listContractDeadlines, updateDeadline, type DeadlineDto, type DeadlineValues } from "@/lib/domain-api/deadlines";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import { getContractRegister } from "@/lib/domain-api/register";
import { REVIEW_TARGET, workItemTarget, type FixTarget } from "@/lib/fix-targets";
import { formatDate } from "@/lib/format";
import { buildIcs, downloadIcs } from "@/lib/ics";
import { formatLeadTime, formatRelativeDate } from "@/lib/relative-date";

export type TerminKind = "Aufgabe" | "Erinnerung" | "Frist" | "Wartung" | "Löschprüfung" | "KI-Prüfung";
type Filter = "all" | "aufgaben" | "erinnerungen" | "fristen";

const icon = (path: ReactNode, className = "signal-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{path}</svg>;

// Kennfarbe je Typ (Identität, nicht Status) – immer mit Symbol und Wort.
const KINDS: Record<TerminKind, { slug: string; icon: ReactNode; filter: Exclude<Filter, "all"> }> = {
  Aufgabe: { slug: "aufgabe", filter: "aufgaben", icon: icon(<><rect x="4" y="4" width="16" height="16" rx="2" /><path d="m8 12 3 3 5-6" /></>) },
  Erinnerung: { slug: "erinnerung", filter: "erinnerungen", icon: icon(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></>) },
  Frist: { slug: "frist", filter: "fristen", icon: icon(<><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>) },
  Wartung: { slug: "wartung", filter: "fristen", icon: icon(<><path d="M14.7 6.3a4 4 0 0 0 5 5L13 18a2.1 2.1 0 0 1-3-3l6.7-6.7a4 4 0 0 0-2-2z" /><path d="m3 21 6-6" /></>) },
  Löschprüfung: { slug: "loeschung", filter: "fristen", icon: icon(<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />) },
  "KI-Prüfung": { slug: "ki", filter: "aufgaben", icon: icon(<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />) },
};
const KIND_ORDER = Object.keys(KINDS) as TerminKind[];

const META_ICONS = {
  calendar: icon(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>, "tl-meta-icon"),
  escalate: icon(<path d="M12 19V5M5 12l7-7 7 7" />, "tl-meta-icon"),
  todo: icon(<><rect x="4" y="4" width="16" height="16" rx="2" /><path d="m8 12 3 3 5-6" /></>, "tl-meta-icon"),
  info: icon(<><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.5" /></>, "tl-meta-icon"),
};
const MENU_ICONS = {
  edit: icon(<><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></>, "action-menu-icon"),
  assign: icon(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>, "action-menu-icon"),
  calendar: icon(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>, "action-menu-icon"),
  done: icon(<path d="M20 6 9 17l-5-5" />, "action-menu-icon"),
  cancel: icon(<path d="M6 6l12 12M18 6 6 18" />, "action-menu-icon"),
};

/** Typ-Chip: Symbol + Wort + Kennfarbe. */
export function KindChip({ kind }: { kind: TerminKind }) {
  return <span className={`signal signal--sm tl-kind-chip tl-kind-chip--${KINDS[kind].slug}`}>{KINDS[kind].icon}<span className="signal-label">{kind}</span></span>;
}

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
  /** Zweite Zeile unter dem Datum statt der Zeit ab heute (Erinnerungen: Vorlauf). */
  lead?: string;
  primary?: ReactNode;
  menu?: ActionMenuItem[];
  expand?: ReactNode;
  closed?: "done" | "cancelled";
  /** Für die Erkennung doppelt angelegter Aufgaben. */
  duplicateKey?: string;
}

type Editor = { id: string; mode: "edit" | "assign" | "cancel" };

const EMPTY_FORM = { title: "", kind: "pruefung", due_date: "", remind_on: "", assignee_account_id: "", escalation_account_id: "", todo_text: "", send_email: true, send_ics: false };
type DeadlineForm = typeof EMPTY_FORM;

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function deadlineKind(item: DeadlineDto): TerminKind {
  if (item.source === "manual") return "Aufgabe";
  if (item.system_key === "maintenance_due") return "Wartung";
  if (item.system_key === "retention_review") return "Löschprüfung";
  if (item.system_key === "set_ended") return "Aufgabe";
  return "Frist";
}

// Ein Name je Tatsache: Kündigungstermin = „Kündbar bis“, Ende = „Vertragsende“.
function deadlineTitle(item: DeadlineDto) {
  if (item.system_key === "cancel_by") return "Kündbar bis";
  if (item.system_key === "contract_end") return "Vertragsende";
  return item.title;
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

function Person({ name }: { name: string | null }) {
  if (!name) return <span className="tl-none" aria-label="Niemand zugewiesen">–</span>;
  return <span className="tl-person"><span className="tl-avatar" aria-hidden="true">{initials(name)}</span><span className="tl-person-name">{name}</span></span>;
}

const normalizeTitle = (value: string) => value.trim().toLocaleLowerCase("de-DE");

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
  const [reminderDates, setReminderDates] = useState<string[]>([]);
  const [reminderTodo, setReminderTodo] = useState<string | null>(null);
  const [today, setToday] = useState(localToday);
  const [kinds, setKinds] = useState<LookupDto[]>([]);
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [form, setForm] = useState<DeadlineForm | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [editForm, setEditForm] = useState<DeadlineForm | null>(null);
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
      setReminderDates(register.value.terms?.reminder_dates ?? []);
      const todo = register.value.fields?.reminder_todo?.value;
      setReminderTodo(typeof todo === "string" && todo.trim() ? todo.trim() : null);
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
        {allowed.has("title") ? <label>Bezeichnung *<input required maxLength={255} value={editForm.title} onChange={(event) => set({ title: event.target.value })} /></label> : null}
        {allowed.has("kind") ? <label>Art<select value={editForm.kind} onChange={(event) => set({ kind: event.target.value })}>{kinds.length === 0 ? <option value={editForm.kind}>{editForm.kind === "pruefung" ? "Prüfung" : editForm.kind}</option> : kinds.map((entry) => <option key={entry.id} value={entry.code}>{entry.label}</option>)}</select></label> : null}
        {allowed.has("due_date") ? <label>Fällig am *<input type="date" required value={editForm.due_date} onChange={(event) => set({ due_date: event.target.value })} /></label> : null}
        {allowed.has("remind_on") ? <label>Erinnern am<input type="date" value={editForm.remind_on} max={editForm.due_date || undefined} onChange={(event) => set({ remind_on: event.target.value })} /></label> : null}
        {allowed.has("assignee_account_id") ? assigneeSelect : null}
        {allowed.has("escalation_account_id") ? <label>Eskalation an<select value={editForm.escalation_account_id} onChange={(event) => set({ escalation_account_id: event.target.value })}><option value="">Niemand</option>{assignees.map((entry) => <option key={entry.id} value={entry.id}>{entry.display_name}</option>)}</select></label> : null}
        {allowed.has("todo_text") ? <label className="span-full">ToDo<input maxLength={500} value={editForm.todo_text} onChange={(event) => set({ todo_text: event.target.value })} /></label> : null}
        {allowed.has("send_email") ? <label className="rg-check"><input type="checkbox" checked={editForm.send_email} onChange={(event) => set({ send_email: event.target.checked })} />Erinnerungs-E-Mail</label> : null}
        {allowed.has("send_ics") ? <label className="rg-check"><input type="checkbox" checked={editForm.send_ics} onChange={(event) => set({ send_ics: event.target.checked })} />Kalendereinladung (ICS) mit der Erinnerung</label> : null}
        {item.source === "system" ? <p className="cw-muted span-full">Datum, Zuständigkeit und ToDo kommen aus den Vertragsdaten (Laufzeit, Erinnerung &amp; Verantwortung).</p> : null}
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

  // Erinnerungen der Laufzeitfrist hängen an „Kündbar bis“ bzw. dem Vertragsende.
  const anchor = (items ?? []).find((item) => item.status === "open" && item.system_key === "cancel_by")
    ?? (items ?? []).find((item) => item.status === "open" && item.system_key === "contract_end");
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
        primary: editable ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => void act(() => deadlineAction(orgSlug, item.id, "reopen"), "Termin wieder geöffnet.")}>Wieder öffnen</button> : null,
      });
      continue;
    }
    const meta: ReactNode[] = [];
    if (item.system_key === "contract_end") meta.push(<span key="what" className="tl-meta-text">Feste Laufzeit, endet ohne Kündigung</span>);
    else if (item.system_key === "cancel_by") meta.push(<span key="what" className="tl-meta-text">Spätester Eingang der Kündigung beim Vertragspartner</span>);
    if (item.todo_text && kind !== "Frist") meta.push(<span key="todo" className="tl-meta-chip tl-meta-text" title={item.todo_text}>{META_ICONS.todo}{item.todo_text}</span>);
    if (item.escalation_name) meta.push(<span key="esc" className="tl-meta-chip">{META_ICONS.escalate}Eskalation an {item.escalation_name}</span>);
    if (item.basis_unconfirmed) meta.push(<button key="ai" type="button" className="signal-link" onClick={() => onOpenTarget(REVIEW_TARGET)}><Signal tone="ai" size="sm">Basiert auf ungeprüften KI-Werten</Signal></button>);

    const termTarget: FixTarget | null = item.system_key === "cancel_by" || item.system_key === "contract_end" ? { tab: "register", section: "term" } : null;
    const done = () => void act(() => deadlineAction(orgSlug, item.id, "done"), "Termin erledigt.");
    const assign = item.source === "manual"
      ? () => openEditor(item, "assign")
      : () => onOpenTarget({ tab: "deadlines", field: "reminder_recipient_account_id" });
    const description = [item.todo_text, item.escalation_name ? `Eskalation an ${item.escalation_name}` : null].filter(Boolean).join("\n");
    const menu: ActionMenuItem[] = editable ? [
      { label: "Bearbeiten", icon: MENU_ICONS.edit, onSelect: () => openEditor(item, "edit") },
      { label: "Zuweisen …", icon: MENU_ICONS.assign, onSelect: assign },
      { label: "In Kalender eintragen", icon: MENU_ICONS.calendar, onSelect: () => calendar({ date: item.due_date, title, key: item.id }, description) },
      ...(termTarget ? [{ label: "Erledigt", icon: MENU_ICONS.done, onSelect: done }] : []),
      ...(item.source === "manual" ? ["separator" as const, { label: "Abbrechen", icon: MENU_ICONS.cancel, danger: true, onSelect: () => setEditor({ id: item.id, mode: "cancel" }) }] : []),
    ] : [{ label: "In Kalender eintragen", icon: MENU_ICONS.calendar, onSelect: () => calendar({ date: item.due_date, title, key: item.id }, description) }];
    open.push({
      key: `deadline:${item.id}`, date: item.due_date, kind, title, meta,
      person: item.assignee_name, personId: item.assignee_account_id,
      primary: termTarget
        ? <button type="button" className="btn btn-sm btn-ghost" onClick={() => onOpenTarget(termTarget)}>Öffnen</button>
        : editable ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={done}>Erledigt</button> : null,
      menu,
      expand: deadlineEditor(item),
      duplicateKey: kind === "Aufgabe" ? normalizeTitle(title) : undefined,
    });

    // Erinnerungen: Titel = was zu tun ist (ToDo aus „Erinnerung & Verantwortung“), der Termin steht in der zweiten Zeile.
    const reminders = new Set<string>();
    const isAnchor = anchor !== undefined && item.id === anchor.id;
    if (item.remind_on && item.remind_on < item.due_date) reminders.add(item.remind_on);
    if (isAnchor) for (const value of reminderDates) if (value < item.due_date) reminders.add(value);
    for (const value of reminders) {
      if (value < today) continue;
      const todo = isAnchor ? reminderTodo : item.source === "manual" ? item.todo_text : null;
      const reminderTitle = todo || `Erinnerung: ${title}`;
      const reminderMeta: ReactNode[] = [<span key="anchor" className="tl-meta-chip">{META_ICONS.calendar}{title} {formatDate(item.due_date)}</span>];
      if (item.escalation_name) reminderMeta.push(<span key="esc" className="tl-meta-chip">{META_ICONS.escalate}Eskalation an {item.escalation_name}</span>);
      open.push({
        key: `reminder:${item.id}:${value}`, date: value, kind: "Erinnerung", title: reminderTitle, meta: reminderMeta,
        person: item.assignee_name, personId: item.assignee_account_id,
        lead: formatLeadTime(value, item.due_date, title),
        menu: editable ? [
          { label: "Bearbeiten", icon: MENU_ICONS.edit, onSelect: () => openEditor(item, "edit") },
          { label: "Zuweisen …", icon: MENU_ICONS.assign, onSelect: assign },
          { label: "In Kalender eintragen", icon: MENU_ICONS.calendar, onSelect: () => calendar({ date: value, title: reminderTitle, key: `${item.id}-${value}` }, `${title} am ${formatDate(item.due_date)}`) },
        ] : [{ label: "In Kalender eintragen", icon: MENU_ICONS.calendar, onSelect: () => calendar({ date: value, title: reminderTitle, key: `${item.id}-${value}` }, `${title} am ${formatDate(item.due_date)}`) }],
      });
    }
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
  for (const row of open) counts[KINDS[row.kind].filter] += 1;
  const visible = open.filter((row) => (filter === "all" || KINDS[row.kind].filter === filter) && (!mine || (row.personId != null && row.personId === account?.id)));
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
    const relative = row.closed || !row.date ? null : row.lead ?? formatRelativeDate(row.date, today);
    const meta = [...row.meta];
    if (duplicates.has(row.key)) meta.push(<span key="dup" className="tl-dup"><Signal tone="warning" size="sm">Doppelt angelegt – eine Aufgabe genügt</Signal></span>);
    return <li key={row.key} className={`tl-row${row.closed ? " tl-row--closed" : ""}`}>
      <span className={dotClass(row)} aria-hidden="true" />
      <span className="tl-when">
        <span className="tl-date">{row.date ? formatDate(row.date) : "offen"}</span>
        {relative ? <small className={overdue ? "tl-rel tl-rel--overdue" : "tl-rel"}>{overdue ? `überfällig · ${relative}` : relative}</small> : null}
      </span>
      <span className="tl-kind">{row.closed
        ? <Signal tone={row.closed === "done" ? "done" : "neutral"} size="sm">{row.closed === "done" ? "Erledigt" : "Abgebrochen"}</Signal>
        : <KindChip kind={row.kind} />}</span>
      <span className="tl-what">
        <span className="tl-title" title={row.title}>{row.title}</span>
        {meta.length || row.person ? <span className="tl-meta">{meta}{row.person ? <span className="tl-meta-chip tl-meta-person">{row.person}</span> : null}</span> : null}
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
    description="Alle Termine, Erinnerungen und Aufgaben zu diesem Vertrag"
    summary={items === null ? null : nothing ? "Keine Termine" : <span>{`${open.filter((row) => row.kind !== "Erinnerung").length} offen`}{allUpcoming[0]?.date ? <> · nächster: <b>{formatDate(allUpcoming[0].date)}</b> {allUpcoming[0].title}</> : null}{overdueCount ? ` · ${overdueCount} überfällig` : ""}</span>}
    icon={KINDS.Erinnerung.icon}
    iconClassName="section-tile--type"
    actions={editable && !form ? <button type="button" className="btn btn-sm" onClick={() => setForm(EMPTY_FORM)}>Termin hinzufügen</button> : null}
  >
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {form ? <form className="rg-transition" aria-label="Neuer Termin" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <div className="rg-form-grid">
        <label>Bezeichnung *<input required maxLength={255} value={form.title} onChange={(event) => setForm((current) => current && ({ ...current, title: event.target.value }))} /></label>
        <label>Art<select value={form.kind} onChange={(event) => setForm((current) => current && ({ ...current, kind: event.target.value }))}>{kinds.length === 0 ? <option value="pruefung">Prüfung</option> : kinds.map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}</select></label>
        <label>Fällig am *<input type="date" required value={form.due_date} onChange={(event) => setForm((current) => current && ({ ...current, due_date: event.target.value }))} /></label>
        <label>Erinnern am<input type="date" value={form.remind_on} max={form.due_date || undefined} onChange={(event) => setForm((current) => current && ({ ...current, remind_on: event.target.value }))} /></label>
        <label>Zuständig<select value={form.assignee_account_id} onChange={(event) => setForm((current) => current && ({ ...current, assignee_account_id: event.target.value }))}><option value="">Ich selbst</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label>Eskalation an<select value={form.escalation_account_id} onChange={(event) => setForm((current) => current && ({ ...current, escalation_account_id: event.target.value }))}><option value="">Niemand</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label className="span-full">ToDo<input maxLength={500} value={form.todo_text} onChange={(event) => setForm((current) => current && ({ ...current, todo_text: event.target.value }))} /></label>
        <label className="rg-check"><input type="checkbox" checked={form.send_email} onChange={(event) => setForm((current) => current && ({ ...current, send_email: event.target.checked }))} />Erinnerungs-E-Mail</label>
        <label className="rg-check"><input type="checkbox" checked={form.send_ics} onChange={(event) => setForm((current) => current && ({ ...current, send_ics: event.target.checked }))} />Kalendereinladung (ICS)</label>
      </div>
      <div className="rg-actions"><button type="button" className="btn" onClick={() => setForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Termin anlegen</button></div>
    </form> : null}

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
        {closed.length > 0 ? <details className="tl-done"><summary>Erledigte und abgebrochene ({closed.length})</summary>
          <ol className="tl tl--closed" aria-label="Erledigte und abgebrochene">{closed.map((row) => <Fragment key={row.key}>{renderRow(row)}</Fragment>)}</ol>
        </details> : null}
        <div className="tl-legend" aria-label="Kennfarben der Typen">
          <span>Typen:</span>
          {KIND_ORDER.map((kind) => <KindChip key={kind} kind={kind} />)}
          <span className="tl-legend-note">Farbe = Typ · Status (überfällig, heute, erledigt) nur am Punkt</span>
        </div>
      </>}
  </CollapsibleSection>;
}
