"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ContractTable from "@/components/contracts/ContractTable";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/components/auth/AuthProvider";
import { listContracts, unarchiveContract } from "@/lib/domain-api/contracts";
import type { ContractListResponse } from "@/lib/contract-types";
import { formatDate } from "@/lib/format";

export default function ArchivPage() {
  const { organizationSlug } = useAuth();
  const requestSeq = useRef(0);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ContractListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    if (!organizationSlug) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await listContracts(organizationSlug, { archived: true, page_size: 100, page });
      if (seq === requestSeq.current) setData(result);
    } catch {
      if (seq !== requestSeq.current) return;
      setError("Archiv konnte nicht geladen werden.");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [organizationSlug, page]);

  useEffect(() => {
    void load();
    return () => { requestSeq.current += 1; };
  }, [load]);

  useEffect(() => { setPage(1); setData(null); }, [organizationSlug]);

  async function unarchive(contractId: string) {
    if (!organizationSlug) return;
    setBusyId(contractId);
    try {
      await unarchiveContract(contractId, organizationSlug);
      toast("Vertrag wieder ins aktive Portfolio verschoben.", "success");
      if (data?.items.length === 1 && page > 1) setPage((p) => p - 1);
      else await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Wiederherstellung fehlgeschlagen.", "error");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <PageHeader title="Archiv" description="Nicht-destruktiv abgelegte Verträge mit Wiederherstellung ins aktive Portfolio." />
      {error && <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>{error}</InlineAlert>}
      {loading && <LoadingState>Archiv wird geladen…</LoadingState>}
      {!loading && !error && data && (
        <section className="panel" aria-labelledby="archiv-heading">
          <div className="panel-head"><div><h2 id="archiv-heading">Archivierte Verträge</h2><p>Archivierung ist reversibel – es wird nichts gelöscht.</p></div></div>
          {data.items.length === 0 ? (
            <div className="state-box"><div className="state-icon">∅</div><h3>Keine archivierten Verträge</h3><p>Verträge erscheinen hier, sobald sie im Contract 360 ins Archiv verschoben wurden.</p></div>
          ) : (
            <div className="table-wrap"><ContractTable items={data.items} extraHeader="Archiviert" extra={(item) => <><span className="muted">{item.archived_at ? formatDate(item.archived_at) : "–"}</span>{" "}<button type="button" className="btn btn-sm" onClick={() => void unarchive(item.contract_id)} disabled={busyId === item.contract_id}>{busyId === item.contract_id ? "Wird…" : "Wiederherstellen"}</button></>} /></div>
          )}
          {(page > 1 || data.has_more) && (
            <nav className="pagination" aria-label="Archiv Seiten">
              <button type="button" className="btn btn-sm" disabled={loading || page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Zurück</button>
              <span>Seite {data.page}</span>
              <button type="button" className="btn btn-sm" disabled={loading || !data.has_more} onClick={() => setPage((p) => p + 1)}>Weiter</button>
            </nav>
          )}
        </section>
      )}
    </div>
  );
}
