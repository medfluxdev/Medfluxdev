"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import HistoryDetails from "@/components/history/HistoryDetails";
import { listContracts } from "@/lib/domain-api/contracts";
import { downloadHistoryCsv, listHistory, type HistoryFilters, type HistoryPage } from "@/lib/domain-api/history";
import type { ContractListItem } from "@/lib/contract-types";
import { formatDateTime } from "@/lib/format";

const PAGE_SIZE = 50;
const FILTER_KEYS: (keyof HistoryFilters)[] = ["account_id", "category", "contract_id", "date_from", "date_to"];

// Filter stehen in der Adresse, damit gefilterte Ansichten teilbar und per Zurueck erreichbar sind.
function filtersFromUrl(): { filters: HistoryFilters; offset: number } {
  const params = new URLSearchParams(window.location.search);
  const filters: HistoryFilters = {};
  for (const key of FILTER_KEYS) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  return { filters, offset: Math.max(0, Number(params.get("offset")) || 0) };
}

function writeUrl(filters: HistoryFilters, offset: number) {
  const params = new URLSearchParams(window.location.search);
  for (const key of FILTER_KEYS) {
    if (filters[key]) params.set(key, filters[key] as string);
    else params.delete(key);
  }
  if (offset) params.set("offset", String(offset));
  else params.delete("offset");
  const query = params.toString();
  window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

export default function OrganizationHistory({ organizationSlug }: { organizationSlug: string }) {
  const { role, account } = useAuth();
  const canExport = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [filters, setFilters] = useState<HistoryFilters>({});
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<HistoryPage | null>(null);
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const initial = filtersFromUrl();
    setFilters(initial.filters);
    setOffset(initial.offset);
    setReady(true);
  }, []);

  useEffect(() => { if (ready) writeUrl(filters, offset); }, [filters, offset, ready]);

  const load = useCallback(async () => {
    if (!ready) return;
    setLoading(true);
    setError(null);
    try {
      setPage(await listHistory(organizationSlug, filters, { limit: PAGE_SIZE, offset }));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Historie konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [filters, offset, organizationSlug, ready]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    let cancelled = false;
    listContracts(organizationSlug, { page_size: 100 })
      .then((result) => { if (!cancelled) setContracts(result.items); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [organizationSlug]);

  function update(key: keyof HistoryFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value || undefined }));
    setOffset(0);
  }

  async function exportCsv() {
    try {
      const { blob, filename } = await downloadHistoryCsv(organizationSlug, filters);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename ?? "historie.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Export fehlgeschlagen.");
    }
  }

  const total = page?.total ?? 0;

  return <div className="rg-panel">
    <form className="cw-section hist-filters" aria-label="Historie filtern" onSubmit={(event) => event.preventDefault()}>
      <label>Benutzer<select value={filters.account_id ?? ""} onChange={(event) => update("account_id", event.target.value)}>
        <option value="">Alle</option>
        {(page?.actors ?? []).map((item) => <option key={item.account_id} value={item.account_id}>{item.display_name}</option>)}
      </select></label>
      <label>Bereich<select value={filters.category ?? ""} onChange={(event) => update("category", event.target.value)}>
        <option value="">Alle</option>
        {(page?.categories ?? []).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
      </select></label>
      <label>Vertrag<select value={filters.contract_id ?? ""} onChange={(event) => update("contract_id", event.target.value)}>
        <option value="">Alle</option>
        {contracts.map((item) => <option key={item.contract_id} value={item.contract_id}>{item.register_number ?? item.contract_number ?? "–"} · {item.contract_title ?? item.supplier ?? "ohne Titel"}</option>)}
      </select></label>
      <label>Von<input type="date" value={filters.date_from ?? ""} onChange={(event) => update("date_from", event.target.value)} /></label>
      <label>Bis<input type="date" value={filters.date_to ?? ""} onChange={(event) => update("date_to", event.target.value)} /></label>
      <div className="rg-actions">
        <button type="button" className="btn" onClick={() => { setFilters({}); setOffset(0); }}>Zurücksetzen</button>
        {canExport ? <button type="button" className="btn" onClick={() => void exportCsv()}>CSV exportieren</button> : null}
      </div>
    </form>

    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {loading && !page ? <p role="status">Historie wird geladen…</p> : null}

    {page ? <section className="cw-section" aria-labelledby="org-hist-heading" aria-busy={loading}>
      <div className="cw-section-head"><div><h2 id="org-hist-heading">Protokoll</h2><p>{total === 0 ? "Keine Einträge für diese Auswahl." : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} von ${total} Einträgen`}</p></div></div>
      {page.items.length > 0 ? <table className="rg-table hist-table">
        <thead><tr><th scope="col">Zeitpunkt</th><th scope="col">Benutzer</th><th scope="col">Aktion</th><th scope="col">Vertrag</th></tr></thead>
        <tbody>{page.items.map((item) => <tr key={item.id}>
          <td>{item.at ? formatDateTime(item.at) : "–"}</td>
          <td>{item.actor ?? "System"}</td>
          <th scope="row">{item.label}<HistoryDetails details={item.details} /></th>
          <td>{item.object_type === "contract" && item.object_id ? <Link href={`/contracts/${item.object_id}?tab=history`}>{item.contract_number ?? "Vertrag"}{item.contract_title ? ` · ${item.contract_title}` : ""}</Link> : "–"}</td>
        </tr>)}</tbody>
      </table> : null}
      {total > PAGE_SIZE ? <div className="rg-actions">
        <button type="button" className="btn" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(offset - PAGE_SIZE, 0))}>Zurück</button>
        <button type="button" className="btn" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>Weiter</button>
      </div> : null}
    </section> : null}
  </div>;
}
