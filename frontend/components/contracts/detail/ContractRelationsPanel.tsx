"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { BUSINESS_STATUS_LABEL, type BusinessStatus } from "@/lib/domain-api/register";
import {
  getContractRelations,
  linkFramework,
  unlinkFramework,
  type ContractRelationsDto,
  type RelatedContractDto,
} from "@/lib/domain-api/contractDocuments";

export default function ContractRelationsPanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [data, setData] = useState<ContractRelationsDto | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getContractRelations(orgSlug, contractId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verknüpfungen konnten nicht geladen werden.");
    }
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<ContractRelationsDto>) {
    setBusy(true);
    setError(null);
    try {
      setData(await action());
      setSelected("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  function row(item: RelatedContractDto) {
    return <li key={item.relation_id} className="rg-deadline">
      <div className="rg-deadline-main">
        <Link href={`/contracts/${item.contract_id}`}><strong>{item.register_number ?? "ohne Nummer"} · {item.short_description ?? "Vertrag"}</strong></Link>
        <span className="cw-muted">{item.business_status ? BUSINESS_STATUS_LABEL[item.business_status as BusinessStatus] ?? item.business_status : ""}{item.rationale ? ` · ${item.rationale}` : ""}</span>
        {!item.confirmed ? <span className="rg-origin rg-origin-ai">KI-Vorschlag – bitte bestätigen</span> : null}
      </div>
      {editable ? <div className="rg-actions">
        {!item.confirmed ? <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run(() => linkFramework(orgSlug, contractId, item.contract_id))}>Bestätigen</button> : null}
        <button type="button" className="btn" disabled={busy} onClick={() => void run(() => unlinkFramework(orgSlug, contractId, item.relation_id))}>{item.confirmed ? "Verknüpfung lösen" : "Verwerfen"}</button>
      </div> : null}
    </li>;
  }

  if (!data) return <section className="cw-section"><p role={error ? "alert" : "status"}>{error ?? "Verknüpfungen werden geladen…"}</p></section>;

  const linked = new Set(data.frameworks.map((item) => item.contract_id));
  const options = data.framework_options.filter((item) => !linked.has(item.contract_id));

  return <div className="rg-panel">
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    <section className="cw-section" aria-labelledby="relations-framework-heading">
      <div className="cw-section-head"><div><h2 id="relations-framework-heading">Gehört zu Rahmenvertrag</h2><p>Einzelverträge werden ihrem Rahmenvertrag zugeordnet. Erkennt die KI eine Referenz im Dokument, erscheint sie als Vorschlag.</p></div></div>
      {data.frameworks.length === 0 ? <p className="cw-muted">Keinem Rahmenvertrag zugeordnet.</p> : <ul className="rg-deadlines">{data.frameworks.map(row)}</ul>}
      {editable ? <form className="rg-form-grid mt-3" onSubmit={(event) => { event.preventDefault(); if (selected) void run(() => linkFramework(orgSlug, contractId, selected)); }}>
        <label className="span-2">Rahmenvertrag auswählen<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">{options.length ? "Bitte auswählen" : "Keine Rahmenverträge verfügbar"}</option>{options.map((item) => <option key={item.contract_id} value={item.contract_id}>{item.register_number ?? "–"} · {item.short_description ?? "Vertrag"}</option>)}</select></label>
        <button type="submit" className="btn btn-primary" disabled={busy || !selected}>Verknüpfen</button>
      </form> : null}
    </section>
    {data.is_framework || data.members.length > 0 ? <section className="cw-section" aria-labelledby="relations-members-heading">
      <div className="cw-section-head"><div><h2 id="relations-members-heading">Einzelverträge dieses Rahmenvertrags</h2><p>{data.members.length} zugeordnet</p></div></div>
      {data.members.length === 0 ? <p className="cw-muted">Noch keine Einzelverträge zugeordnet.</p> : <ul className="rg-deadlines">{data.members.map(row)}</ul>}
    </section> : null}
  </div>;
}
