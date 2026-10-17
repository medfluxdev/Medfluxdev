"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import { PersonTag } from "@/components/ui/TagChip";
import { useToast } from "@/components/ui/Toast";
import { FINANCE_ENTRIES_TARGET, asFixTarget, contractHref, fixLabel } from "@/lib/fix-targets";
import { formatCurrency, formatDate, formatISODateOnly } from "@/lib/format";
import {
  createContractLifecycleDecision,
  deleteContractLifecycleDecision,
  getContractLifecycle,
  updateContractLifecycleDecision,
  updateDecisionStep,
  type ContractLifecycleDecision,
  type ContractLifecycleDecisionKind,
  type ContractLifecycleStatus,
} from "@/lib/domain-api/lifecycle";
import { getRenewalBrief, type RenewalBrief, type RenewalUrgency } from "@/lib/domain-api/registerGrid";

// Liste „Kündigungsentscheidungen“: verstrichen = kritisch, ≤ 30 Tage = prüfen, alles andere ruhig.
export const URGENCY: Record<RenewalUrgency, { label: string; tone: SignalTone }> = {
  missed: { label: "Frist verstrichen", tone: "critical" },
  critical: { label: "Dringend (≤ 30 Tage)", tone: "warning" },
  soon: { label: "Bald (≤ 90 Tage)", tone: "neutral" },
  planned: { label: "Geplant", tone: "neutral" },
  unknown: { label: "Frist unbekannt", tone: "neutral" },
  none: { label: "Keine offene Frist", tone: "neutral" },
};

export const DECISIONS: { key: ContractLifecycleDecisionKind; label: string }[] = [
  { key: "renew", label: "Verlängern" },
  { key: "renegotiate", label: "Neu verhandeln" },
  { key: "terminate", label: "Kündigen" },
  { key: "monitor", label: "Beobachten" },
];

// Passender Termin zur Entscheidung, damit Entscheidung und Erinnerung ein Schritt sind.
const FOLLOW_UP: Record<ContractLifecycleDecisionKind, { title: string; kind: string; todo: string }> = {
  renew: { title: "Verlängerung umsetzen", kind: "pruefung", todo: "Verlängerung mit dem Vertragspartner vereinbaren und dokumentieren." },
  renegotiate: { title: "Neu verhandeln", kind: "pruefung", todo: "Gespräch mit dem Vertragspartner führen und neue Konditionen festhalten." },
  terminate: { title: "Kündigung versenden", kind: "kuendigungsfrist", todo: "Kündigung fristgerecht versenden und den Status auf „Gekündigt“ setzen." },
  monitor: { title: "Entscheidung erneut prüfen", kind: "pruefung", todo: "Vertrag erneut bewerten und eine Entscheidung treffen." },
};

function reminderInput(decision: ContractLifecycleDecisionKind, title: string, due: string, note: string) {
  const follow = FOLLOW_UP[decision];
  return { title: title.trim() || follow.title, kind: follow.kind, due_date: due, todo_text: [follow.todo, note.trim()].filter(Boolean).join(" ").slice(0, 500) };
}

function shiftDate(iso: string, days: number, months = 0): string {
  const date = new Date(`${iso}T00:00:00`);
  date.setMonth(date.getMonth() + months);
  date.setDate(date.getDate() + days);
  return formatISODateOnly(date);
}

/** Fälligkeit des Folgetermins: Kündigungsfrist, sonst Wirksamkeit, nie in der Vergangenheit; Beobachten = in 3 Monaten. */
export function followUpDue(decision: ContractLifecycleDecisionKind, brief: Pick<RenewalBrief, "cancel_by" | "current_end"> | null, effective: string, today = formatISODateOnly(new Date())): string {
  if (decision === "monitor") return shiftDate(today, 0, 3);
  const candidates = decision === "terminate" ? [brief?.cancel_by, effective] : [brief?.cancel_by, effective, brief?.current_end];
  const due = candidates.find((value): value is string => Boolean(value) && value! >= today);
  return due ?? shiftDate(today, 7);
}

const STATUS_WORD: Record<ContractLifecycleStatus, string> = {
  planned: "geplant", in_progress: "in Bearbeitung", completed: "abgeschlossen", cancelled: "storniert",
};

interface DecisionEdit {
  id: string;
  decision: ContractLifecycleDecisionKind;
  status: ContractLifecycleStatus;
  effective: string;
  note: string;
  /** Erinnerung: an = offene behalten/ändern bzw. neu anlegen; aus = offene abbrechen. */
  remind: boolean;
  remindTitle: string;
  remindDue: string;
  /** Verknüpfte Erinnerung ist offen (Ändern statt Neu anlegen). */
  hasOpenReminder: boolean;
}

// Offene Entscheidung: verstrichen = kritisch, ≤ 30 Tage = prüfen, sonst Hinweis (gleich wie „Offene Punkte“).
const PENDING_TONE: Record<RenewalUrgency, SignalTone> = { missed: "critical", critical: "warning", soon: "info", planned: "info", unknown: "info", none: "info" };

const HINT_LABEL = { action: "Handlungsbedarf", check: "Prüfen", info: "Hinweis" } as const;

const icon = (body: JSX.Element) => <svg viewBox="0 0 24 24" focusable="false">{body}</svg>;
const KPI_ICON = {
  cal: icon(<path d="M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM3 10h18M8 3v4M16 3v4" />),
  clock: icon(<path d="M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 7v5l3 2" />),
  coins: icon(<path d="M9 6c0-1.7 2.7-3 6-3s6 1.3 6 3-2.7 3-6 3-6-1.3-6-3zM9 6v4c0 1.7 2.7 3 6 3s6-1.3 6-3V6M3 12c0-1.7 2.7-3 6-3s6 1.3 6 3-2.7 3-6 3-6-1.3-6-3zM3 12v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5" />),
  info: icon(<path d="M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 11v6M12 7.5v.5" />),
  target: icon(<path d="M12 4a8 8 0 1 0 8 8M12 8a4 4 0 1 0 4 4M12 12l7-7M16 5h3v3" />),
  warn: icon(<path d="M12 3 2 20h20zM12 10v4M12 17v.5" />),
  pen: icon(<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" />),
  chevron: icon(<path d="m6 9 6 6 6-6" />),
};
const DECISION_ICON: Record<ContractLifecycleDecisionKind, JSX.Element> = {
  renew: icon(<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16M20 20v-4h-4" />),
  renegotiate: icon(<path d="M4 5h11a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-4 3v-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM19 9h1a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-1v3l-4-3h-3" />),
  terminate: icon(<path d="M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM9 9l6 6M15 9l-6 6" />),
  monitor: icon(<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9a3 3 0 1 1 0 6a3 3 0 1 1 0-6" />),
};
const decisionIcon = (kind: ContractLifecycleDecisionKind | null) => (kind ? DECISION_ICON[kind] : SCALE_ICON);

const SCALE_ICON = <svg viewBox="0 0 24 24" focusable="false"><path d="M12 3v18M7 21h10M5 7h14M5 7l-3 6a3 3 0 0 0 6 0L5 7M19 7l-3 6a3 3 0 0 0 6 0l-3-6" /></svg>;

/** Status im Kopf: verstrichen = kritisch, ≤ 30 Tage = prüfen (wie „Kündigungsentscheidungen“), sonst ruhig. */
export function deadlineSignal(brief: Pick<RenewalBrief, "urgency" | "days_left"> & Partial<Pick<RenewalBrief, "cancel_by" | "current_end">>, today = formatISODateOnly(new Date())): { tone: SignalTone; label: string } {
  const days = brief.days_left;
  if (brief.urgency === "missed") return { tone: "critical", label: "Frist überschritten" };
  // Ohne Kündigungsfrist zählt das Vertragsende (z. B. feste Laufzeit).
  if (brief.urgency === "none" && !brief.cancel_by && brief.current_end) {
    return { tone: "neutral", label: brief.current_end >= today ? `Keine Kündigungsfrist – Vertrag endet am ${formatDate(brief.current_end)}` : `Vertrag endete am ${formatDate(brief.current_end)}` };
  }
  if (brief.urgency === "none") return { tone: "neutral", label: "Keine offene Frist" };
  if (brief.urgency === "unknown" || days == null) return { tone: "neutral", label: "Frist unbekannt" };
  const label = days === 0 ? "Frist heute" : days === 1 ? "Frist in 1 Tag" : `Frist in ${days} Tagen`;
  return { tone: brief.urgency === "critical" ? "warning" : "neutral", label };
}

/**
 * Entscheidung fällig: laufender Vertrag („Gültig“) mit Kündigungsfrist oder Vertragsende, ohne offene Entscheidung.
 * Liefert, bis wann und wie dringend (gleiche Stufen wie „Kündigungsentscheidungen“), sonst null.
 */
export function pendingDecision(brief: Pick<RenewalBrief, "decision" | "business_status" | "cancel_by" | "current_end" | "urgency"> | null): { due: string; byCancel: boolean; urgency: RenewalUrgency } | null {
  // Eine abgeschlossene oder stornierte Entscheidung gilt nicht mehr: dann ist wieder zu entscheiden (wie auf der Karte).
  const open = brief?.decision && (brief.decision.status === "planned" || brief.decision.status === "in_progress");
  if (!brief || open || brief.business_status !== "gueltig") return null;
  const due = brief.cancel_by ?? brief.current_end;
  return due ? { due, byCancel: Boolean(brief.cancel_by), urgency: brief.urgency } : null;
}

/** Wohin ein Schritt führt (für die Beschriftung des Knopfs). */
function stepTargetKind(target: Record<string, string> | null): string {
  if (!target) return "none";
  if (target.action === "change_decision") return "change_decision";
  if (target.tab === "register") return target.section === "status" ? "status" : "term";
  if (target.tab === "finance") return "finance";
  if (target.tab === "documents") return "documents";
  return "other";
}

const STEP_ACTION: Record<string, string> = {
  term: "Laufzeit eintragen", status: "Status setzen", finance: "Kosten erfassen", documents: "Dokument hochladen",
  change_decision: "Entscheidung ändern", other: "Öffnen",
};

/** Fälligkeit eines offenen Schritts: überfällig = kritisch, ≤ 14 Tage = prüfen, sonst ruhig. */
export function dueInfo(due: string | null, today: string): { tone: SignalTone; label: string } | null {
  if (!due) return null;
  const days = Math.round((Date.parse(`${due}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000);
  if (days < 0) return { tone: "critical", label: `überfällig seit ${formatDate(due)}` };
  if (days === 0) return { tone: "warning", label: "heute fällig" };
  return { tone: days <= 14 ? "warning" : "neutral", label: `bis ${formatDate(due)} · noch ${days} ${days === 1 ? "Tag" : "Tage"}` };
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * Fristen & Aufgaben → „Entscheidung“: was zum nächsten Termin mit dem Vertrag passieren soll.
 * Fakten und Beträge berechnet das Backend (Entscheidungsvorlage); gespeichert wird über die Lifecycle-API.
 */
export default function ContractDecisionCard({ contractId, orgSlug, onReminderCreated, onDecisionChanged }: { contractId: string; orgSlug: string; onReminderCreated?: () => void; /** Nach Speichern/Ändern/Löschen (z. B. „Offene Punkte“ neu laden). */ onDecisionChanged?: () => void }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const toast = useToast();
  const [brief, setBrief] = useState<RenewalBrief | null>(null);
  const [decisions, setDecisions] = useState<ContractLifecycleDecision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<{ decision: ContractLifecycleDecisionKind; effective: string; note: string; remind: boolean; remindTitle: string; remindDue: string } | null>(null);
  const [busy, setBusy] = useState(false);
  // Nach „Kündigen“: die Kündigung selbst wird über den Status „Gekündigt“ dokumentiert.
  const [terminated, setTerminated] = useState(false);
  const effectiveRef = useRef<HTMLInputElement | null>(null);
  // Bisherige Entscheidungen: eine Zeile bearbeiten bzw. das Löschen bestätigen.
  const [editing, setEditing] = useState<DecisionEdit | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);

  const load = useCallback(async () => {
    const [briefResult, lifecycleResult] = await Promise.allSettled([getRenewalBrief(orgSlug, contractId), getContractLifecycle(orgSlug, contractId)]);
    if (briefResult.status === "fulfilled" && briefResult.value && Array.isArray(briefResult.value.hints)) {
      setBrief({ ...briefResult.value, partner_contracts: briefResult.value.partner_contracts ?? [] });
    } else {
      setError(briefResult.status === "rejected" ? errorText(briefResult.reason, "Die Entscheidung konnte nicht geladen werden.") : "Die Entscheidung ist derzeit nicht verfügbar.");
    }
    setDecisions(lifecycleResult.status === "fulfilled" ? lifecycleResult.value.items ?? [] : []);
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (form) effectiveRef.current?.focus(); }, [form?.decision]); // eslint-disable-line react-hooks/exhaustive-deps

  function choose(decision: ContractLifecycleDecisionKind) {
    setForm((current) => {
      if (current?.decision === decision) return null;
      const effective = current?.effective ?? brief?.current_end ?? "";
      return { decision, effective, note: current?.note ?? "", remind: true, remindTitle: FOLLOW_UP[decision].title, remindDue: followUpDue(decision, brief, effective) };
    });
  }

  async function save() {
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      // Entscheidung und Erinnerung in einem Schritt; die Erinnerung bleibt mit der Entscheidung verknüpft
      // (änderbar und löschbar mit ihr).
      const remind = form.remind && form.remindDue ? reminderInput(form.decision, form.remindTitle, form.remindDue, form.note) : null;
      await createContractLifecycleDecision(orgSlug, contractId, { decision: form.decision, status: "planned", effective_date: form.effective || null, note: form.note.trim() || null, ...(remind ? { reminder: remind } : {}) });
      // Geänderte Entscheidung: die bisher offene wird storniert (bleibt im Verlauf), ihre offene Erinnerung entfällt.
      if (current) {
        await updateContractLifecycleDecision(orgSlug, contractId, current.id, {
          status: "cancelled", effective_date: current.effective_date, note: current.note,
          ...(current.reminder?.status === "open" ? { remove_reminder: true } : {}),
        });
      }
      setChanging(false);
      if (remind || current?.reminder?.status === "open") onReminderCreated?.();
      setTerminated(form.decision === "terminate");
      setForm(null);
      toast(remind ? `Entscheidung gespeichert, Erinnerung am ${formatDate(remind.due_date)} angelegt.` : "Entscheidung gespeichert.", "success");
      await load();
      onDecisionChanged?.();
    } catch (err) {
      setError(errorText(err, "Die Entscheidung konnte nicht gespeichert werden."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleStep(item: ContractLifecycleDecision, key: string, done: boolean) {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateDecisionStep(orgSlug, contractId, item.id, key, done);
      setDecisions((current) => (current ?? []).map((row) => (row.id === updated.id ? { ...row, ...updated, reminder: updated.reminder ?? row.reminder } : row)));
      onDecisionChanged?.();
    } catch (err) {
      setError(errorText(err, "Der Schritt konnte nicht gespeichert werden."));
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(item: ContractLifecycleDecision, status: ContractLifecycleStatus) {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateContractLifecycleDecision(orgSlug, contractId, item.id, { status, effective_date: item.effective_date, note: item.note });
      setDecisions((current) => (current ?? []).map((row) => (row.id === updated.id ? updated : row)));
      onDecisionChanged?.();
    } catch (err) {
      setError(errorText(err, "Der Status der Entscheidung konnte nicht geändert werden."));
    } finally {
      setBusy(false);
    }
  }

  function startEdit(item: ContractLifecycleDecision) {
    setConfirmDelete(null);
    const open = item.reminder?.status === "open" ? item.reminder : null;
    const effective = item.effective_date ?? "";
    setEditing({
      id: item.id, decision: item.decision, status: item.status, effective, note: item.note ?? "",
      remind: Boolean(open), hasOpenReminder: Boolean(open),
      remindTitle: open?.title ?? FOLLOW_UP[item.decision].title,
      remindDue: open?.due_date ?? followUpDue(item.decision, brief, effective),
    });
  }

  /** Andere Entscheidung gewählt: eine unveränderte Standard-Bezeichnung der Erinnerung zieht mit. */
  function changeEditDecision(decision: ContractLifecycleDecisionKind) {
    setEditing((current) => current && ({
      ...current,
      decision,
      remindTitle: current.remindTitle === FOLLOW_UP[current.decision].title ? FOLLOW_UP[decision].title : current.remindTitle,
    }));
  }

  async function saveEdit() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      const remind = editing.remind && editing.remindDue ? reminderInput(editing.decision, editing.remindTitle, editing.remindDue, editing.note) : null;
      const updated = await updateContractLifecycleDecision(orgSlug, contractId, editing.id, {
        decision: editing.decision, status: editing.status, effective_date: editing.effective || null, note: editing.note.trim() || null,
        ...(remind ? { reminder: remind } : editing.hasOpenReminder ? { remove_reminder: true } : {}),
      });
      setDecisions((current) => (current ?? []).map((row) => (row.id === updated.id ? updated : row)));
      setEditing(null);
      if (remind || editing.hasOpenReminder) onReminderCreated?.();
      toast(remind ? `Entscheidung geändert, Erinnerung am ${formatDate(remind.due_date)}.` : editing.hasOpenReminder ? "Entscheidung geändert, Erinnerung entfernt." : "Entscheidung geändert.", "success");
      onDecisionChanged?.();
    } catch (err) {
      setError(errorText(err, "Die Entscheidung konnte nicht geändert werden."));
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: ContractLifecycleDecision) {
    setBusy(true);
    setError(null);
    try {
      await deleteContractLifecycleDecision(orgSlug, contractId, item.id);
      setDecisions((current) => (current ?? []).filter((row) => row.id !== item.id));
      setConfirmDelete(null);
      if (item.reminder?.status === "open") onReminderCreated?.();
      toast(item.reminder?.status === "open" ? "Entscheidung und Erinnerung gelöscht." : "Entscheidung gelöscht.", "success");
      onDecisionChanged?.();
    } catch (err) {
      setError(errorText(err, "Die Entscheidung konnte nicht gelöscht werden."));
    } finally {
      setBusy(false);
    }
  }

  const signal = brief ? deadlineSignal(brief) : null;
  const sorted = [...(decisions ?? [])].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  // Die gültige Entscheidung: die jüngste, die noch nicht abgeschlossen oder storniert ist.
  const current = sorted.find((item) => item.status === "planned" || item.status === "in_progress") ?? null;
  const currentLabel = current ? DECISIONS.find((entry) => entry.key === current.decision)?.label ?? current.decision : null;
  const currentDue = current?.reminder?.status === "open" ? current.reminder.due_date : null;
  const showChoices = editable && (!current || changing);
  const steps = current?.steps ?? [];
  const stepsDone = steps.filter((step) => step.done).length;
  const nextOpen = steps.find((step) => !step.done) ?? null;
  // Die Liste hier ist aktueller als die Vorlage (Ändern/Löschen ohne Neuladen): „offen“ allein aus der Liste.
  const pending = current || !brief ? null : pendingDecision({ ...brief, decision: null });
  // Ohne Kündigungsfrist (feste Laufzeit) entfällt „Kündbar bis“; fehlende Werte führen zum Feld.
  const termHref = contractHref(contractId, { tab: "register", section: "term" });

  return <CollapsibleSection
    id="dec"
    title="Vertragsentscheidung"
    summary={brief ? <span>{sorted[0] ? <>Zuletzt: <b>{DECISIONS.find((entry) => entry.key === sorted[0].decision)?.label ?? sorted[0].decision}</b>{sorted[0].effective_date ? ` · wirksam am ${formatDate(sorted[0].effective_date)}` : ""}</> : "Noch keine Entscheidung erfasst"}{brief.cancel_by ? ` · Kündbar bis ${formatDate(brief.cancel_by)}` : brief.current_end ? ` · Vertragsende ${formatDate(brief.current_end)}` : ""}</span> : null}
    icon={SCALE_ICON}
    iconClassName="section-tile--accent"
    actions={<>{signal ? <Signal tone={signal.tone}>{signal.label}</Signal> : null}{current && editable ? <button type="button" className="btn btn-sm dec-change" aria-expanded={changing} onClick={() => { setChanging((value) => !value); setForm(null); }}>{KPI_ICON.pen}{changing ? "Nicht ändern" : "Entscheidung ändern"}</button> : null}</>}
  >
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {!brief ? (error ? null : <p role="status" aria-busy="true">Entscheidung wird geladen…</p>) : <div className="dec-body">
      <div className="dec-top">
        {/* Links: die gültige Entscheidung (sonst die letzte bzw. „noch keine“); rechts Fakten und „Ohne Handeln“. */}
        <div className={`dec-now${current ? ` is-set dec-kind--${current.decision}` : pending ? " is-pending" : ""}`}>
          <span className="dec-now-icon" aria-hidden="true">{decisionIcon(current?.decision ?? sorted[0]?.decision ?? null)}</span>
          <div className="dec-now-text">
            <span className="dec-now-label">Entscheidung</span>
            {current
              ? <><strong className="dec-now-value">{currentLabel}</strong><span className="dec-now-meta">{[current.actor_display_name ? `Entschieden von ${current.actor_display_name}` : "Entschieden", current.created_at ? formatDate(current.created_at) : null].filter(Boolean).join(" · ")}</span></>
              : sorted[0]
                ? <><strong className={`dec-now-value${pending ? " dec-now-value--none" : ""}`}>{pending ? "Noch nicht entschieden" : DECISIONS.find((entry) => entry.key === sorted[0].decision)?.label ?? sorted[0].decision}</strong><span className="dec-now-meta">Zuletzt: {DECISIONS.find((entry) => entry.key === sorted[0].decision)?.label ?? sorted[0].decision} · {STATUS_WORD[sorted[0].status]}{sorted[0].created_at ? ` · ${formatDate(sorted[0].created_at)}` : ""}</span></>
                : <><strong className="dec-now-value dec-now-value--none">Noch nicht entschieden</strong><span className="dec-now-meta">Noch keine Entscheidung erfasst.</span></>}
            {!current && pending ? <span className="dec-now-due">
              <Signal tone={PENDING_TONE[pending.urgency]} size="sm">{pending.urgency === "missed" ? "Frist verstrichen" : "Entscheidung offen"}</Signal>
              <span>Bis {formatDate(pending.due)} entscheiden{pending.byCancel ? " (Kündbar bis)" : " (Vertragsende)"}</span>
            </span> : null}
          </div>
        </div>
        <div className="dec-side">
          <dl className="dec-kpis">
            {brief.cancel_by || brief.urgency !== "none" ? <div className="dec-kpi"><dt><span className="dec-kpi-icon" aria-hidden="true">{KPI_ICON.clock}</span>Kündbar bis</dt><dd>{brief.cancel_by
              ? <><span className="num dec-value">{formatDate(brief.cancel_by)}</span>{brief.days_left != null ? <small>{brief.days_left >= 0 ? `noch ${brief.days_left} Tage` : `seit ${-brief.days_left} Tagen verstrichen`}</small> : null}</>
              : <Link className="rg-link" href={termHref}>Kündigungsfrist ergänzen</Link>}</dd></div> : null}
            <div className="dec-kpi"><dt><span className="dec-kpi-icon" aria-hidden="true">{KPI_ICON.cal}</span>Vertragsende</dt><dd>{brief.current_end ? <span className="num dec-value">{formatDate(brief.current_end)}</span> : <Link className="rg-link" href={termHref}>Laufzeit ergänzen</Link>}</dd></div>
            <div className="dec-kpi"><dt><span className="dec-kpi-icon" aria-hidden="true">{KPI_ICON.coins}</span>Jährliche Kosten</dt><dd>{brief.annual_cost ? <span className="num dec-value">{formatCurrency(brief.annual_cost, "EUR")}</span> : <Link className="rg-link" href={contractHref(contractId, FINANCE_ENTRIES_TARGET)}>Kosten ergänzen</Link>}</dd></div>
            {brief.renewal_cost ? <div className="dec-kpi"><dt><span className="dec-kpi-icon" aria-hidden="true">{KPI_ICON.coins}</span>Kosten bei Verlängerung</dt><dd><span className="num dec-value">{formatCurrency(brief.renewal_cost, "EUR")}</span>{brief.next_end_if_no_action ? <small>bis {formatDate(brief.next_end_if_no_action)}</small> : null}</dd></div> : null}
          </dl>
          <p className="dec-info"><span className="dec-info-icon" aria-hidden="true">{KPI_ICON.info}</span><span><strong>Ohne Handeln:</strong> {brief.if_no_action}</span></p>
        </div>
      </div>
      {brief.urgency === "unknown" ? <p className="cw-muted">Ohne vollständige Laufzeitangaben ist keine Frist berechenbar. <Link className="rg-link" href={contractHref(contractId, { tab: "register", section: "term" })}>Laufzeit erfassen</Link></p> : null}

      {current && !changing ? <section className={`dec-plan dec-kind--${current.decision}`} aria-labelledby="dec-plan-heading">
        <div className="dec-plan-head">
          <h3 id="dec-plan-heading"><span className="dec-plan-icon" aria-hidden="true">{KPI_ICON.target}</span>Umsetzung: {currentLabel}</h3>
          {steps.length ? <span className="dec-plan-progress">
            <span>{stepsDone} von {steps.length} erledigt</span>
            <span className="dec-plan-bar" role="progressbar" aria-label="Fortschritt der Umsetzung" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={stepsDone}><span style={{ width: `${(stepsDone / steps.length) * 100}%` }} /></span>
          </span> : null}
        </div>
        {steps.length ? <ol className="dec-steps">
          {steps.map((step) => {
            const isNext = step.key === nextOpen?.key;
            const due = step.done ? null : dueInfo(step.due, brief.as_of);
            const action = step.done || !step.target ? null : STEP_ACTION[stepTargetKind(step.target)];
            return <li key={step.key} className={`dec-step${step.done ? " is-done" : ""}${isNext ? " is-next" : ""}`}>
              <label className="dec-step-check">
                <input type="checkbox" checked={step.done} disabled={!editable || busy || step.done_how === "auto"}
                  onChange={(event) => void toggleStep(current, step.key, event.target.checked)}
                  aria-label={`${step.title}: ${step.done ? "erledigt" : "offen"}`} />
                <span aria-hidden="true" />
              </label>
              <div className="dec-step-text">
                <span className="dec-step-title">{isNext ? <span className="dec-step-next">Als Nächstes</span> : null}{step.title}</span>
                <small>{step.done_how === "auto" ? "Erledigt – aus den Vertragsdaten erkannt." : step.done_how === "manual" ? `Erledigt von ${step.done_by ?? "–"}${step.done_at ? ` am ${formatDate(step.done_at)}` : ""}.` : step.detail}</small>
              </div>
              {due ? <Signal tone={due.tone} size="sm">{due.label}</Signal> : <span />}
              {action ? (stepTargetKind(step.target) === "change_decision"
                ? <button type="button" className={`btn btn-sm${isNext ? " btn-primary" : ""}`} disabled={!editable} onClick={() => { setChanging(true); setForm(null); }}>{action}</button>
                : <Link scroll={false} className={`btn btn-sm${isNext ? " btn-primary" : ""}`} href={contractHref(contractId, asFixTarget(step.target) ?? { tab: "deadlines" })}>{action} →</Link>) : <span />}
            </li>;
          })}
        </ol> : null}
        {editable ? <div className="dec-plan-foot">
          {steps.length && stepsDone === steps.length
            ? <><span className="dec-plan-done"><Signal tone="done" size="sm">Alle Schritte erledigt</Signal></span><button type="button" className="btn btn-primary" disabled={busy} onClick={() => void changeStatus(current, "completed")}>Entscheidung abschließen</button></>
            : <button type="button" className="rg-link" disabled={busy} onClick={() => void changeStatus(current, "completed")}>Ohne alle Schritte abschließen</button>}
        </div> : null}
      </section> : null}

      {showChoices ? <div className="dec-choose">
        {current ? <span className="dec-choose-label">Neue Entscheidung</span> : null}
        <div className="dec-seg" role="group" aria-label={current ? "Neue Entscheidung" : "Entscheidung"}>
          {DECISIONS.map((item) => <button key={item.key} type="button" className={`dec-kind--${item.key}`} aria-pressed={form?.decision === item.key} onClick={() => choose(item.key)}>{decisionIcon(item.key)}{item.label}</button>)}
        </div>
      </div> : null}
      {current && changing && form ? <p className="cw-muted">Beim Speichern wird „{currentLabel}“ storniert{currentDue ? " und die Erinnerung entfernt" : ""}; sie bleibt in der Entscheidungshistorie.</p> : null}
      {form ? <form className="dec-form" aria-label={`Entscheidung: ${DECISIONS.find((item) => item.key === form.decision)?.label}`} onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <div className="dec-field"><label htmlFor="dec-effective">Wirksam am</label><input ref={effectiveRef} id="dec-effective" className="num" type="date" value={form.effective} onChange={(event) => setForm((current) => current && ({ ...current, effective: event.target.value }))} /></div>
        <div className="dec-field dec-full"><label htmlFor="dec-note">Notiz</label><textarea id="dec-note" rows={3} maxLength={2000} placeholder="Begründung, Ansprechpartner, nächste Schritte …" value={form.note} onChange={(event) => setForm((current) => current && ({ ...current, note: event.target.value }))} /></div>
        <div className="dec-full dec-remind">
          <label className="rg-check"><input type="checkbox" checked={form.remind} onChange={(event) => setForm((current) => current && ({ ...current, remind: event.target.checked }))} />Erinnerung anlegen</label>
          {form.remind ? <div className="dec-remind-fields">
            <div className="dec-field"><label htmlFor="dec-remind-title">Termin</label><input id="dec-remind-title" type="text" maxLength={200} value={form.remindTitle} onChange={(event) => setForm((current) => current && ({ ...current, remindTitle: event.target.value }))} /></div>
            <div className="dec-field"><label htmlFor="dec-remind-due">Fällig am</label><input id="dec-remind-due" className="num" type="date" required value={form.remindDue} onChange={(event) => setForm((current) => current && ({ ...current, remindDue: event.target.value }))} /></div>
            <p className="cw-muted dec-full">Erscheint unter „Termine & Aufgaben“; Sie werden am Fälligkeitstag erinnert (Glocke und E-Mail).</p>
          </div> : null}
        </div>
        {form.decision === "terminate" ? <p className="rg-hint dec-full">Die Entscheidung wird nur erfasst. Die Kündigung selbst versenden Sie und dokumentieren sie anschließend über den Status „Gekündigt“.</p> : null}
        <div className="rg-actions dec-full"><button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Entscheidung speichern</button></div>
      </form> : null}

      {terminated && brief.business_status !== "gekuendigt" && brief.business_status !== "beendet" ? <p className="dec-followup" role="status">
        Kündigung versendet? Dann den Vertrag auf „Gekündigt“ setzen – mit Datum der Kündigung und Wirksamkeit.{" "}
        <Link className="rg-link" href={contractHref(contractId, { tab: "overview", section: "status" })}>Status auf „Gekündigt“ setzen</Link>
      </p> : null}

      {brief.hints.length > 0 ? <ul className="dec-hints" aria-label="Hinweise">
        {brief.hints.map((hint) => {
          const target = asFixTarget(hint.target);
          return <li key={hint.text} className={`dec-hint dec-hint--${hint.kind}`}>
            <span className="dec-hint-icon" aria-hidden="true">{KPI_ICON.warn}</span>
            <span className="dec-hint-text"><span className="sr-only">{HINT_LABEL[hint.kind]}: </span><strong>{hint.text}</strong> <small className="cw-muted">Grundlage: {hint.reason}</small></span>
            {target ? <Link className="rg-link" href={contractHref(contractId, target)}>{fixLabel(target)} →</Link> : null}
          </li>;
        })}
      </ul> : null}
      {brief.partner_contracts.length > 0 ? <details className="dec-partners"><summary>Weitere Verträge mit {brief.partner} ({brief.partner_contracts.length})</summary>
        <ul>{brief.partner_contracts.map((item) => <li key={item.contract_id}><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link></li>)}</ul>
      </details> : null}

      {decisions === null ? <p role="status">Wird geladen…</p> : sorted.length > 0 ? <div className="dec-history">
        <button type="button" className="dec-history-toggle" aria-expanded={historyOpen} aria-controls="dec-history-list" onClick={() => setHistoryOpen((open) => !open)}>
          <span className="dec-history-chevron" aria-hidden="true">{KPI_ICON.chevron}</span>Entscheidungshistorie ({sorted.length})
        </button>
        {historyOpen ? <ul id="dec-history-list" aria-label="Bisherige Entscheidungen">
          {sorted.map((item) => {
            const label = DECISIONS.find((entry) => entry.key === item.decision)?.label ?? item.decision;
            const date = item.created_at ? formatDate(item.created_at) : "–";
            if (editing?.id === item.id) return <li key={item.id} className="dec-history-row dec-history-row--edit">
              <form className="dec-form" aria-label={`Entscheidung vom ${date} bearbeiten`} onSubmit={(event) => { event.preventDefault(); void saveEdit(); }}>
                <div className="dec-field"><label htmlFor={`dec-edit-kind-${item.id}`}>Entscheidung</label><select id={`dec-edit-kind-${item.id}`} value={editing.decision} onChange={(event) => changeEditDecision(event.target.value as ContractLifecycleDecisionKind)}>{DECISIONS.map((entry) => <option key={entry.key} value={entry.key}>{entry.label}</option>)}</select></div>
                <div className="dec-field"><label htmlFor={`dec-edit-status-${item.id}`}>Stand</label><select id={`dec-edit-status-${item.id}`} value={editing.status} onChange={(event) => setEditing((current) => current && ({ ...current, status: event.target.value as ContractLifecycleStatus }))}>{(Object.keys(STATUS_WORD) as ContractLifecycleStatus[]).map((key) => <option key={key} value={key}>{STATUS_WORD[key]}</option>)}</select></div>
                <div className="dec-field"><label htmlFor={`dec-edit-effective-${item.id}`}>Wirksam am</label><input id={`dec-edit-effective-${item.id}`} className="num" type="date" value={editing.effective} onChange={(event) => setEditing((current) => current && ({ ...current, effective: event.target.value }))} /></div>
                <div className="dec-field dec-full"><label htmlFor={`dec-edit-note-${item.id}`}>Notiz</label><textarea id={`dec-edit-note-${item.id}`} rows={2} maxLength={2000} value={editing.note} onChange={(event) => setEditing((current) => current && ({ ...current, note: event.target.value }))} /></div>
                <div className="dec-full dec-remind">
                  <label className="rg-check"><input type="checkbox" checked={editing.remind} onChange={(event) => setEditing((current) => current && ({ ...current, remind: event.target.checked }))} />{editing.hasOpenReminder ? "Erinnerung" : "Erinnerung anlegen"}</label>
                  {editing.remind ? <div className="dec-remind-fields">
                    <div className="dec-field"><label htmlFor={`dec-edit-remind-title-${item.id}`}>Termin</label><input id={`dec-edit-remind-title-${item.id}`} type="text" maxLength={200} value={editing.remindTitle} onChange={(event) => setEditing((current) => current && ({ ...current, remindTitle: event.target.value }))} /></div>
                    <div className="dec-field"><label htmlFor={`dec-edit-remind-due-${item.id}`}>Fällig am</label><input id={`dec-edit-remind-due-${item.id}`} className="num" type="date" required value={editing.remindDue} onChange={(event) => setEditing((current) => current && ({ ...current, remindDue: event.target.value }))} /></div>
                  </div> : <p className="cw-muted">{editing.hasOpenReminder ? "Die Erinnerung wird beim Speichern entfernt." : item.reminder?.status === "done" ? `Erinnerung „${item.reminder.title}“ ist erledigt.` : "Keine Erinnerung zu dieser Entscheidung."}</p>}
                </div>
                <div className="rg-actions dec-full"><button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Änderung speichern</button></div>
              </form>
            </li>;
            return <li key={item.id} className={`dec-history-row${item.status === "cancelled" ? " is-closed" : ""}`}>
              <span className="num">{date}</span>
              <span className={`dec-chip dec-kind--${item.decision}`}>{decisionIcon(item.decision)}{label}</span>
              <PersonTag name={item.actor_display_name} />
              <span className="cw-muted">{[item.effective_date ? `wirksam am ${formatDate(item.effective_date)}` : null, item.note, item.status !== "planned" ? STATUS_WORD[item.status] : null, item.reminder?.status === "open" ? `Erinnerung am ${formatDate(item.reminder.due_date)}` : null].filter(Boolean).join(" · ")}</span>
              {editable ? (confirmDelete === item.id
                ? <span className="dec-history-actions" role="group" aria-label={`Löschen von „${label}“ bestätigen`}>
                  <span>{item.reminder?.status === "open" ? `Wirklich löschen? Die Erinnerung am ${formatDate(item.reminder.due_date)} wird mit entfernt.` : "Wirklich löschen?"}</span>
                  <button type="button" className="rg-link dec-delete" disabled={busy} onClick={() => void remove(item)}>Endgültig löschen</button>
                  <button type="button" className="rg-link" onClick={() => setConfirmDelete(null)}>Abbrechen</button>
                </span>
                : <span className="dec-history-actions">
                  {item.status === "planned" || item.status === "in_progress" ? <>
                    <button type="button" className="rg-link" disabled={busy} onClick={() => void changeStatus(item, "completed")}>Abschließen</button>
                    <button type="button" className="rg-link" disabled={busy} onClick={() => void changeStatus(item, "cancelled")}>Stornieren</button>
                  </> : null}
                  <button type="button" className="rg-link" disabled={busy} aria-label={`${label} vom ${date} bearbeiten`} onClick={() => startEdit(item)}>Bearbeiten</button>
                  <button type="button" className="rg-link" disabled={busy} aria-label={`${label} vom ${date} löschen`} onClick={() => { setEditing(null); setConfirmDelete(item.id); }}>Löschen</button>
                </span>) : null}
            </li>;
          })}
        </ul> : null}
      </div> : null}
    </div>}
  </CollapsibleSection>;
}
