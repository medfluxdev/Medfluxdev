"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import PageHeader from "@/components/ui/PageHeader";
import { formatDate } from "@/lib/format";
import { listDeadlines, type DeadlineDto, type DeadlineStatus } from "@/lib/domain-api/deadlines";

const HORIZONS = [
  { value: "30", label: "30 Tage" },
  { value: "90", label: "90 Tage" },
  { value: "180", label: "6 Monate" },
  { value: "", label: "Alle" },
];

function isoInDays(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export default function DeadlinesPage() {
  const { organizationSlug } = useAuth();
  const [items, setItems] = useState<DeadlineDto[] | null>(null);
  const [mine, setMine] = useState(false);
  const [horizon, setHorizon] = useState("90");
  const [status, setStatus] = useState<DeadlineStatus | "all">("open");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!organizationSlug) return;
    try {
      const data = await listDeadlines(organizationSlug, { status, mine, dueBefore: horizon ? isoInDays(Number(horizon)) : undefined });
      setItems(data.items);
      setError(null);
    } catch (caught) {
      setItems([]);
      setError(caught instanceof Error ? caught.message : "Termine konnten nicht geladen werden.");
    }
  }, [horizon, mine, organizationSlug, status]);

  useEffect(() => { void load(); }, [load]);

  if (!organizationSlug) return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;

  const overdue = (items ?? []).filter((item) => item.overdue).length;

  return <div className="page">
    <PageHeader title="Termine" description="Kündigungsfristen, Vertragsenden und Wiedervorlagen aller sichtbaren Verträge." />
    <section className="cw-section">
      <div className="rg-toolbar">
        <label className="rg-check"><input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} />Nur meine</label>
        <label>Zeitraum <select value={horizon} onChange={(event) => setHorizon(event.target.value)}>{HORIZONS.map((item) => <option key={item.label} value={item.value}>{item.label}</option>)}</select></label>
        <label>Status <select value={status} onChange={(event) => setStatus(event.target.value as DeadlineStatus | "all")}><option value="open">Offen</option><option value="done">Erledigt</option><option value="cancelled">Abgebrochen</option><option value="all">Alle</option></select></label>
        {overdue > 0 ? <span className="cw-badge cw-badge-red">{overdue} überfällig</span> : null}
      </div>
    </section>
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    <section className="cw-section">
      {items === null ? <p role="status">Termine werden geladen…</p> : items.length === 0 ? <p className="cw-muted">Keine Termine im gewählten Zeitraum.</p> : <div style={{ overflowX: "auto" }}><table className="rg-table">
        <thead><tr><th scope="col">Fällig</th><th scope="col">Termin</th><th scope="col">Vertrag</th><th scope="col">Zuständig</th><th scope="col">Erinnerung</th><th scope="col">Hinweis</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.id} className={item.overdue ? "rg-row-overdue" : undefined}>
          <td>{formatDate(item.due_date)}{item.overdue ? <span className="contract-business-status">überfällig</span> : null}</td>
          <th scope="row">{item.title}{item.todo_text ? <span className="contract-business-status">{item.todo_text}</span> : null}</th>
          <td><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.contract_label ?? "Vertrag"}</Link></td>
          <td>{item.assignee_name ?? "Vertragsverantwortliche/r"}</td>
          <td>{formatDate(item.remind_on)}</td>
          <td>{item.basis_unconfirmed ? "Ungeprüfte KI-Werte" : item.source === "system" ? "Berechnet" : "Manuell"}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>
  </div>;
}
