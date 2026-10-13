"use client";

import { Fragment, useCallback, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import EmptyState from "@/components/ui/EmptyState";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import { PersonTag } from "@/components/ui/TagChip";
import { useToast } from "@/components/ui/Toast";
import type { DetailWorkItem } from "@/lib/contract-detail-types";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { createContractDeadline, deadlineAction, listContractDeadlines, updateDeadline, type DeadlineDto } from "@/lib/domain-api/deadlines";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import { getContractRegister } from "@/lib/domain-api/register";
import { REVIEW_TARGET, workItemTarget, type FixTarget } from "@/lib/fix-targets";
import { formatDate } from "@/lib/format";

type Kind = "Erinnerung" | "Frist" | "Aufgabe" | "Wartung" | "Löschprüfung" | "KI-Prüfung";

const svg = (path: ReactNode) => <svg className="signal-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{path}</svg>;
const KIND_ICON: Partial<Record<Kind, ReactNode>> = {
  Erinnerung: svg(<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16M10 20a2 2 0 0 0 4 0" />),
  Aufgabe: svg(<path d="m5 12 4.5 4.5L19 7" />),
  Wartung: svg(<path d="M14.5 6.5a4 4 0 0 0-5.3 5.3L4 17l3 3 5.2-5.2a4 4 0 0 0 5.3-5.3l-2.4 2.4-2.6-.6-.6-2.6 2.6-2.2" />),
  Löschprüfung: svg(<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6" />),
};

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
  kind: Kind | "Abgebrochen";
  tone: SignalTone;
  dot: "ai" | "warning" | "critical" | "neutral";
  title: string;
  sub?: ReactNode;
  person?: string | null;
  action?: ReactNode;
  expand?: ReactNode;
}

const EMPTY_FORM = { title: "", kind: "pruefung", due_date: "", remind_on: "", assignee_account_id: "", escalation_account_id: "", todo_text: "", send_email: true, send_ics: false };

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function deadlineKind(item: DeadlineDto): Kind {
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

/**
 * Fristen & Aufgaben → „Termine & Aufgaben“: alle Termine, Erinnerungen und Aufgaben eines Vertrags auf einer Zeitachse.
 * Offene Punkte ohne Datum oben, dann „Heute“, dann chronologisch; Erledigtes eingeklappt darunter.
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
  const [today, setToday] = useState(localToday);
  const [kinds, setKinds] = useState<LookupDto[]>([]);
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [form, setForm] = useState<typeof EMPTY_FORM | null>(null);
  const [comparing, setComparing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [deadlines, register] = await Promise.allSettled([listContractDeadlines(orgSlug, contractId), getContractRegister(orgSlug, contractId)]);
    if (deadlines.status === "fulfilled") setItems(deadlines.value?.items ?? []);
    else { setItems([]); setError(errorText(deadlines.reason, "Termine konnten nicht geladen werden.")); }
    if (register.status === "fulfilled" && register.value) {
      setReminderDates(register.value.terms?.reminder_dates ?? []);
      if (register.value.as_of) setToday(register.value.as_of);
    }
  }, [contractId, orgSlug, version]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!editable || !form) return;
    let cancelled = false;
    Promise.allSettled([listLookups(orgSlug, "deadline_kind"), listOwnershipAssignees(orgSlug)]).then(([kindResult, assigneeResult]) => {
      if (cancelled) return;
      if (kindResult.status === "fulfilled") setKinds(kindResult.value.items);
      if (assigneeResult.status === "fulfilled") setAssignees(assigneeResult.value.items);
    });
    return () => { cancelled = true; };
  }, [editable, orgSlug, form !== null]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const open: Row[] = [];
  const closed: Row[] = [];

  if (endCheck) {
    const where = endCheck.documented ? `Im Dokument steht ${formatDate(endCheck.documented)}` : "Im Dokument wurde kein Enddatum gefunden";
    open.push({
      key: "end-check", date: null, kind: "KI-Prüfung", tone: "ai", dot: "ai",
      title: "Abweichung beim Vertragsende prüfen",
      sub: `${where}; in den Vertragsdaten steht ${formatDate(endCheck.maintained)}.`,
      action: <button type="button" className="btn btn-sm" aria-expanded={comparing} aria-controls="tl-compare" onClick={() => setComparing((value) => !value)}>Prüfen</button>,
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
    const row: Row = {
      key: `work:${item.work_item_id}`, date: item.target_date, kind: item.requires_review ? "KI-Prüfung" : "Aufgabe",
      tone: item.requires_review ? "ai" : "neutral", dot: item.requires_review ? "ai" : item.days_remaining != null && item.days_remaining < 0 ? "critical" : "neutral",
      title: item.title_de, sub: item.why_de ?? undefined,
    };
    if (item.status === "resolved") { closed.push({ ...row, tone: "done", dot: "neutral" }); continue; }
    if (target && target.tab !== "deadlines") row.action = <button type="button" className="btn btn-sm" onClick={() => onOpenTarget(target)}>{item.requires_review ? "Prüfen" : "Öffnen"}</button>;
    open.push(row);
  }

  // Erinnerungen der Laufzeitfrist hängen an „Kündbar bis“ bzw. dem Vertragsende.
  const anchor = (items ?? []).find((item) => item.status === "open" && item.system_key === "cancel_by")
    ?? (items ?? []).find((item) => item.status === "open" && item.system_key === "contract_end");
  for (const item of items ?? []) {
    const kind = deadlineKind(item);
    const title = deadlineTitle(item);
    if (item.status !== "open") {
      closed.push({
        key: `deadline:${item.id}`, date: item.done_at?.slice(0, 10) ?? item.due_date, kind: item.status === "cancelled" ? "Abgebrochen" : kind,
        tone: item.status === "cancelled" ? "neutral" : "done", dot: "neutral", title, person: item.done_by_name ?? item.assignee_name,
        action: editable ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => void act(() => deadlineAction(orgSlug, item.id, "reopen"), "Termin wieder geöffnet.")}>Wieder öffnen</button> : null,
      });
      continue;
    }
    const subParts: ReactNode[] = [];
    if (item.system_key === "contract_end") subParts.push("Feste Laufzeit, endet ohne Kündigung");
    else if (item.system_key === "cancel_by") subParts.push("Spätester Eingang der Kündigung beim Vertragspartner");
    if (item.todo_text) subParts.push(`ToDo: ${item.todo_text}`);
    if (item.escalation_name) subParts.push(`Eskalation an ${item.escalation_name}`);
    open.push({
      key: `deadline:${item.id}`, date: item.due_date, kind,
      tone: item.overdue ? "critical" : kind === "Frist" ? "warning" : "neutral",
      dot: item.overdue ? "critical" : kind === "Frist" ? "warning" : "neutral",
      title,
      sub: <>{subParts.join(" · ")}{item.basis_unconfirmed ? <> <button type="button" className="signal-link" onClick={() => onOpenTarget(REVIEW_TARGET)}><Signal tone="ai" size="sm">Basiert auf ungeprüften KI-Werten</Signal></button></> : null}</>,
      person: item.assignee_name,
      action: editable ? <span className="tl-actions">
        <button type="button" className="btn btn-sm btn-ghost" disabled={busy} aria-pressed={item.send_ics} title="Kalendereinladung (ICS) mit der Erinnerung senden" onClick={() => void act(() => updateDeadline(orgSlug, item.id, { send_ics: !item.send_ics }), item.send_ics ? "Kalendereinladung aus." : "Kalendereinladung an.")}>{item.send_ics ? "Kalender aus" : "Kalender an"}</button>
        <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => void act(() => deadlineAction(orgSlug, item.id, "done"), "Termin erledigt.")}>Erledigt</button>
        {item.source === "manual" ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => void act(() => deadlineAction(orgSlug, item.id, "cancel"), "Termin abgebrochen.")}>Abbrechen</button> : null}
      </span> : null,
    });
    const reminders = new Set<string>();
    if (item.remind_on && item.remind_on < item.due_date) reminders.add(item.remind_on);
    if (anchor && item.id === anchor.id) for (const value of reminderDates) if (value < item.due_date) reminders.add(value);
    for (const value of reminders) {
      if (value < today) continue;
      open.push({
        key: `reminder:${item.id}:${value}`, date: value, kind: "Erinnerung", tone: "neutral", dot: "neutral",
        title, sub: `Erinnerung vor dem Termin am ${formatDate(item.due_date)}`, person: item.assignee_name,
      });
    }
  }

  // Ohne Datum („offen“) zuerst, dann chronologisch; „Heute“ trennt Vergangenes von Kommendem.
  const undated = open.filter((row) => !row.date);
  const dated = open.filter((row) => row.date).sort((a, b) => a.date!.localeCompare(b.date!) || a.kind.localeCompare(b.kind));
  const past = dated.filter((row) => row.date! < today);
  const upcoming = dated.filter((row) => row.date! >= today);
  closed.sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
  const nothing = items !== null && open.length === 0 && closed.length === 0;

  const renderRow = (row: Row) => <li key={row.key} className={`tl-row${row.kind === "KI-Prüfung" ? " tl-row--ai" : ""}`}>
    <span className={`tl-dot tl-dot--${row.dot}`} aria-hidden="true" />
    <span className="tl-date num">{row.date ? formatDate(row.date) : "offen"}</span>
    <span className="tl-kind"><Signal tone={row.tone} size="sm" icon={row.kind === "Abgebrochen" ? undefined : KIND_ICON[row.kind]}>{row.kind}</Signal></span>
    <span className="tl-title">{row.title}{row.sub ? <small>{row.sub}</small> : null}</span>
    <span className="tl-who">{row.person ? <PersonTag name={row.person} /> : null}</span>
    <span className="tl-act">{row.action}</span>
    {row.expand}
  </li>;

  return <CollapsibleSection
    id="tl"
    title="Termine & Aufgaben"
    description="Alle Termine, Erinnerungen und Aufgaben zu diesem Vertrag"
    icon={KIND_ICON.Erinnerung}
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
        <ol className="tl" aria-label="Termine und Aufgaben">
          {undated.map(renderRow)}
          {past.map(renderRow)}
          <li className="tl-row tl-row--today" aria-label={`Heute, ${formatDate(today)}`}>
            <span className="tl-dot tl-dot--today" aria-hidden="true" />
            <span className="tl-today">Heute</span>
            <span />
            <span className="tl-today num">{formatDate(today)}</span>
          </li>
          {upcoming.map(renderRow)}
        </ol>
        {closed.length > 0 ? <details className="tl-done"><summary>Erledigte und abgebrochene ({closed.length})</summary>
          <ol className="tl tl--closed" aria-label="Erledigte und abgebrochene">{closed.map((row) => <Fragment key={row.key}>{renderRow(row)}</Fragment>)}</ol>
        </details> : null}
      </>}
  </CollapsibleSection>;
}
