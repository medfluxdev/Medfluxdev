"use client";

import { FormEvent, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { formatDate } from "@/lib/format";
import {
  createContractLifecycleDecision,
  getContractLifecycle,
  updateContractLifecycleDecision,
  type ContractLifecycleDecision,
  type ContractLifecycleDecisionKind,
  type ContractLifecycleStatus,
} from "@/lib/domain-api/lifecycle";

interface Props { contractId: string; organizationSlug: string; }

const DECISIONS: [ContractLifecycleDecisionKind, string][] = [
  ["monitor", "Weiter beobachten"],
  ["renew", "Verlängern"],
  ["renegotiate", "Neu verhandeln"],
  ["terminate", "Kündigen"],
];

const STATUS_LABEL: Record<ContractLifecycleStatus, string> = {
  planned: "Geplant", in_progress: "In Bearbeitung", completed: "Abgeschlossen", cancelled: "Storniert",
};

export default function ContractLifecyclePanel({ contractId, organizationSlug }: Props) {
  const [items, setItems] = useState<ContractLifecycleDecision[]>([]);
  const [decision, setDecision] = useState<ContractLifecycleDecisionKind>("monitor");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    return getContractLifecycle(organizationSlug, contractId)
      .then((res) => setItems(res.items ?? []))
      .catch((err) => setError(err instanceof Error ? err.message : "Lifecycle konnte nicht geladen werden."));
  }

  useEffect(() => { void load(); }, [contractId, organizationSlug]);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const created = await createContractLifecycleDecision(organizationSlug, contractId, { decision, effective_date: effectiveDate || null, note: note || null });
      setItems((current) => [created, ...current]); setNote(""); setEffectiveDate("");
    } catch (err) { setError(err instanceof Error ? err.message : "Lifecycle-Entscheidung konnte nicht gespeichert werden."); }
    finally { setBusy(false); }
  }

  async function changeStatus(item: ContractLifecycleDecision, status: ContractLifecycleStatus) {
    setBusy(true); setError(null);
    try {
      const updated = await updateContractLifecycleDecision(organizationSlug, contractId, item.id, { status, effective_date: item.effective_date, note: item.note });
      setItems((current) => current.map((row) => row.id === updated.id ? updated : row));
    } catch (err) { setError(err instanceof Error ? err.message : "Lifecycle-Status konnte nicht geändert werden."); }
    finally { setBusy(false); }
  }

  return <section className="cw-section" aria-labelledby="lifecycle-heading">
    <div className="cw-section-head"><div><h2 id="lifecycle-heading">Vertragsentscheidung</h2><p>Operative Entscheidung getrennt von extrahierten Vertragsfakten.</p></div></div>
    {error ? <InlineAlert tone="warning" role="alert">{error}</InlineAlert> : null}
    <form className="form-grid cw-lifecycle-form" onSubmit={submit}>
      <label>Entscheidung<select value={decision} onChange={(e) => setDecision(e.target.value as ContractLifecycleDecisionKind)}>{DECISIONS.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Wirksam am<input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} /></label>
      <label className="form-field-wide">Notiz<textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></label>
      <div><Button type="submit" variant="primary" disabled={busy}>Entscheidung anlegen</Button></div>
    </form>
    <div className="cw-task-list">
      {items.map((item) => <div className="cw-task" key={item.id}><div><strong>{DECISIONS.find(([value]) => value === item.decision)?.[1] ?? item.decision}</strong><p>{item.note || "Keine Notiz"}</p><small>{item.actor_display_name}{item.effective_date ? ` · ${formatDate(item.effective_date)}` : ""}</small></div><span>{STATUS_LABEL[item.status]}</span><div className="button-row">{item.status === "planned" ? <Button size="sm" disabled={busy} onClick={() => void changeStatus(item, "in_progress")}>Starten</Button> : null}{item.status === "in_progress" ? <Button size="sm" variant="primary" disabled={busy} onClick={() => void changeStatus(item, "completed")}>Abschließen</Button> : null}{!["completed","cancelled"].includes(item.status) ? <Button size="sm" disabled={busy} onClick={() => void changeStatus(item, "cancelled")}>Stornieren</Button> : null}</div></div>)}
      {items.length === 0 ? <p className="cw-muted">Noch keine operative Lifecycle-Entscheidung.</p> : null}
    </div>
  </section>;
}
