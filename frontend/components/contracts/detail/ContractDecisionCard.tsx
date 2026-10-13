"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import EmptyState from "@/components/ui/EmptyState";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import { PersonTag } from "@/components/ui/TagChip";
import { useToast } from "@/components/ui/Toast";
import { FINANCE_ENTRIES_TARGET, asFixTarget, contractHref, fixLabel } from "@/lib/fix-targets";
import { formatCurrency, formatDate } from "@/lib/format";
import {
  createContractLifecycleDecision,
  getContractLifecycle,
  updateContractLifecycleDecision,
  type ContractLifecycleDecision,
  type ContractLifecycleDecisionKind,
  type ContractLifecycleStatus,
} from "@/lib/domain-api/lifecycle";
import { getRenewalBrief, getRenewalSummary, type RenewalBrief, type RenewalUrgency } from "@/lib/domain-api/registerGrid";

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

const STATUS_WORD: Record<ContractLifecycleStatus, string> = {
  planned: "geplant", in_progress: "in Bearbeitung", completed: "abgeschlossen", cancelled: "storniert",
};

const HINT_LABEL = { action: "Handlungsbedarf", check: "Prüfen", info: "Hinweis" } as const;

const SCALE_ICON = <svg viewBox="0 0 24 24" focusable="false"><path d="M12 3v18M7 21h10M5 7h14M5 7l-3 6a3 3 0 0 0 6 0L5 7M19 7l-3 6a3 3 0 0 0 6 0l-3-6" /></svg>;

/** Status im Kopf: verstrichen = kritisch, ≤ 30 Tage = prüfen (wie „Kündigungsentscheidungen“), sonst ruhig. */
export function deadlineSignal(brief: Pick<RenewalBrief, "urgency" | "days_left">): { tone: SignalTone; label: string } {
  const days = brief.days_left;
  if (brief.urgency === "missed") return { tone: "critical", label: "Frist überschritten" };
  if (brief.urgency === "none") return { tone: "neutral", label: "Keine offene Frist" };
  if (brief.urgency === "unknown" || days == null) return { tone: "neutral", label: "Frist unbekannt" };
  const label = days === 0 ? "Frist heute" : days === 1 ? "Frist in 1 Tag" : `Frist in ${days} Tagen`;
  return { tone: brief.urgency === "critical" ? "warning" : "neutral", label };
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * Fristen & Aufgaben → „Entscheidung“: was zum nächsten Termin mit dem Vertrag passieren soll.
 * Fakten und Beträge berechnet das Backend (Entscheidungsvorlage); gespeichert wird über die Lifecycle-API.
 */
export default function ContractDecisionCard({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const toast = useToast();
  const [brief, setBrief] = useState<RenewalBrief | null>(null);
  const [decisions, setDecisions] = useState<ContractLifecycleDecision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<{ decision: ContractLifecycleDecisionKind; effective: string; note: string } | null>(null);
  const [busy, setBusy] = useState(false);
  // Nach „Kündigen“: die Kündigung selbst wird über den Status „Gekündigt“ dokumentiert.
  const [terminated, setTerminated] = useState(false);
  const [summary, setSummary] = useState<{ loading: boolean; text: string | null; note: string | null }>({ loading: false, text: null, note: null });
  const effectiveRef = useRef<HTMLInputElement | null>(null);

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
    setForm((current) => current?.decision === decision ? null : { decision, effective: current?.effective ?? brief?.current_end ?? "", note: current?.note ?? "" });
  }

  async function save() {
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      await createContractLifecycleDecision(orgSlug, contractId, { decision: form.decision, status: "planned", effective_date: form.effective || null, note: form.note.trim() || null });
      setTerminated(form.decision === "terminate");
      setForm(null);
      toast("Entscheidung gespeichert.", "success");
      await load();
    } catch (err) {
      setError(errorText(err, "Die Entscheidung konnte nicht gespeichert werden."));
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
    } catch (err) {
      setError(errorText(err, "Der Status der Entscheidung konnte nicht geändert werden."));
    } finally {
      setBusy(false);
    }
  }

  async function summarize() {
    setSummary({ loading: true, text: null, note: null });
    try {
      const result = await getRenewalSummary(orgSlug, contractId);
      setSummary({
        loading: false,
        text: result.available ? result.text : null,
        note: result.available ? `Lokale KI${result.model ? ` (${result.model})` : ""} – formuliert nur die obigen Fakten um; jede Zahl wurde gegen die Fakten geprüft.` : result.message,
      });
    } catch (err) {
      setSummary({ loading: false, text: null, note: errorText(err, "Die Kurzfassung konnte nicht erstellt werden.") });
    }
  }

  const signal = brief ? deadlineSignal(brief) : null;
  const sorted = [...(decisions ?? [])].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));

  return <CollapsibleSection
    id="dec"
    title="Entscheidung"
    description="Was soll mit dem Vertrag zum nächsten Termin passieren?"
    icon={SCALE_ICON}
    iconClassName="section-tile--accent"
    actions={signal ? <Signal tone={signal.tone}>{signal.label}</Signal> : null}
  >
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {!brief ? (error ? null : <p role="status" aria-busy="true">Entscheidung wird geladen…</p>) : <div className="dec-body">
      <dl className="dec-kpis">
        <div className="dec-kpi"><dt>Kündbar bis</dt><dd><span className={brief.cancel_by ? "num dec-value" : "dec-value dec-none"}>{brief.cancel_by ? formatDate(brief.cancel_by) : "–"}</span>{brief.cancel_by && brief.days_left != null ? <small>{brief.days_left >= 0 ? `noch ${brief.days_left} Tage` : `seit ${-brief.days_left} Tagen verstrichen`}</small> : null}</dd></div>
        <div className="dec-kpi"><dt>Vertragsende</dt><dd><span className={brief.current_end ? "num dec-value" : "dec-value dec-none"}>{brief.current_end ? formatDate(brief.current_end) : "–"}</span></dd></div>
        <div className="dec-kpi"><dt>Jährliche Kosten</dt><dd><span className={brief.annual_cost ? "num dec-value" : "dec-value dec-none"}>{brief.annual_cost ? formatCurrency(brief.annual_cost, "EUR") : "–"}</span>{brief.annual_cost ? null : <Link className="rg-link" href={contractHref(contractId, FINANCE_ENTRIES_TARGET)}>Kosten erfassen</Link>}</dd></div>
        <div className="dec-kpi"><dt>Kosten bei Verlängerung</dt><dd><span className={brief.renewal_cost ? "num dec-value" : "dec-value dec-none"}>{brief.renewal_cost ? formatCurrency(brief.renewal_cost, "EUR") : "–"}</span>{brief.renewal_cost && brief.next_end_if_no_action ? <small>bis {formatDate(brief.next_end_if_no_action)}</small> : null}</dd></div>
      </dl>

      <div className="dec-sentence">
        <span><strong>Ohne Handeln:</strong> {brief.if_no_action}</span>
        <button type="button" className="btn btn-sm" disabled={summary.loading} onClick={() => void summarize()}>{summary.loading ? "Kurzfassung wird erstellt…" : "Kurzfassung mit lokaler KI"}</button>
      </div>
      {summary.text ? <blockquote className="dec-summary">{summary.text}</blockquote> : null}
      {summary.note ? <p className="cw-muted" role="status">{summary.note}</p> : null}
      {brief.urgency === "unknown" ? <p className="cw-muted">Ohne vollständige Laufzeitangaben ist keine Frist berechenbar. <Link className="rg-link" href={contractHref(contractId, { tab: "register", section: "term" })}>Laufzeit erfassen</Link></p> : null}

      {brief.hints.length > 0 ? <ul className="dec-hints">
        {brief.hints.map((hint) => {
          const target = asFixTarget(hint.target);
          return <li key={hint.text}>
            <span className="dec-hint-kind">{HINT_LABEL[hint.kind]}</span>
            <span>{hint.text} <small className="cw-muted">Grundlage: {hint.reason}</small></span>
            {target ? <Link className="rg-link" href={contractHref(contractId, target)}>{fixLabel(target)}</Link> : null}
          </li>;
        })}
      </ul> : null}
      {brief.partner_contracts.length > 0 ? <details className="dec-partners"><summary>Weitere Verträge mit {brief.partner} ({brief.partner_contracts.length})</summary>
        <ul>{brief.partner_contracts.map((item) => <li key={item.contract_id}><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link></li>)}</ul>
      </details> : null}

      {editable ? <div className="dec-seg" role="group" aria-label="Entscheidung">
        {DECISIONS.map((item) => <button key={item.key} type="button" aria-pressed={form?.decision === item.key} onClick={() => choose(item.key)}>{item.label}</button>)}
      </div> : null}
      {form ? <form className="dec-form" aria-label={`Entscheidung: ${DECISIONS.find((item) => item.key === form.decision)?.label}`} onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <div className="dec-field"><label htmlFor="dec-effective">Wirksam am</label><input ref={effectiveRef} id="dec-effective" className="num" type="date" value={form.effective} onChange={(event) => setForm((current) => current && ({ ...current, effective: event.target.value }))} /></div>
        <div className="dec-field dec-full"><label htmlFor="dec-note">Notiz</label><textarea id="dec-note" rows={3} maxLength={2000} placeholder="Begründung, Ansprechpartner, nächste Schritte …" value={form.note} onChange={(event) => setForm((current) => current && ({ ...current, note: event.target.value }))} /></div>
        {form.decision === "terminate" ? <p className="rg-hint dec-full">Die Entscheidung wird nur erfasst. Die Kündigung selbst versenden Sie und dokumentieren sie anschließend über den Status „Gekündigt“.</p> : null}
        <div className="rg-actions dec-full"><button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Entscheidung speichern</button></div>
      </form> : null}

      {terminated && brief.business_status !== "gekuendigt" && brief.business_status !== "beendet" ? <p className="dec-followup" role="status">
        Kündigung versendet? Dann den Vertrag auf „Gekündigt“ setzen – mit Datum der Kündigung und Wirksamkeit.{" "}
        <Link className="rg-link" href={contractHref(contractId, { tab: "register", section: "status" })}>Status auf „Gekündigt“ setzen</Link>
      </p> : null}

      <div className="dec-history">
        <h3>Bisherige Entscheidungen</h3>
        {decisions === null ? <p role="status">Wird geladen…</p> : sorted.length === 0 ? <EmptyState variant="calm">Noch keine Entscheidung erfasst.</EmptyState> : <ul aria-label="Bisherige Entscheidungen">
          {sorted.map((item) => <li key={item.id} className="dec-history-row">
            <span className="num">{item.created_at ? formatDate(item.created_at) : "–"}</span>
            <Signal tone="neutral" size="sm">{DECISIONS.find((entry) => entry.key === item.decision)?.label ?? item.decision}</Signal>
            <PersonTag name={item.actor_display_name} />
            <span className="cw-muted">{[item.effective_date ? `wirksam am ${formatDate(item.effective_date)}` : null, item.note, item.status !== "planned" ? STATUS_WORD[item.status] : null].filter(Boolean).join(" · ")}</span>
            {editable && (item.status === "planned" || item.status === "in_progress") ? <span className="dec-history-actions">
              <button type="button" className="rg-link" disabled={busy} onClick={() => void changeStatus(item, "completed")}>Abschließen</button>
              <button type="button" className="rg-link" disabled={busy} onClick={() => void changeStatus(item, "cancelled")}>Stornieren</button>
            </span> : null}
          </li>)}
        </ul>}
      </div>
    </div>}
  </CollapsibleSection>;
}
