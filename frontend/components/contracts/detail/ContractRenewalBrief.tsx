"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { createContractLifecycleDecision, type ContractLifecycleDecisionKind } from "@/lib/domain-api/lifecycle";
import { getRenewalBrief, getRenewalSummary, type RenewalBrief, type RenewalUrgency } from "@/lib/domain-api/registerGrid";
import { formatCurrency, formatDate } from "@/lib/format";

export const URGENCY: Record<RenewalUrgency, { label: string; tone: string }> = {
  missed: { label: "Frist verstrichen", tone: "cw-badge-red" },
  critical: { label: "Dringend (≤ 30 Tage)", tone: "cw-badge-red" },
  soon: { label: "Bald (≤ 90 Tage)", tone: "cw-badge-amber" },
  planned: { label: "Geplant", tone: "" },
  unknown: { label: "Frist unbekannt", tone: "" },
  none: { label: "Keine offene Frist", tone: "" },
};

const DECISIONS: { key: ContractLifecycleDecisionKind; label: string }[] = [
  { key: "renew", label: "Verlängern" },
  { key: "renegotiate", label: "Neu verhandeln" },
  { key: "terminate", label: "Kündigen" },
  { key: "monitor", label: "Beobachten" },
];

const HINT_LABEL = { action: "Handlungsbedarf", check: "Prüfen", info: "Hinweis" } as const;

export default function ContractRenewalBrief({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [brief, setBrief] = useState<RenewalBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<{ decision: ContractLifecycleDecisionKind; note: string } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ loading: boolean; text: string | null; note: string | null }>({ loading: false, text: null, note: null });

  const load = useCallback(async () => {
    try {
      setBrief(await getRenewalBrief(orgSlug, contractId));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Entscheidungsvorlage konnte nicht geladen werden.");
    }
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);

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
      setSummary({ loading: false, text: null, note: err instanceof Error && err.message ? err.message : "Die Kurzfassung konnte nicht erstellt werden." });
    }
  }

  async function record() {
    if (!form) return;
    try {
      await createContractLifecycleDecision(orgSlug, contractId, { decision: form.decision, status: "planned", note: form.note.trim() || null });
      setForm(null);
      setMessage("Entscheidung erfasst.");
      await load();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Entscheidung konnte nicht gespeichert werden.");
    }
  }

  if (error) return <section className="cw-section"><p role="alert" className="rg-error">{error}</p></section>;
  if (!brief) return <section className="cw-section" aria-busy="true"><p role="status">Entscheidungsvorlage wird geladen…</p></section>;

  const urgency = URGENCY[brief.urgency];

  return <section className="cw-section" aria-labelledby="renewal-heading">
    <div className="cw-section-head"><div>
      <h2 id="renewal-heading">Entscheidungsvorlage zur Kündigungsfrist</h2>
      <p>Fakten und Beträge sind aus Stammdaten und Finanzdaten berechnet. Die Hinweise sind Beratung – entschieden wird von Ihnen.</p>
    </div><span className={`cw-badge ${urgency.tone}`}>{urgency.label}</span></div>

    <div className="rg-terms">
      <div><span>Kündbar bis</span><strong>{formatDate(brief.cancel_by)}</strong>{brief.days_left != null ? <small className="cw-muted">{brief.days_left >= 0 ? `noch ${brief.days_left} Tage` : `seit ${-brief.days_left} Tagen verstrichen`}</small> : null}</div>
      <div><span>Aktuelles Ende</span><strong>{formatDate(brief.current_end)}</strong></div>
      <div><span>Jährliche Kosten</span><strong>{brief.annual_cost ? formatCurrency(brief.annual_cost, "EUR") : "nicht gepflegt"}</strong></div>
      <div><span>Kosten bei Verlängerung</span><strong>{brief.renewal_cost ? formatCurrency(brief.renewal_cost, "EUR") : "–"}</strong>{brief.next_end_if_no_action ? <small className="cw-muted">bis {formatDate(brief.next_end_if_no_action)}</small> : null}</div>
    </div>
    <p><strong>Ohne Handeln:</strong> {brief.if_no_action}</p>

    <div className="renewal-summary">
      <button type="button" className="btn" disabled={summary.loading} onClick={() => void summarize()}>{summary.loading ? "Kurzfassung wird erstellt…" : "Kurzfassung mit lokaler KI"}</button>
      {summary.text ? <blockquote>{summary.text}</blockquote> : null}
      {summary.note ? <p className="cw-muted" role="status">{summary.note}</p> : null}
    </div>

    {brief.hints.length > 0 ? <ul className="renewal-hints">
      {brief.hints.map((hint) => <li key={hint.text} className={`renewal-hint renewal-${hint.kind}`}>
        <span className="renewal-kind">{HINT_LABEL[hint.kind]}</span>
        <div>{hint.text}<small className="cw-muted">Grundlage: {hint.reason}</small></div>
      </li>)}
    </ul> : null}

    {brief.partner_contracts.length > 0 ? <details><summary>Weitere Verträge mit {brief.partner} ({brief.partner_contracts.length})</summary>
      <ul className="hist-details">{brief.partner_contracts.map((item) => <li key={item.contract_id}><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link></li>)}</ul>
    </details> : null}

    <div className="renewal-decision">
      {brief.decision ? <p><strong>Erfasste Entscheidung:</strong> {brief.decision.label} ({brief.decision.status === "planned" ? "geplant" : brief.decision.status === "in_progress" ? "in Arbeit" : "erledigt"}) · {brief.decision.by}{brief.decision.at ? `, ${formatDate(brief.decision.at)}` : ""}{brief.decision.note ? ` – ${brief.decision.note}` : ""}</p> : <p className="cw-muted">Noch keine Entscheidung erfasst.</p>}
      {editable && !form ? <div className="rg-actions">{DECISIONS.map((item) => <button key={item.key} type="button" className="btn" onClick={() => setForm({ decision: item.key, note: "" })}>{item.label}</button>)}</div> : null}
      {form ? <form className="rg-transition" aria-label="Entscheidung erfassen" onSubmit={(event) => { event.preventDefault(); void record(); }}>
        <strong>Entscheidung: {DECISIONS.find((item) => item.key === form.decision)?.label}</strong>
        {form.decision === "terminate" ? <p className="rg-hint">Die Entscheidung wird nur erfasst. Die Kündigung selbst versenden Sie und dokumentieren sie anschließend über den Status „Gekündigt“.</p> : null}
        <label>Begründung (optional)<input maxLength={2000} value={form.note} onChange={(event) => setForm((current) => current && ({ ...current, note: event.target.value }))} /></label>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary">Entscheidung erfassen</button></div>
      </form> : null}
      {message ? <p role="status" className="rg-ok">{message}</p> : null}
    </div>
  </section>;
}
