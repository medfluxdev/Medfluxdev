"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ContractWorkspace from "@/components/contracts/detail/ContractWorkspace";
import { apiGet } from "@/lib/api";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

export default function ContractDetailPage() {
  const params = useParams<{ "contract-id": string }>();
  const contractId = params?.["contract-id"] ?? "";

  const [data, setData] = useState<ContractDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(false);
    apiGet<ContractDetailResponse>(
      `/api/contracts/${encodeURIComponent(contractId)}?organization_slug=${encodeURIComponent(ORG_SLUG)}`
    )
      .then((res) => setData(res))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);

  return (
    <div className="page">
      {!data && loading && <p className="state-loading">Vertrag wird geladen…</p>}

      {!data && error && !loading && (
        <div className="alert alert--critical" role="alert">
          <span>Vertrag konnte nicht geladen werden.</span>
          <button className="btn btn-sm retry" type="button" onClick={load}>
            Erneut laden
          </button>
        </div>
      )}

      {data && error && (
        <div className="alert" role="status">
          Aktualisierung fehlgeschlagen – die Anzeige zeigt den zuletzt geladenen
          Stand.
        </div>
      )}

      {data && <ContractWorkspace data={data} orgSlug={ORG_SLUG} onReload={load} />}
    </div>
  );
}
