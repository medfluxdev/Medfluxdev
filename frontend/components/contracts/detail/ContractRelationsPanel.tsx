"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import AiOrigin, { AiReviewContext } from "@/components/ui/AiOrigin";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Signal from "@/components/ui/Signal";
import { registerHref } from "@/lib/fix-targets";
import { BUSINESS_STATUS_LABEL, type BusinessStatus } from "@/lib/domain-api/register";
import {
  getContractRelations,
  linkFramework,
  unlinkFramework,
  type ContractRelationsDto,
  type RelatedContractDto,
} from "@/lib/domain-api/contractDocuments";

const svg = (body: JSX.Element) => <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const LINK_ICON = svg(<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />);
const GEAR_ICON = svg(<path d="M12 9a3 3 0 1 1 0 6a3 3 0 1 1 0-6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />);

export default function ContractRelationsPanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [data, setData] = useState<ContractRelationsDto | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await getContractRelations(orgSlug, contractId);
      setData({ ...result, frameworks: result?.frameworks ?? [], members: result?.members ?? [], framework_options: result?.framework_options ?? [] });
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
        {!item.confirmed ? <AiReviewContext.Provider value={null}><AiOrigin state="unreviewed" subject="Zuordnung zum Rahmenvertrag" detail="Bitte bestätigen oder verwerfen" /></AiReviewContext.Provider> : null}
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
  const confirmed = data.frameworks.filter((item) => item.confirmed);
  const state = confirmed.length ? { label: "Zugeordnet", tone: "done" as const } : data.frameworks.length ? { label: "KI-Vorschlag", tone: "ai" as const } : { label: "Nicht zugeordnet", tone: "neutral" as const };
  const manageHref = registerHref([{ column: "is_framework", op: "is", value: true }]);

  return <div className="rg-panel">
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    <CollapsibleSection id="relations-framework" title="Rahmenvertrag" icon={LINK_ICON} iconClassName="section-tile--type" description={<Signal tone={state.tone} size="sm">{state.label}</Signal>}
      actions={<Link className="btn" href={manageHref}>{GEAR_ICON}Rahmenverträge verwalten</Link>}>
      <div className="rel-main">
        {data.frameworks.length === 0
          ? <p className="rel-lead">{options.length ? "Kein Rahmenvertrag zugeordnet." : "Kein Rahmenvertrag zugeordnet – noch keiner verfügbar."}</p>
          : <ul className="rg-deadlines">{data.frameworks.map(row)}</ul>}
        {editable && options.length ? <form className="rel-link-form" onSubmit={(event) => { event.preventDefault(); if (selected) void run(() => linkFramework(orgSlug, contractId, selected)); }}>
          <label>Rahmenvertrag auswählen<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">Bitte auswählen</option>{options.map((item) => <option key={item.contract_id} value={item.contract_id}>{item.register_number ?? "–"} · {item.short_description ?? "Vertrag"}</option>)}</select></label>
          <button type="submit" className="btn btn-primary" disabled={busy || !selected}>Verknüpfen</button>
        </form> : null}
      </div>
    </CollapsibleSection>
    {data.is_framework || data.members.length > 0 ? <CollapsibleSection id="relations-members" title="Einzelverträge dieses Rahmenvertrags" icon={LINK_ICON} iconClassName="section-tile--type" description={<Signal tone="neutral" size="sm">{`${data.members.length} zugeordnet`}</Signal>}>
      <div className="rel-main">
        {data.members.length === 0 ? <p className="rel-lead">Noch keine Einzelverträge zugeordnet.</p> : <ul className="rg-deadlines">{data.members.map(row)}</ul>}
      </div>
    </CollapsibleSection> : null}
  </div>;
}
