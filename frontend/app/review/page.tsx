"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import ContractTable from "@/components/contracts/ContractTable";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import { listContracts } from "@/lib/domain-api/contracts";
import type { ContractListResponse } from "@/lib/contract-types";

export default function ReviewPage() {
  const { organizationSlug } = useAuth();
  const requestSeq = useRef(0);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ContractListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const result = await listContracts(organizationSlug, { requires_review: true, page_size: 100, page });
      if (seq === requestSeq.current) setData(result);
    } catch {
      if (seq !== requestSeq.current) return;
      setError("Prüfungsliste konnte nicht geladen werden.");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [organizationSlug, page]);

  useEffect(() => {
    void load();
    return () => { requestSeq.current += 1; };
  }, [load]);

  useEffect(() => { setPage(1); setData(null); }, [organizationSlug]);

  return (
    <div className="page">
      <PageHeader title="Prüfungen" description="Manuelle Prüfung materialer Vertragsangaben und faktengenauer Quellenbelege." />
      {error && <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>{error}</InlineAlert>}
      {loading && <LoadingState>Prüfungsliste wird geladen…</LoadingState>}
      {!loading && !error && data && (
        <section className="panel" aria-labelledby="review-heading">
          <div className="panel-head"><div><h2 id="review-heading">Zu prüfende Verträge</h2><p>{data.total_count} {data.total_count === 1 ? "Vertrag" : "Verträge"} benötigen eine manuelle Prüfung der extrahierten Fakten.</p></div></div>
          {data.items.length === 0 ? (
            <div className="state-box"><div className="state-icon">✓</div><h3>Keine offenen Prüfungen</h3><p>Alle aktiven Verträge sind geprüft – es liegt kein manueller Prüfbedarf vor.</p></div>
          ) : (
            <div className="table-wrap"><ContractTable items={data.items} extraHeader="Prüfung" extra={(item) => <Link className="btn btn-sm btn-primary" href={`/contracts/${item.contract_id}?tab=documents&subtab=review`}>Prüfen</Link>} /></div>
          )}
          {(page > 1 || data.has_more) && (
            <nav className="pagination" aria-label="Prüfungsliste Seiten">
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
