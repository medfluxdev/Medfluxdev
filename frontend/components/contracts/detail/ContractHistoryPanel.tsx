"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import HistoryDetails from "@/components/history/HistoryDetails";
import { getContractHistory, type HistoryEntry } from "@/lib/domain-api/history";
import { formatDateTime } from "@/lib/format";

const KIND_FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "Alle" },
  { key: "contract", label: "Vertrag & Dokumente" },
  { key: "fact_review", label: "Prüfungen" },
  { key: "override", label: "Manuelle Werte" },
  { key: "deadline", label: "Termine & E-Mails" },
  { key: "finance", label: "Finanzen" },
];

export default function ContractHistoryPanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const allowed = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [items, setItems] = useState<HistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    getContractHistory(orgSlug, contractId)
      .then((result) => { if (!cancelled) setItems(result.items); })
      .catch(() => { if (!cancelled) setError("Die Historie konnte nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [allowed, contractId, orgSlug]);

  const visible = useMemo(() => (items ?? []).filter((item) => filter === "all" || item.category === filter), [filter, items]);

  if (!allowed) return <section className="cw-section"><p>Die Historie ist für Ihre Rolle nicht freigegeben.</p></section>;
  if (error) return <section className="cw-section"><p role="alert" className="rg-error">{error}</p></section>;
  if (!items) return <section className="cw-section" aria-busy="true"><p role="status">Historie wird geladen…</p></section>;

  return <section className="cw-section" aria-labelledby="hist-heading">
    <div className="cw-section-head"><div><h2 id="hist-heading">Historie</h2><p>Alle Änderungen, Prüfungen, Dokumente und versendeten Erinnerungen – neueste zuerst.</p></div></div>
    <div className="rg-tabs" role="group" aria-label="Historie filtern">
      {KIND_FILTERS.map((item) => <button key={item.key} type="button" aria-pressed={filter === item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>{item.label}</button>)}
    </div>
    {visible.length === 0 ? <p className="cw-muted">Keine Einträge.</p> : <ol className="hist-list">
      {visible.map((item) => <li key={item.id}>
        <time dateTime={item.at ?? undefined}>{item.at ? formatDateTime(item.at) : "–"}</time>
        <div><strong>{item.label}</strong> <span className="cw-muted">· {item.actor ?? "System"}</span><HistoryDetails details={item.details} fieldLabels={item.field_labels} /></div>
      </li>)}
    </ol>}
  </section>;
}
